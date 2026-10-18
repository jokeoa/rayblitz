"""Run the complete experiment and save stage timings, logs, and exit status."""
import argparse
import datetime
import shutil
import subprocess
import sys
import time

from common import ROOT, config, write_json


def main():
    stages=["detect","track","roles","render","audit"]
    parser=argparse.ArgumentParser()
    parser.add_argument("--from-stage",choices=stages,default="detect")
    args=parser.parse_args()
    folder=ROOT/"runs"
    folder.mkdir(exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if (folder/"run.json").exists():
        shutil.copy2(folder/"run.json",folder/f"previous-run-{stamp}.json")
    record={"started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"config":config(),"from_stage":args.from_stage,"stages":[],"status":"running"}
    started=time.perf_counter()
    try:
        for stage in stages[stages.index(args.from_stage):]:
            print(f"START {stage}",flush=True)
            start=time.perf_counter()
            if (folder/f"{stage}.log").exists():
                shutil.copy2(folder/f"{stage}.log",folder/f"previous-{stage}-{stamp}.log")
            with open(folder/f"{stage}.log","w") as log:
                result=subprocess.run([sys.executable,str(ROOT/f"{stage}.py")],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            record["stages"].append({"stage":stage,"seconds":time.perf_counter()-start,"exit_code":result.returncode})
            write_json(folder/"run.json",record)
            print(f"END {stage}: {result.returncode}, {record['stages'][-1]['seconds']:.1f}s",flush=True)
            if result.returncode:
                raise RuntimeError(f"{stage} failed; inspect runs/{stage}.log")
        record["status"]="completed"
    except Exception as exc:
        record["status"]="failed"
        record["error"]=str(exc)
        raise
    finally:
        record["elapsed_seconds"]=time.perf_counter()-started
        write_json(folder/"run.json",record)


if __name__=="__main__":
    main()
