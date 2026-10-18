"""Render and compare the two role-initialization experiments on identical clips."""
import argparse
import json
import subprocess
import shutil
from pathlib import Path
from collections import Counter

import cv2
import numpy as np

from common import ROOT, read_json, sampled_frames, sha256, video_info, write_json
from safe_side_policy import geometry_axis
from safe_side_labels import apply_labels

BASE = ROOT / 'runs/remaining-videos'
OUT = ROOT / 'runs/safe-side'
PREVIOUS = ROOT / 'runs/safe-side-calibration-v1'


def coverage(data, start=0.):
    rows = [r for r in data['rows'] if r['t'] >= start]
    count = sum(any(tr['association']['usable_for_actions'] and data['people'].get(tr['person_id'], {}).get('role') == 'banker' and ('active_banker_person_id' not in r or tr.get('is_active_banker',False)) for tr in r['tracks']) for r in rows)
    return {'supported': count, 'frames': len(rows), 'share': count / max(1, len(rows))}


def decorate(image, data, row):
    h, w = image.shape[:2]; canvas = np.zeros((h+64, w, 3), np.uint8); canvas[:h] = image
    if row['t'] >= data['geometry']['available_at']:
        for kind, obj in data['geometry']['objects'].items():
            if obj:
                b = list(map(round, obj['box'])); color = (175, 115, 35) if kind == 'desk' else (150, 60, 180)
                cv2.rectangle(canvas, tuple(b[:2]), tuple(b[2:]), color, 1)
                name = 'safe-like anchor ?' if obj.get('kind') == 'safe_like_storage' else kind
                cv2.putText(canvas, name, (b[0], max(14,b[1]-4)), cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1)
        axis = geometry_axis(data['geometry'])
        if axis:
            d, u = axis['origin'], axis['unit']; a=(round(d[0]-u[1]*1200), round(d[1]+u[0]*1200)); b=(round(d[0]+u[1]*1200), round(d[1]-u[0]*1200))
            cv2.line(canvas[:h], a, b, (190,180,150), 1)
            cv2.arrowedLine(canvas, (round(d[0]),round(d[1])), (round(d[0]+u[0]*60),round(d[1]+u[1]*60)), (150,60,180), 2)
    for tr in row['tracks']:
        supported = tr['association']['usable_for_actions']; pid = tr['person_id']
        observation = tr['classification']
        color = ((90,170,35) if tr.get('is_active_banker') else (210,150,40)) if supported else (150,150,150)
        b = list(map(round,tr['box'])); cv2.rectangle(canvas,tuple(b[:2]),tuple(b[2:]),color,2)
        label = f'{pid} banker' + (' ACTIVE' if tr.get('is_active_banker') else '') if supported else f'T{tr["id"]} unknown'
        if pid and not supported: label = f'{pid} banker ?'
        if observation['role'] == 'customer':
            color = (30,170,230); label = f'T{tr["id"]} customer'
        if observation['possible_reflection']:
            color = (200,95,190)
            label = f'{pid or "T"+str(tr["id"])} possible reflection'
        pos = (max(0,b[0]), max(14,b[1]-5))
        cv2.putText(canvas,label,pos,cv2.FONT_HERSHEY_SIMPLEX,.42,(0,0,0),3,cv2.LINE_AA)
        cv2.putText(canvas,label,pos,cv2.FONT_HERSHEY_SIMPLEX,.42,color,1,cv2.LINE_AA)
    cv2.putText(canvas,f'{data["video"]} {row["t"]:.1f}s | Active: {row.get("active_banker_person_id") or "unknown"}',(8,h+23),cv2.FONT_HERSHEY_SIMPLEX,.46,(230,230,230),1,cv2.LINE_AA)
    cv2.putText(canvas,'2D dividing line is a hypothesis; not a floor plan',(8,h+47),cv2.FONT_HERSHEY_SIMPLEX,.39,(185,185,185),1,cv2.LINE_AA)
    return canvas


def render(video, data):
    h,w=data['info']['height'],data['info']['width']; directory=OUT/video
    proc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{w}x{h+64}','-r',str(data['fps']),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart',str(directory/'tracked.mp4')],stdin=subprocess.PIPE)
    count=0; audits=[]
    times=sorted(set([20,len(data['rows'])//2,len(data['rows'])-1]))
    for i,t,image in sampled_frames(ROOT/'data'/f'{video}.mov',data['fps']):
        canvas=decorate(image,data,data['rows'][i]);proc.stdin.write(canvas.tobytes());count+=1
        if i==20: cv2.imwrite(str(directory/'preview.jpg'),canvas)
        if i==20: cv2.imwrite(str(directory/'geometry.jpg'),canvas[:h])
        if i in times: audits.append(canvas)
    proc.stdin.close()
    if proc.wait()!=0 or count!=len(data['rows']): raise RuntimeError(f'Incomplete {video}')
    cv2.imwrite(str(directory/'audit.jpg'),np.concatenate(audits,axis=1))
    info=video_info(directory/'tracked.mp4')
    assert abs(info['duration']-count/data['fps'])<.11
    return {'video':video,'frames':count,'duration':info['duration'],'sha256':sha256(directory/'tracked.mp4')}


def build():
    videos=[]; counts=Counter()
    for item in read_json(BASE/'selection.json')['videos']:
        video=item['id']; before=read_json(BASE/video/'person_tracks.json'); after=read_json(OUT/video/'person_tracks.json')
        automatic=read_json(PREVIOUS/video/'person_tracks_auto.json')
        previous=read_json(PREVIOUS/video/'person_tracks.json')
        banker_path=OUT/video/'banker_tracks.json'; banker=read_json(banker_path)
        assert after['banker_tracks_sha256']==sha256(banker_path)
        expected=apply_labels(banker,before)
        assert after['rows']==expected['rows'] and after['people']==banker['people']
        assert after['banker_transitions']==banker['banker_transitions']
        assert after['label_code_sha256']==sha256(ROOT/'safe_side_labels.py')
        counts.update(after['label_counts'])
        assert before['source_sha256']==after['source_sha256']==item['sha256']
        assert after['baseline_tracks_sha256']==sha256(BASE/video/'person_tracks.json')
        assert len(before['rows'])==len(after['rows'])==len(automatic['rows'])
        assert after['geometry']['reference_manifest_sha256']==sha256(ROOT/'scene_references.json')
        assert after['geometry']['automatic_replacement'] is False
        opening=read_json(OUT/video/'initial_window.json')
        assert opening['native_frames']==opening['analyzed_frames']==len(opening['rows'])
        assert opening['all_native_frames_analyzed']
        assert all(0<=r['t']<2. for r in opening['rows'])
        assert [r['native_frame'] for r in opening['rows']]==list(range(opening['native_frames']))
        transitions=after['banker_transitions']
        active=None; transition_index=0
        for name,digest in after['code_sha256'].items(): assert sha256(OUT/'source_snapshot'/name)==digest
        for old,new in zip(before['rows'],after['rows']):
            assert [(x['id'],x['box']) for x in old['tracks']]==[(x['id'],x['box']) for x in new['tracks']]
            assert all('role' not in t for t in new['tracks'])
            while transition_index<len(transitions) and transitions[transition_index]['t']<=new['t']:
                event=transitions[transition_index]
                assert event['from_person_id']==active
                active=event['to_person_id']; transition_index+=1
                assert after['people'][active]['initialized_at']<=event['t']
                if event['reason']=='stable_new_candidate_on_safe_side':
                    tr=next(x for x in new['tracks'] if x['person_id']==active)
                    assert tr['safe_side']>=after['policy']['side_margin']
            assert new['active_banker_person_id']==active
            pids=[x['person_id'] for x in new['tracks'] if x['person_id']]
            assert len(pids)==len(set(pids))
            for tr in new['tracks']:
                pid=tr['person_id']
                assert tr['association']['usable_for_actions']==(pid is not None and tr['association']['confidence']=='supported' and not tr['classification']['possible_reflection'])
                assert tr['is_active_banker']==(pid is not None and pid==active)
                if pid: assert after['people'][pid]['initialized_at']<=new['t']
        videos.append({'video':video,'duration':after['info']['duration'],
                       'before':coverage(before),'after':coverage(after),'before_reflection_veto':coverage(banker),'automatic':coverage(automatic),'previous':coverage(previous),
                       'label_counts':after['label_counts'],
                       'initial_window':after['initial_window'],'transitions':transitions,
                       'before_after5':coverage(before,5.),'after_after5':coverage(after,5.),
                       'people':after['people'],'geometry':after['geometry'],
                       'frames':len(after['rows'])})
    payload={'videos':videos,'accuracy':None,'independent_test':False,
             'scope':'All 37 target videos; role/tracking comparison only. Full action pipeline remains the appearance-reference baseline.',
             'method':'Appearance baseline vs frozen desk/safe reference with reviewed desk divider, every native frame in [0,2), and explicit stable safe-side handoff. Earlier geometry runs are historical comparisons.',
             'limitations':['Two-dimensional direction can differ from physical side of desk.',
                            'Reflections and similar storage furniture can confuse localization.',
                            'Initial assignment at 2 seconds; later switches require a stable safe-side candidate. Geometry is a role hypothesis, not proof of employment.',
                            'Parameters refined after inspecting this development set; no independent accuracy estimate.',
                            'Change of clothes during tracking is not validated; conflicting appearance suspends association, not role.'],
             'label_counts':dict(counts),
             'checks':{'source_and_tracks_identical':True,'causal_assignment':True,'roles_separate_from_association':True,'native_opening_frames_complete':True,'frozen_reference_verified':True,'handoff_log_consistent':True,'labels_reproduced':True,'banker_choices_unchanged':True,'reflection_action_veto':True}}
    for arm in ('before','automatic','previous','after','before_reflection_veto','before_after5','after_after5'):
        support=sum(v[arm]['supported'] for v in videos);frames=sum(v[arm]['frames'] for v in videos)
        payload[arm]={'supported':support,'frames':frames,'share':support/frames,'videos_with_banker':sum(v[arm]['supported']>0 for v in videos)}
    payload['geometry_ready']=sum(all(v['geometry']['objects'].values()) for v in videos)
    payload['calibration_source']='Assistant-reviewed object coordinates at t=2s; no target person-role annotation'
    payload['native_opening_frames']=sum(v['initial_window']['native_frames'] for v in videos)
    payload['initial_assignments']=sum(v['initial_window']['selected_track_id'] is not None for v in videos)
    payload['handoffs']=sum(sum(e['from_person_id'] is not None for e in v['transitions']) for v in videos)
    payload['media_version']=sha256(ROOT/'safe_side_labels.py')[:12]
    shutil.copytree(ROOT/'scene-references',OUT/'references',dirs_exist_ok=True)
    shutil.copy2(ROOT/'SAFE_REFERENCE.md',OUT/'SAFE_REFERENCE.md')
    write_json(OUT/'summary.json',payload)
    (OUT/'index.html').write_text((ROOT/'safe_side_report.html').read_text().replace('__DATA__',json.dumps(payload,ensure_ascii=False).replace('</','<\\/')))
    print(json.dumps({k:v for k,v in payload.items() if k in ('before','after','before_after5','after_after5','geometry_ready')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--render',action='store_true');parser.add_argument('--output-root',type=Path,default=OUT);args=parser.parse_args();OUT=args.output_root
    if args.render:
        checks=[]
        for item in read_json(BASE/'selection.json')['videos']:
            checks.append(render(item['id'],read_json(OUT/item['id']/'person_tracks.json')));print('rendered',item['id'],flush=True)
        write_json(OUT/'media_validation.json',checks)
    build()
