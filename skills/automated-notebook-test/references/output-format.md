# Output folder

Everything the user gets is in the output folder (`--out`):

```
OUT/
├── fix-report.md            summary: counts, one section per notebook, tool reports, branches, points to review
├── fix-report.json          the same as data (all state, for other tools)
├── fix-state.json           working state of nbfix.py (do not edit by hand)
├── notebook-test-config.yml the config used for the baseline run (report mode: for the reruns)
├── tool-reports/            every notebook-test report: baseline.json/.md (report mode: the input reports,
│                            prefixed with their platform) and rerun-*.json/.md
├── diffs/REPO.diff          uncommitted changes per repository (fixes "yes" only)
└── pr/REPO.md               ready-to-paste pull request text per repository (fixes "yes" only)
```

`pr/REPO.md` exists only for repositories with changes and lists only the fixes in that repository (Before / After / Fixes). In report mode, fixes of notebooks that failed only on the WEkEO JupyterHub follow under the heading "Not yet verified on the WEkEO JupyterHub (checked by the next weekly JH run)". That section is a list of fixes, not of remaining issues. Notebooks that still fail or are not fixable are not in it; they stay in `fix-report.md`. A notebook fixed through a superproject's environment file is listed in the superproject's PR text.

Results per notebook in `fix-report.md`:
- **passed (not rerun)**: passed in the baseline run (report mode: passed on every platform it was tested on).
- **fixed**: passes after the listed tries.
- **fixed, not verified on the WEkEO JupyterHub** (report mode): failed only on the WEkEO JupyterHub; after the fix it passes locally (or stops, as before, at the cell that needs a JupyterHub service). The next weekly JupyterHub run confirms it. `fix-report.md` lists these under the same heading as the PR text.
- **not fixable by the LLM**: with the reason (service, quota, platform, or why the change would not be a real fix).
- **still failing after the try limit**: the last error is shown.
- **skipped: an open fix PR already changes it** (report mode): an open PR from a `notebook-test-fixes/` branch changes this notebook; the PR link is given. Not worked on.
- **failing, but no open issue (not worked on)** (report mode with `--issues`): fails in the reports, but the dashboard has no open issue for it.
- **broke after an environment change**: passed before, fails after a changed environment file. The environment change must be reconsidered.

Not in the output: executed notebooks (they stay in the notebook-test work folder, may contain account output, and must not be shared or committed).

The notebook-test report format is documented in the notebook-test README ("Report format", `schema_version` 1).

In report mode, `fix-report.md` also lists the reports used and, per repository, whether the commit worked on differs from the commit in the reports. Each notebook shows its newest result per platform instead of a baseline line. `fix-state.json` has per notebook `platforms` (newest result per platform), `failing_platforms` and `jh_only`.
