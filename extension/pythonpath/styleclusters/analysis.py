"""Turns candidates and styles into suggestions using anchored k-means.
UNO-free: the document side (unodoc.py) supplies plain Unit / StyleInfo data.
"""
from dataclasses import dataclass, field

from . import kmeans
from .attributes import ATTRS, BY_KEY, CHAR, PARA, Encoder, describe, diffs

SAME, SIMILAR, CLUSTER, UNIQUE = "same", "similar", "cluster", "unique"
KIND_LABEL = {SAME: "Same as style", SIMILAR: "Similar", CLUSTER: "New style?",
              UNIQUE: "Unique"}
KIND_ORDER = {SAME: 0, SIMILAR: 1, CLUSTER: 2, UNIQUE: 3}


@dataclass
class Unit:
    """A paragraph or text run carrying direct formatting."""
    uid: int
    family: str            # PARA or CHAR
    text: str
    style: str             # current paragraph / character style ('' = none)
    values: dict           # effective attribute values
    raw: dict              # raw UNO property values (for creating styles)
    direct: list           # UNO property names set directly
    key: str = ""          # stable key for "ignore"
    context: dict = None   # CHAR only: values of the surrounding paragraph
    ref: object = None     # opaque handle used by the document layer


@dataclass
class StyleInfo:
    name: str
    display: str
    family: str
    values: dict           # PARA: effective values; CHAR: only attributes it sets
    in_use: bool = True
    user_defined: bool = False


@dataclass
class Settings:
    adopt: float = 0.80      # similarity needed to suggest adopting a style
    cluster: float = 0.92    # similarity every member needs to its free centroid
    min_cluster: int = 2     # members needed to propose a new style
    include_unused: bool = False
    seed: int = 0


@dataclass
class Suggestion:
    unit: Unit
    kind: str
    style: str = None          # suggested existing style (assigned or nearest)
    style_display: str = ""
    similarity: float = 0.0
    diffs: list = field(default_factory=list)   # [(attr, unit value, style value)]
    group: tuple = None        # k-means label shared with other suggestions
    group_size: int = 1
    cluster_id: int = None     # 1-based number for free clusters
    shared: list = field(default_factory=list)  # CLUSTER: [(attr, value)] all members share
    medoid: Unit = None        # CLUSTER: member closest to the centroid
    new_style_values: list = field(default_factory=list)  # [(attr, value)] for "Create style"
    new_style_parent: str = ""
    new_style_name: str = ""

    @property
    def label(self):
        return KIND_LABEL[self.kind]

    def tooltip(self, compact=False):
        """How the candidate differs from the suggestion. compact=True gives a
        single paragraph for tooltips, which do not honour line breaks."""
        if compact:
            return " ".join(line.strip().replace("• ", "") + ("" if line.endswith((".", ":")) else ";")
                            for line in self.tooltip().splitlines()).rstrip(";")
        lines = []
        if self.kind == CLUSTER:
            lines.append(f"Cluster {self.cluster_id}: {self.group_size} candidates share "
                         "this manual formatting and no style matches it.")
            if self.shared:
                lines.append("Shared: " + "; ".join(f"{a.label} {a.fmt(v)}" for a, v in self.shared)
                             + ".")
        if self.style is not None:
            head = {SAME: "Identical to", SIMILAR: "Could adopt"}.get(self.kind, "Nearest style")
            lines.append(f"{head} '{self.style_display}' ({self.similarity:.0%} similar).")
            if self.diffs:
                lines.append("Differences (now → with style):")
                lines += ["  • " + d for d in describe(self.diffs)]
            elif self.unit.style == self.style:
                lines.append("The direct formatting is redundant: removing it changes nothing.")
            else:
                lines.append("Adopting it changes nothing visible.")
        return "\n".join(lines)


def _anchor_values(unit, style):
    if unit.family == PARA:
        return style.values
    merged = dict(unit.context)
    merged.update(style.values)
    return merged


def style_name_for(unit_style, new_values, existing):
    namers = {"para_adjust": lambda v: {3: "Centred", 1: "Right", 2: "Justified"}.get(v),
              "italic": lambda v: "Italic" if v else None,
              "weight": lambda v: "Bold" if v >= 140 else None,
              "size": lambda v: f"{v:g}pt",
              "casemap": lambda v: {4: "Small Caps", 1: "Caps"}.get(v),
              "highlight": lambda v: "Highlight" if v >= 0 else None,
              "para_left": lambda v: "Indented" if v else None,
              "border_bottom": lambda v: "Rule" if v else None,
              "border_top": lambda v: "Rule" if v else None,
              "color": lambda v: "Coloured",
              "underline": lambda v: "Underlined" if v else None}
    words = []
    for a, v in new_values:
        w = namers[a.key](v) if a.key in namers else None
        if w and w not in words:
            words.append(w)
    base = f"{unit_style or 'Text'} {' '.join(words[:3]) or 'Variant'}".strip()
    name, n = base, 2
    while name in existing:
        name, n = f"{base} {n}", n + 1
    return name


def analyse(units, styles, settings=None):
    settings = settings or Settings()
    out = []
    existing = {s.name for s in styles} | {s.display for s in styles}
    for family in (PARA, CHAR):
        fam_units = [u for u in units if u.family == family]
        if not fam_units:
            continue
        current = {u.style for u in fam_units}
        fam_styles = [s for s in styles if s.family == family and
                      (settings.include_unused or s.in_use or s.user_defined or s.name in current
                       or (family == CHAR and not s.values))]
        out += _analyse_family(family, fam_units, fam_styles, settings, existing)
    out.sort(key=lambda s: (KIND_ORDER[s.kind], s.unit.uid))
    return out


def _analyse_family(family, units, styles, settings, existing):
    samples = [u.values for u in units] + [_anchor_values(u, s) for u in units for s in styles]
    enc = Encoder(family, samples)
    points = [enc.encode(u.values) for u in units]

    # Per unit: every style as (id, vector, similarity); the nearest one is always
    # reported, but only those above the threshold may capture the unit.
    per_unit, eligible = [], []
    for u, x in zip(units, points):
        cands = []
        for idx, s in enumerate(styles):
            v = enc.encode(_anchor_values(u, s))
            cands.append((idx, v, enc.similarity(x, v)))
        cands.sort(key=lambda c: -c[2])
        per_unit.append(cands)
        eligible.append([(idx, v) for idx, v, sim in cands if sim >= settings.adopt])

    fit = kmeans.fit(points, eligible,
                     accept=lambda i, c: enc.similarity(points[i], c) >= settings.cluster,
                     seed=settings.seed)

    # Free clusters too small to justify a new style dissolve: their members fall
    # back to the best style they may adopt (if any).
    labels = list(fit.labels)
    for i, label in enumerate(labels):
        if label and label[0] == "free" and len(fit.members(label)) < settings.min_cluster:
            labels[i] = ("anchor", eligible[i][0][0]) if eligible[i] else ("single", i)

    free_ids = {}
    result = []
    for i, (u, label) in enumerate(zip(units, labels)):
        members = [m for m, l in enumerate(labels) if l == label]
        if label[0] == "anchor":
            idx = label[1]
            sim = next(c[2] for c in per_unit[i] if c[0] == idx)
        else:
            idx, _, sim = per_unit[i][0] if per_unit[i] else (None, None, 0.0)
        style = styles[idx] if idx is not None else None
        target = _anchor_values(u, style) if style else None
        d = diffs(family, u.values, target) if style else []
        if label[0] == "anchor":
            kind = SAME if not d else SIMILAR
        elif label[0] == "free":
            kind = CLUSTER
        else:
            kind = UNIQUE
        sug = Suggestion(unit=u, kind=kind, group=label, group_size=len(members),
                         style=style.name if style else None,
                         style_display=style.display if style else "",
                         similarity=sim, diffs=d)
        if kind == CLUSTER:
            sug.cluster_id = free_ids.setdefault(label, len(free_ids) + 1)
            c = fit.centroids[label[1]]
            sug.medoid = units[min(members, key=lambda m: kmeans.dist(points[m], c))]
            sug.shared = _shared(family, [units[m] for m in members], u)
        _plan_new_style(sug, family, existing)
        result.append(sug)
    return result


def _shared(family, members, unit):
    """Attributes every member has in common that differ from the baseline
    (the paragraph style, or the surrounding paragraph for runs)."""
    out = []
    for a in ATTRS[family]:
        vals = [m.values[a.key] for m in members]
        if all(not a.differs(vals[0], v) for v in vals[1:]):
            base = unit.context[a.key] if family == CHAR else None
            if family == CHAR and not a.differs(vals[0], base):
                continue
            out.append((a, vals[0]))
    if family == PARA:  # keep only what members set by hand
        direct = set.intersection(*(set(m.direct) for m in members))
        out = [(a, v) for a, v in out if set(a.props) & direct]
    return out


def _plan_new_style(sug, family, existing):
    """Values a new style would need: what the source (the cluster medoid, or the
    unit itself) sets by hand on top of its parent style / paragraph."""
    src = sug.medoid or sug.unit
    direct = set(src.direct)
    vals = [(a, src.values[a.key]) for a in ATTRS[family] if set(a.props) & direct]
    if family == CHAR:
        vals = [(a, v) for a, v in vals if a.differs(v, src.context[a.key])]
    sug.new_style_values = vals
    sug.new_style_parent = src.style if family == PARA else ""
    sug.new_style_name = style_name_for(src.style if family == PARA else "", vals, existing)


def new_style_props(sug):
    """UNO property -> raw value to set on a style created from this suggestion."""
    src = sug.medoid or sug.unit
    props = {}
    for a, _ in sug.new_style_values:
        for p in a.props:
            if p in src.direct and src.raw.get(p) is not None:
                props[p] = src.raw[p]
    return props


__all__ = ["Unit", "StyleInfo", "Settings", "Suggestion", "analyse", "new_style_props",
           "SAME", "SIMILAR", "CLUSTER", "UNIQUE", "PARA", "CHAR", "BY_KEY"]
