"""Frozen desk/safe geometry, immutable person roles, explicit service handoffs."""
from collections import deque
from math import hypot

from .common import overlap_fraction
from .reference_policy import similarity, unit
from .reflection_filter import iou

POLICY = dict(initial_window_seconds=2., initial_support=.7, handoff_seconds=1.,
              distinct_seconds=.5, distinct_overlap=.05,
              observation_max_gap=.2, side_margin=.08, minimum_person_area=.015,
              max_desk_distance=1.4, overlap=.3, candidate_distance_margin=.15,
              identity_similarity=.65, reconnect_similarity=.88,
              reconnect_margin=.08, max_gap=3., gallery_size=8)


def center(box):
    return ((box[0]+box[2])/2, (box[1]+box[3])/2)


def geometry_axis(geometry):
    objects = geometry['objects']
    if not objects['desk'] or not objects['safe']: return None
    desk, safe = objects['desk']['box'], objects['safe']['box']
    # The desk's reviewed longitudinal divider defines its two sides. Using
    # desk->safe box centers instead rotates the divider towards the customer.
    a, b = objects['desk']['side_divider']
    d, s = ((a[0]+b[0])/2, (a[1]+b[1])/2), center(safe)
    length = hypot(b[0]-a[0], b[1]-a[1])
    scale = hypot(desk[2]-desk[0], desk[3]-desk[1])
    if length < 1.: return None
    normal = (-(b[1]-a[1])/length, (b[0]-a[0])/length)
    safe_side = (s[0]-d[0])*normal[0]+(s[1]-d[1])*normal[1]
    if abs(safe_side) < .02 * scale: return None
    sign = 1 if safe_side > 0 else -1
    return {'origin': d, 'unit': (sign*normal[0], sign*normal[1]), 'scale': scale}


class SafeSideAssociator:
    def __init__(self, geometry, width, height, seed=None):
        self.axis = geometry_axis(geometry)
        self.area = width * height
        self.safe_center = center(geometry['objects']['safe']['box']) if geometry['objects']['safe'] else None
        self.people, self.states, self.transitions = {}, {}, []
        self.active_person_id, self.pending = None, None
        self.seed, self.seed_installed = seed, False
        self.distinct_tracks = set()
        self.distinct_pending = {}

    def side(self, box):
        if self.axis is None: return None
        p = center(box); d = self.axis['origin']; u = self.axis['unit']
        return ((p[0]-d[0])*u[0] + (p[1]-d[1])*u[1]) / self.axis['scale']

    def eligible(self, tr, overlap):
        if self.axis is None or tr['score'] < .5 or overlap >= POLICY['overlap']: return False
        b = tr['box']; c, d = center(b), self.axis['origin']
        return ((b[2]-b[0])*(b[3]-b[1]) >= POLICY['minimum_person_area'] * self.area
                and hypot(c[0]-d[0], c[1]-d[1]) <= POLICY['max_desk_distance'] * self.axis['scale']
                and self.side(b) >= POLICY['side_margin'])

    def candidate(self, tracks):
        # Native detection retains low-score proposals for audit. A weak head
        # duplicate must not veto a strong full-person candidate as an occlusion.
        overlaps = [max((overlap_fraction(tr['box'], other['box']) for j, other in enumerate(tracks) if j != i and other['score'] >= .5), default=0.) for i,tr in enumerate(tracks)]
        candidates = [i for i, tr in enumerate(tracks) if self.eligible(tr, overlaps[i])]
        if len(candidates) > 1:
            distances = sorted((hypot(center(tracks[i]['box'])[0]-self.safe_center[0],
                                      center(tracks[i]['box'])[1]-self.safe_center[1]) / self.axis['scale'], i)
                               for i in candidates)
            candidates = [distances[0][1]] if distances[1][0]-distances[0][0] >= POLICY['candidate_distance_margin'] else []
        return candidates[0] if candidates else None

    def _register(self, t, tr, features, basis):
        pid = f'P{len(self.people)+1}'
        features = [unit(f) for f in features]
        self.people[pid] = {'person_id':pid, 'role':'banker', 'initialized_at':t,
                            'role_basis':basis, 'human_confirmed_in_this_video':False,
                            'initial_track_id':tr['id'], 'initial_side':self.side(tr['box'])}
        self.states[pid] = {'track_id':tr['id'], 'last':t, 'box':tr['box'], 'initial':features[0],
                            'gallery':deque(features, maxlen=POLICY['gallery_size'])}
        return pid

    def _activate(self, t, pid, reason, track_id):
        self.transitions.append({'t':t, 'from_person_id':self.active_person_id,
                                 'to_person_id':pid, 'reason':reason, 'track_id':track_id})
        self.active_person_id = pid

    def _reconnect(self, t, tracks, features, overlaps):
        live_ids = {tr['id'] for tr in tracks}
        claimed = {s['track_id'] for s in self.states.values()}
        for pid, state in self.states.items():
            if state['track_id'] in live_ids or not 0 < t-state['last'] <= POLICY['max_gap']: continue
            candidates = [(similarity(features[i], [state['initial'], *state['gallery']]), i) for i, tr in enumerate(tracks)
                          if tr['id'] not in claimed and overlaps[i] < POLICY['overlap'] and tr['score'] >= .5 and iou(state['box'], tr['box']) >= .1]
            candidates.sort(reverse=True)
            if not candidates: continue
            score, i = candidates[0]
            competitors = [similarity(features[i], [s['initial'], *s['gallery']]) for p,s in self.states.items() if p != pid]
            if score >= POLICY['reconnect_similarity'] and score-max([x[0] for x in candidates[1:]]+competitors+[-1.]) >= POLICY['reconnect_margin']:
                claimed.discard(state['track_id']); state['track_id'] = tracks[i]['id']; claimed.add(state['track_id'])

    def _handoff(self, t, tracks, features, output):
        i = self.candidate(tracks)
        if i is None:
            self.pending = None; return
        tr, row = tracks[i], output[i]
        pid = row['person_id']
        if pid == self.active_person_id and pid is not None:
            self.pending = None; return
        if row['candidate_person_id'] is not None and row['association']['confidence'] != 'supported':
            self.pending = None; return  # A broken link is not a new person.
        if pid is None:
            if self.active_person_id is not None and (tr['id'],self.active_person_id) not in self.distinct_tracks:
                row['association']['reason'] = 'different_identity_not_established'
            # Without simultaneous separate observations, similar appearance may
            # be a fragment of an existing banker rather than a new employee.
            for old_pid, state in self.states.items():
                old_visible = any(r['person_id']==old_pid and r['association']['confidence']=='supported' for r in output)
                if not old_visible and similarity(features[i], [state['initial'], *state['gallery']]) >= POLICY['identity_similarity']:
                    self.pending = None; return
        key = (tr['id'], pid)
        if self.pending is None or self.pending['key'] != key or t-self.pending['last'] > POLICY['observation_max_gap']+1e-6 or similarity(features[i], self.pending['features']) < POLICY['identity_similarity']:
            self.pending = {'key':key, 'start':t, 'last':t, 'features':deque(maxlen=POLICY['gallery_size'])}
        self.pending['last'] = t; self.pending['features'].append(features[i])
        if t-self.pending['start'] < POLICY['handoff_seconds']-1e-6: return
        if pid is None and self.active_person_id is not None and (tr['id'],self.active_person_id) not in self.distinct_tracks:
            return
        if pid is None:
            pid = self._register(t, tr, list(self.pending['features']), 'stable_safe_side_candidate')
            row['person_id'] = row['candidate_person_id'] = pid
            row['association'].update(confidence='supported', reason='stable_safe_side_candidate', usable_for_actions=True)
        self._activate(t, pid, 'stable_new_candidate_on_safe_side', tr['id'])
        self.pending = None

    def update(self, t, tracks, features):
        features = [unit(f) for f in features]
        if not self.seed_installed and t >= POLICY['initial_window_seconds']:
            self.seed_installed = True
            if self.seed is not None:
                pid = self._register(POLICY['initial_window_seconds'], self.seed['track'], self.seed['features'], 'all_native_frames_initial_window')
                self._activate(POLICY['initial_window_seconds'], pid, 'initial_window_consensus', self.seed['track']['id'])
        overlaps = [max((overlap_fraction(tr['box'], other['box']) for j, other in enumerate(tracks) if j != i), default=0.) for i,tr in enumerate(tracks)]
        self._reconnect(t, tracks, features, overlaps)
        by_track = {s['track_id']:(pid,s) for pid,s in self.states.items()}
        output = []
        for i, tr in enumerate(tracks):
            pid, level, score = None, 'unresolved', None
            reason = 'no_geometry' if self.axis is None else 'not_initialized_or_not_banker'
            candidate, state = by_track.get(tr['id'], (None,None))
            if state:
                gap = t-state['last']; a, b = center(tr['box']), center(state['box'])
                scale = max(hypot(state['box'][2]-state['box'][0], state['box'][3]-state['box'][1]), 1.)
                score = similarity(features[i], [state['initial'], *state['gallery']])
                if gap > POLICY['max_gap']: reason = 'long_gap'
                elif iou(tr['box'], state['box']) < .1 and hypot(a[0]-b[0], a[1]-b[1])/scale > .35*max(1., gap*10): reason = 'geometric_jump'
                elif overlaps[i] >= POLICY['overlap']: pid, level, reason = candidate, 'uncertain', 'overlap'
                elif score < POLICY['identity_similarity']: reason = 'appearance_conflict'
                elif tr['score'] < .5: reason = 'low_detection_score'
                else:
                    pid, level, reason = candidate, 'supported', 'continuous_track_and_appearance'
                    state['gallery'].append(features[i])
                if pid: state.update(last=t, box=tr['box'])
            output.append({**tr, 'person_id':pid, 'candidate_person_id':candidate, 'safe_side':self.side(tr['box']),
                           'association':{'confidence':level, 'reason':reason, 'similarity':score,
                                          'usable_for_actions':level=='supported', 'overlap':overlaps[i]}})
        # A second tracker ID alone never establishes a different human. Record
        # evidence only while two separated, supported observations coexist.
        distinct_now = set()
        for i,row in enumerate(output):
            if row['person_id'] is not None or tracks[i]['score'] < .5 or overlaps[i] >= POLICY['overlap']: continue
            for other in output:
                if other['person_id'] and other['association']['confidence']=='supported' and overlap_fraction(row['box'],other['box']) < POLICY['distinct_overlap']:
                    key = (row['id'],other['person_id']); distinct_now.add(key)
                    first,last = self.distinct_pending.get(key,(t,t))
                    if t-last > POLICY['observation_max_gap']+1e-6: first=t
                    self.distinct_pending[key]=(first,t)
                    if t-first >= POLICY['distinct_seconds']-1e-6: self.distinct_tracks.add(key)
        self.distinct_pending = {k:v for k,v in self.distinct_pending.items() if k in distinct_now}
        if t >= POLICY['initial_window_seconds']: self._handoff(t, tracks, features, output)
        for row in output: row['is_active_banker'] = row['person_id'] is not None and row['person_id']==self.active_person_id
        return output
