"""Document side: reads candidates and styles out of a Writer document and
applies the actions (adopt, create style, ignore, preview, marks).
Works in-process (the extension) and over a UNO bridge (tests, tools/analyse.py).
"""
import datetime
import hashlib
import json
from contextlib import contextmanager

import uno

from .analysis import CHAR, PARA, StyleInfo, Unit, new_style_props
from .attributes import ATTRS, props_for, read_values

MARK_AUTHOR = "Style Clusters"
IGNORE_PROP = "StyleClustersIgnored"
NO_CHAR_STYLE = "Standard"   # programmatic name of "No Character Style"

PARA_PROPS = props_for(PARA)
CHAR_PROPS = props_for(CHAR)
PARA_ONLY = [p for p in PARA_PROPS if p not in CHAR_PROPS]


def _states(obj, names):
    try:
        return dict(zip(names, (s.value for s in obj.getPropertyStates(names))))
    except Exception:
        out = {}
        for n in names:
            try:
                out[n] = obj.getPropertyState(n).value
            except Exception:
                out[n] = "DEFAULT_VALUE"
        return out


def _values(obj, names):
    try:
        return dict(zip(names, obj.getPropertyValues(names)))
    except Exception:
        out = {}
        for n in names:
            try:
                out[n] = obj.getPropertyValue(n)
            except Exception:
                out[n] = None
        return out


def _direct(states):
    return [n for n, s in states.items() if s == "DIRECT_VALUE"]


def _sha(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


class DocModel:
    def __init__(self, doc):
        self.doc = doc
        self._undo_n = 0

    # ------------------------------------------------------------ reading
    def paragraphs(self):
        """Body paragraphs, including those inside tables, in document order."""
        def walk(text):
            for el in text.createEnumeration():
                if el.supportsService("com.sun.star.text.Paragraph"):
                    yield el
                elif el.supportsService("com.sun.star.text.TextTable"):
                    for name in el.getCellNames():
                        yield from walk(el.getCellByName(name))
        yield from walk(self.doc.getText())

    def collect_units(self):
        units, uid = [], 0
        for par in self.paragraphs():
            text = par.getString()
            if not text.strip():
                continue
            pstates = _states(par, PARA_PROPS)
            pdirect = _direct(pstates)
            praw = _values(par, PARA_PROPS)
            if pdirect:
                units.append(Unit(uid, PARA, text, par.ParaStyleName,
                                  read_values(PARA, praw), praw, pdirect,
                                  key=self._key(PARA, par.ParaStyleName, text, pdirect, praw),
                                  ref=par))
                uid += 1
            context = read_values(CHAR, praw)
            for run in self._runs(par):
                cur, rtext, rraw, rdirect, cstyle = run
                units.append(Unit(uid, CHAR, rtext, cstyle, read_values(CHAR, rraw), rraw,
                                  rdirect, key=self._key(CHAR, cstyle, text + "|" + rtext,
                                                         rdirect, rraw),
                                  context=context, ref=cur))
                uid += 1
        return units

    def _runs(self, par):
        """Maximal sequences of text portions sharing the same direct character
        formatting: (cursor, text, raw values, direct props, char style)."""
        runs, prev_sig = [], None
        for por in par.createEnumeration():
            if por.TextPortionType != "Text" or not por.getString():
                prev_sig = None
                continue
            direct = _direct(_states(por, CHAR_PROPS))
            if not direct:
                prev_sig = None
                continue
            raw = _values(por, CHAR_PROPS)
            sig = (por.CharStyleName, tuple((p, repr(raw[p])) for p in direct))
            if sig == prev_sig:
                cur, text, _, _, _ = runs[-1]
                cur.gotoRange(por.getEnd(), True)
                runs[-1] = (cur, text + por.getString(), raw, direct, por.CharStyleName)
            else:
                cur = par.getText().createTextCursorByRange(por.getStart())
                cur.gotoRange(por.getEnd(), True)
                runs.append((cur, por.getString(), raw, direct, por.CharStyleName))
            prev_sig = sig
        return runs

    @staticmethod
    def _key(family, style, text, direct, raw):
        sig = json.dumps(sorted((p, repr(raw.get(p))) for p in direct))
        return f"{family}|{style}|{_sha(text)}|{_sha(sig)}"

    def collect_styles(self):
        fams = self.doc.getStyleFamilies()
        out = []
        para = fams.getByName("ParagraphStyles")
        for name in para.getElementNames():
            st = para.getByName(name)
            out.append(StyleInfo(name, st.DisplayName, PARA,
                                 read_values(PARA, _values(st, PARA_PROPS)),
                                 st.isInUse(), st.isUserDefined()))
        chars = fams.getByName("CharacterStyles")
        for name in chars.getElementNames():
            out.append(StyleInfo(name, chars.getByName(name).DisplayName, CHAR,
                                 self._char_style_values(chars, name),
                                 chars.getByName(name).isInUse(),
                                 chars.getByName(name).isUserDefined()))
        return out

    @staticmethod
    def _char_style_values(family, name):
        """Only the attributes the style (or its ancestors) actually set; a
        character style leaves everything else to the paragraph."""
        chain = []
        while name and family.hasByName(name) and name not in chain:
            chain.append(name)
            name = family.getByName(name).ParentStyle
        values = {}
        for n in reversed(chain):
            st = family.getByName(n)
            set_props = set(_direct(_states(st, CHAR_PROPS)))
            if not set_props:
                continue
            raw = _values(st, CHAR_PROPS)
            for a in ATTRS[CHAR]:
                if set_props & set(a.props):
                    values[a.key] = a.read(raw)
        return values

    # ------------------------------------------------------------ actions
    def select(self, unit):
        ctrl = self.doc.getCurrentController()
        if ctrl is not None:
            ctrl.select(unit.ref)

    def adopt(self, unit, style_name):
        if unit.family == PARA:
            self._adopt_para(unit.ref, style_name)
        else:
            self._adopt_char(unit.ref, style_name)

    def _adopt_para(self, par, style_name):
        direct = _direct(_states(par, PARA_PROPS))
        char_direct = [p for p in direct if p in CHAR_PROPS]
        # Resetting a character attribute on the paragraph also strips it from
        # spans inside it, so remember span formatting and put it back.
        spans = []
        if char_direct:
            for por in par.createEnumeration():
                if por.TextPortionType != "Text":
                    continue
                keep = [p for p in _direct(_states(por, char_direct))]
                if keep:
                    cur = par.getText().createTextCursorByRange(por.getStart())
                    cur.gotoRange(por.getEnd(), True)
                    spans.append((cur, _values(por, keep)))
        par.ParaStyleName = style_name
        for p in direct:
            par.setPropertyToDefault(p)
        for cur, vals in spans:
            for p, v in vals.items():
                cur.setPropertyValue(p, v)

    def _adopt_char(self, cur, style_name):
        for p in _direct(_states(cur, CHAR_PROPS)):
            cur.setPropertyToDefault(p)
        if not style_name or style_name == NO_CHAR_STYLE:
            cur.setPropertyToDefault("CharStyleName")
        else:
            cur.CharStyleName = style_name

    def create_style(self, suggestion, name):
        """Create a style from the suggestion's source candidate; returns its name."""
        unit = suggestion.medoid or suggestion.unit
        fams = self.doc.getStyleFamilies()
        if unit.family == PARA:
            family = fams.getByName("ParagraphStyles")
            st = self.doc.createInstance("com.sun.star.style.ParagraphStyle")
        else:
            family = fams.getByName("CharacterStyles")
            st = self.doc.createInstance("com.sun.star.style.CharacterStyle")
        if family.hasByName(name):
            raise ValueError(f"A style called '{name}' already exists.")
        family.insertByName(name, st)
        if unit.family == PARA and suggestion.new_style_parent:
            st.ParentStyle = suggestion.new_style_parent
            st.FollowStyle = suggestion.new_style_parent
        for p, v in new_style_props(suggestion).items():
            st.setPropertyValue(p, v)
        return name

    # ------------------------------------------------------------ undo
    @contextmanager
    def undo_context(self, title):
        um = self.doc.getUndoManager()
        um.enterUndoContext(title)
        try:
            yield
        finally:
            um.leaveUndoContext()

    def begin_preview(self, unit, style_name):
        """Apply the adoption as a single undo step; returns a token for end_preview."""
        self._undo_n += 1
        title = f"Style Clusters preview {self._undo_n}"
        with self.undo_context(title):
            self.adopt(unit, style_name)
        return title

    def end_preview(self, token):
        um = self.doc.getUndoManager()
        if token and um.isUndoPossible() and um.getCurrentUndoActionTitle() == token:
            um.undo()
            return True
        return False

    # ------------------------------------------------------------ ignore list
    def _udp(self):
        return self.doc.getDocumentProperties().getUserDefinedProperties()

    def ignored(self):
        try:
            return set(json.loads(self._udp().getPropertyValue(IGNORE_PROP)))
        except Exception:
            return set()

    def set_ignored(self, keys):
        udp = self._udp()
        value = json.dumps(sorted(keys))
        if udp.getPropertySetInfo().hasPropertyByName(IGNORE_PROP):
            if keys:
                udp.setPropertyValue(IGNORE_PROP, value)
            else:
                udp.removeProperty(IGNORE_PROP)
        elif keys:
            udp.addProperty(IGNORE_PROP, 128, value)  # 128 = REMOVABLE

    # ------------------------------------------------------------ marks (comments)
    def add_marks(self, suggestions):
        t = datetime.datetime.now()
        now = uno.createUnoStruct("com.sun.star.util.DateTime", 0, t.second, t.minute, t.hour,
                                  t.day, t.month, t.year, False)
        with self.undo_context("Style Clusters: mark candidates"):
            for s in suggestions:
                ann = self.doc.createInstance("com.sun.star.text.textfield.Annotation")
                ann.Author = MARK_AUTHOR
                ann.DateTimeValue = now
                ann.Content = f"[{s.label}] " + s.tooltip()
                # A cursor made from the whole paragraph object includes the
                # paragraph mark and the insert fails; span start..end instead.
                rng = s.unit.ref
                cur = rng.getText().createTextCursorByRange(rng.getStart())
                cur.gotoRange(rng.getEnd(), True)
                rng.getText().insertTextContent(cur, ann, True)

    def clear_marks(self):
        fields = self.doc.getTextFields().createEnumeration()
        doomed = []
        while fields.hasMoreElements():
            f = fields.nextElement()
            if f.supportsService("com.sun.star.text.textfield.Annotation") and \
                    f.Author == MARK_AUTHOR:
                doomed.append(f)
        if doomed:
            with self.undo_context("Style Clusters: remove marks"):
                for f in doomed:
                    f.dispose()
        return len(doomed)
