# Output folder

Everything the user gets is in the output folder (`--out`):

```
OUT/
├── fix-report.md            summary: counts, one section per notebook, tool reports, branches, points to review
├── fix-report.json          the same as data (all state, for other tools)
├── fix-state.json           working state of nbfix.py (do not edit by hand)
├── notebook-test-config.yml the config used for the baseline run
├── tool-reports/            every notebook-test report: baseline.json/.md and rerun-*.json/.md
├── diffs/REPO.diff          uncommitted changes per repository (fixes "yes" only)
└── pr/REPO.md               ready-to-paste pull request text per repository (fixes "yes" only)
```

`pr/REPO.md` exists only for repositories with changes and lists only the fixes in that repository (Before / After / Fixes). Notebooks that still fail or are not fixable are not in it; they stay in `fix-report.md`. A notebook fixed through a superproject's environment file is listed in the superproject's PR text.

Results per notebook in `fix-report.md`:
- **passed (not rerun)**: passed in the baseline run.
- **fixed**: passes after the listed tries.
- **not fixable by the LLM**: with the reason (service, quota, platform, or why the change would not be a real fix).
- **still failing after the try limit**: the last error is shown.
- **broke after an environment change**: passed before, fails after a changed environment file. The environment change must be reconsidered.

Not in the output: executed notebooks (they stay in the notebook-test work folder, may contain account output, and must not be shared or committed).

The notebook-test report format is documented in the notebook-test README ("Report format", `schema_version` 1).
