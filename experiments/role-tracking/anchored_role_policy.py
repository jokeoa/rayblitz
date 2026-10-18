"""One immutable service role per person, separate from frame association.

Offline role estimation uses the complete clip and no manual labels. The unique
opening banker anchors the session. Other people require repeated supported
customer observations; not being the banker is insufficient evidence.
"""
from collections import Counter

from person_association import associate_people


def anchored_role_timeline(tracks, role_observations, reflection_observations, cfg):
    rows, people, events = associate_people(tracks, reflection_observations, cfg)
    observed = {o['frame']: {p['detection_id']: p['role'] for p in o['people']}
                for o in role_observations}
    opening = []
    if rows and rows[0]['frame'] == 0:
        opening = [t['person_id'] for t in rows[0]['tracks']
                   if t['association']['usable_for_actions']
                   and observed.get(0, {}).get(t['det_idx']) == 'banker']
    anchor = opening[0] if len(opening) == 1 else None
    votes = {pid: [] for pid in people}
    for row in rows:
        for tr in row['tracks']:
            role = observed.get(row['frame'], {}).get(tr['det_idx'])
            if tr['person_id'] is not None and tr['association']['usable_for_actions'] and role not in (None, 'unknown'):
                votes[tr['person_id']].append({'t': row['t'], 'frame': row['frame'],
                                               'detection_id': tr['det_idx'], 'role': role})
    for pid, person in people.items():
        counts = Counter(v['role'] for v in votes[pid])
        if pid == anchor:
            role, basis = 'banker', 'unique_opening_banker'
        elif counts['customer'] >= cfg['role_min_votes']:
            role, basis = 'customer', 'repeated_supported_customer_observations'
        else:
            role, basis = 'unknown', 'insufficient_initial_role_evidence'
        person.update(role=role, role_basis=basis, role_evidence=votes[pid],
                      role_vote_counts=dict(counts),
                      conflicting_observations=sum(v['role'] != role for v in votes[pid]) if role != 'unknown' else 0)
    return rows, {'people': people, 'opening_banker_person_id': anchor,
                  'opening_candidates': opening, 'diagnostics': events,
                  'scope': 'static roles within one-banker service sessions; roles are person properties',
                  'role_estimation': 'offline whole-clip observations; never reclassify per frame',
                  'association_confidence': 'heuristic categories, not calibrated probabilities; identity breaks require new evidence'}
