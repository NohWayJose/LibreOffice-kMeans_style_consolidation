"""Integration tests against a private headless LibreOffice.
Skipped automatically when pyuno is not importable."""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "extension", "pythonpath"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
SAMPLE = os.path.join(ROOT, "hitchhikers_ch1_styles.odt")

try:
    from lo_headless import Office
except ImportError:  # no pyuno
    Office = None

from styleclusters.analysis import CHAR, CLUSTER, PARA, SAME, Settings, analyse  # noqa: E402

if Office:
    from styleclusters.unodoc import MARK_AUTHOR, DocModel


@unittest.skipIf(Office is None, "pyuno not available")
class IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="styleclusters-test-")
        cls.office = Office(profile=os.path.join(cls.tmp, "profile"))

    @classmethod
    def tearDownClass(cls):
        cls.office.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        path = os.path.join(self.tmp, f"{self._testMethodName}.odt")
        shutil.copy(SAMPLE, path)
        self.doc = self.office.load(path)
        self.model = DocModel(self.doc)

    def tearDown(self):
        self.doc.close(True)

    def run_analysis(self):
        return analyse(self.model.collect_units(), self.model.collect_styles(), Settings())

    def find(self, sugs, text):
        return next(s for s in sugs if s.unit.text.startswith(text))

    def paragraph(self, text):
        return next(p for p in self.model.paragraphs() if p.getString().startswith(text))

    def test_finds_every_manually_formatted_paragraph(self):
        sugs = self.run_analysis()
        self.assertEqual(sum(s.unit.family == PARA for s in sugs), 5)
        self.assertEqual(sorted(s.unit.text for s in sugs if s.unit.family == CHAR),
                         ["DON’T PANIC", "Horse and Groom", "bypass", "demolished"])

    def test_adopt_paragraph_keeps_spans(self):
        # paragraph-level direct formatting around a 16pt span (setting the
        # paragraph attribute overwrites spans, so re-apply the span after)
        par = self.paragraph("Those two words")
        par.CharHeight = 9.0
        span = next(p for p in par.createEnumeration() if p.getString() == "DON’T PANIC")
        cur = par.getText().createTextCursorByRange(span)
        cur.CharHeight = 16.0
        s = self.find(self.run_analysis(), "Those two words")
        self.assertEqual(s.style, "Text Body")
        self.model.adopt(s.unit, s.style)
        sizes = {p.getString(): p.CharHeight for p in par.createEnumeration()}
        self.assertEqual(sizes["DON’T PANIC"], 16.0)
        self.assertEqual(sizes["Those two words, the narrator explains, are "], 11.0)

    def test_adopt_run_removes_direct_formatting_only_there(self):
        s = self.find(self.run_analysis(), "Horse and Groom")
        self.model.adopt(s.unit, s.style)
        par = self.paragraph("And so, with")
        self.assertTrue(all(p.CharCaseMap == 0 and p.CharUnderline == 0
                            for p in par.createEnumeration()))
        self.assertNotIn("Horse and Groom", [u.text for u in self.model.collect_units()])

    def test_create_style_from_cluster_then_rerun(self):
        s = self.find(self.run_analysis(), "bypass")
        self.assertEqual(s.kind, CLUSTER)
        name = self.model.create_style(s, s.new_style_name)
        self.model.adopt(s.unit, name)
        after = self.find(self.run_analysis(), "demolished")
        self.assertEqual((after.kind, after.style), (SAME, name))
        self.model.adopt(after.unit, name)
        self.assertNotIn("demolished", [u.text for u in self.model.collect_units()])

    def test_create_paragraph_style(self):
        s = self.find(self.run_analysis(), "A Matter of Some Urgency")
        name = self.model.create_style(s, "Fake Heading")
        st = self.doc.getStyleFamilies().getByName("ParagraphStyles").getByName(name)
        self.assertEqual((st.ParentStyle, st.CharHeight, st.CharWeight),
                         (s.unit.style, 15.0, 150.0))
        self.model.adopt(s.unit, name)
        self.assertEqual(self.find(self.run_analysis(), "In which").unit.style, "Text Body")
        self.assertNotIn("A Matter", " ".join(u.text for u in self.model.collect_units()))

    def test_preview_is_undone(self):
        s = self.find(self.run_analysis(), "A Matter of Some Urgency")
        par = self.paragraph("A Matter")
        token = self.model.begin_preview(s.unit, s.style)
        self.assertEqual((par.ParaStyleName, par.CharHeight), (s.style, 18.0))
        self.assertTrue(self.model.end_preview(token))
        self.assertEqual((par.ParaStyleName, par.CharHeight), ("Text Body", 15.0))

    def test_marks_round_trip(self):
        sugs = self.run_analysis()
        text_before = self.doc.getText().getString()
        self.model.add_marks(sugs)
        authors = []
        e = self.doc.getTextFields().createEnumeration()
        while e.hasMoreElements():
            authors.append(e.nextElement().Author)
        self.assertEqual(authors.count(MARK_AUTHOR), len(sugs))
        self.assertEqual(self.doc.getText().getString(), text_before)
        # marks must not change what the analysis sees
        self.assertEqual(len(self.run_analysis()), len(sugs))
        self.assertEqual(self.model.clear_marks(), len(sugs))
        self.assertEqual(self.doc.getText().getString(), text_before)

    def test_ignore_persists_in_document(self):
        keys = {u.key for u in self.model.collect_units()[:2]}
        self.model.set_ignored(keys)
        self.assertEqual(self.model.ignored(), keys)
        self.model.set_ignored(set())
        self.assertEqual(self.model.ignored(), set())


if __name__ == "__main__":
    unittest.main()
