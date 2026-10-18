"""Freeze the reviewed desk/safe rectangles and their source-image evidence."""
import cv2
from PIL import Image

from common import ROOT, read_json, sha256, write_json


def main():
    calibration = read_json(ROOT/'scene_calibration.json')
    manifest = {'purpose':'Banker initialization from safe position relative to desk',
                'active_object_types':['desk','safe'], 'automatic_replacement':False,
                'reviewer':'assistant visual review of frame at 2 seconds',
                'calibration_sha256':sha256(ROOT/'scene_calibration.json'),
                'note':'These crops document the reference. No appearance-template matcher is claimed. Coordinates apply only to the exact source/view.',
                'videos':{}}
    for video, entry in calibration['videos'].items():
        source=ROOT/'data'/f'{video}.mov'; assert sha256(source)==entry['source_sha256']
        cap=cv2.VideoCapture(str(source));cap.set(cv2.CAP_PROP_POS_MSEC,entry['time']*1000)
        ok,bgr=cap.read(); frame=int(cap.get(cv2.CAP_PROP_POS_FRAMES))-1;cap.release()
        if not ok: raise RuntimeError(f'{video}: missing reference frame')
        image=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB));objects={}
        directory=ROOT/'scene-references'/video;directory.mkdir(parents=True,exist_ok=True)
        for kind in ('desk','safe'):
            if kind == 'safe' and entry[kind] is None:
                objects[kind] = None
                continue
            path=directory/f'{kind}.png';image.crop(tuple(round(v) for v in entry[kind])).save(path)
            objects[kind]={'reference_id':f'{kind}-{entry["source_sha256"][:12]}-2s', 'box':entry[kind],
                           'image':str(path.relative_to(ROOT)), 'image_sha256':sha256(path),
                           'source':'assistant_reviewed_reference', 'score':None}
        objects['desk']['side_divider'] = entry['desk_side_divider']
        manifest['videos'][video]={'source_sha256':entry['source_sha256'],'image_size':list(image.size),
                                  'time':entry['time'],'decoded_frame':frame,'objects':objects}
    write_json(ROOT/'scene_references.json',manifest)
    print(f'Frozen desk/safe references: {len(manifest["videos"])} source videos')


if __name__=='__main__': main()
