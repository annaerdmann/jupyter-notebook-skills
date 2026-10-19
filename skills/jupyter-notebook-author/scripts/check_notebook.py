#!/usr/bin/env python3
"""Static checks for an educational notebook: structure, style, writing, code hygiene.

Usage:
    python check_notebook.py NOTEBOOK.ipynb [--style style_profile.json] [--out report.md]

Exit code 1 if any ERROR finding, else 0. WARN findings need a look but may be fine.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import nbformat

HERE = Path(__file__).resolve().parent
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.M)

# Writing patterns from references/writing-rules.md. (pattern, message)
BANNED_WORDS = [
    "delve", "delves", "delving", "crucial", "pivotal", "tapestry", "realm", "foster", "fosters",
    "testament", "underscore", "underscores", "showcase", "showcases", "leverage", "leverages",
    "leveraging", "utilize", "utilise", "utilizes", "utilises", "seamless", "seamlessly",
    "cutting-edge", "state-of-the-art", "game-changing", "game-changer", "harness", "unlock",
    "empower", "embark", "journey", "comprehensive", "meticulous", "meticulously", "intricate",
    "myriad", "plethora", "notably", "essentially", "ultimately", "moreover", "furthermore",
    "simply", "easily", "obviously", "basically", "of course",
]
BANNED_PHRASES = [
    (r"\bit is (important|worth) (to note|noting)\b|\bit's (important|worth) (to note|noting)\b", "filler: 'it is important to note'"),
    (r"(?<!to )\bnote that\b", "filler: 'note that' (use a Note box if it matters)"),
    (r"\bin order to\b", "use 'to' instead of 'in order to'"),
    (r"\blet'?s\b", "filler opener 'let's': state what happens"),
    (r"\bwe will\b", "filler 'we will': state what happens"),
    (r"\bdive (in|into)\b|\bdeep dive\b", "filler 'dive into'"),
    (r"\bnot (just|only)\b[^.]{0,80}\b(but|it'?s)\b", "negative parallelism ('not just X but Y')"),
    (r"\b(may|might|could) (potentially|possibly|perhaps)\b", "stacked hedge"),
    (r"^\s*(in conclusion|overall|to sum up|in summary)\b", "closing recap opener"),
    (r",\s+(highlighting|underscoring|emphasi[sz]ing|ensuring|reflecting|showcasing)\b", "trailing participle evaluation"),
    (r"\bstudies (show|have shown)\b|\bexperts (say|agree)\b", "vague attribution without citation"),
    (r"!\s*$", "exclamation mark"),
]
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
SECRET_RE = re.compile(
    r"(password|passwd|api[_-]?key|secret|token)\s*[=:]\s*['\"][^'\"<>{}\s]{4,}['\"]", re.I
)


def src(cell):
    return cell.source if isinstance(cell.source, str) else "".join(cell.source)


def strip_code(md):
    """Remove code spans, code blocks, HTML tags and URLs before checking prose."""
    md = re.sub(r"```.*?```", " ", md, flags=re.S)
    md = re.sub(r"`[^`]*`", " ", md)
    md = re.sub(r"<[^>]+>", " ", md)
    md = re.sub(r"\(https?://[^)]+\)|https?://\S+", " ", md)
    return md


def sentences(text):
    text = re.sub(r"^\s*([-*]|\d+\.)\s+", "\n", text, flags=re.M)  # list items are separate units
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])|\n(?=\s*\n)|\n(?=[^\n]*$)|:\s*\n", text)
    parts = [q for p in parts for q in p.split("\n")] if "\n" in text else parts
    return [p.strip() for p in parts if len(p.split()) > 3]


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, where, msg):
        self.items.append((level, where, msg))

    def render(self, path):
        errs = sum(1 for i in self.items if i[0] == "ERROR")
        warns = sum(1 for i in self.items if i[0] == "WARN")
        out = [f"# Check report: `{Path(path).name}`", "", f"{errs} errors, {warns} warnings.", ""]
        for level in ("ERROR", "WARN", "INFO"):
            rows = [i for i in self.items if i[0] == level]
            if rows:
                out += [f"## {level}", ""]
                out += [f"- {w}: {m}" for _, w, m in rows]
                out.append("")
        return "\n".join(out)


def check(nb_path, style=None):
    nb = nbformat.read(nb_path, as_version=4)
    r = Report()
    cells = nb.cells
    lang = (nb.metadata.get("kernelspec", {}).get("language") or "").lower()
    is_r = lang == "r"

    # --- structure -------------------------------------------------------
    h1 = []
    prev_level = 0
    for i, c in enumerate(cells):
        if c.cell_type != "markdown":
            continue
        for m in HEADING_RE.finditer(src(c)):
            lvl = len(m.group(1))
            if lvl == 1:
                h1.append(i)
            if prev_level and lvl > prev_level + 1:
                r.add("WARN", f"cell {i}", f"heading level jumps from H{prev_level} to H{lvl}: '{m.group(2)[:50]}'")
            prev_level = lvl
    if len(h1) != 1:
        r.add("ERROR", "notebook", f"expected exactly one H1 title, found {len(h1)}")

    for i, c in enumerate(cells):
        if not src(c).strip():
            r.add("ERROR", f"cell {i}", "empty cell")

    # code cells preceded by markdown
    for i, c in enumerate(cells):
        if c.cell_type == "code" and i > 0 and cells[i - 1].cell_type == "code":
            r.add("WARN", f"cell {i}", "code cell without a Markdown cell before it (say what and why)")

    md_cells = [c for c in cells if c.cell_type == "markdown"]
    code_cells = [c for c in cells if c.cell_type == "code"]
    if code_cells:
        ratio = len(md_cells) / len(code_cells)
        if ratio < 1.5:
            r.add("WARN", "notebook", f"{ratio:.1f} Markdown cells per code cell; educational notebooks usually have 2–3")

    # --- code hygiene ----------------------------------------------------
    imp_re = r"^\s*(library|require)\(" if is_r else r"^\s*(import|from)\s+[\w.]+(\s+import|\s*$|\s+as)"
    import_idx = [
        k for k, c in enumerate(code_cells)
        if re.search(imp_re, src(c), re.M) and "except ImportError" not in src(c)
        and "requireNamespace" not in src(c)
    ]
    if len(import_idx) > 1 or (import_idx and import_idx[0] > 2):
        r.add("WARN", "code", f"imports spread over code cells {import_idx}; put all imports in one cell at the top")
    for k, c in enumerate(code_cells):
        lines = [ln for ln in src(c).splitlines() if ln.strip()]
        if len(lines) > 25 and not re.match(r"\s*(def |\w+\s*<-\s*function)", src(c)):
            r.add("WARN", f"code cell {k}", f"{len(lines)} lines; split into steps (max ~25)")
        if SECRET_RE.search(src(c)):
            r.add("ERROR", f"code cell {k}", "looks like a hard-coded credential")
        if re.search(r"warnings\.filterwarnings\(\s*['\"]ignore['\"]\s*\)\s*$", src(c), re.M):
            r.add("WARN", f"code cell {k}", "all warnings suppressed; suppress only a specific, explained warning")
        if re.search(r"cmap\s*=\s*['\"](jet|rainbow|hsv)['\"]", src(c)):
            r.add("WARN", f"code cell {k}", "rainbow colour map; use viridis/cividis or a diverging map")
        for o in c.get("outputs", []):
            if o.get("output_type") == "error":
                r.add("ERROR", f"code cell {k}", f"stored error output: {o.get('ename')}: {str(o.get('evalue'))[:80]}")
            text = "".join(o.get("text", "")) if isinstance(o.get("text"), list) else o.get("text", "")
            if text and SECRET_RE.search(text):
                r.add("ERROR", f"code cell {k}", "credential visible in output")

    # --- writing -----------------------------------------------------------
    word_re = re.compile(r"\b(" + "|".join(re.escape(w) for w in BANNED_WORDS) + r")\b", re.I)
    for i, c in enumerate(cells):
        if c.cell_type != "markdown":
            continue
        prose = strip_code(src(c))
        hits = sorted({m.group(1).lower() for m in word_re.finditer(prose)})
        if hits:
            r.add("WARN", f"cell {i}", f"banned words: {', '.join(hits)}")
        for pat, msg in BANNED_PHRASES:
            if re.search(pat, prose, re.I | re.M):
                r.add("WARN", f"cell {i}", msg)
        if prose.count("—") > 1:
            r.add("WARN", f"cell {i}", f"{prose.count('—')} em dashes; use at most one")
        if EMOJI_RE.search(prose):
            r.add("WARN", f"cell {i}", "emoji in text")
        for s in sentences(prose):
            n = len(s.split())
            if n > 30:
                r.add("WARN", f"cell {i}", f"long sentence ({n} words): '{s[:70]}…'")
        for m in re.finditer(r"!\[\s*\]\(", src(c)):
            r.add("WARN", f"cell {i}", "image without alt text")
        if re.search(r"\b(TODO|TBD|lorem ipsum|XXX)\b|<insert|\[insert", src(c), re.I):
            r.add("ERROR", f"cell {i}", "placeholder text left in the notebook")

    # --- style profile -----------------------------------------------------
    if style:
        p = json.loads(Path(style).read_text())
        head_text = "\n".join(src(c).lower() for c in cells[: max(12, len(p.get("header", [])) + 6)])
        checks = {
            "prerequisites": "prerequisite",
            "learning_outcomes": r"learning (outcome|objective)|you will (learn|know|be able)",
            "contents": r"\bcontents\b|outline",
            "licence": r"copyright|licen[cs]e",
            "badges": r"shields\.io|mybinder|colab",
        }
        for h in p.get("header", []):
            for kind in h["kinds"]:
                if kind in checks and not re.search(checks[kind], head_text):
                    r.add("ERROR", "header", f"style source has '{kind}' in the header; not found here")
                if kind == "image":
                    imgs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)|<img[^>]+src=[\"']([^\"']+)", h["text"])
                    if imgs and not any((a or b).lower() in head_text for a, b in imgs):
                        r.add("WARN", "header", "header image of the style source not found")
        tail = "\n".join(src(c) for c in cells[-4:])
        for f in p.get("footer", []):
            urls = set(re.findall(r"https?://[^\s)\]]+|mailto:[^\s)\]]+", f["text"]))
            missing_urls = [u for u in urls if u not in tail]
            if urls and missing_urls:
                r.add("WARN", "footer", f"footer links of the style source missing: {', '.join(sorted(missing_urls))}")
        missing = [k for k in p.get("metadata_keys", []) if k not in nb.metadata]
        if missing:
            r.add("WARN", "metadata", f"metadata fields missing: {', '.join(missing)}")
        empty = [k for k in p.get("metadata_keys", []) if k in nb.metadata and nb.metadata[k] in ("", None, {}, [])]
        if empty:
            r.add("INFO", "metadata", f"metadata fields empty: {', '.join(empty)} (list them in the hand-over)")
        if p.get("section_numbering", "").startswith("numbered"):
            lvl = "#" * p.get("section_level", 2)
            titles = [m.group(2) for c in md_cells for m in HEADING_RE.finditer(src(c)) if m.group(1) == lvl]
            unnumbered = [t for t in titles if not re.match(r"^\d+[.)]?\s", t)]
            if unnumbered:
                r.add("WARN", "sections", f"style numbers its sections; unnumbered: {', '.join(unnumbered[:5])}")
        for d in p.get("instruction_cells", []):
            snippet = d["text"][:50]
            if any(snippet in src(c) for c in md_cells):
                r.add("ERROR", "template", f"template instruction left in the notebook: '{snippet}…'")

    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("notebook")
    ap.add_argument("--style")
    ap.add_argument("--out")
    a = ap.parse_args()
    rep = check(a.notebook, a.style)
    text = rep.render(a.notebook)
    out = Path(a.out) if a.out else Path(a.notebook).with_suffix(".check_report.md")
    out.write_text(text)
    print(text)
    sys.exit(1 if any(i[0] == "ERROR" for i in rep.items) else 0)


if __name__ == "__main__":
    main()
