#!/usr/bin/env python3
"""Cell-level diff between the notebook the assistant created and the author's edited version.

Usage:
    python diff_notebooks.py ORIGINAL.ipynb EDITED.ipynb [--out diff.md]

Lists added, removed and changed cells (outputs ignored) with a unified diff
per changed cell. Use the report to propose general rules (references/feedback-loop.md).
"""

import argparse
import difflib
from pathlib import Path

import nbformat


def src(c):
    return c.source if isinstance(c.source, str) else "".join(c.source)


def key(c):
    return f"{c.cell_type}:{src(c).strip()}"


def label(c, i):
    first = src(c).strip().splitlines()[0][:70] if src(c).strip() else "(empty)"
    return f"{c.cell_type} cell {i}: `{first}`"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("original")
    ap.add_argument("edited")
    ap.add_argument("--out")
    a = ap.parse_args()
    o = nbformat.read(a.original, as_version=4).cells
    e = nbformat.read(a.edited, as_version=4).cells

    sm = difflib.SequenceMatcher(a=[key(c) for c in o], b=[key(c) for c in e], autojunk=False)
    out = [f"# Diff: `{Path(a.original).name}` → `{Path(a.edited).name}`", ""]
    stats = {"added": 0, "removed": 0, "changed": 0}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            # pair cells one to one where possible, the rest are added/removed
            for k in range(max(i2 - i1, j2 - j1)):
                oc = o[i1 + k] if i1 + k < i2 else None
                ec = e[j1 + k] if j1 + k < j2 else None
                if oc is not None and ec is not None:
                    stats["changed"] += 1
                    ratio = difflib.SequenceMatcher(a=src(oc), b=src(ec)).ratio()
                    out += [f"## Changed: {label(oc, i1 + k)} → cell {j1 + k} (similarity {ratio:.0%})", "", "```diff"]
                    out += list(difflib.unified_diff(src(oc).splitlines(), src(ec).splitlines(), lineterm="", n=1))[2:]
                    out += ["```", ""]
                elif oc is not None:
                    stats["removed"] += 1
                    out += [f"## Removed: {label(oc, i1 + k)}", "", "```", src(oc), "```", ""]
                else:
                    stats["added"] += 1
                    out += [f"## Added: {label(ec, j1 + k)}", "", "```", src(ec), "```", ""]
        elif tag == "delete":
            for k in range(i1, i2):
                stats["removed"] += 1
                out += [f"## Removed: {label(o[k], k)}", "", "```", src(o[k]), "```", ""]
        elif tag == "insert":
            for k in range(j1, j2):
                stats["added"] += 1
                out += [f"## Added: {label(e[k], k)}", "", "```", src(e[k]), "```", ""]
    out.insert(2, f"{stats['changed']} changed, {stats['added']} added, {stats['removed']} removed cells.\n")
    text = "\n".join(out)
    if a.out:
        Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
