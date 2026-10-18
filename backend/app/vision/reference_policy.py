"""Causal appearance transfer; a role is assigned once, association is per frame.

Thresholds are conservative engineering defaults, not calibrated probabilities.
Reference identities never imply that two clips contain the same individual.
"""
from collections import deque
from math import hypot

import numpy as np

from .common import overlap_fraction
from .reflection_filter import iou

POLICY = dict(reference_similarity=.78, role_margin=.08, reflection_margin=.02,
              initial_samples=3, initial_span=.2, identity_similarity=.65,
              reconnect_similarity=.88, reconnect_margin=.08, max_gap=3.,
              overlap=.3, gallery_size=8)


def unit(x):
    x = np.asarray(x, dtype=np.float32)
    return x / max(float(np.linalg.norm(x)), 1e-12)


def similarity(feature, gallery):
    return max((float(np.dot(feature, f)) for f in gallery), default=-1.)


def reference_match(feature, references):
    scores = {role: similarity(feature, [r['feature'] for r in references if r['category'] == role])
              for role in ('banker', 'customer', 'reflection')}
    role = max(('banker', 'customer'), key=scores.get)
    other = 'customer' if role == 'banker' else 'banker'
    reflected = scores['reflection'] >= POLICY['reference_similarity'] and scores['reflection'] >= scores[role] - POLICY['reflection_margin']
    accepted = (not reflected and scores[role] >= POLICY['reference_similarity']
                and scores[role] - scores[other] >= POLICY['role_margin'])
    best = max((r for r in references if r['category'] == role),
               key=lambda r: float(np.dot(feature, r['feature'])))
    return {'role': role if accepted else 'unknown', 'kind': 'possible_reflection' if reflected else 'unverified_person',
            'scores': {k: round(v, 5) for k, v in scores.items()}, 'reference': best['reference']}


class ReferenceAssociator:
    def __init__(self, references):
        self.references = references
        self.people, self.states, self.track_people = {}, {}, {}
        self.pending = {}

    def update(self, t, tracks, features):
        output = []
        active = {x['id'] for x in tracks}
        claimed = set()
        for tr, raw in zip(tracks, features):
            feature = unit(raw)
            match = reference_match(feature, self.references)
            overlap = max((overlap_fraction(tr['box'], o['box']) for o in tracks if o['id'] != tr['id']), default=0.)
            safe = overlap < POLICY['overlap'] and tr['score'] >= .5 and match['kind'] != 'possible_reflection'
            pid = self.track_people.get(tr['id'])
            reason, level = 'not_initialized', 'unresolved'
            if pid is None and safe:
                candidates = []
                for p, state in self.states.items():
                    gap = t - state['last']
                    if state['track_id'] in active or p in claimed or not 0 < gap <= POLICY['max_gap']:
                        continue
                    if iou(state['box'], tr['box']) < .1:
                        continue
                    candidates.append((similarity(feature, state['gallery']), p))
                candidates.sort(reverse=True)
                if candidates and candidates[0][0] >= POLICY['reconnect_similarity'] and (len(candidates) == 1 or candidates[0][0] - candidates[1][0] >= POLICY['reconnect_margin']):
                    pid = candidates[0][1]
                    self.track_people.pop(self.states[pid]['track_id'], None)
                    self.track_people[tr['id']] = pid
                    self.states[pid]['track_id'] = tr['id']
                    reason = 'appearance_and_position_reconnection'
            if pid is None:
                pending = self.pending.setdefault(tr['id'], deque(maxlen=POLICY['initial_samples']))
                if safe and match['role'] != 'unknown':
                    if pending and (pending[-1]['role'] != match['role'] or t - pending[-1]['t'] > .5):
                        pending.clear()
                    pending.append({'t': t, 'role': match['role'], 'feature': feature, 'reference': match['reference']})
                else:
                    pending.clear()
                if len(pending) == POLICY['initial_samples'] and t - pending[0]['t'] >= POLICY['initial_span'] - 1e-6:
                    pid = f'P{len(self.people) + 1}'
                    self.people[pid] = {'person_id': pid, 'role': match['role'], 'initialized_at': t,
                                        'role_basis': 'automatic_reference_transfer',
                                        'human_confirmed_in_this_video': False,
                                        'reference': match['reference'], 'initial_scores': match['scores']}
                    self.states[pid] = {'last': t, 'box': tr['box'], 'track_id': tr['id'],
                                        'initial': feature, 'gallery': deque([x['feature'] for x in pending], maxlen=POLICY['gallery_size'])}
                    self.track_people[tr['id']] = pid
                    reason = 'initial_reference_transfer'
            candidate = pid
            if pid is not None:
                state = self.states[pid]
                own_similarity = similarity(feature, [state['initial'], *state['gallery']])
                gap = t - state['last']
                step = hypot((tr['box'][0] + tr['box'][2] - state['box'][0] - state['box'][2]) / 2,
                             (tr['box'][1] + tr['box'][3] - state['box'][1] - state['box'][3]) / 2)
                diagonal = max(hypot(state['box'][2] - state['box'][0], state['box'][3] - state['box'][1]), 1.)
                if pid in claimed:
                    level, reason, pid = 'unresolved', 'non_unique_person', None
                elif gap > POLICY['max_gap']:
                    level, reason, pid = 'unresolved', 'long_gap', None
                elif iou(state['box'], tr['box']) < .1 and step / diagonal > .35 * max(1., gap * 10):
                    level, reason, pid = 'unresolved', 'geometric_jump', None
                elif match['kind'] == 'possible_reflection':
                    level, reason, pid = 'unresolved', 'reflection_conflict', None
                elif overlap >= POLICY['overlap']:
                    level, reason = 'uncertain', 'overlap'
                elif own_similarity < POLICY['identity_similarity']:
                    level, reason, pid = 'unresolved', 'appearance_conflict', None
                elif match['role'] not in ('unknown', self.people[pid]['role']):
                    level, reason, pid = 'unresolved', 'reference_role_conflict', None
                else:
                    level = 'supported'
                    if reason == 'not_initialized':
                        reason = 'continuous_track_and_appearance'
                    state['gallery'].append(feature)
                if pid is not None:
                    claimed.add(pid)
                    state.update(last=t, box=tr['box'])
            else:
                own_similarity = None
                if match['kind'] == 'possible_reflection': reason = 'possible_reflection'
                elif not safe: reason = 'overlap_or_low_detection_score'
            output.append({**tr, 'person_id': pid, 'candidate_person_id': candidate,
                           'reference_match': match,
                           'association': {'confidence': level, 'reason': reason,
                                           'similarity': round(own_similarity, 5) if own_similarity is not None else None,
                                           'usable_for_actions': level == 'supported', 'overlap': round(overlap, 4)}})
        return output
