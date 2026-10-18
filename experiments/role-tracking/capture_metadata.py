"""Record immutable model snapshots from the local inference-machine cache."""
from pathlib import Path

from huggingface_hub import try_to_load_from_cache

from common import ROOT, config, sha256, write_json


def main():
    cfg=config()
    result={}
    for key in ["detector","role_model"]:
        revision=cfg["detector_revision" if key=="detector" else "role_revision"]
        cached=try_to_load_from_cache(cfg[key],"config.json",revision=revision)
        if not isinstance(cached,str):
            raise RuntimeError(f"No cached configuration for {cfg[key]}")
        path=Path(cached)
        result[key]={"model":cfg[key],"snapshot_revision":path.parent.name,"config_sha256":sha256(path),"provenance":"snapshot that supplied config.json in the local inference cache"}
    result["reid"]={"file":cfg["reid"],"sha256":sha256(ROOT/"weights"/cfg["reid"])}
    write_json(ROOT/"runs/model-snapshots.json",result)
    print(result)


if __name__=="__main__":
    main()
