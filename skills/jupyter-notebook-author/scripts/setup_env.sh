#!/usr/bin/env bash
# Create a test environment and register a Jupyter kernel for it.
#
# Usage: bash setup_env.sh <environment.yml|requirements.txt|renv.lock|DESCRIPTION|python|r> <env-name>
#
# Uses micromamba, mamba or conda when available; otherwise Python venv + pip (Python only).
# Prints the kernel name to pass to run_notebook.py.
set -euo pipefail

SPEC="${1:?usage: setup_env.sh <env-file|python|r> <env-name>}"
NAME="${2:?usage: setup_env.sh <env-file|python|r> <env-name>}"
ENV_ROOT="${NB_ENV_ROOT:-$HOME/.nb-test-envs}"
mkdir -p "$ENV_ROOT"

CONDA=""
for c in micromamba mamba conda; do
  if command -v "$c" >/dev/null 2>&1; then CONDA="$c"; break; fi
done

lang="python"
case "$SPEC" in
  r|R|*renv.lock|*DESCRIPTION) lang="r" ;;
  *.yml|*.yaml) grep -qiE '^\s*-\s*r-base|^\s*-\s*r-irkernel|^\s*-\s*r=' "$SPEC" && lang="r" ;;
esac

if [ -n "$CONDA" ]; then
  PREFIX="$ENV_ROOT/$NAME"
  case "$SPEC" in
    *.yml|*.yaml)
      "$CONDA" env create -y -p "$PREFIX" -f "$SPEC" 2>/dev/null || "$CONDA" create -y -p "$PREFIX" -f "$SPEC" ;;
    python) "$CONDA" create -y -p "$PREFIX" -c conda-forge python=3.11 ;;
    r|R|*renv.lock|*DESCRIPTION) "$CONDA" create -y -p "$PREFIX" -c conda-forge r-base r-renv ;;
    *requirements.txt)
      "$CONDA" create -y -p "$PREFIX" -c conda-forge python=3.11 pip
      "$PREFIX/bin/pip" install -r "$SPEC" ;;
    *) echo "unknown environment spec: $SPEC" >&2; exit 2 ;;
  esac
  if [ "$lang" = "r" ]; then
    "$CONDA" install -y -p "$PREFIX" -c conda-forge r-irkernel jupyter_client
    case "$SPEC" in
      *renv.lock) (cd "$(dirname "$SPEC")" && "$PREFIX/bin/Rscript" -e 'renv::restore(prompt = FALSE)') ;;
      *DESCRIPTION) (cd "$(dirname "$SPEC")" && "$PREFIX/bin/Rscript" -e 'install.packages("remotes", repos="https://cloud.r-project.org"); remotes::install_deps(".")') ;;
    esac
    PATH="$PREFIX/bin:$PATH" "$PREFIX/bin/Rscript" -e "IRkernel::installspec(name = '$NAME', displayname = '$NAME')"
  else
    "$CONDA" install -y -p "$PREFIX" -c conda-forge ipykernel
    "$PREFIX/bin/python" -m ipykernel install --user --name "$NAME" --display-name "$NAME"
  fi
  echo "PYTHON=$PREFIX/bin/python"
else
  if [ "$lang" = "r" ]; then
    if command -v Rscript >/dev/null 2>&1 && Rscript -e 'quit(status = !requireNamespace("IRkernel", quietly = TRUE))'; then
      echo "No conda found; using system R. Packages from $SPEC are NOT installed automatically." >&2
      Rscript -e "IRkernel::installspec(name = '$NAME', displayname = '$NAME')"
    else
      echo "Cannot create an R environment: no micromamba/mamba/conda and no system R with IRkernel." >&2
      exit 3
    fi
  else
    PREFIX="$ENV_ROOT/$NAME"
    python3 -m venv "$PREFIX"
    "$PREFIX/bin/pip" install -q --upgrade pip ipykernel
    case "$SPEC" in
      *requirements.txt) "$PREFIX/bin/pip" install -q -r "$SPEC" ;;
      *.yml|*.yaml)
        # best effort: install the pip-installable dependencies of a conda file
        python3 - "$SPEC" > "$PREFIX/requirements-from-yml.txt" <<'PY'
import re, sys
skip = {"python", "pip", "ipykernel"}
for line in open(sys.argv[1]):
    m = re.match(r"\s*-\s*([A-Za-z0-9_.\-]+)\s*([=<>!~][^#\s]*)?", line)
    if m and m.group(1) not in skip and not line.strip().startswith("- pip:"):
        name, ver = m.group(1), (m.group(2) or "")
        if ver.startswith("=") and not ver.startswith("=="):
            ver = "==" + ver.lstrip("=").replace(".*", ".*")
        print(name + ver)
PY
        echo "No conda found; installing conda dependencies with pip (best effort)." >&2
        "$PREFIX/bin/pip" install -q -r "$PREFIX/requirements-from-yml.txt" ;;
      python) ;;
      *) echo "unknown environment spec: $SPEC" >&2; exit 2 ;;
    esac
    "$PREFIX/bin/python" -m ipykernel install --user --name "$NAME" --display-name "$NAME"
    echo "PYTHON=$PREFIX/bin/python"
  fi
fi
echo "KERNEL=$NAME"
