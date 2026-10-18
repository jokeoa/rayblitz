import json
import tempfile
import unittest
from pathlib import Path

from common import sha256
from scene_references import reference_geometry


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.image=self.root/'safe.png';self.image.write_bytes(b'reference evidence')
        obj={'side_divider':[[10,20],[30,20]],'box':[10,10,30,40],'image':'safe.png','image_sha256':sha256(self.image)}
        self.manifest={'videos':{'X-1':{'source_sha256':'known','image_size':[100,100],'time':2.,'objects':{'safe':obj,'desk':obj}}}}
        self.write()

    def tearDown(self): self.temp.cleanup()
    def write(self): (self.root/'scene_references.json').write_text(json.dumps(self.manifest))
    def load(self,source='known'): return reference_geometry('X-1',source,100,100,self.root)

    def test_exact_reference_and_no_automatic_replacement(self):
        g=self.load();self.assertEqual(set(g['objects']),{'safe','desk'});self.assertFalse(g['automatic_replacement'])

    def test_wrong_source_is_rejected(self):
        with self.assertRaises(ValueError):self.load('another recording')

    def test_explicitly_absent_safe_allows_anchor_search(self):
        self.manifest['videos']['X-1']['objects']['safe']=None;self.write()
        self.assertIsNone(self.load()['objects']['safe'])

    def test_changed_image_is_rejected(self):
        self.image.write_bytes(b'pedestal instead of safe')
        with self.assertRaises(ValueError):self.load()

    def test_missing_reference_and_extra_object_rejected(self):
        with self.assertRaises(ValueError):reference_geometry('X-2','known',100,100,self.root)
        self.manifest['videos']['X-1']['objects']['chair']=self.manifest['videos']['X-1']['objects']['safe'];self.write()
        with self.assertRaises(ValueError):self.load()


if __name__=='__main__':unittest.main()
