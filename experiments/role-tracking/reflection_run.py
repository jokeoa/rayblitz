"""Run the isolated reflection comparison with per-stage provenance."""
import argparse
import datetime
import subprocess
import sys
import time

from common import ROOT,sha256,write_json


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--skip-observe",action="store_true",help="Use the complete cached observation pass")
    args=p.parse_args()
    output=ROOT/"runs/reflections"
    output.mkdir(parents=True,exist_ok=True)
    stages=[("tests",["test_reflection_filter.py"])]
    if not args.skip_observe: stages.append(("observe",["reflection_observe.py"]))
    stages.extend([("filter",["reflection_filter.py"]),("track",["track.py","--run-dir",str(output)]),("render",["reflection_render.py"]),("evaluate",["reflection_evaluate.py"]),("report",["reflection_report.py"]),("validate",["reflection_validate.py"])])
    scripts=list(ROOT.glob("reflection_*.py"))+[ROOT/"track.py",ROOT/"render.py",ROOT/"common.py",ROOT/"roles.py",ROOT/"test_reflection_filter.py",ROOT/"reflection_config.json",ROOT/"config.json"]
    manifest={"started_utc":datetime.datetime.now(datetime.UTC).isoformat(),"code_sha256":{p.name:sha256(p) for p in scripts},"human_labels_sha256":sha256(ROOT/"reflection_human_labels.json"),"assistant_labels_sha256":sha256(ROOT/"reflection_assistant_labels.json"),"labels_used_only_in_evaluate":True,"skip_observe":args.skip_observe,"stages":[]}
    target=output/"run.json"
    if target.exists(): raise FileExistsError("Move the existing run manifest before a new pipeline run")
    write_json(target,manifest)
    for stage,argv in stages:
        start=time.perf_counter()
        with open(output/f"{stage}.log","w") as log:
            result=subprocess.run([sys.executable,"-u",*argv],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        manifest["stages"].append({"name":stage,"seconds":time.perf_counter()-start,"returncode":result.returncode})
        write_json(target,manifest)
        print(stage,manifest["stages"][-1],flush=True)
        if result.returncode: raise RuntimeError(f"{stage} failed; see {output/stage}.log")
    manifest["finished_utc"]=datetime.datetime.now(datetime.UTC).isoformat()
    write_json(target,manifest)


if __name__=="__main__": main()
