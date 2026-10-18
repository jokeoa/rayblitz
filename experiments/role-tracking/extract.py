"""Extract only source MOV files with validated names; record byte hashes."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("archive",type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    folder=root/"data"
    folder.mkdir(exist_ok=True)
    records=[]
    with zipfile.ZipFile(args.archive) as archive:
        for name in archive.namelist():
            if "__MACOSX" in name: continue
            base=Path(name).name.replace("Х","X")
            if not re.fullmatch(r"X-\d+\.mov",base,re.IGNORECASE): continue
            payload=archive.read(name)
            target=folder/base
            digest=hashlib.sha256(payload).hexdigest()
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                raise ValueError(f"Different contents already exist: {target}")
            target.write_bytes(payload)
            records.append({"id":target.stem,"archive_member":name,"path":str(target.relative_to(root)),"bytes":len(payload),"sha256":digest})
    records.sort(key=lambda r:int(r["id"].split("-")[1]))
    (folder/"manifest.json").write_text(json.dumps(records,ensure_ascii=False,indent=2))
    print(f"Extracted {len(records)} videos; {len({r['sha256'] for r in records})} unique byte hashes")


if __name__=="__main__":
    main()
