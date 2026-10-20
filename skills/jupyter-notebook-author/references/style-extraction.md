# Style extraction

The style of a notebook is everything except the actual content: what comes before the first section, how sections are numbered and named, how notes and warnings look, what the footer says, and which metadata fields are filled. Take it from the author's template or example notebook. Do not apply any organisation's house style unless the author's source uses it.

## Run the extractor

```bash
python scripts/extract_style.py <source.ipynb> --out style_profile.json
```

The script writes `style_profile.json` (machine-readable) and `style_profile.md` (for the author). It is a heuristic. Always read the source notebook yourself as well, and correct the profile where the script got it wrong. Keep the script output as `style_profile.raw.json` and save the corrected version as `style_profile.json`, which `check_notebook.py --style` reads.

## What the profile contains

| Field | Meaning | How to use it |
|---|---|---|
| `language` | Kernel language (python, R, …) | Must match the author's choice. If it does not, keep the layout and adapt the code conventions. |
| `header` | Cells before the first section heading, classified as `image`, `licence`, `title`, `badges`, `navigation`, `prerequisites`, `learning_outcomes`, `contents`, `separator`, `text` | Reproduce the same elements in the same order. Replace content (title, outcomes, links), keep form (bold labels, separators, image paths or URLs). |
| `sections` | Heading level, numbering pattern, and titles of the main sections. The section level is the one with the most numbered headings, so a style with "# 1. Introduction" gets `section_level` 1 | Reuse the pattern (for example "## 1. Title"). Reuse generic sections that fit the storyline (environment set-up, data access, take-home messages, next steps). With `section_level` 1, `check_notebook.py` expects an H1 title before the first section instead of exactly one H1. |
| `back_links` | Section cells that link back to the contents ("Go back to the Table of contents") | Add the same link to each section. |
| `template_sections` | Sections that document the template itself ("How to use this template") | Do not reproduce them. |
| `heading_case` | `sentence`, `title` or `mixed` (neither above 80 %) | Follow it in all headings; for `mixed`, read the source and pick the case its main sections use. |
| `boxes` | How notes and warnings are written (HTML `div` with colours, Bootstrap `alert` classes, MyST admonitions, blockquotes) | Use the same markup and colours for every box. |
| `footer` | Cells after the last section | Reproduce them unchanged unless they contain notebook-specific links. |
| `metadata_keys` / `metadata_template` | Notebook-level metadata fields | Fill every field the source fills. Leave a field empty rather than guessing; list empty fields in the hand-over. |
| `instruction_cells` | Cells that look like guidance for authors (italic-only text, "This block is to…", "[H2]") | Do not copy them. Read them: they often contain rules (for example "imports at the top", "one topic per notebook"). Apply those rules. |
| `code` | Install pattern (`%pip install`, `try/except ImportError`, `install.packages`), whether imports sit in the first code cell, mean code cell length | Follow the same conventions. |
| `ratio` | Markdown cells per code cell, words of text | Aim for a similar ratio. Below 2:1 usually means the text is too thin for an educational notebook. |

## Show the author a summary

Keep it short. Example:

> **Style from `template.ipynb`:** banner image → licence line → H1 title → run badges → prerequisites → learning outcomes → contents → separator. Sections numbered "## 1. …", sentence case. Notes as blue HTML boxes, warnings as orange boxes. Footer with four links. Metadata: title, author, description, tags (7 fields), licence. 12 template-instruction cells will be dropped; they ask for imports at the top and one topic per notebook.

## Default style (no source given)

Use only after the author confirms.

1. H1 title.
2. One-paragraph introduction: what the notebook does and for whom.
3. **Prerequisites** (bullets).
4. **Learning outcomes** (bullets, "you will be able to …").
5. **Contents** with anchor links.
6. Numbered H2 sections: set-up (imports, parameters), data access, one section per storyline step, summary, next steps.
7. Notes and warnings as blockquotes starting with **Note:** or **Warning:** (render everywhere, including GitHub and Jupyter Book).
8. No footer; licence line at the end if the author gives one.
