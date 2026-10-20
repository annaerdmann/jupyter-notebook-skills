#!/usr/bin/env python3
"""Generate a conda environment.yml from the imports of a notebook.

Usage:
    python make_env.py NOTEBOOK.ipynb [--out environment.yml] [--name NAME]
                       [--python-env PATH_TO_ENV_PYTHON] [--python 3.11]

Python: collects `import x` / `from x import`; R: `library(x)`, `require(x)` and `pkg::fun`.
With --python-env (or --rscript for R), pins versions installed in that environment (major.minor).
With --packages-only, prints one package per line (for `setup_env.sh --packages`).
The import-to-package mapping is a heuristic: review the result.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import nbformat

# import name -> conda-forge package name
PY_MAP = {
    "sklearn": "scikit-learn", "skimage": "scikit-image", "cv2": "opencv", "PIL": "pillow",
    "yaml": "pyyaml", "bs4": "beautifulsoup4", "osgeo": "gdal", "netCDF4": "netcdf4",
    "dateutil": "python-dateutil", "mpl_toolkits": "matplotlib", "dask_gateway": "dask-gateway",
    "pystac_client": "pystac-client", "odc": "odc-stac", "earthkit": "earthkit", "IPython": "ipython",
    "ipywidgets": "ipywidgets", "hda": "hda", "eumdac": "eumdac", "cdsapi": "cdsapi",
    "copernicusmarine": "copernicusmarine", "rioxarray": "rioxarray", "shapely": "shapely",
}
# packages only on PyPI (go under pip:); everything else comes from conda-forge
PIP_ONLY = {"eocanvas"}
R_BASE = {"base", "stats", "utils", "graphics", "grDevices", "methods", "datasets", "tools", "grid", "parallel", "IRkernel"}
STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}


def src(c):
    return c.source if isinstance(c.source, str) else "".join(c.source)


def python_imports(code):
    mods = set()
    for m in re.finditer(r"^\s*(?:import\s+([\w.]+(?:\s*,\s*[\w.]+)*)|from\s+([\w.]+)\s+import)", code, re.M):
        names = (m.group(1) or m.group(2)).split(",")
        for n in names:
            top = n.strip().split(".")[0].split(" ")[0]
            if top and not top.startswith("_") and top not in STDLIB:
                mods.add(top)
    for m in re.finditer(r"^\s*[%!]\s*pip install\s+([^\n#]+)", code, re.M):
        mods.update(p for p in m.group(1).split() if not p.startswith("-"))
    return mods


def r_packages(code):
    pkgs = set(re.findall(r"\b(?:library|require|requireNamespace)\(\s*['\"]?([\w.]+)", code))
    pkgs |= set(re.findall(r"\b([A-Za-z][\w.]*):::?[A-Za-z_.]", code))
    return sorted(p for p in pkgs if p not in R_BASE)


def r_version(rscript, pkg):
    if not rscript:
        return None
    out = subprocess.run([rscript, "-e", f"cat(tryCatch(as.character(packageVersion('{pkg}')), error=function(e) ''))"],
                         capture_output=True, text=True).stdout.strip()
    return out or None


def installed_version(python, dist):
    if not python:
        return None
    code = f"import importlib.metadata as m\ntry: print(m.version({dist!r}))\nexcept Exception: pass"
    out = subprocess.run([python, "-c", code], capture_output=True, text=True).stdout.strip()
    return out or None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("notebook")
    ap.add_argument("--out", default="environment.yml")
    ap.add_argument("--name")
    ap.add_argument("--python-env", help="python executable of the test environment, to pin versions")
    ap.add_argument("--python", default="3.11")
    ap.add_argument("--rscript", help="Rscript of the test environment, to pin R package versions")
    ap.add_argument("--packages-only", action="store_true", help="print package names only, one per line")
    a = ap.parse_args()

    nb = nbformat.read(a.notebook, as_version=4)
    lang = (nb.metadata.get("kernelspec", {}).get("language") or "python").lower()
    code = "\n".join(src(c) for c in nb.cells if c.cell_type == "code")
    name = a.name or Path(a.notebook).stem.lower().replace(" ", "-")
    conda, pip = [], []

    if lang == "r":
        conda = ["r-base", "r-irkernel"]
        for p in r_packages(code):
            ver = r_version(a.rscript, p)
            conda.append(f"r-{p.lower()}" + (f"={'.'.join(ver.split('.')[:2])}.*" if ver else ""))
    else:
        conda = [f"python={a.python}", "ipykernel"]
        for mod in sorted(python_imports(code)):
            pkg = PY_MAP.get(mod, mod)
            ver = installed_version(a.python_env, pkg) or installed_version(a.python_env, mod)
            spec = pkg + (f"=={'.'.join(ver.split('.')[:2])}.*" if ver else "")
            if pkg in PIP_ONLY:
                pip.append(spec)
            else:
                conda.append(spec.replace("==", "="))
        # I/O backends are used without being imported
        backends = {
            r"open_(mf)?dataset|\.nc\b|netcdf": "netcdf4",
            r"\.zarr\b|open_zarr|engine=[\"']zarr": "zarr",
            r"grib|cfgrib": "cfgrib",
            r"\.h5\b|h5netcdf": "h5netcdf",
            r"chunks\s*=": "dask",
        }
        names = {d.split("=")[0] for d in conda}
        for pat, pkg in backends.items():
            if re.search(pat, code, re.I) and pkg not in names:
                ver = installed_version(a.python_env, pkg)
                conda.append(pkg + (f"={'.'.join(ver.split('.')[:2])}.*" if ver else "") + "  # I/O backend (inferred)")
        if pip:
            conda.append("pip")

    if a.packages_only:
        skip = ("python=", "ipykernel", "pip", "r-base", "r-irkernel")
        print("\n".join(d.split("  #")[0].split("=")[0] for d in conda + pip if not d.startswith(skip)))
        return

    lines = [f"name: {name}", "channels:", "  - conda-forge", "dependencies:"]
    lines += [f"  - {d}" for d in conda]
    if pip:
        lines += ["  - pip:"] + [f"      - {p}" for p in pip]
    Path(a.out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("\n# Review this file: package names are mapped heuristically.", file=sys.stderr)


if __name__ == "__main__":
    main()
