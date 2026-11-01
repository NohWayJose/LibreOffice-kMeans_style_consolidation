# Style Clusters — LibreOffice Writer extension

Finds manual (direct) formatting in a Writer document and uses **k-means cluster
analysis** to decide, for each manually formatted paragraph or text run, whether it:

| Finding | Meaning | Typical action |
|---|---|---|
| **Redundant** / **Same as style** | Looks identical to an existing style | Adopt it — nothing visible changes |
| **Similar** | Within the similarity threshold of a style | Preview, then adopt (or ignore) |
| **New style?** | Several candidates share the same manual look and no style matches | Create a style from the cluster; the analysis re-runs and the other members join it |
| **Unique** | A one-off that matches nothing | Create a style, adopt the nearest anyway, or ignore |

## Install

```sh
python3 tools/build_oxt.py               # -> dist/StyleClusters.oxt
unopkg add dist/StyleClusters.oxt        # or Tools ▸ Extension Manager ▸ Add…
```

Restart LibreOffice, open a Writer document, choose **Tools ▸ Style Clusters…**.

## The dialog

* **Grid** — one row per candidate. *Hover a row* for a tooltip listing every
  attribute that differs from the suggested style (`Font size: 15 pt → 14 pt; …`).
  Selecting a row selects the text in the document; the pane below shows the full
  difference list.
* **Preview** — applies the style *in the document* as one undo step so you see the
  real result; **End preview** (or picking another row) undoes it.
* **Adopt style** — sets the style and removes the differing direct formatting.
  Character spans inside the paragraph (e.g. a bold word) are preserved.
* **Apply to all N** — adopt for every candidate the algorithm grouped with this one.
* **Create style & apply** — creates a paragraph or character style from the
  candidate (for a *New style?* cluster, from its most central member), parented on
  the current style, applies it and re-runs the analysis so others can adopt it.
* **Ignore** — never suggest this candidate again. Stored in the document's custom
  properties (`StyleClustersIgnored`), so it survives saving. **Un-ignore all** resets.
* **Mark candidates in document** — adds a range comment by *Style Clusters* to each
  candidate (highlight + differences in the margin). Removed when unticked or the
  dialog closes.
* **Adopt if ≥ N % similar** and **Include unused built-in styles** tune the analysis;
  press **Re-analyse**.

Every action is a single named undo step (`Style Clusters: adopt 'Heading 1'`).

## How the analysis works

1. **Candidates.** Paragraphs with paragraph-level direct formatting, and runs of text
   whose portions carry direct character formatting (adjacent identical portions are
   merged). Body text and tables are scanned.
2. **Features.** Each candidate's *effective* formatting becomes a weighted vector
   (`extension/pythonpath/styleclusters/attributes.py`): alignment, indents, spacing,
   line spacing, background, borders, keep-with-next, font, size, weight, italic,
   colour, underline, strikethrough, case, letter spacing, highlight. Categorical values
   are one-hot encoded, colours as RGB, so a full mismatch on any attribute costs
   exactly its weight.
3. **Anchored k-means** (`kmeans.py`). Every existing style is a **fixed centroid**
   (for character runs: the surrounding paragraph overlaid with the character style).
   A candidate may join a style only if it is at least *adopt%* similar. On top of the
   fixed centroids, *k* free centroids are fitted with k-means++ seeding (biased
   towards points no style explains) and Lloyd iterations; *k* is the smallest value
   for which every candidate is ≥ 92 % similar to its centroid.
4. **Interpretation** (`analysis.py`). Candidates on a style centroid are *Same* or
   *Similar*. Free clusters with ≥ 2 members are *New style?* clusters; smaller ones
   dissolve back to their best acceptable style (*Similar*) or are *Unique*.
   Creating a style adds a new fixed centroid, so on the re-run the cluster's other
   members fall onto it.

Similarity is `1 − Σ weightᵢ·min(1, differenceᵢ) / Σ weightᵢ`.

## Development

```sh
python3 -m unittest discover tests        # core tests + headless-LibreOffice integration tests
python3 tools/analyse.py some.odt -v      # the report without the UI (needs pyuno)
python3 tools/make_sample_doc.py out.odt  # regenerate the 80/20 sample document
```

The core (`attributes.py`, `kmeans.py`, `analysis.py`) has no UNO dependency.
`unodoc.py` talks to the document and works in-process or over a UNO bridge;
`dialog.py` is the UI; `StyleClusters.py` is the menu's UNO component. Tests and tools
start a private headless LibreOffice with its own profile, so they never touch a
running office.

## Limitations

* Headers/footers, frames, footnotes and text boxes are not scanned yet.
* Only the attributes listed above are compared and reset; other direct formatting
  (e.g. hyphenation, tab stops) is left alone when adopting.
* Similarity thresholds are global; per-attribute weights live in `attributes.py`.
