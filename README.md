# jupyter-notebook-skills

Agent Skills that help WEkEO staff create Jupyter notebooks with an AI assistant (GitHub Copilot or Claude). Internal to EUMETSAT and the WEkEO team.

## Skills

| Skill | What it does | Status |
|---|---|---|
| [`jupyter-notebook-author`](skills/jupyter-notebook-author/SKILL.md) | Builds a training notebook in Python or R from your storyline, in the style of a template, and runs it in a test environment before hand-over. | 0.3.0, tested in a blind test with three WEkEO notebooks; script fixes from that test |
| [`automated-notebook-test`](skills/automated-notebook-test/SKILL.md) | Runs `notebook-test` on notebook repositories (run mode) or starts from existing reports such as the weekly local and WEkEO JupyterHub runs (report mode), reports which notebooks fail and why, and fixes failing notebooks one by one in an uncommitted branch, for one PR per repository after review. | 0.2.0: run mode tested on `wekeo4data` (2026-10-22), report mode added (2026-11-02) |

More skills will follow in `skills/`.

## jupyter-notebook-author

### Who it is for
WEkEO staff who write training notebooks. You stay the author: you give the storyline (goal, audience, data, sections); the assistant writes the code and the explanatory text and checks that the notebook runs.

### What happens
1. **Intake.** The assistant asks for the language (Python or R), a style source, an environment file (optional), the storyline, the output name, whether to deliver the notebook executed, and the licence under which you will publish it. The licence is required: the skill never assumes one. It writes nothing before this.
2. **Style.** It reads the style source and shows you the style it will follow.
3. **Agenda.** It proposes an agenda. You describe each section yourself, or it proposes them for your review.
4. **Build.** Skeleton, code, text; then it checks every number in the text against the real output.
5. **Run and check.** The notebook runs top to bottom in a fresh environment; structure, writing, credentials and package licences are checked.
6. **Hand-over.** Notebook (executed by default) with `data/` and `img/` next to it, environment file, reports, and a list of what could not be tested.
7. **Learn.** When you edit a notebook, the assistant proposes general rules from your edits. Only rules you confirm go into `references/learned-rules.md`.

### Install
Copy `skills/jupyter-notebook-author/` to one of these places:

| Assistant | Folder |
|---|---|
| GitHub Copilot in VS Code (agent mode) or Copilot CLI | `.github/skills/` in your notebook repository, or `~/.copilot/skills/` for all repositories |
| Claude Code | `.claude/skills/` in your repository, or `~/.claude/skills/` |

Then ask, for example: "Create a training notebook from this storyline."

### Requirements
- Python 3.9+ with `nbformat` and `nbclient` for the scripts: `pip install nbformat nbclient`.
- To run notebooks: `micromamba`, `mamba` or `conda` (needed for R), or Python `venv` for Python-only notebooks.

### WEkEO tips
- **Style source:** use the DEx WEkEO notebook template from the `wekeo-dex` repository (`working-practices/notebook-style-guide/`), or an existing notebook from the target repository (e.g. `wekeo4training`). Clear its outputs first: a template with stored outputs can contain credentials.
- **Environment:** give the environment file of the target repository or of the WEkEO JupyterHub image if the notebook must run there.
- **Data access:** the skill puts credential prompts and HDA downloads behind a switch (`DOWNLOAD_DATA = False`) when you provide the data, so "Run all" never blocks. Credentials never go into cells or outputs.
- **Storyline:** the more precise it is (dataset IDs, the exact HDA request, area, period, what each figure shows), the closer the result. Template: `skills/jupyter-notebook-author/assets/storyline-template.md`.

### Known limitations
- HDA downloads were not tested in the blind test (no gateway access); request keys must be checked against "Show API request" in the WEkEO Viewer.
- The style extractor is a heuristic. It now handles styles that number sections at H1, but the assistant still reads the style source and corrects the profile.
- Copyleft packages (GPL, e.g. `ncdf4` in R) are flagged until the notebook owner records a decision per package in `licence-decisions.md` next to the notebook.
- The 0.3.0 script fixes were tested on the blind-test notebooks only, not yet on a new notebook from start to finish.

## Contributing
- Report problems and rule proposals as issues in this repository.
- Changes to a skill go through a merge request. Rules in `learned-rules.md` need the confirmation of the notebook author who proposed them.
- Do not commit notebooks with outputs that contain credentials, or data files.

## Licence
MIT, see `LICENSE`. The scripts depend only on permissively licensed packages (nbformat, nbclient, jupyter_client, ipykernel, traitlets, jupyter_core, pyzmq: BSD-3-Clause; jsonschema: MIT; tornado: Apache-2.0); `automated-notebook-test` also uses PyYAML (MIT), `hda` (Apache-2.0) and `notebook-test`. Notebooks you create get the licence you choose at intake; the skill checks that their packages fit it.
