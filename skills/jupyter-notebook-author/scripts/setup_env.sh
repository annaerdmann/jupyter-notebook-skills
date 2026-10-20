#!/usr/bin/env bash
# Create a test environment and register a Jupyter kernel for it.
#
# Usage: bash setup_env.sh <environment.yml|requirements.txt|renv.lock|DESCRIPTION|python|r> <env-name> [--packages "pkg1 pkg2" | --packages-file FILE]
#        bash setup_env.sh --remove <env-name>
#
# Uses micromamba, mamba or conda when available; otherwise Python venv + pip (Python only).
# --packages / --packages-file: extra packages from conda-forge (R: plain names become r-<name>),
#   e.g. the output of `make_env.py NOTEBOOK.ipynb --packages-only`. Use this when no environment file is given.
# Prints KERNEL=<name> and PYTHON=<path> (Python) or RSCRIPT=<path> (R).
set -euo pipefail

if [ "${1:-}" = "--remove" ]; then
  NAME="${2:?usage: setup_env.sh --remove <env-name>}"
  jupyter kernelspec remove -f "$NAME" 2>/dev/null || true
  rm -rf "${NB_ENV_ROOT:-$HOME/.nb-test-envs}/$NAME"
  echo "removed $NAME"; exit 0
fi

SPEC="${1:?usage: setup_env.sh <env-file|python|r> <env-name> [--packages \"a b\"]}"
NAME="${2:?usage: setup_env.sh <env-file|python|r> <env-name> [--packages \"a b\"]}"
shift 2
EXTRA=""
while [ $# -gt 0 ]; do
  case "$1" in
    --packages) EXTRA="$EXTRA ${2:-}"; shift 2 ;;
    --packages-file) EXTRA="$EXTRA $(grep -v '^\s*#' "${2:?}" | tr '\n' ' ')"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
ENV_ROOT="${NB_ENV_ROOT:-$HOME/.nb-test-envs}"
mkdir -p "$ENV_ROOT"
LOG="$ENV_ROOT/$NAME.setup.log"

CONDA=""
for c in micromamba mamba conda; do
  if command -v "$c" >/dev/null 2>&1; then CONDA="$c"; break; fi
done

lang="python"
case "$SPEC" in
  r|R|*renv.lock|*DESCRIPTION) lang="r" ;;
  *.yml|*.yaml) grep -qiE '^\s*-\s*r-base|^\s*-\s*r-irkernel|^\s*-\s*r=' "$SPEC" && lang="r" ;;
esac

# R packages from conda-forge are called r-<name>
extra_specs() {
  for p in $EXTRA; do
    if [ "$lang" = "r" ] && [[ "$p" != r-* ]]; then echo "r-$(echo "$p" | tr 'A-Z' 'a-z')"; else echo "$p"; fi
  done
}

fail() {  # show the solver's own message, not only the last fallback
  echo "Environment creation failed. Solver output ($LOG):" >&2
  tail -n 40 "$LOG" >&2
  exit 4
}

if [ -n "$CONDA" ]; then
  PREFIX="$ENV_ROOT/$NAME"
  : > "$LOG"
  case "$SPEC" in
    *.yml|*.yaml)
      if ! "$CONDA" env create -y -p "$PREFIX" -f "$SPEC" >>"$LOG" 2>&1; then
        echo "'$CONDA env create' failed; trying '$CONDA create -f'." >&2
        "$CONDA" create -y -p "$PREFIX" -f "$SPEC" >>"$LOG" 2>&1 || fail
      fi ;;
    python) "$CONDA" create -y -p "$PREFIX" -c conda-forge python=3.11 >>"$LOG" 2>&1 || fail ;;
    r|R|*renv.lock|*DESCRIPTION) "$CONDA" create -y -p "$PREFIX" -c conda-forge r-base r-renv >>"$LOG" 2>&1 || fail ;;
    *requirements.txt)
      "$CONDA" create -y -p "$PREFIX" -c conda-forge python=3.11 pip >>"$LOG" 2>&1 || fail
      "$PREFIX/bin/pip" install -r "$SPEC" >>"$LOG" 2>&1 || fail ;;
    *) echo "unknown environment spec: $SPEC" >&2; exit 2 ;;
  esac
  SPECS=$(extra_specs)
  if [ -n "$SPECS" ]; then
    # shellcheck disable=SC2086
    "$CONDA" install -y -p "$PREFIX" -c conda-forge $SPECS >>"$LOG" 2>&1 || fail
  fi
  if [ "$lang" = "r" ]; then
    "$CONDA" install -y -p "$PREFIX" -c conda-forge r-irkernel jupyter_client >>"$LOG" 2>&1 || fail
    case "$SPEC" in
      *renv.lock) (cd "$(dirname "$SPEC")" && "$PREFIX/bin/Rscript" -e 'renv::restore(prompt = FALSE)') ;;
      *DESCRIPTION) (cd "$(dirname "$SPEC")" && "$PREFIX/bin/Rscript" -e 'install.packages("remotes", repos="https://cloud.r-project.org"); remotes::install_deps(".")') ;;
    esac
    PATH="$PREFIX/bin:$PATH" "$PREFIX/bin/Rscript" -e "IRkernel::installspec(name = '$NAME', displayname = '$NAME')"
    echo "RSCRIPT=$PREFIX/bin/Rscript"
  else
    "$CONDA" install -y -p "$PREFIX" -c conda-forge ipykernel >>"$LOG" 2>&1 || fail
    "$PREFIX/bin/python" -m ipykernel install --user --name "$NAME" --display-name "$NAME"
    echo "PYTHON=$PREFIX/bin/python"
  fi
else
  if [ "$lang" = "r" ]; then
    if command -v Rscript >/dev/null 2>&1 && Rscript -e 'quit(status = !requireNamespace("IRkernel", quietly = TRUE))'; then
      echo "No conda found; using system R. Packages from $SPEC and --packages are NOT installed automatically." >&2
      Rscript -e "IRkernel::installspec(name = '$NAME', displayname = '$NAME')"
      echo "RSCRIPT=$(command -v Rscript)"
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
    # shellcheck disable=SC2086
    [ -n "$EXTRA" ] && "$PREFIX/bin/pip" install -q $EXTRA
    "$PREFIX/bin/python" -m ipykernel install --user --name "$NAME" --display-name "$NAME"
    echo "PYTHON=$PREFIX/bin/python"
  fi
fi
echo "KERNEL=$NAME"
