#!/usr/bin/env python3
"""Extract a style profile from a template or example Jupyter notebook.

Usage:
    python extract_style.py SOURCE.ipynb [--out style_profile.json]

Writes style_profile.json and style_profile.md (same name, .md). The result is
a heuristic summary; the assistant must review it against the source notebook.
"""

import argparse
import json
import re
import statistics
from pathlib import Path

import nbformat

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.M)
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)|<img[^>]+src=[\"']([^\"']+)", re.I)
INSTRUCTION_RE = re.compile(
    r"(this (block|section|cell|template) (is|should|can)|\[H[1-6]\]|should be removed|"
    r"please (add|insert|fill|replace|revisit)|insert here|to be discussed|todo)",
    re.I,
)


def source(cell):
    return cell.source if isinstance(cell.source, str) else "".join(cell.source)


def is_italic_only(text):
    """True if every non-empty line is wrapped in *...* or _..._ (author guidance)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False
    italic = sum(
        1 for ln in lines
        if re.match(r"^[-*\d.\s]*[*_][^*_].*[*_]$", ln) or ln.startswith("- *")
    )
    return italic / len(lines) >= 0.8


def classify_header_cell(text):
    t = text.strip()
    low = t.lower()
    kinds = []
    if IMG_RE.search(t) and len(re.sub(IMG_RE, "", t).strip()) < 40:
        kinds.append("image")
    if re.search(r"copyright|licen[cs]e:|spdx", low):
        kinds.append("licence")
    if re.search(r"^#\s", t, re.M):
        kinds.append("title")
    if "shields.io" in low or "mybinder.org/badge" in low or "colab-badge" in low:
        kinds.append("badges")
    if re.search(r"<<|&lt;&lt;|previous|next notebook|index\]|index</a>", low) and "href" in low:
        kinds.append("navigation")
    if "prerequisite" in low:
        kinds.append("prerequisites")
    if re.search(r"learning (outcome|objective)|you will (learn|know|be able)", low):
        kinds.append("learning_outcomes")
    if re.search(r"\bcontents\b|table of contents|\boutline\b", low):
        kinds.append("contents")
    if re.fullmatch(r"(<hr\s*/?>|---|\*\*\*)", t, re.I):
        kinds.append("separator")
    return kinds or ["text"]


def heading_case(titles):
    words_title, words_total = 0, 0
    for t in titles:
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]*", t)[1:] if len(w) > 3]
        words_total += len(words)
        words_title += sum(1 for w in words if w[0].isupper() and not w.isupper())
    if not words_total:
        return "unknown"
    return "title" if words_title / words_total > 0.5 else "sentence"


def box_styles(md_texts):
    styles = {}
    for t in md_texts:
        for m in re.finditer(r"<div[^>]*>", t, re.I):
            tag = m.group(0)
            if "alert" in tag:
                cls = re.search(r"class=[\"']([^\"']+)", tag)
                styles.setdefault("bootstrap_alert", set()).add(cls.group(1) if cls else tag)
            elif "style=" in tag and ("border" in tag or "background" in tag):
                label = re.search(r"<b>([^<]+)</b>", t[m.end(): m.end() + 200])
                key = label.group(1).strip(": ") if label else "box"
                styles.setdefault("html_div", {})[key] = tag
        if re.search(r"^:::\{?\w+\}?|^```\{(note|warning|tip|admonition)", t, re.M):
            styles.setdefault("myst_admonition", set()).add(
                re.search(r"\{?(\w+)\}?", t.split(":::")[1] if ":::" in t else t).group(1)
            )
        if re.search(r"^>\s*\*\*(note|warning|tip)", t, re.I | re.M):
            styles.setdefault("blockquote", set()).add("> **Note:** …")
    return {k: (sorted(v) if isinstance(v, set) else v) for k, v in styles.items()}


def code_conventions(code_cells, language):
    texts = [source(c) for c in code_cells]
    joined = "\n".join(texts)
    conv = {}
    if language.lower().startswith("python"):
        conv["install_pattern"] = (
            "try/except ImportError + %pip install" if re.search(r"except ImportError", joined)
            else "%pip install" if "%pip install" in joined
            else "!pip install" if "!pip install" in joined
            else "none"
        )
        import_cells = [
            i for i, t in enumerate(texts)
            if re.search(r"^\s*(import|from)\s+\w", t, re.M) and "except ImportError" not in t
        ]
    else:
        conv["install_pattern"] = "install.packages" if "install.packages" in joined else "none"
        import_cells = [i for i, t in enumerate(texts) if re.search(r"^\s*(library|require)\(", t, re.M)]
    conv["import_cell_indices"] = import_cells
    conv["imports_in_one_early_cell"] = bool(import_cells) and len(import_cells) == 1 and import_cells[0] <= 2
    lines = [len([ln for ln in t.splitlines() if ln.strip()]) for t in texts if t.strip()]
    conv["mean_code_lines"] = round(statistics.mean(lines), 1) if lines else 0
    conv["max_code_lines"] = max(lines) if lines else 0
    conv["uses_getpass"] = "getpass" in joined
    conv["parameters_tag"] = any("parameters" in c.get("metadata", {}).get("tags", []) for c in code_cells)
    return conv


def extract(path):
    nb = nbformat.read(path, as_version=4)
    cells = nb.cells
    language = (
        nb.metadata.get("kernelspec", {}).get("language")
        or nb.metadata.get("language_info", {}).get("name", "unknown")
    )

    # first H2 (or H1 if the notebook has no H2) marks the end of the header block
    def level_of(cell):
        if cell.cell_type != "markdown":
            return None
        m = HEADING_RE.search(source(cell))
        return len(m.group(1)) if m else None

    levels = [level_of(c) for c in cells]
    section_level = 2 if 2 in levels else 1
    first_section = next((i for i, lv in enumerate(levels) if lv == section_level), len(cells))
    if section_level == 1:  # skip the title
        first_section = next((i for i, lv in enumerate(levels) if lv == 1 and i > first_section), len(cells))

    instruction_cells, header = [], []
    for i, c in enumerate(cells):
        if c.cell_type == "markdown":
            t = source(c)
            if is_italic_only(t) or (INSTRUCTION_RE.search(t) and len(t) < 1500 and is_italic_only(t.split("\n\n")[0])):
                instruction_cells.append({"index": i, "text": t.strip()[:300]})
    instr_idx = {d["index"] for d in instruction_cells}

    for i in range(first_section):
        c = cells[i]
        if i in instr_idx or c.cell_type != "markdown":
            continue
        t = source(c)
        header.append({"index": i, "kinds": classify_header_cell(t), "text": t.strip()[:400]})

    sections = []
    for i, c in enumerate(cells):
        if c.cell_type == "markdown" and i not in instr_idx:
            for m in HEADING_RE.finditer(source(c)):
                lvl = len(m.group(1))
                if lvl <= section_level + 1 and i >= first_section:
                    sections.append({"index": i, "level": lvl, "title": m.group(2).strip()})
    main_titles = [s["title"] for s in sections if s["level"] == section_level]
    numbering = "numbered (e.g. '1. Title')" if main_titles and sum(
        bool(re.match(r"^\d+[.)]?\s", t)) for t in main_titles) >= len(main_titles) / 2 else "unnumbered"

    # footer: markdown cells after the last code cell that are not headings-only
    last_code = max((i for i, c in enumerate(cells) if c.cell_type == "code"), default=-1)
    last_section = max((s["index"] for s in sections if s["level"] == section_level), default=-1)
    footer = []
    for i in range(max(last_code, last_section) + 1, len(cells)):
        t = source(cells[i])
        if i in instr_idx or not t.strip():
            continue
        if re.search(r"https?://", t) and len(t) < 800 and not HEADING_RE.search(t):
            footer.append({"index": i, "text": t.strip()[:400]})

    md = [c for i, c in enumerate(cells) if c.cell_type == "markdown" and i not in instr_idx]
    code = [c for c in cells if c.cell_type == "code"]
    words = sum(len(re.findall(r"\w+", source(c))) for c in md)

    def blank(v):
        if isinstance(v, dict):
            return {k: blank(x) for k, x in v.items()}
        if isinstance(v, list):
            return []
        return ""

    meta = {k: v for k, v in nb.metadata.items() if k not in ("kernelspec", "language_info", "vscode", "widgets")}

    return {
        "source": str(path),
        "language": language,
        "kernel": nb.metadata.get("kernelspec", {}).get("name"),
        "header": header,
        "section_level": section_level,
        "section_numbering": numbering,
        "sections": sections,
        "heading_case": heading_case([s["title"] for s in sections]),
        "boxes": box_styles([source(c) for c in md]),
        "footer": footer,
        "images": sorted({(m.group(1) or m.group(2)) for c in md for m in IMG_RE.finditer(source(c))}),
        "metadata_keys": sorted(meta.keys()),
        "metadata_template": blank(meta),
        "instruction_cells": instruction_cells,
        "code": code_conventions(code, language),
        "ratio": {
            "markdown_cells": len(md),
            "code_cells": len(code),
            "markdown_per_code": round(len(md) / len(code), 2) if code else None,
            "words": words,
        },
        "outputs_kept": any(c.get("outputs") for c in code),
    }


def to_markdown(p):
    out = [f"# Style profile: `{Path(p['source']).name}`", ""]
    out.append(f"- **Language / kernel:** {p['language']} / {p['kernel']}")
    out.append("- **Header (in order):** " + " → ".join("+".join(h["kinds"]) for h in p["header"]))
    out.append(f"- **Sections:** level H{p['section_level']}, {p['section_numbering']}, {p['heading_case']} case")
    for s in p["sections"]:
        out.append(f"  - {'  ' * (s['level'] - p['section_level'])}{s['title']}")
    out.append(f"- **Boxes:** {', '.join(p['boxes']) or 'none found'}")
    out.append(f"- **Footer cells:** {len(p['footer'])}")
    out.append(f"- **Images:** {', '.join(p['images']) or 'none'}")
    out.append(f"- **Notebook metadata fields:** {', '.join(p['metadata_keys']) or 'none'}")
    c = p["code"]
    out.append(
        f"- **Code:** install pattern {c['install_pattern']}; imports in one early cell: "
        f"{c['imports_in_one_early_cell']}; mean {c['mean_code_lines']} lines per code cell (max {c['max_code_lines']})"
    )
    r = p["ratio"]
    out.append(
        f"- **Text:** {r['markdown_cells']} Markdown / {r['code_cells']} code cells "
        f"({r['markdown_per_code']} per code cell), {r['words']} words"
    )
    out.append(f"- **Outputs kept in source:** {p['outputs_kept']}")
    if p["instruction_cells"]:
        out += ["", f"## Template instructions ({len(p['instruction_cells'])} cells, not copied; apply their rules)", ""]
        for d in p["instruction_cells"]:
            out.append(f"- [{d['index']}] " + d["text"].replace("\n", " ")[:200])
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source")
    ap.add_argument("--out", default="style_profile.json")
    a = ap.parse_args()
    profile = extract(a.source)
    out = Path(a.out)
    out.write_text(json.dumps(profile, indent=2, ensure_ascii=False))
    out.with_suffix(".md").write_text(to_markdown(profile))
    print(to_markdown(profile))


if __name__ == "__main__":
    main()
