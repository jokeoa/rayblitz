"""Clip-local identity association, independent of service roles.

Confidence is a heuristic category, not a calibrated probability. Continuous
tracker IDs are evidence, not proof. Broken links require new identity evidence.
"""
from collections import Counter

from reflection_filter import continuous, iou


def associate_people(tracks, physical_observations, cfg):
    physical = {o['frame']: {p['detection_id']: p['kind'] for p in o['people']}
                for o in physical_observations}
    states, people, output, events = {}, {}, [], []
    previous = []
    for row in tracks:
        ids = Counter(t['id'] for t in row['tracks'])
        detections = Counter(t['det_idx'] for t in row['tracks'])
        current = []
        for tr in row['tracks']:
            state = states.setdefault(tr['id'], {'person_id': None, 'last': None,
                                                 'box': None, 'broken': False})
            kind = physical.get(row['frame'], {}).get(tr['det_idx'])
            gap = row['t'] - state['last'] if state['last'] is not None else None
            step_iou = iou(state['box'], tr['box']) if state['box'] is not None else None
            reasons = []
            if ids[tr['id']] != 1 or detections[tr['det_idx']] != 1:
                reasons.append('non_unique_association')
            if gap is not None and gap > cfg['role_reset_gap_seconds']:
                reasons.append('track_gap')
            if state['box'] is not None and not continuous(state['box'], tr['box'], cfg):
                reasons.append('geometric_jump')
            # Service roles must not influence identity association. A known
            # other person fitting the box better can indicate an ID swap.
            competing = [p for p in previous if p['id'] != tr['id']
                         and p['person_id'] is not None
                         and iou(p['box'], tr['box']) >= cfg['min_step_iou']
                         and step_iou is not None
                         and iou(p['box'], tr['box']) > step_iou]
            if competing:
                reasons.append('competing_person_geometry')
            if kind == 'reflection' and state['person_id'] is not None:
                reasons.append('physical_identity_conflict')
            if reasons and not state['broken']:
                state['broken'] = True
                events.append({'t': row['t'], 'track_id': tr['id'],
                               'person_id': state['person_id'], 'event': 'identity_link_broken',
                               'reasons': reasons.copy()})
            if not state['broken'] and state['person_id'] is None and kind == 'direct' and tr['overlap'] < cfg['overlap_fraction']:
                pid = f'E{len(people) + 1}'
                state['person_id'] = pid
                people[pid] = {'person_id': pid, 'track_id': tr['id'],
                               'established_at': row['t'], 'basis': 'direct_person_observation'}
            candidate = state['person_id']
            if state['broken']:
                level, pid = 'unresolved', None
                reasons = reasons or ['identity_link_requires_new_evidence']
            elif candidate is None:
                level, pid = 'unresolved', None
                reasons = ['reflection' if kind == 'reflection' else 'person_not_established']
            elif tr['overlap'] >= cfg['overlap_fraction']:
                level, pid, reasons = 'uncertain', candidate, ['overlapping_boxes']
            else:
                level, pid, reasons = 'supported', candidate, ['continuous_unique_track']
            current.append({**tr, 'person_id': pid, 'candidate_person_id': candidate,
                            'association': {'confidence': level, 'reasons': reasons,
                                            'usable_for_actions': level == 'supported',
                                            'evidence': {'gap_seconds': gap, 'step_iou': step_iou,
                                                         'box_overlap': tr['overlap'],
                                                         'physical_observation': kind,
                                                         'competing_track_ids': [p['id'] for p in competing]}}})
            state['last'], state['box'] = row['t'], tr['box']
        output.append({'frame': row['frame'], 't': row['t'], 'tracks': current})
        previous = current
    return output, people, events
