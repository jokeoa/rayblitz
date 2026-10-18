"""Frozen-policy replication on the two additional videos requested by the user."""
import datetime
import shutil
import subprocess
import sys
import time

from common import ROOT,read_json,sha256,write_json


def main():
    videos=["X-48","X-11"]
    output=ROOT/"runs/reflections-extra"
    target=output/"run.json"
    if target.exists(): raise FileExistsError("This additional run already has a manifest")
    source=output/"source"
    source.mkdir(parents=True,exist_ok=True)
    scripts=list(ROOT.glob("*.py"))+[ROOT/"config.json",ROOT/"reflection_config.json"]
    for path in scripts: shutil.copy2(path,source/path.name)
    selection=["--videos",*videos]
    filtered=[*selection,"--output-root",str(output)]
    stages=[
        ("tests",["test_reflection_filter.py"]),
        ("detect",["detect.py",*selection]),
        ("baseline_track",["track.py",*selection]),
        ("roles",["roles.py",*selection]),
        ("observe",["reflection_observe.py",*filtered]),
        ("filter",["reflection_filter.py",*filtered]),
        ("filtered_track",["track.py",*selection,"--run-dir",str(output)]),
        ("render",["reflection_render.py",*filtered]),
        ("validate",["reflection_validate.py",*filtered]),
    ]
    manifest={"started_utc":datetime.datetime.now(datetime.UTC).isoformat(),"videos":videos,"source_sha256":{v:sha256(ROOT/"data"/f"{v}.mov") for v in videos},"code_sha256":{p.name:sha256(p) for p in scripts},"policy":read_json(ROOT/"reflection_config.json"),"configuration":read_json(ROOT/"config.json"),"evaluation_labels_used_in_inference":False,"stages":[]}
    write_json(target,manifest)
    for stage,argv in stages:
        start=time.perf_counter()
        print("Starting",stage,flush=True)
        with open(output/f"{stage}.log","w") as log:
            result=subprocess.run([sys.executable,"-u",*argv],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        manifest["stages"].append({"name":stage,"command":argv,"seconds":time.perf_counter()-start,"returncode":result.returncode})
        write_json(target,manifest)
        print(manifest["stages"][-1],flush=True)
        if result.returncode: raise RuntimeError(f"{stage} failed; see its log")
    manifest["finished_utc"]=datetime.datetime.now(datetime.UTC).isoformat()
    write_json(target,manifest)


if __name__=="__main__": main()
