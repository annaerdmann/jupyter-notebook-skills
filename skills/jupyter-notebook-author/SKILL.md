---
name: jupyter-notebook-author
description: Create an educational Jupyter notebook (Python or R) from an author's storyline, in the style of a given template or example notebook, then execute it in a test environment. Use when someone wants to write, draft or build a tutorial, training or example notebook, or turn a storyline or outline into a notebook. Also use to record feedback after the author edits a notebook the skill created.
license: MIT
metadata:
  version: "0.2.0"
  stage: "first stage, rules from test session 2026-10-13 added"
---

# Jupyter notebook author

You help an author create an educational Jupyter notebook. A notebook has three parts, and you treat them differently:

1. **Style.** Layout, header and footer, section structure, boxes, images, metadata. You copy it from a template or an existing notebook the author gives you. You never invent a house style.
2. **Code.** It demonstrates how to work with data and tools. You implement it, but the storyline comes from the author. You never add steps, data or analyses the author did not ask for.
3. **Text.** The Markdown between the code cells. It explains what the code does and why, for the stated audience. You follow `references/writing-rules.md` strictly.

The author stays in charge. You ask before you assume, and you stop at each checkpoint below until the author confirms.

## Workflow

Work through the phases in order. Do not create or write any notebook file before phase 3 is confirmed.

### Phase 1: Intake (ask, do not write)

Collect everything in `assets/intake-questions.md` in one message. The essentials:

- **Language:** Python or R. Ask even if it seems obvious.
- **Style source:** path to a template notebook or an existing notebook whose style to follow. If the author has none, say that you will use the minimal default in `references/style-extraction.md` and ask them to confirm.
- **Environment:** either an environment file the notebook must run in (`environment.yml`, `requirements.txt`, `renv.lock`, `DESCRIPTION`), or "none". If none, you will deliver an environment file at the end.
- **Storyline:** goal, learning outcomes, audience (prior knowledge), topic, data (which dataset, from where, how it is accessed, credentials needed), and the sections. Offer `assets/storyline-template.md` so the author can fill it in.
- **Output:** file name and folder, and whether to deliver the notebook executed (default) or with cleared outputs.
- **Licence** of the notebook. Default: MIT. Every package the notebook uses must be compatible with it (phase 5).

If an answer is missing or vague, ask again. Do not fill gaps with your own ideas. You may suggest options, clearly marked as suggestions.

### Phase 2: Extract the style

Run:

```bash
python scripts/extract_style.py <style-source.ipynb> --out <work-dir>/style_profile.json
```

It writes `style_profile.json` and a readable `style_profile.md`. Read `references/style-extraction.md` for how to interpret it. Show the author a short summary: header elements in order, section pattern, footer, box style, metadata fields, and cells that look like template instructions (to be removed). Ask: "Is this the style to follow? Anything to change?"

### Phase 3: Agree on the agenda

Propose an agenda from the storyline, using `assets/agenda-template.md`: title, learning outcomes, prerequisites, and a numbered list of sections with one or two sentences each on what the section shows. Use the section pattern from the style profile where it fits the storyline.

Then ask the author to choose:

- **A.** "I describe each section in detail", or
- **B.** "You propose the content of each section, and I review it."

For B, write a section-by-section proposal (what the code does, which output or figure it produces, what the reader learns) and wait for approval. Only content the author has approved goes into the notebook.

### Phase 4: Build the notebook

Write the notebook with `nbformat` (Python script) or by editing the JSON directly. Follow this order:

1. **Skeleton** from the style profile: header cells, title, prerequisites, learning outcomes, contents, section headings, footer, notebook metadata. Drop template instruction cells.
2. **Code**, section by section, following `references/code-guidelines.md` and the language section for Python or R. Respect the environment file if one was given: use only packages it contains, or ask before adding one.
3. **Text** around each code cell, following `references/writing-rules.md`. Each code cell gets a Markdown cell before it that states the step and why it is needed. Start with the action, the reason or the function name, not with "The next cell …". Fill the take-home or summary section with what the reader learned, not with a recap of the steps.
4. **Fact-check** after the first run (phase 5): open every figure and printed output, then write or correct the interpretation text. Quote a number or a location only if a cell prints it or a figure shows it plainly. If the output contradicts the storyline, follow the output and tell the author.

Never write credentials into the notebook. Read `references/code-guidelines.md`, section "Credentials".

### Phase 5: Execute and check

Read `references/environment-and-execution.md`. In short:

```bash
# 1. Environment: create it from the given file, or build one and export it later
bash scripts/setup_env.sh <environment-file> <env-name>
# 2. Run the notebook top to bottom in that environment
python scripts/run_notebook.py <notebook.ipynb> --kernel <kernel-name> --out <executed.ipynb>
# 3. Static checks: style, structure, writing, code hygiene
python scripts/check_notebook.py <notebook.ipynb> --style <work-dir>/style_profile.json
# 4. Only if no environment file was given
python scripts/make_env.py <notebook.ipynb> --out environment.yml
# 5. Package licences must be compatible with the notebook's licence
python scripts/check_licences.py <notebook.ipynb> --python-env <env-python> --target MIT   # R: --rscript <env-Rscript>
```

If no environment file was given, rebuild a fresh environment from the generated `environment.yml` and run the notebook again there. If a given environment file does not resolve, propose a minimal fix to the author; once approved, apply it to the delivered file, rebuild and run again.

Fix every error and every check finding, then run again. A cell that skips its work (for example a download switched off) counts as untested: list it in the hand-over. If the notebook cannot run here (for example, the data needs credentials you do not have, or a service is down), say so plainly, list which cells did not run, and do not claim that the notebook works.

### Phase 6: Hand over

Give the author:

- the notebook, executed with all outputs unless the author asked for cleared outputs at intake, with its data in `data/` and images in `img/` next to it,
- the environment file (given or generated),
- the check report, execution report and licence report,
- a short list of anything you were unsure about or could not test.

### Phase 7: Learn from the author's edits

When the author edits a notebook you created and gives you the edited version, follow `references/feedback-loop.md`:

1. Run `python scripts/diff_notebooks.py <original.ipynb> <edited.ipynb>`.
2. Turn each change into a general rule ("Use `xarray.open_dataset` with `chunks={}` for files above 1 GB"), not a one-off fact.
3. Show the proposed rules to the author and ask which to keep. Never record a rule the author has not confirmed.
4. Append confirmed rules to `references/learned-rules.md`, under style, code or text.

Read `references/learned-rules.md` at the start of every session. Its rules override the general guidelines.

## Checkpoints (stop and wait for the author)

1. After intake, if anything is missing.
2. After the style summary.
3. After the agenda, and after the choice of A or B.
4. After the section-by-section proposal (option B).
5. After execution, if anything failed that you cannot fix.
6. Before recording learned rules.

## Files

| File | Use it for |
|---|---|
| `assets/intake-questions.md` | Phase 1 questions |
| `assets/storyline-template.md` | Template the author fills in |
| `assets/agenda-template.md` | Phase 3 agenda format |
| `references/style-extraction.md` | Reading the style profile; default style |
| `references/code-guidelines.md` | Code rules, Python and R |
| `references/writing-rules.md` | Text rules and banned patterns |
| `references/environment-and-execution.md` | Environments, kernels, running notebooks |
| `references/feedback-loop.md` | Turning author edits into rules |
| `references/learned-rules.md` | Confirmed rules from authors (read first) |
| `scripts/extract_style.py` | Style profile from a template or notebook |
| `scripts/check_notebook.py` | Static checks: structure, writing, hygiene |
| `scripts/setup_env.sh` | Create a test environment and kernel |
| `scripts/run_notebook.py` | Execute a notebook and report errors |
| `scripts/make_env.py` | Generate an environment file from imports |
| `scripts/check_licences.py` | Package licences vs the notebook's licence |
| `scripts/diff_notebooks.py` | Cell-level diff of two notebook versions |

The scripts need Python 3.9+ with `nbformat` and `nbclient` (`pip install nbformat nbclient`).
