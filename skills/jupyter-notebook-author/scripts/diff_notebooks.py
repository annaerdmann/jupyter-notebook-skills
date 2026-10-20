#!/usr/bin/env python3
"""Cell-level diff between two versions of a notebook (outputs ignored).

Usage:
    python diff_notebooks.py ORIGINAL.ipynb EDITED.ipynb [--out diff.md] [--threshold 0.5]

Use it for the author's edited version of your notebook, or for your own
round N and round N+1 after written feedback (references/feedback-loop.md).

Inside each changed block, cells are paired by content (best similarity of at
least --threshold, same cell type), not by position. The report lists:
- changed cells, with a unified diff;
- moved cells (same content at another place), and moved and changed cells;
- merged cells (an old cell whose text now sits inside a new cell);
- added and removed cells.
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


def first_line(c):
    s = src(c).strip()
    return s.splitlines()[0].split(". ")[0] if s else ""


def similarity(a, b):
    return difflib.SequenceMatcher(a=src(a), b=src(b), autojunk=False).ratio()


def contained(part, whole):
    """Share of `part` that appears in `whole` (to detect merged cells)."""
    p, w = src(part).strip(), src(whole)
    if not p:
        return 0.0
    sm = difflib.SequenceMatcher(a=p, b=w, autojunk=False)
    return sum(b.size for b in sm.get_matching_blocks()) / len(p)


def compare(o, e, threshold=0.5):
    """Return lists of (kind, old_index, new_index, ratio)."""
    sm = difflib.SequenceMatcher(a=[key(c) for c in o], b=[key(c) for c in e], autojunk=False)
    blocks = [(i1, i2, j1, j2) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]
    removed = {i for i1, i2, _, _ in blocks for i in range(i1, i2)}
    added = {j for _, _, j1, j2 in blocks for j in range(j1, j2)}
    result = []

    # moves: identical content elsewhere
    for i in sorted(removed):
        match = next((j for j in sorted(added) if key(e[j]) == key(o[i])), None)
        if match is not None:
            result.append(("moved", i, match, 1.0))
            removed.discard(i)
            added.discard(match)

    # pair by similarity inside each changed block
    for i1, i2, j1, j2 in blocks:
        pairs = sorted(
            ((similarity(o[i], e[j]), i, j) for i in range(i1, i2) if i in removed
             for j in range(j1, j2) if j in added and o[i].cell_type == e[j].cell_type),
            reverse=True,
        )
        for ratio, i, j in pairs:
            if ratio >= threshold and i in removed and j in added:
                result.append(("changed", i, j, ratio))
                removed.discard(i)
                added.discard(j)

    # moved and changed: leftovers that match a cell in another block
    pairs = sorted(
        ((similarity(o[i], e[j]), i, j) for i in removed for j in added if o[i].cell_type == e[j].cell_type),
        reverse=True,
    )
    for ratio, i, j in pairs:
        same_start = first_line(o[i]) == first_line(e[j]) and len(first_line(o[i])) >= 20
        if (ratio >= max(threshold, 0.6) or same_start) and i in removed and j in added:
            near = any(i1 <= i < i2 and j1 <= j < j2 for i1, i2, j1, j2 in blocks)
            result.append(("changed" if near else "moved and changed", i, j, ratio))
            removed.discard(i)
            added.discard(j)

    # merges: an old cell whose text is now inside a new or changed cell nearby
    new_of_block = {}
    for i1, i2, j1, j2 in blocks:
        for i in range(i1, i2):
            new_of_block[i] = range(max(0, j1 - 1), min(len(e), j2 + 1))
    for i in sorted(removed):
        best = max(((contained(o[i], e[j]), j) for j in new_of_block.get(i, [])
                    if e[j].cell_type == o[i].cell_type), default=(0, None))
        if best[0] >= 0.8:
            j = best[1]
            if j in added:  # the new cell has no other origin: it is this cell, changed
                result.append(("changed", i, j, similarity(o[i], e[j])))
                added.discard(j)
            else:
                result.append(("merged", i, j, best[0]))
            removed.discard(i)

    result += [("removed", i, None, 0) for i in sorted(removed)]
    result += [("added", None, j, 0) for j in sorted(added)]
    return sorted(result, key=lambda r: (r[2] if r[2] is not None else r[1] or 0, r[1] or 0))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("original")
    ap.add_argument("edited")
    ap.add_argument("--out")
    ap.add_argument("--threshold", type=float, default=0.5, help="minimum similarity to pair two cells")
    a = ap.parse_args()
    o = nbformat.read(a.original, as_version=4).cells
    e = nbformat.read(a.edited, as_version=4).cells

    rows = compare(o, e, a.threshold)
    stats = {k: sum(1 for r in rows if r[0] == k) for k in ("changed", "moved", "moved and changed", "merged", "added", "removed")}
    out = [f"# Diff: `{Path(a.original).name}` → `{Path(a.edited).name}`", "",
           f"{len(o)} → {len(e)} cells: " + ", ".join(f"{v} {k}" for k, v in stats.items()) + ".", ""]
    for kind, i, j, ratio in rows:
        if kind in ("changed", "moved and changed"):
            out += [f"## {kind.capitalize()}: {label(o[i], i)} → cell {j} (similarity {ratio:.0%})", "", "```diff"]
            out += list(difflib.unified_diff(src(o[i]).splitlines(), src(e[j]).splitlines(), lineterm="", n=1))[2:]
            out += ["```", ""]
        elif kind == "moved":
            out += [f"## Moved: {label(o[i], i)} → cell {j}", ""]
        elif kind == "merged":
            out += [f"## Merged: {label(o[i], i)} → into cell {j} ({ratio:.0%} of its text)", ""]
        elif kind == "removed":
            out += [f"## Removed: {label(o[i], i)}", "", "```", src(o[i]), "```", ""]
        else:
            out += [f"## Added: {label(e[j], j)}", "", "```", src(e[j]), "```", ""]
    text = "\n".join(out)
    if a.out:
        Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
