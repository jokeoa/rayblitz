"""Check failure cases where stale identity evidence could leak into a role."""
import unittest

from render import role_timeline


class RolePolicyTests(unittest.TestCase):
    cfg={"role_reset_gap_seconds":1,"role_min_votes":2,"overlap_fraction":.3}

    def run_case(self, samples):
        rows=[]
        observations=[]
        for frame,(timestamp,identity,vote,overlap) in enumerate(samples):
            rows.append({"frame":frame,"t":timestamp,"tracks":[{"id":identity,"det_idx":0,"overlap":overlap}]})
            observations.append({"frame":frame,"people":[{"detection_id":0,"role":vote}]})
        return [r["tracks"][0]["role"] for r in role_timeline(rows,observations,self.cfg)]

    def test_one_observation_cannot_assign_role(self):
        self.assertEqual(self.run_case([(0,1,"banker",0)]),["unknown"])

    def test_new_id_does_not_inherit_role(self):
        self.assertEqual(self.run_case([(0,1,"banker",0),(.5,1,"banker",0),(1,2,"banker",0)]),["unknown","banker","unknown"])

    def test_long_gap_requires_reconfirmation(self):
        self.assertEqual(self.run_case([(0,1,"banker",0),(.5,1,"banker",0),(3,1,"banker",0)]),["unknown","banker","unknown"])

    def test_conflicting_evidence_clears_role(self):
        self.assertEqual(self.run_case([(0,1,"banker",0),(.5,1,"banker",0),(1,1,"customer",0)]),["unknown","banker","unknown"])

    def test_overlapping_detection_does_not_confirm_role(self):
        self.assertEqual(self.run_case([(0,1,"banker",0),(.5,1,"banker",.8)]),["unknown","unknown"])


if __name__=="__main__":
    unittest.main()
