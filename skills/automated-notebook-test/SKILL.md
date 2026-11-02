---
name: automated-notebook-test
description: Runs the automated notebook test (notebook-test) on Jupyter notebook repositories, reports which notebooks fail and why, and, if asked, fixes the failing notebooks one by one in a new branch; commits and opens pull requests only after the user has reviewed the changes. Use when someone wants notebooks tested, a test report explained, or broken notebooks repaired.
license: MIT
metadata:
  version: "0.1.0"
  stage: "first version, tested on wekeo4data 2026-10-22"
---

# Automated notebook test

You run the notebook test tool on one or more repositories, report the result, and, if the user asks for it, fix failing notebooks one at a time until each one passes or has an error you cannot fix. You commit, push and open pull requests only after the user has reviewed the changes and said so (Phase 8).

`scripts/nbfix.py` does all the bookkeeping: baseline run, triage, branch, reruns with a try limit, output clearing, edit review and the final report. Always use it; never run `notebook-test` by hand for reruns, and never keep your own counts.

## Rules that always apply
1. **Never commit, push or open a PR before the user has reviewed the changes and said so.** Until then, leave changes in the working tree of the fix branch. Never merge and never open issues.
2. **Never read, print, copy or ask for credentials.** `~/.hdarc` and similar files exist or they don't. If one is missing, the user creates it.
3. **A fix must not hide an error or change what the notebook teaches.** See `references/forbidden-fixes.md`. This rule is the most important one.
4. **A notebook that passed is never rerun**, with one exception: once at the end, if its environment file was changed by a fix (`rerun --after-env-change`).
5. **At most 5 tries per notebook** (`--max-tries`). The script stops you.
6. **Errors you must not try to fix:** service down or unreachable, quota exceeded, a platform service missing here (GPU, Dask Gateway). With environment fixes not allowed, also missing packages. The script sorts these out.
7. **Never share executed notebooks.** They are in the notebook-test work folder and may contain account output.

## Phase 1 – Intake
Ask only for what is missing. Defaults in brackets.
- **Repositories:** URLs of public repositories, or paths of local clones.
- **Fixes:** yes or no. With "no" you only test and report.
- **Environment fixes:** may fixes change `environment.yml` files? [no]
- **Profile:** which platform the notebooks are for (`notebook-test` profile). [`wekeo`]
- **Output folder** for the reports and hand-over. [`./notebook-test-results/YYYY-MM-DD`]
- **Work folder** for clones, environments and executed notebooks. [`~/notebook-test-work`]

## Phase 2 – Setup check
```bash
python scripts/nbfix.py setup-check --repo PATH_OR_URL ... --profile wekeo --fixes yes
```
If it says NOT READY, tell the user exactly what is missing and stop. Do not install system tools or create credential files yourself. You may install `notebook-test` with pip if the user agrees.

## Phase 3 – Baseline run
```bash
python scripts/nbfix.py baseline --repo PATH_OR_URL ... --out OUT --workdir WORK \
    --profile wekeo --fixes yes|no --env-fixes yes|no
```
This runs every notebook once (it can take hours) and saves the tool report in `OUT/tool-reports/`.

## Phase 4 – Triage
```bash
python scripts/nbfix.py triage --out OUT
```
Show the user the three lists: passed, not fixable (with reasons), to fix (with the first error).

**Checkpoint.** With fixes "no", go to Phase 7 now. With fixes "yes", tell the user how many notebooks you will work on and continue.

## Phase 5 – Fix loop
```bash
python scripts/nbfix.py branch --out OUT
```
Then take the "to fix" notebooks **one at a time**. For each:
1. Read the first error from triage, or from the last rerun. Open the notebook source (the file in the repository, not the executed copy) and find the cause. Read `references/fix-playbook.md` for the error's label, and `references/platform-<profile>.md` if it exists.
2. Make the **smallest** change that removes the cause: edit the cell source in the `.ipynb` with a JSON-aware edit, keeping cell ids. Edit the environment file only if environment fixes are allowed.
3. Rerun and say what you changed:
   ```bash
   python scripts/nbfix.py rerun --out OUT REPO/path/to/notebook.ipynb --note "replaced placeholder login with ~/.hdarc"
   ```
   Write the note so it stands on its own: the notes of the tries that made a notebook pass go into the PR text.
4. The script prints the new state:
   - **passes**: done, next notebook;
   - **not fixable**: done, next notebook;
   - **limit reached**: done, next notebook;
   - **still failing**: go back to 1. If the error is now a *different* error further down, your fix worked; continue with the new one.

   If a fix did not help, undo it before trying something else, so only useful changes stay. When a notebook ends as not fixable or at the try limit, undo its changes with `nbfix.py revert --out OUT NOTEBOOK`, unless a change fixes a real error on its own (say so in the report).
5. If you find that the error cannot be fixed in the notebook (for example the data is no longer offered at all), stop early and record why:
   ```bash
   python scripts/nbfix.py mark --out OUT NOTEBOOK --reason "dataset withdrawn from the catalogue" [--candidates ID1 ID2]
   ```

## Phase 6 – Final checks (fixes "yes" only)
1. If an environment file changed, rerun each notebook that **passed** in the baseline and uses that environment file, once:
   `nbfix.py rerun --out OUT NOTEBOOK --after-env-change`.
2. `nbfix.py clear-outputs --out OUT` clears the stored outputs of the cells you changed. Other stored outputs stay.
3. `nbfix.py check-diff --out OUT` lists edits that may hide an error, change the science, or leak a secret. Look at every point. Undo forbidden edits, then rerun that notebook if it has tries left, or mark it.

## Phase 7 – Hand-over
```bash
python scripts/nbfix.py summary --out OUT
```
Give the user:
- the counts (passed, fixed, not fixable, still failing) and the path of `OUT/fix-report.md`;
- the tool reports in `OUT/tool-reports/`;
- for each repository with changes: the branch, `OUT/diffs/REPO.diff`, and the ready PR text `OUT/pr/REPO.md`. For a mirrored repository (git submodule), the PR goes to that repository's own upstream, which is shown in the report;
- the points to review, if any.

End with: the changes are not committed yet; please review them and tell me when I may commit and open the pull requests (Phase 8).

## Phase 8 – Commit and PRs (only after the user's OK)
Only when the user has reviewed the changes and said so. Fix the PR texts or changes first if the user asks.
1. **Identity and signing.** In each repository, check that `git config user.name` and `user.email` are the user's own identity and that signing is set up (`gpg.format`, `user.signingkey`). Stop and tell the user if they are not, or if signing fails. Never commit as an assistant or bot identity.
2. **Commit** each repository with changes, on its fix branch: `git commit -sS -m "ONE LINE"`. One-line message only, no body. Never add an LLM as co-author, and no "Generated with ..." or session trailers. In a superproject, commit only its own files (for example its `environment.yml`), never submodule pointer changes.
3. **Push** from the user's account. If the user has no write access to the upstream repository, fork it to the user's account and push the branch there.
4. **One PR per changed repository**, with `OUT/pr/REPO.md` as the template (Before / After / Fixes) and no LLM lines. Never open a PR for a repository without changes; delete its empty fix branch. The PR lists only the fixes, never remaining or not fixable errors: those stay in `fix-report.md`.
5. **Check** each PR's commit: the user is the author and the commit is signed. Give the user the PR links.

## Files
- `scripts/nbfix.py`: the bookkeeping.
- `scripts/find_dataset.py`: finds a renamed WEkEO dataset ID through the HDA API.
- `references/forbidden-fixes.md`: what a fix must never do.
- `references/fix-playbook.md`: what to try for each error label.
- `references/platform-wekeo.md`: WEkEO notes: credentials, HDA, known services and quotas.
- `references/output-format.md`: what is in the output folder.
