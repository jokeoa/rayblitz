import unittest
from pathlib import Path
from initial_window import native_frames, mapped_track, opening_consensus

class TestOpening(unittest.TestCase):
    def test_votes_include_missed_frames_in_denominator(self):
        self.assertEqual(opening_consensus([{'track_id':1}]*6+[{'track_id':None}]*4)[0],None)
        self.assertEqual(opening_consensus([{'track_id':1}]*7+[{'track_id':None}]*3)[0],1)
        self.assertEqual(opening_consensus([])[0],None)

    def test_ambiguous_track_match_is_withheld(self):
        rows=[{'t':0.,'tracks':[{'id':1,'box':[0,0,100,100]},{'id':2,'box':[1,1,101,101]}]}]
        self.assertIsNone(mapped_track([0,0,100,100],0.,rows))
        rows[0]['tracks'].pop()
        self.assertEqual(mapped_track([0,0,100,100],0.,rows),1)

    def test_native_interval_has_every_original_frame(self):
        # This source is 30 fps. An accidental 10 fps sampler would yield 20.
        frames=list(native_frames(Path(__file__).parent/'data/X-12.mov',2.))
        self.assertEqual(len(frames),60)
        self.assertEqual([f[0] for f in frames],list(range(60)))
        self.assertAlmostEqual(frames[-1][1],59/30,places=4)

if __name__=='__main__': unittest.main()
