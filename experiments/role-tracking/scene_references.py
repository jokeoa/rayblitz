"""Authoritative scene landmarks. Detector proposals cannot replace a reference."""
from pathlib import Path

from common import ROOT, read_json, sha256


def reference_geometry(video, source_sha256, width, height, root=ROOT):
    root = Path(root); manifest_path = root / 'scene_references.json'
    manifest = read_json(manifest_path)
    if video not in manifest['videos']:
        raise ValueError(f'{video}: reviewed desk and side divider required before anchor search')
    item = manifest['videos'][video]
    if item['source_sha256'] != source_sha256 or item['image_size'] != [width, height]:
        raise ValueError(f'{video}: source/view does not match the scene reference')
    if set(item['objects']) != {'desk', 'safe'}:
        raise ValueError('The active geometry contract contains exactly desk and safe')
    if item['objects']['desk'] is None:
        raise ValueError(f'{video}: reviewed desk required before anchor search')
    divider = item['objects']['desk'].get('side_divider')
    if not divider or len(divider) != 2 or any(len(p)!=2 or not 0<=p[0]<=width or not 0<=p[1]<=height for p in divider) or divider[0]==divider[1]:
        raise ValueError(f'{video}: reviewed desk side divider required')
    for kind, obj in item['objects'].items():
        if kind == 'safe' and obj is None:
            continue  # An explicitly missing safe enables the bounded anchor search.
        x0,y0,x1,y1 = obj['box']
        if not 0 <= x0 < x1 <= width or not 0 <= y0 < y1 <= height:
            raise ValueError(f'{video}: invalid {kind} reference coordinates')
        path = (root / obj['image']).resolve()
        if not path.is_relative_to(root.resolve()) or sha256(path) != obj['image_sha256']:
            raise ValueError(f'{video}: reference image was changed')
    return {'video':video, 'source_sha256':source_sha256, 'available_at':item['time'],
            'basis':'frozen_scene_reference', 'objects':item['objects'],
            'reference_manifest_sha256':sha256(manifest_path),
            'review_status':'assistant_visual_review; not target-person role ground truth',
            'automatic_replacement':False}
