# Forbidden fixes

A fix makes the notebook work **as its author meant it**. A change that only makes the error disappear is not a fix. If the only way to make a notebook pass is one of the changes below, stop and mark the notebook as not fixable, with the reason.

## Never
- **Delete or comment out a cell or a line that fails**, or move it to the end, or turn a code cell into Markdown.
- **Swallow an error**: `try: ... except: pass`, `except Exception: continue`, `if False:`, `|| true`, `warnings.filterwarnings("ignore")` to hide a real failure.
- **Skip or fake the data**: removing a download, replacing real data with random or dummy data, loading a cached file instead of the documented download, shortening the period or area so the notebook runs faster.
- **Change the science**: another dataset (except the same dataset under a new ID), variable, area, period, resolution, threshold, method or colour scale; anything that changes the numbers, maps or conclusions the text describes.
- **Remove teaching content**: explanations, exercises, plots or outputs that the text refers to.
- **Hard-code credentials** or write them to a file. Use the platform's standard login (for WEkEO: `hda.Client()` reading `~/.hdarc`).
- **Pin an old package version to dodge an error** when updating the code to the current API is possible.
- **Install packages from inside the notebook** (`!pip install`, `%conda install`) to make it pass. Packages belong in the environment file, and only when environment fixes are allowed.
- **Touch other files**: only notebooks and, if allowed, environment files may change. No new notebooks, no deleted files.

## Allowed, and preferred
- Updating code to a current package API (renamed functions, changed arguments) with the same result.
- Replacing a placeholder login (`user="username"`) with the standard login from the credentials file.
- Replacing a dataset ID that was renamed, when the new ID is clearly the same dataset (`scripts/find_dataset.py`).
- Fixing paths: OS-specific paths (`C:\...`, backslashes) to `os.path.join` or `pathlib`, relative to the notebook.
- Adding a missing package or raising a version in the environment file (only with environment fixes allowed).
- Fixing a plain bug (typo, wrong variable name) where the intent is obvious from the text.

## When unsure
If you are not sure whether a change alters what the notebook teaches, do not make it. Mark the notebook as not fixable and write in the reason what you would change, so the owner can decide.
