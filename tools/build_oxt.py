#!/usr/bin/env python3
"""Package extension/ into dist/StyleClusters.oxt."""
import os
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "extension")
OUT = os.path.join(ROOT, "dist", "StyleClusters.oxt")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for base, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            path = os.path.join(base, f)
            z.write(path, os.path.relpath(path, SRC))
print(OUT)
