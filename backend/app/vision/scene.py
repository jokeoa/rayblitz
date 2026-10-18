"""Reviewed scene geometry is bound to the exact source bytes and view."""
from copy import deepcopy

from .common import ROOT, read_json, sha256


def geometry_for(digest, info):
    manifest = read_json(ROOT / 'scene_references.json')
    for name, item in manifest['videos'].items():
        if item['source_sha256'] != digest:
            continue
        if item['image_size'] != [info['width'], info['height']]:
            raise ValueError('Scene dimensions changed')
        for obj in item['objects'].values():
            if obj and sha256(ROOT / obj['image']) != obj['image_sha256']:
                raise ValueError('Scene reference changed')
        return {'video': name, 'source_sha256': digest, 'basis': 'reviewed_scene',
                'available_at': item['time'], 'objects': deepcopy(item['objects'])}
    return {'video': None, 'source_sha256': digest, 'basis': 'uncalibrated',
            'available_at': 0, 'objects': {'desk': None, 'safe': None}}


def equipment_for(digest):
    return [anchor for values in read_json(ROOT / 'scene_objects.json')['videos'].values()
            for anchor in values if anchor['source_sha256'] == digest]


def human_opening(digest):
    frames = read_json(ROOT / 'role_review_labels.json')['frames']
    return next((frame for frame in frames if frame['source_sha256'] == digest and frame['frame'] == 0), None)
