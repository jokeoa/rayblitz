import unittest
from app.vision.safe_side_policy import SafeSideAssociator

GEO={'available_at':2.,'objects':{'desk':{'box':[100,100,300,200],'side_divider':[[100,150],[300,150]]},'safe':{'box':[300,20,400,80]}}}
def track(i=1,box=None): return {'id':i,'box':box or [250,30,310,150],'score':.9,'det_idx':0}
def seeded(): return SafeSideAssociator(GEO,464,848,{'track':track(),'features':[[1.,0.]]})
def initialized():
    p=seeded();p.update(2.,[track()],[[1.,0.]]);return p

class TestSafeSide(unittest.TestCase):
    def test_weak_nested_detector_proposal_does_not_block_initialization(self):
        p=SafeSideAssociator(GEO,464,848)
        weak={**track(2,[260,35,280,60]),'score':.2}
        self.assertEqual(p.candidate([track(),weak]),0)
        strong={**weak,'score':.8}
        self.assertIsNone(p.candidate([track(),strong]))

    def test_seed_available_at_two_seconds_without_extra_wait(self):
        p=seeded()
        for i in range(20): self.assertIsNone(p.update(i/10,[track()],[[1.,0.]])[0]['person_id'])
        self.assertEqual(p.update(2.,[track()],[[1.,0.]])[0]['person_id'],'P1')
        self.assertEqual(p.people['P1']['initialized_at'],2.)

    def test_role_remains_when_crossing_table(self):
        p=initialized()
        for i in range(1,31):
            row=p.update(2+i/10,[track(box=[250-i*5,30+i*5,310-i*5,150+i*5])],[[1.,0.]])[0]
        self.assertLess(row['safe_side'],0)
        self.assertEqual(row['person_id'],'P1')
        self.assertEqual(p.active_person_id,'P1')
        self.assertEqual(p.people['P1']['role'],'banker')

    def test_customer_opposite_desk_is_not_safe_side_regression(self):
        geo={'objects':{'desk':{'box':[18,388,297,548],'side_divider':[[18,444],[297,412]]},'safe':{'box':[306,357,413,499]}}}
        p=SafeSideAssociator(geo,464,848)
        banker=track(0,[75.8,385.6,273.4,591.6])
        customer=track(2,[134.3,289.8,217.4,403.9])
        self.assertGreater(p.side(banker['box']),0)
        self.assertLess(p.side(customer['box']),0)
        self.assertEqual(p.candidate([banker,customer]),0)

    def test_ambiguous_geometry_never_initializes(self):
        p=SafeSideAssociator(GEO,464,848)
        for i in range(60): p.update(i/10,[track(),track(2)],[[1.,0.],[0.,1.]])
        self.assertEqual(p.people,{})

    def test_handoff_only_after_stable_new_safe_side_person(self):
        p=initialized()
        for i in range(6): p.update(2+i/10,[track(),track(2,[30,350,90,470])],[[1.,0.],[0.,1.]])
        for i in range(10):
            p.update(2.6+i/10,[track(2)],[[0.,1.]])
            self.assertEqual(p.active_person_id,'P1')
        row=p.update(3.6,[track(2)],[[0.,1.]])[0]
        self.assertEqual(p.active_person_id,'P2')
        self.assertEqual(row['person_id'],'P2')
        self.assertTrue(row['is_active_banker'])
        self.assertEqual(p.people['P1']['role'],'banker')
        self.assertEqual(p.transitions[-1]['from_person_id'],'P1')

    def test_single_separated_fragment_frame_does_not_prove_other_person(self):
        p=initialized()
        p.update(2.,[track(),track(2,[30,350,90,470])],[[1.,0.],[0.,1.]])
        for i in range(30): p.update(2.1+i/10,[track(2)],[[0.,1.]])
        self.assertEqual(p.active_person_id,'P1')
        self.assertEqual(len(p.people),1)

    def test_different_appearance_after_loss_is_not_proof_of_another_person(self):
        p=initialized()
        for i in range(30): row=p.update(2.1+i/10,[track(2)],[[0.,1.]])[0]
        self.assertEqual(p.active_person_id,'P1')
        self.assertEqual(len(p.people),1)
        self.assertIsNone(row['person_id'])
        self.assertEqual(row['association']['reason'],'different_identity_not_established')

    def test_handoff_preserves_old_person_role_and_separate_active_flag(self):
        p=initialized()
        for i in range(1,31):
            p.update(2+i/10,[track(box=[250-i*5,30+i*8,310-i*5,150+i*8])],[[1.,0.]])
        old_box=[100,270,160,390]
        for i in range(11):
            rows=p.update(5.1+i/10,[track(box=old_box),track(2)],[[1.,0.],[0.,1.]])
        self.assertEqual([r['person_id'] for r in rows],['P1','P2'])
        self.assertEqual([r['is_active_banker'] for r in rows],[False,True])
        self.assertEqual([p.people[k]['role'] for k in ('P1','P2')],['banker','banker'])

    def test_customer_side_cannot_handoff(self):
        p=initialized()
        for i in range(40): p.update(2.1+i/10,[track(2,[30,350,90,470])],[[0.,1.]])
        self.assertEqual(p.active_person_id,'P1');self.assertEqual(len(p.people),1)

    def test_interrupted_candidates_do_not_handoff(self):
        p=initialized()
        for i in range(30): p.update(2.1+i/10,[track(2)] if i%5 else [],[[0.,1.]] if i%5 else [])
        self.assertEqual(p.active_person_id,'P1')

    def test_lost_track_keeps_selection_but_withholds_actions(self):
        p=initialized();p.update(7.,[],[])
        self.assertEqual(p.active_person_id,'P1')
        row=p.update(7.1,[track()],[[1.,0.]])[0]
        self.assertIsNone(row['person_id']);self.assertEqual(row['association']['reason'],'long_gap')

    def test_changed_appearance_on_same_track_does_not_create_person(self):
        p=initialized()
        for i in range(20): row=p.update(2.1+i/10,[track()],[[0.,1.]])[0]
        self.assertIsNone(row['person_id']);self.assertFalse(row['association']['usable_for_actions'])
        self.assertEqual(len(p.people),1);self.assertEqual(p.active_person_id,'P1')

    def test_fragment_reconnect_is_not_handoff(self):
        p=initialized()
        self.assertEqual(p.update(2.1,[track(2)],[[1.,0.]])[0]['person_id'],'P1')
        rows=p.update(2.2,[track(2),track(1,[50,400,110,520])],[[1.,0.],[1.,0.]])
        self.assertEqual([r['person_id'] for r in rows],['P1',None]);self.assertEqual(len(p.transitions),1)

    def test_similar_unresolved_fragment_is_not_new_person(self):
        p=initialized()
        for i in range(30): p.update(6+i/10,[track(2)],[[1.,0.]])
        self.assertEqual(len(p.people),1);self.assertEqual(p.active_person_id,'P1')

    def test_overlap_withholds_action_without_erasing_role(self):
        p=initialized();row=p.update(2.1,[track(),track(2)],[[1.,0.],[0.,1.]])[0]
        self.assertEqual(row['person_id'],'P1');self.assertEqual(row['association']['confidence'],'uncertain')
        self.assertFalse(row['association']['usable_for_actions']);self.assertEqual(p.people['P1']['role'],'banker')

if __name__=='__main__': unittest.main()
