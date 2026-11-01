"""Unit tests for the UNO-free core: python3 -m unittest discover tests"""
import os
import sys
import unittest
from collections import namedtuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "extension", "pythonpath"))

from styleclusters import kmeans  # noqa: E402
from styleclusters.analysis import (CHAR, CLUSTER, PARA, SAME, SIMILAR, UNIQUE,  # noqa: E402
                                    Settings, StyleInfo, Unit, analyse, new_style_props)
from styleclusters.attributes import Encoder, read_values  # noqa: E402

LS = namedtuple("LS", "Mode Height")

BODY = {"ParaAdjust": 2, "ParaLeftMargin": 0, "ParaRightMargin": 0, "ParaFirstLineIndent": 0,
        "ParaTopMargin": 0, "ParaBottomMargin": 250, "ParaLineSpacing": LS(0, 115),
        "ParaBackColor": -1, "TopBorder": None, "BottomBorder": None, "LeftBorder": None,
        "RightBorder": None, "ParaKeepTogether": False, "CharFontName": "Liberation Serif",
        "CharHeight": 11.0, "CharWeight": 100.0, "CharPosture": "NONE", "CharColor": -1,
        "CharUnderline": 0, "CharStrikeout": 0, "CharCaseMap": 0, "CharKerning": 0,
        "CharHighlight": -1, "CharBackColor": -1}
H2 = dict(BODY, ParaAdjust=0, ParaTopMargin=450, ParaBottomMargin=200, ParaKeepTogether=True,
          ParaLineSpacing=LS(0, 100), CharFontName="Liberation Sans", CharHeight=14.0,
          CharWeight=150.0, CharPosture="ITALIC", CharColor=0x2E5A88)


def para_style(name, raw, **kw):
    return StyleInfo(name, name, PARA, read_values(PARA, raw), **kw)


def para_unit(uid, raw, direct, style="Text Body"):
    return Unit(uid, PARA, f"p{uid}", style, read_values(PARA, raw), raw, list(direct))


def char_unit(uid, overrides, para_raw=BODY):
    raw = dict(para_raw, **overrides)
    return Unit(uid, CHAR, f"r{uid}", "", read_values(CHAR, raw), raw, list(overrides),
                context=read_values(CHAR, para_raw))


STYLES = [para_style("Text Body", BODY), para_style("Heading 2", H2),
          StyleInfo("Standard", "No Character Style", CHAR, {}),
          StyleInfo("Strong", "Strong Emphasis", CHAR, {"weight": 150.0})]


class EncoderTest(unittest.TestCase):
    def test_similarity(self):
        a = read_values(PARA, BODY)
        b = read_values(PARA, dict(BODY, CharFontName="Liberation Sans"))
        enc = Encoder(PARA, [a, b])
        self.assertAlmostEqual(enc.similarity(enc.encode(a), enc.encode(a)), 1.0)
        # one categorical mismatch costs exactly its share of the total weight
        self.assertAlmostEqual(enc.similarity(enc.encode(a), enc.encode(b)),
                               1 - 1.0 / enc.total_weight)


class KMeansTest(unittest.TestCase):
    def test_points_on_anchors_need_no_free_clusters(self):
        pts = [[0, 0], [0.1, 0]]
        anchors = [[("A", [0, 0])]] * 2
        fit = kmeans.fit(pts, anchors, accept=lambda i, c: kmeans.dist(pts[i], c) < 0.5)
        self.assertEqual(fit.k, 0)
        self.assertEqual(fit.labels, [("anchor", "A")] * 2)

    def test_discovers_groups_away_from_anchors(self):
        pts = [[5, 5], [5.1, 5], [5, 5.1], [-5, 5], [-5.1, 5], [0, 0]]
        anchors = [[]] * 5 + [[("A", [0, 0])]]
        fit = kmeans.fit(pts, anchors, accept=lambda i, c: kmeans.dist(pts[i], c) < 0.5)
        self.assertEqual(fit.k, 2)
        self.assertEqual(len({fit.labels[i] for i in range(3)}), 1)
        self.assertEqual(len({fit.labels[i] for i in (3, 4)}), 1)
        self.assertNotEqual(fit.labels[0], fit.labels[3])
        self.assertEqual(fit.labels[5], ("anchor", "A"))


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        epigraph = dict(BODY, ParaAdjust=3, CharPosture="ITALIC", CharColor=0x666666,
                        CharHeight=12.0)
        epi_direct = ["ParaAdjust", "CharPosture", "CharColor", "CharHeight"]
        fake_heading = dict(H2, CharPosture="NONE", CharHeight=15.0)
        weird = dict(BODY, CharFontName="Comic Sans", CharHeight=30.0, CharColor=0xFF00FF,
                     ParaAdjust=1, ParaLeftMargin=4000)
        self.units = [
            para_unit(1, epigraph, epi_direct),
            para_unit(2, epigraph, epi_direct),
            para_unit(3, dict(epigraph, CharHeight=12.2), epi_direct),
            para_unit(4, fake_heading, ["CharFontName", "CharHeight", "CharWeight"]),
            para_unit(5, BODY, ["ParaAdjust"]),
            para_unit(6, weird, ["CharFontName", "CharHeight"]),
            char_unit(7, {"CharBackColor": 0xFFFF00}),
            char_unit(8, {"CharBackColor": 0xFFFF00}),
            char_unit(9, {"CharWeight": 150.0}),
            char_unit(10, {"CharFontName": "Liberation Serif"}),
        ]
        self.by_uid = {s.unit.uid: s for s in analyse(self.units, STYLES, Settings())}

    def test_classification(self):
        kinds = {uid: s.kind for uid, s in self.by_uid.items()}
        self.assertEqual(kinds, {1: CLUSTER, 2: CLUSTER, 3: CLUSTER, 4: SIMILAR, 5: SAME,
                                 6: UNIQUE, 7: CLUSTER, 8: CLUSTER, 9: SAME, 10: SAME})
        self.assertEqual(self.by_uid[4].style, "Heading 2")
        self.assertEqual(self.by_uid[9].style, "Strong")
        self.assertEqual(self.by_uid[10].style, "Standard")

    def test_cluster_details(self):
        s = self.by_uid[1]
        self.assertEqual(s.group_size, 3)
        self.assertEqual(len({self.by_uid[u].cluster_id for u in (1, 2, 3)}), 1)
        self.assertEqual({a.key for a, _ in s.shared}, {"para_adjust", "italic", "color"})
        self.assertIn("Cluster", s.tooltip())

    def test_diff_tooltip(self):
        tip = self.by_uid[4].tooltip()
        self.assertIn("Font size: 15 pt → 14 pt", tip)
        self.assertIn("Italic: no → yes", tip)
        compact = self.by_uid[4].tooltip(compact=True)
        self.assertNotIn("\n", compact)
        self.assertIn("Font size: 15 pt → 14 pt; Italic: no → yes", compact)

    def test_new_style_from_cluster(self):
        s = self.by_uid[7]
        self.assertEqual(new_style_props(s), {"CharBackColor": 0xFFFF00})
        self.assertIn("Highlight", s.new_style_name)

    def test_new_style_rejoins_cluster(self):
        """Once a style exists for the cluster, its members adopt it."""
        sug = self.by_uid[1]
        raw = dict(BODY, **new_style_props(sug))
        styles = STYLES + [para_style(sug.new_style_name, raw, user_defined=True)]
        res = {s.unit.uid: s for s in analyse(self.units, styles, Settings())}
        for uid in (1, 2, 3):
            self.assertIn(res[uid].kind, (SAME, SIMILAR))
            self.assertEqual(res[uid].style, sug.new_style_name)


if __name__ == "__main__":
    unittest.main()
