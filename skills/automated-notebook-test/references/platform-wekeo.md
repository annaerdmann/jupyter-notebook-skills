# Platform notes: WEkEO (profile `wekeo`)

## Login
- WEkEO notebooks log in with the HDA client: `from hda import Client; c = Client()`. The client reads `~/.hdarc` (lines `user: ...` and `password: ...`). The user creates this file; you never read, print or change it.
- Placeholder logins such as `Configuration(user="username", password="password")`, `input()`/`getpass()` prompts, or code that writes `~/.hdarc` are fixed by using `Client()` without arguments. Keep any markdown text that explains how to create `~/.hdarc` (and update it if it describes the old way).
- `notebook-test` restores `~/.hdarc` and other credential files after every notebook, so a notebook that overwrites them cannot break the next one. Such notebooks are listed in the report; writing credential files from a notebook is itself something to fix.

## Dataset IDs
WEkEO dataset IDs look like `EO:EUM:DAT:...` or `EO:ECMWF:DAT:...`. A 404 or "dataset not found" for an ID usually means it was renamed.
```bash
python scripts/find_dataset.py "EO:ECMWF:DAT:OLD_ID" --check
python scripts/find_dataset.py "EO:ECMWF:DAT:OLD_ID" --keyword "words from the notebook title or text"
```
- Replace the ID only when the script reports a **clear match** and its title describes the same product the notebook uses. Also check that the query keys (variables, product type) still exist for the new ID: run the notebook and look at the next error.
- Otherwise do not guess: `nbfix.py mark NOTEBOOK --reason "dataset ID not found; candidates listed" --candidates ID1 ID2`.

## Errors that are not fixable here
- Dask Gateway, NVIDIA GPU, a local Ollama server: only on the WEkEO JupyterHub (label "needs JupyterHub service").
- EOCanvas quota (about 10 requests per hour): label "quota exceeded". Do not rerun EOCanvas notebooks repeatedly.
- HTTP 5xx from the HDA broker or a data service: service unavailable. The test reruns once on its own.

## Environments
Each WEkEO repository folder can have an `environment.yml`; `notebook-test` builds one environment per file and reuses it for reruns. Package names come from conda-forge (the HDA client is `hda` on conda-forge).
