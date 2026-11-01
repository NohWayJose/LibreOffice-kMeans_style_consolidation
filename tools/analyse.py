#!/usr/bin/env python3
"""Print the Style Clusters report for a document without opening the UI.

    python3 tools/analyse.py document.odt [--adopt 0.8] [--cluster 0.92] [--all-styles] [-v]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "extension", "pythonpath"))
sys.path.insert(0, HERE)

from lo_headless import Office  # noqa: E402
from styleclusters.analysis import Settings, analyse  # noqa: E402
from styleclusters.unodoc import DocModel  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("document")
    ap.add_argument("--adopt", type=float, default=Settings.adopt)
    ap.add_argument("--cluster", type=float, default=Settings.cluster)
    ap.add_argument("--all-styles", action="store_true", help="include unused built-in styles")
    ap.add_argument("-v", "--verbose", action="store_true", help="print tooltips")
    args = ap.parse_args()
    with Office() as office:
        doc = office.load(args.document)
        model = DocModel(doc)
        ignored = model.ignored()
        units = [u for u in model.collect_units() if u.key not in ignored]
        settings = Settings(adopt=args.adopt, cluster=args.cluster,
                            include_unused=args.all_styles)
        for s in analyse(units, model.collect_styles(), settings):
            fam = "¶" if s.unit.family == "para" else "a"
            text = s.unit.text.replace("\n", " ")[:38]
            print(f"{s.label:14} {fam} {text:40} {s.unit.style or '-':12} → "
                  f"{s.style_display or '-':22} {s.similarity:4.0%}  "
                  f"grp={s.group_size} new='{s.new_style_name}'")
            if args.verbose:
                print("    " + s.tooltip().replace("\n", "\n    "))
        doc.close(True)


if __name__ == "__main__":
    main()
