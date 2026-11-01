"""Formatting attributes compared by the analysis, and how each is encoded for
k-means. Free of UNO imports so it can be unit tested without LibreOffice.

Every attribute maps one or more UNO properties to a plain Python value
("read"), says how far apart two values are (0 = same, 1 = clearly different),
and how to show a value to a human ("fmt").
"""
import math

PARA, CHAR = "para", "char"

ADJUST = {0: "Left", 1: "Right", 2: "Justified", 3: "Centred", 4: "Stretched"}
CASEMAP = {0: "Normal", 1: "UPPERCASE", 2: "lowercase", 3: "Title Case", 4: "Small caps"}
LINE_MODE = {0: "Proportional", 1: "At least", 2: "Leading", 3: "Fixed"}

_INV_SQRT2 = 1 / math.sqrt(2)
_INV_SQRT3 = 1 / math.sqrt(3)


def _enum(v):
    return getattr(v, "value", v)


def _cm(v):
    return f"{v / 1000:.2f} cm"


def _pt(v):
    return f"{v:g} pt"


def _hex(v):
    return "auto" if v is None or v < 0 else f"#{v:06x}"


def _border_width(b):
    if b is None:
        return 0
    w = getattr(b, "LineWidth", 0) or 0
    return w or (b.OuterLineWidth + b.InnerLineWidth + b.LineDistance)


def _line_mode(ls):
    if ls is None:
        return "Proportional"
    if ls.Mode == 0:
        return "Proportional"
    return f"{LINE_MODE.get(ls.Mode, ls.Mode)} {ls.Height / 1000:.2f} cm"


class Attr:
    """kind: num | cat | bool | color | bgcolor"""

    def __init__(self, key, label, family, props, kind, weight=1.0, scale=1.0,
                 tol=0.0, read=None, fmt=None):
        self.key, self.label, self.family = key, label, family
        self.props, self.kind = tuple(props), kind
        self.weight, self.scale, self.tol = weight, scale, tol
        self._read, self._fmt = read, fmt

    def read(self, raw):
        if self._read:
            return self._read(raw)
        v = _enum(raw.get(self.props[0]))
        if self.kind == "bool":
            return bool(v)
        if self.kind in ("color", "bgcolor"):
            return -1 if v is None or v < 0 else v
        return v

    def fmt(self, v):
        if self._fmt:
            return self._fmt(v)
        if self.kind == "bool":
            return "yes" if v else "no"
        if self.kind == "color":
            return "automatic" if v < 0 else _hex(v)
        if self.kind == "bgcolor":
            return "none" if v < 0 else _hex(v)
        return str(v)

    def differs(self, a, b):
        if self.kind == "num":
            return abs((a or 0) - (b or 0)) > self.tol
        if self.kind == "color":  # automatic font colour renders black
            return max(a, 0) != max(b, 0)
        return a != b

    def dims(self, vocab):
        if self.kind == "cat":
            return len(vocab)
        return {"num": 1, "bool": 1, "color": 3, "bgcolor": 4}[self.kind]

    def encode(self, v, vocab):
        """Unweighted encoding; Euclidean distance between two encodings is the
        per-attribute difference (1.0 for a categorical mismatch)."""
        k = self.kind
        if k == "num":
            return [(v or 0) / self.scale]
        if k == "bool":
            return [1.0 if v else 0.0]
        if k == "cat":
            return [_INV_SQRT2 if v == x else 0.0 for x in vocab]
        if k == "color":
            v = max(v, 0)
        rgb = 0xFFFFFF if v is None or v < 0 else v
        c = [((rgb >> s) & 0xFF) / 255 * _INV_SQRT3 for s in (16, 8, 0)]
        if k == "color":
            return c
        return [0.8 if v is not None and v >= 0 else 0.0] + [x * 0.6 for x in c]


def _highlight(raw):
    for p in ("CharHighlight", "CharBackColor"):
        v = raw.get(p)
        if v is not None and v >= 0:
            return v
    return -1


def _posture(raw):
    return str(_enum(raw.get("CharPosture"))) not in ("NONE", "0", "None")


def _strike(raw):
    return (raw.get("CharStrikeout") or 0) not in (0, 3)


def _weight(v):
    return {100.0: "Normal", 150.0: "Bold"}.get(v, f"{v:g}")


def _border(side):
    prop = side + "Border"
    return Attr(f"border_{side.lower()}", f"{side} border", PARA, [prop], "num",
                weight=0.4, scale=50, tol=1, read=lambda r: _border_width(r.get(prop)),
                fmt=lambda v: "none" if not v else f"{v * 72 / 2540:.2f} pt")


PARA_ATTRS = [
    Attr("para_adjust", "Alignment", PARA, ["ParaAdjust"], "cat", 1.0,
         fmt=lambda v: ADJUST.get(v, str(v))),
    Attr("para_left", "Left indent", PARA, ["ParaLeftMargin"], "num", 1.0, 1000, 5, fmt=_cm),
    Attr("para_right", "Right indent", PARA, ["ParaRightMargin"], "num", 0.5, 1000, 5, fmt=_cm),
    Attr("para_first", "First-line indent", PARA, ["ParaFirstLineIndent"], "num", 0.8, 1000, 5,
         fmt=_cm),
    Attr("para_top", "Space above", PARA, ["ParaTopMargin"], "num", 0.5, 500, 5, fmt=_cm),
    Attr("para_bottom", "Space below", PARA, ["ParaBottomMargin"], "num", 0.5, 500, 5, fmt=_cm),
    Attr("line_mode", "Line spacing mode", PARA, ["ParaLineSpacing"], "cat", 0.4,
         read=lambda r: _line_mode(r.get("ParaLineSpacing"))),
    Attr("line_value", "Line spacing", PARA, ["ParaLineSpacing"], "num", 0.8, 50, 0.5,
         read=lambda r: (r["ParaLineSpacing"].Height
                         if r.get("ParaLineSpacing") is not None
                         and r["ParaLineSpacing"].Mode == 0 else 100),
         fmt=lambda v: f"{v:g}%"),
    Attr("para_bg", "Paragraph background", PARA, ["ParaBackColor"], "bgcolor", 0.8),
    _border("Top"), _border("Bottom"), _border("Left"), _border("Right"),
    Attr("keep_next", "Keep with next", PARA, ["ParaKeepTogether"], "bool", 0.3),
]

CHAR_ATTRS = [
    Attr("font", "Font", CHAR, ["CharFontName"], "cat", 1.0),
    Attr("size", "Font size", CHAR, ["CharHeight"], "num", 1.5, 4, 0.05, fmt=_pt),
    Attr("weight", "Weight", CHAR, ["CharWeight"], "num", 1.2, 50, 1, fmt=_weight),
    Attr("italic", "Italic", CHAR, ["CharPosture"], "bool", 1.0, read=_posture),
    Attr("color", "Font colour", CHAR, ["CharColor"], "color", 1.0),
    Attr("underline", "Underline", CHAR, ["CharUnderline"], "bool", 0.7,
         read=lambda r: bool(r.get("CharUnderline"))),
    Attr("strike", "Strikethrough", CHAR, ["CharStrikeout"], "bool", 0.5, read=_strike),
    Attr("casemap", "Case", CHAR, ["CharCaseMap"], "cat", 0.7,
         fmt=lambda v: CASEMAP.get(v, str(v))),
    Attr("kerning", "Letter spacing", CHAR, ["CharKerning"], "num", 0.5, 100, 1,
         fmt=lambda v: f"{v * 72 / 2540:.1f} pt"),
    Attr("highlight", "Highlight", CHAR, ["CharHighlight", "CharBackColor"], "bgcolor", 1.0,
         read=_highlight),
]

# Paragraph candidates compare paragraph *and* paragraph-level character
# attributes; text-run candidates compare character attributes only.
ATTRS = {PARA: PARA_ATTRS + CHAR_ATTRS, CHAR: CHAR_ATTRS}
BY_KEY = {a.key: a for a in PARA_ATTRS + CHAR_ATTRS}


def props_for(family):
    seen = []
    for a in ATTRS[family]:
        for p in a.props:
            if p not in seen:
                seen.append(p)
    return seen


def read_values(family, raw):
    return {a.key: a.read(raw) for a in ATTRS[family]}


class Encoder:
    """Turns value dicts into weighted vectors (so plain Euclidean distance is
    the weighted distance) and measures per-attribute similarity."""

    def __init__(self, family, samples):
        self.attrs = ATTRS[family]
        samples = list(samples)
        self.vocab, self.slices, pos = {}, {}, 0
        for a in self.attrs:
            vocab = []
            if a.kind == "cat":
                vocab = sorted({s[a.key] for s in samples if a.key in s}, key=repr)
            self.vocab[a.key] = vocab
            n = a.dims(vocab)
            self.slices[a.key] = (pos, pos + n)
            pos += n
        self.dim = pos
        self.total_weight = sum(a.weight for a in self.attrs)

    def encode(self, values):
        out = []
        for a in self.attrs:
            w = math.sqrt(a.weight)
            out.extend(x * w for x in a.encode(values[a.key], self.vocab[a.key]))
        return out

    def attr_distance(self, x, y, a):
        lo, hi = self.slices[a.key]
        return math.sqrt(sum((x[i] - y[i]) ** 2 for i in range(lo, hi)) / a.weight)

    def similarity(self, x, y):
        """1.0 = identical; each attribute contributes its weight times its
        (capped) difference."""
        lost = sum(a.weight * min(1.0, self.attr_distance(x, y, a)) for a in self.attrs)
        return 1.0 - lost / self.total_weight


def diffs(family, values, target):
    """[(attr, value, target_value)] for attributes that visibly differ."""
    return [(a, values[a.key], target[a.key]) for a in ATTRS[family]
            if a.differs(values[a.key], target[a.key])]


def describe(diff_list, arrow=" → "):
    return [f"{a.label}: {a.fmt(v)}{arrow}{a.fmt(t)}" for a, v, t in diff_list]
