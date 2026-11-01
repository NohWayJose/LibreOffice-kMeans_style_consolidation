"""Non-modal Style Clusters dialog: candidate grid (row tooltips list the
differences), in-document preview via undo, and the adopt / apply-to-group /
create-style / ignore actions."""
import traceback

import unohelper
from com.sun.star.awt import XActionListener, XItemListener, XTopWindowListener
from com.sun.star.awt.grid import XGridSelectionListener
from com.sun.star.awt.MessageBoxType import ERRORBOX
from com.sun.star.util import XCloseListener
from com.sun.star.view.SelectionType import SINGLE

from .analysis import CHAR, CLUSTER, SAME, SIMILAR, UNIQUE, Settings, analyse
from .unodoc import NO_CHAR_STYLE, DocModel

_OPEN = {}  # document RuntimeUID -> dialog; keeps non-modal dialogs alive

COLUMNS = [("Finding", 58), ("Type", 34), ("Text", 150), ("Current style", 62),
           ("Suggested style", 78), ("Similar", 34)]


def open_for(ctx, doc):
    if doc is None or not doc.supportsService("com.sun.star.text.TextDocument"):
        _message(ctx, None, "Style Clusters works on Writer documents.")
        return None
    uid = doc.RuntimeUID
    if uid in _OPEN:
        _OPEN[uid].dlg.setFocus()
        return _OPEN[uid]
    _OPEN[uid] = StyleClustersDialog(ctx, doc)
    return _OPEN[uid]


def _message(ctx, parent, text, title="Style Clusters"):
    tk = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    tk.createMessageBox(parent, ERRORBOX, 1, title, text).execute()


def _guard(fn):
    def wrapper(self, *args):
        try:
            return fn(self, *args)
        except Exception as e:
            traceback.print_exc()
            peer = self.dlg.getPeer() if self.dlg else None
            _message(self.ctx, peer, f"{e}\n\n{traceback.format_exc()}")
    return wrapper


class _Listener(unohelper.Base, XActionListener, XItemListener, XGridSelectionListener,
                XTopWindowListener, XCloseListener):
    def __init__(self, owner):
        self.owner = owner

    def actionPerformed(self, ev):
        self.owner.on_action(ev.ActionCommand)

    def itemStateChanged(self, ev):
        self.owner.on_toggle()

    def selectionChanged(self, ev):
        self.owner.on_select()

    def windowClosing(self, ev):
        self.owner.close()

    def queryClosing(self, ev, owns):
        self.owner.close()

    def notifyClosing(self, ev):
        pass

    def windowOpened(self, ev): pass
    def windowClosed(self, ev): pass
    def windowMinimized(self, ev): pass
    def windowNormalized(self, ev): pass
    def windowActivated(self, ev): pass
    def windowDeactivated(self, ev): pass
    def disposing(self, ev): pass


class StyleClustersDialog:
    def __init__(self, ctx, doc):
        self.ctx, self.doc = ctx, doc
        self.model = DocModel(doc)
        self.smgr = ctx.ServiceManager
        self.sugs, self.preview, self.marked = [], None, False
        self.listener = _Listener(self)
        self._build()
        doc.addCloseListener(self.listener)
        self.reanalyse()

    # ------------------------------------------------------------ layout
    def _add(self, kind, name, x, y, w, h, **props):
        service = (f"com.sun.star.awt.{kind}Model" if "." in kind
                   else f"com.sun.star.awt.UnoControl{kind}Model")
        m = self.dm.createInstance(service)
        m.PositionX, m.PositionY, m.Width, m.Height = x, y, w, h
        for k, v in props.items():
            setattr(m, k, v)
        self.dm.insertByName(name, m)
        return m

    def _button(self, name, label, x, y, w, tip=""):
        self._add("Button", name, x, y, w, 14, Label=label, HelpText=tip)
        self.dlg.getControl(name).setActionCommand(name)
        self.dlg.getControl(name).addActionListener(self.listener)

    def _build(self):
        sm, ctx = self.smgr, self.ctx
        self.dm = sm.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
        self.dm.Width, self.dm.Height = 440, 296
        self.dm.Title = "Style Clusters — " + (self.doc.getTitle() if hasattr(self.doc, "getTitle")
                                                 else "document")
        self.dm.Closeable, self.dm.Moveable = True, True
        self.dlg = sm.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
        self.dlg.setModel(self.dm)

        self._button("analyse", "Re-analyse", 6, 6, 56,
                     "Run the k-means analysis again with the current settings")
        self._add("FixedText", "lblAdopt", 68, 9, 42, 10, Label="Adopt if ≥")
        self._add("NumericField", "threshold", 108, 6, 32, 14, Value=Settings.adopt * 100,
                  ValueMin=50, ValueMax=100, DecimalAccuracy=0, Spin=True,
                  HelpText="Minimum similarity for suggesting an existing style")
        self._add("FixedText", "lblPct", 143, 9, 34, 10, Label="% similar")
        self._add("CheckBox", "unused", 180, 8, 118, 10, Label="Include unused built-in styles",
                  HelpText="Also compare against built-in styles the document does not use")
        self._add("CheckBox", "marks", 302, 8, 134, 10, Label="Mark candidates in document",
                  HelpText="Add a 'Style Clusters' comment to every candidate; "
                           "removed again when unticked or the dialog closes")

        grid = self._add("grid.UnoControlGrid", "grid", 6, 24, 428, 140,
                         ShowRowHeader=False, ShowColumnHeader=True, HScroll=False,
                         VScroll=True, SelectionModel=SINGLE)
        cols = sm.createInstanceWithContext("com.sun.star.awt.grid.DefaultGridColumnModel", ctx)
        for title, width in COLUMNS:
            c = cols.createColumn()
            c.Title, c.ColumnWidth = title, width
            c.Flexibility = 1 if title == "Text" else 0
            cols.addColumn(c)
        grid.ColumnModel = cols
        grid.GridDataModel = sm.createInstanceWithContext(
            "com.sun.star.awt.grid.DefaultGridDataModel", ctx)

        self._add("Edit", "details", 6, 168, 428, 58, MultiLine=True, ReadOnly=True,
                  VScroll=True, Text="")
        self._button("preview", "Preview", 6, 230, 60,
                     "Show the paragraph as it would look with the suggested style "
                     "(undone again with End preview)")
        self._button("adopt", "Adopt style", 70, 230, 62,
                     "Apply the suggested style and drop the differing direct formatting")
        self._button("group", "Apply to group", 136, 230, 86,
                     "Adopt the suggested style for every candidate in the same group")
        self._button("ignore", "Ignore", 226, 230, 50,
                     "Never suggest this candidate again (remembered in the document)")
        self._button("unignore", "Un-ignore all", 280, 230, 62)
        self._add("FixedText", "lblName", 6, 253, 58, 10, Label="New style name:")
        self._add("Edit", "name", 64, 250, 226, 14, Text="")
        self._button("create", "Create style & apply", 294, 250, 100,
                     "Create a style from this candidate (or its cluster), apply it, and "
                     "re-run the analysis so similar candidates can join it")
        self._add("FixedText", "status", 6, 278, 370, 10, Label="")
        self._button("close", "Close", 384, 274, 50)

        self.dlg.getControl("grid").addSelectionListener(self.listener)
        self.dlg.getControl("marks").addItemListener(self.listener)
        self.dlg.addTopWindowListener(self.listener)
        tk = sm.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        parent = self.doc.getCurrentController().getFrame().getContainerWindow()
        self.dlg.createPeer(tk, parent)
        # open beside the text (right-hand side of the document window) so
        # previews stay visible
        win, size = parent.getPosSize(), self.dlg.getPosSize()
        self.dlg.setPosSize(max(win.X, win.X + win.Width - size.Width - 24), win.Y + 90, 0, 0, 3)
        self.dlg.setVisible(True)

    # ------------------------------------------------------------ helpers
    def ctl(self, name):
        return self.dlg.getControl(name)

    def selected(self):
        rows = self.ctl("grid").getSelectedRows()
        if rows and rows[0] < len(self.sugs):
            return rows[0], self.sugs[rows[0]]
        return None, None

    def settings(self):
        return Settings(adopt=self.dm.getByName("threshold").Value / 100,
                        include_unused=bool(self.dm.getByName("unused").State))

    def status(self, text):
        self.dm.getByName("status").Label = text

    def end_preview(self):
        if self.preview:
            self.model.end_preview(self.preview)
            self.preview = None
            self.dm.getByName("preview").Label = "Preview"

    def _finding(self, s):
        if s.kind == SAME and (s.unit.style == s.style or
                               (s.unit.family == CHAR and not s.unit.style and
                                s.style == NO_CHAR_STYLE)):
            return "Redundant"
        return s.label

    # ------------------------------------------------------------ analysis
    @_guard
    def reanalyse(self, keep_row=None):
        self.end_preview()
        if self.marked:
            self.model.clear_marks()
            self.marked = False
        ignored = self.model.ignored()
        units = [u for u in self.model.collect_units() if u.key not in ignored]
        self.sugs = analyse(units, self.model.collect_styles(), self.settings())
        # Fill a fresh data model and swap it in: adding rows to the live model
        # in-process only repaints the first one.
        data = self.smgr.createInstanceWithContext(
            "com.sun.star.awt.grid.DefaultGridDataModel", self.ctx)
        for i, s in enumerate(self.sugs):
            text = " ".join(s.unit.text.split())
            data.addRow("", (self._finding(s),
                                  "Paragraph" if s.unit.family != CHAR else "Text",
                                  text if len(text) <= 70 else text[:67] + "…",
                                  s.unit.style or "—", s.style_display or "—",
                                  f"{s.similarity:.0%}"))
            data.updateRowToolTip(i, s.tooltip(compact=True))
        self.dm.getByName("grid").GridDataModel = data
        self.ctl("grid").getPeer().invalidate(1 | 4)  # InvalidateStyle CHILDREN | UPDATE
        if self.dm.getByName("marks").State and self.sugs:
            self.model.add_marks(self.sugs)
            self.marked = True
        counts = {k: sum(s.kind == k for s in self.sugs) for k in (SAME, SIMILAR, CLUSTER, UNIQUE)}
        clusters = len({s.group for s in self.sugs if s.kind == CLUSTER})
        self.status(f"{len(self.sugs)} candidates: {counts[SAME]} same, {counts[SIMILAR]} similar, "
                    f"{counts[CLUSTER]} in {clusters} possible new style(s), {counts[UNIQUE]} unique"
                    + (f"; {len(ignored)} ignored" if ignored else ""))
        if self.sugs:
            row = min(keep_row or 0, len(self.sugs) - 1)
            self.ctl("grid").selectRow(row)
            self.on_select()
        else:
            self.dm.getByName("details").Text = ("No manual formatting left to tidy up."
                                                 if not ignored else
                                                 "Everything remaining is ignored.")
            self._enable(None)

    def _enable(self, s):
        has_style = s is not None and s.style is not None
        for name, on in (("preview", has_style), ("adopt", has_style),
                         ("group", has_style and s.kind in (SAME, SIMILAR) and s.group_size > 1),
                         ("ignore", s is not None), ("create", s is not None)):
            self.dm.getByName(name).Enabled = on
        self.dm.getByName("group").Label = (f"Apply to all {s.group_size}"
                                            if s and s.group_size > 1 else "Apply to group")

    # ------------------------------------------------------------ events
    @_guard
    def on_select(self):
        self.end_preview()
        self.ctl("grid").getPeer().invalidate(1 | 4)  # repaint the old selection too
        row, s = self.selected()
        self._enable(s)
        if s is None:
            return
        self.model.select(s.unit)
        lines = [f"“{' '.join(s.unit.text.split())[:120]}”", "", s.tooltip()]
        if s.kind == CLUSTER:
            lines += ["", "Create a style from this cluster, then the analysis re-runs and the "
                          "other members can adopt it."]
        self.dm.getByName("details").Text = "\n".join(lines)
        self.dm.getByName("name").Text = s.new_style_name

    @_guard
    def on_toggle(self):
        self.reanalyse(self.selected()[0])

    def on_action(self, cmd):
        getattr(self, "do_" + cmd)()

    @_guard
    def do_analyse(self):
        self.reanalyse(self.selected()[0])

    @_guard
    def do_preview(self):
        row, s = self.selected()
        if self.preview:
            self.end_preview()
            self.status("Preview ended; document restored.")
        elif s and s.style:
            self.preview = self.model.begin_preview(s.unit, s.style)
            self.dm.getByName("preview").Label = "End preview"
            self.model.select(s.unit)
            self.status(f"Previewing '{s.style_display}'. Adopt to keep it, End preview to undo.")

    @_guard
    def do_adopt(self):
        row, s = self.selected()
        if not (s and s.style):
            return
        self.end_preview()
        with self.model.undo_context(f"Style Clusters: adopt '{s.style_display}'"):
            self.model.adopt(s.unit, s.style)
        self.reanalyse(row)

    @_guard
    def do_group(self):
        row, s = self.selected()
        if not (s and s.style):
            return
        self.end_preview()
        members = [m for m in self.sugs if m.group == s.group]
        with self.model.undo_context(f"Style Clusters: adopt '{s.style_display}' ×{len(members)}"):
            for m in members:
                self.model.adopt(m.unit, m.style)
        self.reanalyse(row)

    @_guard
    def do_ignore(self):
        row, s = self.selected()
        if s:
            self.end_preview()
            self.model.set_ignored(self.model.ignored() | {s.unit.key})
            self.reanalyse(row)

    @_guard
    def do_unignore(self):
        self.model.set_ignored(set())
        self.reanalyse(self.selected()[0])

    @_guard
    def do_create(self):
        row, s = self.selected()
        name = self.dm.getByName("name").Text.strip()
        if not (s and name):
            self.status("Enter a name for the new style.")
            return
        self.end_preview()
        with self.model.undo_context(f"Style Clusters: new style '{name}'"):
            self.model.create_style(s, name)
            self.model.adopt(s.unit, name)
        self.reanalyse(row)
        joined = sum(x.style == name and x.kind in (SAME, SIMILAR) for x in self.sugs)
        self.status(f"Created '{name}' and applied it. Re-analysed: {joined} more "
                    f"candidate(s) could adopt it." if joined else
                    f"Created '{name}' and applied it.")

    @_guard
    def do_close(self):
        self.close()

    def close(self):
        if self.dlg is None:
            return
        try:
            self.end_preview()
            if self.marked:
                self.model.clear_marks()
            self.doc.removeCloseListener(self.listener)
        except Exception:
            traceback.print_exc()
        _OPEN.pop(self.doc.RuntimeUID, None)
        dlg, self.dlg = self.dlg, None
        dlg.setVisible(False)
        dlg.dispose()
