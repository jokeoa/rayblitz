"""Safety invariants for removal, not a substitute for annotated video metrics."""
import unittest

from reflection_filter import suppressions

CFG={"max_interval_seconds":2.01,"max_pair_overlap":.15,"min_step_iou":.1,"max_normalized_step":.35}


def fixture():
    detections=[{"frame":i,"t":i/10,"people":[[0,0,20,40,.8,0],[60,0,80,40,.9,0]]} for i in range(21)]
    tracks=[{"frame":i,"t":i/10,"tracks":[{"id":7,"det_idx":0},{"id":9,"det_idx":1}]} for i in range(21)]
    obs=[{"frame":i,"t":i/10,"people":[{"detection_id":0,"kind":"reflection","surface":True,"counterpart":1},{"detection_id":1,"kind":"direct","surface":False,"counterpart":None}]} for i in [0,20]]
    return detections,tracks,obs


class RemovalSafety(unittest.TestCase):
    def test_confirmed_pair_only_removes_reflection(self):
        removed,_=suppressions(*fixture(),CFG)
        self.assertTrue(all(set(r)=={0} for r in removed))

    def test_single_observation_does_not_remove(self):
        d,t,o=fixture()
        self.assertFalse(any(suppressions(d,t,o[:1],CFG)[0]))

    def test_unknown_does_not_remove(self):
        d,t,o=fixture();o[1]["people"][0]["kind"]="uncertain"
        self.assertFalse(any(suppressions(d,t,o,CFG)[0]))

    def test_missing_counterpart_preserves_entire_interval(self):
        d,t,o=fixture();t[10]["tracks"].pop()
        self.assertFalse(any(suppressions(d,t,o,CFG)[0]))

    def test_real_person_behind_glass_with_direct_vote_is_protected(self):
        d,t,o=fixture()
        o.insert(1,{"frame":10,"t":1,"people":[{"detection_id":0,"kind":"direct","counterpart":None}]})
        self.assertFalse(any(suppressions(d,t,o,CFG)[0]))

    def test_direct_vote_outside_interval_is_global_veto(self):
        d,t,o=fixture()
        for f in range(21,31):
            d.append({**d[0],"frame":f,"t":f/10})
            t.append({**t[0],"frame":f,"t":f/10})
        o.append({"frame":30,"t":3,"people":[{"detection_id":0,"kind":"direct","counterpart":None}]})
        self.assertFalse(any(suppressions(d,t,o,CFG)[0]))

    def test_overlapping_people_are_not_reflections(self):
        d,t,o=fixture();d[10]["people"][1][:4]=[5,0,25,40]
        self.assertFalse(any(suppressions(d,t,o,CFG)[0]))

    def test_motion_discontinuity_is_preserved(self):
        d,t,o=fixture();d[10]["people"][0][:4]=[200,200,220,240]
        self.assertFalse(any(suppressions(d,t,o,CFG)[0]))

    def test_new_track_does_not_inherit_removal(self):
        d,t,o=fixture();t[10]["tracks"][0]["id"]=11
        self.assertFalse(any(suppressions(d,t,o,CFG)[0]))


if __name__=="__main__": unittest.main()
