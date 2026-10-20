#!/usr/bin/env python3
"""Check that the licences of the packages a notebook uses are compatible with its licence.

Usage:
    python check_licences.py NOTEBOOK.ipynb --python-env PATH_TO_ENV_PYTHON --target LICENCE
    python check_licences.py NOTEBOOK.ipynb --rscript PATH_TO_ENV_RSCRIPT --target LICENCE

    options: [--decisions licence-decisions.md] [--extra pkg1,pkg2] [--out REPORT.md] [--force]

LICENCE is the licence the author chose at intake (for example MIT). It is required.

Reads each imported package's licence from the test environment (Python package
metadata, or R DESCRIPTION files) and classifies it. A dual licence ("GPL | MIT",
"MIT OR Apache-2.0") counts as its most permissive alternative.

Decisions the author stated are read from a Markdown table, by default
`licence-decisions.md` next to the notebook:

    | package | decision | decided by (role) | date | note |
    |---|---|---|---|---|
    | ncdf4 | accepted | notebook owner | 2026-10-19 | import only |

decision is `accepted` or `rejected`. Write a row only when the author said so
for this notebook; the script never infers a decision.

Exit code 1 if a package still needs a decision (copyleft or unknown licence
without an accepted row, or a rejected package that is still used).
The report keeps everything below the line `<!-- written by hand -->` when it
is rewritten. This is a first check, not legal advice: report findings to the author.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import nbformat

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_env import PY_MAP, python_imports  # noqa: E402

PERMISSIVE = re.compile(
    r"\b(MIT|BSD|Apache|ISC|PSF|Python Software Foundation|Unlicense|CC0|Zlib|HPND|MPL|Mozilla|"
    r"Public Domain|0BSD|Artistic)\b", re.I
)
WEAK_COPYLEFT = re.compile(r"\b(LGPL|Lesser General Public|EPL|Eclipse|CDDL)\b", re.I)
STRONG_COPYLEFT = re.compile(r"\b(AGPL|Affero|GPL|General Public License)\b", re.I)

PY_LICENCE = r"""
import importlib.metadata as m, json, sys
out = {}
for dist in sys.argv[1:]:
    try:
        md = m.metadata(dist)
    except Exception:
        out[dist] = None
        continue
    classifiers = [c.split("::")[-1].strip() for c in md.get_all("Classifier") or [] if c.startswith("License")]
    expr = md.get("License-Expression") or ""
    lic = md.get("License") or ""
    if len(lic) > 120:  # full licence text pasted into the field
        lic = lic.splitlines()[0][:120]
    out[dist] = expr or "; ".join(classifiers) or lic or "UNKNOWN"
print(json.dumps(out))
"""

R_LICENCE = r"""
args <- commandArgs(trailingOnly = TRUE)
for (p in args) {
  d <- tryCatch(packageDescription(p)$License, error = function(e) NA)
  cat(p, "\t", ifelse(is.null(d) || is.na(d), "NOT_INSTALLED", d), "\n", sep = "")
}
"""


RANK = {"permissive": 0, "weak copyleft": 1, "strong copyleft": 2, "unknown": 3}
KEEP_MARK = "<!-- written by hand -->"


def classify_one(lic):
    if STRONG_COPYLEFT.search(lic) and not WEAK_COPYLEFT.search(lic):
        return "strong copyleft"
    if WEAK_COPYLEFT.search(lic):
        return "weak copyleft"
    if PERMISSIVE.search(lic):
        return "permissive"
    return "unknown"


def classify(lic):
    """Classify a licence string; a dual licence takes its most permissive alternative."""
    if lic is None:
        return "not installed"
    parts = [p for p in re.split(r"\s*\|\s*|\s+OR\s+|\s*;\s*", lic) if p.strip()]
    if len(parts) <= 1:
        return classify_one(lic)
    return min((classify_one(p) for p in parts), key=RANK.get)


def r_packages(code):
    pkgs = set(re.findall(r"\b(?:library|require|requireNamespace)\(\s*['\"]?([\w.]+)", code))
    pkgs |= set(re.findall(r"\b([A-Za-z][\w.]*):::?[A-Za-z.]", code))
    return sorted(pkgs - {"base", "stats", "utils", "graphics", "grDevices", "methods", "datasets", "tools", "grid", "parallel"})


def read_decisions(path):
    """Read the decisions table: {package: (decision, by, date, note)}."""
    out = {}
    if not path or not Path(path).exists():
        return out
    for line in Path(path).read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not line.strip().startswith("|"):
            continue
        if cells[0].lower() in ("package", "") or set(cells[0]) <= set("-: "):
            continue
        cells += [""] * (5 - len(cells))
        out[cells[0].strip("`")] = (cells[1].lower(), cells[2], cells[3], cells[4])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("notebook")
    ap.add_argument("--python-env")
    ap.add_argument("--rscript")
    ap.add_argument("--target", required=True, help="licence the author chose at intake, e.g. MIT")
    ap.add_argument("--decisions", help="Markdown table of the author's decisions (default: licence-decisions.md next to the notebook)")
    ap.add_argument("--extra", default="", help="comma-separated packages the notebook needs but does not import")
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true", help="allow --out outside the notebook folder and the current folder")
    a = ap.parse_args()

    nb_dir = Path(a.notebook).resolve().parent
    out = Path(a.out) if a.out else Path(a.notebook).with_suffix(".licence_report.md")
    allowed = [nb_dir, Path.cwd().resolve()]
    if not a.force and not any(out.resolve().is_relative_to(d) for d in allowed):
        sys.exit(f"refusing to write {out}: outside the notebook folder and the current folder (use --force)")
    decisions_path = a.decisions or nb_dir / "licence-decisions.md"
    decisions = read_decisions(decisions_path)
    extra = [x.strip() for x in a.extra.split(",") if x.strip()]

    nb = nbformat.read(a.notebook, as_version=4)
    lang = (nb.metadata.get("kernelspec", {}).get("language") or "python").lower()
    code = "\n".join(
        c.source if isinstance(c.source, str) else "".join(c.source)
        for c in nb.cells if c.cell_type == "code"
    )

    licences = {}
    if lang == "r":
        pkgs = sorted(set(r_packages(code)) | set(extra))
        rscript = a.rscript or "Rscript"
        res = subprocess.run([rscript, "-e", R_LICENCE, *pkgs], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if "\t" in line:
                p, lic = line.split("\t", 1)
                licences[p] = None if lic == "NOT_INSTALLED" else lic
    else:
        if not a.python_env:
            sys.exit("--python-env is required for Python notebooks")
        dists = sorted({PY_MAP.get(m, m) for m in python_imports(code)} | set(extra))
        res = subprocess.run([a.python_env, "-c", PY_LICENCE, *dists], capture_output=True, text=True)
        licences = json.loads(res.stdout or "{}")

    target_permissive = bool(PERMISSIVE.search(a.target)) and not STRONG_COPYLEFT.search(a.target)
    rows, needs_decision = [], []
    for pkg, lic in sorted(licences.items()):
        cls = classify(lic)
        note, status = "", "ok"
        if cls == "strong copyleft" and target_permissive:
            note = f"GPL-type: decide whether a {a.target} notebook may depend on it (importing is usually fine, copying its code into the notebook is not)"
            status = "needs decision"
        elif cls in ("unknown", "not installed"):
            note = "check the licence by hand"
            status = "needs decision"
        elif cls == "weak copyleft":
            note = "fine to use as a dependency; do not copy its code into the notebook"
        d = decisions.get(pkg)
        if d and status == "needs decision":
            decision, by, date, dnote = d
            if decision == "accepted":
                status = f"decided: accepted ({by or 'role not given'}, {date or 'no date'})"
            elif decision == "rejected":
                status = f"decided: rejected ({by or 'role not given'}, {date or 'no date'}); still used, replace it"
            else:
                status = f"decision '{decision}' not understood (use accepted or rejected)"
            if dnote:
                note = f"{note}. Author note: {dnote}" if note else f"Author note: {dnote}"
        if status == "needs decision" or status.startswith(("decided: rejected", "decision '")):
            needs_decision.append(pkg)
        rows.append((pkg, lic or "-", cls, status, note))

    report = [
        f"# Licence check: `{Path(a.notebook).name}`", "",
        f"Target licence: **{a.target}**. Packages needing a decision: {len(needs_decision)}.",
        f"Decisions read from: `{decisions_path if decisions else 'none'}`.", "",
        "| Package | Licence | Class | Status | Note |", "|---|---|---|---|---|",
    ]
    report += [f"| {p} | {lic.replace('|', '/')} | {c} | {s} | {n} |" for p, lic, c, s, n in rows]
    unused = sorted(set(decisions) - set(licences))
    if unused:
        report += ["", f"Decisions for packages the notebook does not use: {', '.join(unused)}."]
    report += ["", "Data licences (dataset terms of use, attribution) are not checked here; state them in the notebook."]
    kept = ""
    if out.exists() and KEEP_MARK in out.read_text():
        kept = out.read_text().split(KEEP_MARK, 1)[1]
    report += ["", KEEP_MARK]
    text = "\n".join(report) + (kept if kept else "\n")
    out.write_text(text)
    print(text)
    sys.exit(1 if needs_decision else 0)


if __name__ == "__main__":
    main()
