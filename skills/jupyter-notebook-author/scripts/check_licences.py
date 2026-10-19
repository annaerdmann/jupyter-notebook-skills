#!/usr/bin/env python3
"""Check that the licences of the packages a notebook uses are compatible with its licence.

Usage:
    python check_licences.py NOTEBOOK.ipynb --python-env PATH_TO_ENV_PYTHON [--target MIT]
    python check_licences.py NOTEBOOK.ipynb --rscript PATH_TO_ENV_RSCRIPT [--target MIT]

Reads each imported package's licence from the test environment (Python package
metadata, or R DESCRIPTION files) and classifies it. Exit code 1 if a package
needs a decision (copyleft or unknown licence) for the target licence.
This is a first check, not legal advice: report findings to the author.
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


def classify(lic):
    if lic is None:
        return "not installed"
    if STRONG_COPYLEFT.search(lic) and not WEAK_COPYLEFT.search(lic):
        return "strong copyleft"
    if WEAK_COPYLEFT.search(lic):
        return "weak copyleft"
    if PERMISSIVE.search(lic):
        return "permissive"
    return "unknown"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("notebook")
    ap.add_argument("--python-env")
    ap.add_argument("--rscript")
    ap.add_argument("--target", default="MIT")
    ap.add_argument("--out")
    a = ap.parse_args()

    nb = nbformat.read(a.notebook, as_version=4)
    lang = (nb.metadata.get("kernelspec", {}).get("language") or "python").lower()
    code = "\n".join(
        c.source if isinstance(c.source, str) else "".join(c.source)
        for c in nb.cells if c.cell_type == "code"
    )

    licences = {}
    if lang == "r":
        pkgs = sorted(set(re.findall(r"\b(?:library|require|requireNamespace)\(\s*['\"]?([\w.]+)", code)))
        rscript = a.rscript or "Rscript"
        res = subprocess.run([rscript, "-e", R_LICENCE, *pkgs], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if "\t" in line:
                p, lic = line.split("\t", 1)
                licences[p] = None if lic == "NOT_INSTALLED" else lic
    else:
        if not a.python_env:
            sys.exit("--python-env is required for Python notebooks")
        dists = sorted({PY_MAP.get(m, m) for m in python_imports(code)})
        res = subprocess.run([a.python_env, "-c", PY_LICENCE, *dists], capture_output=True, text=True)
        licences = json.loads(res.stdout or "{}")

    target_permissive = bool(PERMISSIVE.search(a.target)) and not STRONG_COPYLEFT.search(a.target)
    rows, needs_decision = [], []
    for pkg, lic in sorted(licences.items()):
        cls = classify(lic)
        note = ""
        if cls == "strong copyleft" and target_permissive:
            note = f"GPL-type: decide whether a {a.target} notebook may depend on it (importing is usually fine, copying its code into the notebook is not)"
            needs_decision.append(pkg)
        elif cls in ("unknown", "not installed"):
            note = "check the licence by hand"
            needs_decision.append(pkg)
        elif cls == "weak copyleft":
            note = "fine to use as a dependency; do not copy its code into the notebook"
        rows.append((pkg, lic or "-", cls, note))

    report = [
        f"# Licence check: `{Path(a.notebook).name}`", "",
        f"Target licence: **{a.target}**. Packages needing a decision: {len(needs_decision)}.", "",
        "| Package | Licence | Class | Note |", "|---|---|---|---|",
    ]
    report += [f"| {p} | {lic.replace('|', '/')} | {c} | {n} |" for p, lic, c, n in rows]
    report += ["", "Data licences (dataset terms of use, attribution) are not checked here; state them in the notebook."]
    text = "\n".join(report) + "\n"
    out = Path(a.out) if a.out else Path(a.notebook).with_suffix(".licence_report.md")
    out.write_text(text)
    print(text)
    sys.exit(1 if needs_decision else 0)


if __name__ == "__main__":
    main()
