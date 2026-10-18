import copy
import unittest


from app.vision.object_context import PersonContext, observation_intervals, resolve


class ContextTests(unittest.TestCase):
    def test_role_lookup_is_causal_and_expires(self):
        person = {"person_id":"P1", "classification":{"role":"banker"}}
        context = PersonContext({"fps":10,"people":{"P1":{"initialized_at":2}},
                                 "rows":[{"t":1.9,"tracks":[person]}, {"t":2.,"tracks":[person]}]})
        self.assertIsNone(context.at(1.8))
        self.assertEqual(context.at(1.95)["t"],1.9)
        self.assertEqual(context.at(1.95)["tracks"][0]["classification"]["role"],"unknown")
        self.assertEqual(context.at(2.)["tracks"][0]["classification"]["role"],"banker")
        self.assertIsNone(context.at(2.2))
        self.assertEqual(person["classification"]["role"],"banker")

    def test_worn_clothes_excluded_but_table_jacket_preserved(self):
        clothes = [{"class":"clothing", "box":[20,20,70,100], "score":.9}]
        before = copy.deepcopy(clothes)
        person = {"id":1, "person_id":"P1", "box":[0,0,100,200], "score":.9,
                  "classification":{"role":"banker", "possible_reflection":False},
                  "association":{"usable_for_actions":True}}
        people = {"t":2., "tracks":[person]}
        kept, excluded = resolve(clothes, people, [], 2.)
        self.assertEqual(len(excluded), 1)
        self.assertEqual(len(kept), 0)
        person["box"] = [150,0,250,200]
        kept, excluded = resolve(clothes, people, [], 2.)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(excluded), 0)
        self.assertEqual(clothes, before)

    def test_equipment_override_scoped_in_space_and_time(self):
        anchor={"id":"counter","interval":[7,11],"class":"cash_counter","class_index":10,
                "box":[75,345,147,435],"identity_source":"human"}
        left={"class":"desk_phone","box":[75,350,143,429],"score":.2}
        right={"class":"desk_phone","box":[279,369,319,411],"score":.3}
        kept,_=resolve([left,right],None,[anchor],9)
        self.assertEqual([p['class'] for p in kept],['desk_phone','cash_counter'])
        self.assertEqual(left['class'],'desk_phone')
        self.assertTrue(all(p['class']=='desk_phone' for p in resolve([left,right],None,[anchor],11)[0]))

    def test_duration_does_not_bridge_missing_observation(self):
        track={"id":"cash-1","class":"cash"}
        rows=[{"t":t,"tracks":ps} for t,ps in [(0,[track]),(.1,[track]),(.2,[]),(.3,[track])]]
        item=observation_intervals(rows,10)[0]
        self.assertEqual(item["intervals"],[[0,.2],[.3,.4]])
        self.assertEqual(item["observed_seconds"],.3)
        self.assertEqual(item["observed_samples"],3)


if __name__ == "__main__":
    unittest.main()
