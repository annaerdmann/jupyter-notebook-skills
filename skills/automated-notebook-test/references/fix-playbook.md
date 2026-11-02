# Fix playbook by error label

The labels come from `notebook-test` (see its README). Only the first error that is not a follow-on error matters: later errors are often caused by it.

| Label | Fix? | What to do |
|---|---|---|
| notebook error | yes | Read the traceback and the cell. Typical causes: a package API changed (look up the current API in the package docs, change the call, keep the result), a typo, an OS-specific path, a wrong file name. |
| missing package | only with environment fixes | Add the package to the nearest `environment.yml` (conda-forge name; pip section only if not on conda-forge). Do not `pip install` in the notebook. Without environment fixes: not fixable. |
| credentials | yes, if the notebook does not use the standard login | Replace placeholder or interactive logins with the platform's standard login (see the platform notes). If the standard login itself fails, the credentials file is wrong or missing: not fixable here, tell the user. |
| service unavailable | no | Stop. The script marks it. |
| quota exceeded | no | Stop. Do not rerun: more requests make it worse. |
| needs platform service | no | Stop. The notebook needs something only the target platform has (GPU, Dask Gateway). |
| timeout | rarely | Only if the cause is a plain bug (for example an endless loop). Do not shorten the data or the computation: that changes the science. Otherwise mark it: "needs more time than the test allows". |
| kernel died | rarely | Usually memory. Do not reduce the data. Mark it: "needs more memory than the test machine has". |
| follow-on error | – | Never work on these directly; they go away when the earlier error is fixed. |

## Reading the error
- `nbfix.py triage` and `rerun` print the cell number, label, error and the last lines of the traceback.
- For more context, open the executed copy in the notebook-test work folder (`WORK/outputs/...errored.ipynb`), but **edit only the notebook in the repository**.
- A rerun that fails at a *later* cell means the earlier fix worked.

## Typical fixes seen on WEkEO notebooks (2026-10)
- `Configuration(user="username", password="password")` → `hda.Client()` without arguments (reads `~/.hdarc`).
- HTTP 404 for a dataset ID → `scripts/find_dataset.py OLD_ID --keyword ...`; replace only on a clear match.
- An old pinned client package (for example `eocanvas==0.2.7`) fails against the current service → raise the pin in `environment.yml` (environment fixes only) and adapt the code to the new version.
- `ModuleNotFoundError: ipywidgets` → add `ipywidgets` to `environment.yml` (environment fixes only).
- `C:\\Users\\...\\file.nc` → a path relative to the notebook.
