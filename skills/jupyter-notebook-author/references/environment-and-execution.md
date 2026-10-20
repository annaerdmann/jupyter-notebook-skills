# Environment and execution

Every notebook is executed top to bottom in a clean test environment before hand-over. A notebook that has not run is a draft, and you say so.

## Two cases

| Case | What you do |
|---|---|
| **The author gives an environment file** | Create the test environment from it. Use only its packages. If the notebook needs another package, ask the author before adding it, and if they agree, give them the updated file. |
| **No environment file** | Create a minimal environment for the language, install what the notebook needs, run it, then generate `environment.yml` with `scripts/make_env.py`. Pin major and minor versions of what was installed. Then rebuild a fresh environment from that file and run the notebook again there. |
| **The given file does not resolve** | Do not change it silently. Propose a minimal fix (for example a package from conda-forge instead of an empty channel). Once the author approves, apply it to the delivered file, rebuild and run. |

Supported files: `environment.yml` (conda/mamba), `requirements.txt` (pip), `renv.lock` and `DESCRIPTION` (R).

## 1. Create the environment

```bash
bash scripts/setup_env.sh <environment-file|python|r> <env-name> [--packages "xarray netcdf4" | --packages-file pkgs.txt]
bash scripts/setup_env.sh --remove <env-name>        # remove the environment and its kernel after the test
```

The script:
- uses `micromamba`, `mamba` or `conda` if one is available, else Python `venv` + pip (Python only);
- creates the environment from the file, or a minimal one for `python` or `r`;
- with `--packages` or `--packages-file`, installs those packages from conda-forge (for R, `ncdf4` becomes `r-ncdf4`). Without an environment file, get the list with `python scripts/make_env.py notebook.ipynb --packages-only > pkgs.txt`;
- installs `ipykernel` (Python) or `r-irkernel` (R) and registers a Jupyter kernel named `<env-name>`;
- prints `KERNEL=<name>` and `PYTHON=<path>` (Python) or `RSCRIPT=<path>` (R) for the next steps;
- on failure, prints the solver's own message (full log in `<env-root>/<env-name>.setup.log`).

R needs conda/mamba/micromamba or a system R with IRkernel. If neither exists, tell the author that the R notebook could not be executed here.

## 2. Run the notebook

```bash
python scripts/run_notebook.py notebook.ipynb --kernel <env-name> --out notebook.ipynb --timeout 1200
```

- `--out notebook.ipynb` executes the deliverable in place (the default deliverable is executed). Use another name for a scratch run.
- Runs every cell in order with `nbclient`, from the notebook's own folder. The kernelspec in the file stays as in the source; the test kernel is named in the report.
- Continues after errors so you see all failing cells, and writes a report next to `--out` (`notebook.run_report.md`, or `--report PATH`): per cell the status, run time and error.
- Exit code 0 only if every cell succeeded.

## 3. When cells fail

1. Read the error. Fix the code, not the symptom: do not wrap failing code in `try/except` to hide it.
2. Run again from the top. Do not run single cells out of order and call it done.
3. If a failure is outside your control (credentials you do not have, a service is down, data no longer at the URL), stop fixing. Report which cells failed and why, and what the author needs to do.

## Credentials in the test environment

Do not ask the author to paste credentials into the chat. If data access needs credentials, ask the author to put them where the notebook reads them (config file or environment variables) in the environment where the test runs. If that is not possible, run everything up to the data access, and report the rest as untested.

## 4. Generate an environment file (no file given)

```bash
python scripts/make_env.py notebook.ipynb --out environment.yml --name <env-name> [--python-env <path-to-env-python> | --rscript <path-to-env-Rscript>]
```

- Collects imports (`import x`, `from x import`) or `library(x)`/`require(x)` calls and `pkg::fun()` in R.
- Maps import names to package names (for example `sklearn` → `scikit-learn`, `cv2` → `opencv`). Everything comes from conda-forge; only packages conda-forge lacks go under `pip:`.
- Reads installed versions from the test environment if given and pins them (`xarray=2025.6.*`, `r-ncdf4=1.23.*`).
- Then rebuild a fresh environment from the generated file (new name) and run the deliverable in it before hand-over.
- Leaves standard library modules out.
- Always review the result: the import-to-package mapping is a heuristic.

## 5. Check package licences

```bash
python scripts/check_licences.py notebook.ipynb --python-env <env-python> --target <licence-from-intake>
python scripts/check_licences.py notebook.ipynb --rscript <env-Rscript> --target <licence-from-intake>   # R
```

- Reads each imported package's licence from the test environment and classifies it (permissive, weak copyleft, strong copyleft, unknown).
- Exit code 1 if a package needs a decision: copyleft under a permissive target, or an unknown licence. Report these to the author; do not decide for them.
- Reads the owner's decisions from `licence-decisions.md` next to the notebook (or `--decisions FILE`). Accepted packages show as "decided: accepted" and no longer set the exit code.
- `--extra pkg1,pkg2` adds packages the notebook needs but does not import (I/O back ends such as `netcdf4`).
- Writes the report next to the notebook and refuses paths outside the notebook folder or the current folder unless `--force`.
- It is a first check, not legal advice. Dataset terms of use are not covered.

## 6. Hand-over

Give the author the executed notebook (or cleared, if asked at intake) with `data/` and `img/` next to it, the environment file and the three reports (check, run, licence). Say which environment and kernel the notebook was run in, and list cells that were skipped or untested.
