# Code guidelines

The code teaches. A reader should understand each cell, run it, and reuse it in their own work. Correct and clear beats short and clever.

Sources: "Ten simple rules for writing and sharing computational analyses in Jupyter Notebooks" (PLOS Comput Biol, 2019); "Five guiding principles to make Jupyter notebooks fit for EO data education" (Remote Sensing, 2022); Project Pythia and xarray tutorial contribution guides; a large-scale study of GitHub notebooks (MSR 2019), in which only 24% of executed notebooks ran without errors.

## Scope

- Implement only what the approved agenda and section descriptions ask for. If a step seems missing (for example a unit conversion the plot needs), ask the author, or add it and say so in the hand-over.
- Use the data source and access method the author named. Do not swap in a different dataset because it is easier to reach.

## Structure

- **Set-up first:** one cell with all imports (Python `import`, R `library()`), right after the install cell if one is needed. No imports later in the notebook.
- **Parameters next:** one cell with everything a reader may change (area, dates, dataset ID, output folder). Tag it `parameters` so papermill can run the notebook with other values.
- **One step per cell.** A code cell does one thing the preceding Markdown cell announces. Aim for 5–15 lines; split cells over 25 lines unless they define one function. Put trivial steps (closing a file, setting a figure size, calling a function just defined) in the same cell as the step they belong to; keep separate cells for steps that show their own output.
- **Functions for repetition.** Code used twice becomes a function with a docstring (Python) or roxygen-style comment (R). Keep helpers in the notebook unless the style source uses a helper module.
- **Show results.** End a step with a visible result where it helps learning: a printed summary, the dataset representation, a plot. Do not print large arrays.
- **Run top to bottom.** No hidden state, no cells that must be skipped, no manual steps between cells except an explicit login prompt.

## Naming and style

- Descriptive names in the reader's domain: `sst_celsius`, `chl_monthly_mean`, not `a`, `df2`, `tmp`.
- Python: PEP 8 (`ruff format` style), f-strings, `pathlib.Path` for paths.
- R: tidyverse style guide, `<-` for assignment, `snake_case`.
- Comments say why, not what. Detailed explanation goes in Markdown.
- Units: state them in variable names, axis labels and printed output.

## Data access

- Download or open only the subset needed (area, time, variables). Keep downloads small so the notebook runs in minutes and within shared-hub quotas.
- Write paths for the published layout: data in `data/` and images in `img/` next to the notebook, as relative paths. Never point to the folder the author handed the inputs over in. For test runs, copy the provided files into `data/` and `img/`.
- If the notebook downloads data, create the data folder (`Path("data").mkdir(exist_ok=True)`) and skip downloads when the file already exists. Ship data files with the notebook only when the author provides them for that purpose; otherwise download them from the original source.
- A download step must leave exactly the file the notebook opens: use the name the client returns, or compare the folder before and after; unzip, merge and rename as needed; never pick "the newest file". Print a clear message if the expected file is missing.
- If a data request cannot be checked against the service, put a visible warning box under the request cell: it is untested, where the keys come from, and how to verify them.

## Credentials

- Never write usernames, passwords, API keys or tokens into a cell or an output.
- Read them from the tool's own config file (for example `~/.hdarc`, `~/.cdsapirc`), from environment variables, or with an interactive prompt (`getpass.getpass()` in Python, `askpass::askpass()` or `readline()` in R). Prefer the method the style source uses, but never print a token.
- Guard interactive prompts and downloads with a switch (for example `DOWNLOAD_DATA = False`) that defaults to off when the data are provided, so "Run all" never blocks.
- Tell the reader in Markdown where to get an account and how to store credentials.

## Plots

- One message per figure. Title, axis labels with units, colour bar with label, legend where needed.
- Colour maps: perceptually uniform (`viridis`, `cividis`) for sequential data, diverging maps (`RdBu_r`) centred on a meaningful value. Avoid `jet` and rainbow maps.
- Maps: state the projection; add coastlines. Label axes in geographic form (165°W, 70°N), or name the axis "Longitude [°]" and explain the sign once.
- Set the figure size explicitly; for maps, derive it from the aspect ratio of the mapped area. Open the rendered figure and check margins and colour bars; in multi-panel maps put the colour bar below each panel.

## Packages and environment

- If an environment file is given, use only its packages. Ask before adding any.
- Take every package from conda-forge when it is available there; use a `pip:` section only for packages conda-forge lacks.
- Otherwise prefer well-maintained, widely used packages and note every package the notebook needs; `scripts/make_env.py` builds the environment file from the imports.
- Install cells (for example `%pip install x` inside `try/except ImportError`) only if the style source uses them.

## Licences

- The notebook's licence comes from intake (default MIT). Every package must be compatible with it.
- Run `scripts/check_licences.py` after the test run. Permissive licences (MIT, BSD, Apache, PSF, ISC, MPL) are fine.
- GPL/AGPL packages: importing them is usually acceptable for an MIT notebook, but tell the author and let them decide per package; never copy GPL code into the notebook. Record a decision only if the author states it explicitly for that notebook. Name copyleft packages and their licences in one line of the set-up section. Prefer a permissive alternative if one does the job equally well.
- LGPL packages: fine as dependencies; do not copy their code.
- Unknown licence: look it up (PyPI, CRAN, the repository) and report it.
- Code copied or adapted from elsewhere keeps its licence and needs attribution in a comment and in the hand-over.
- Data has its own terms of use. State the data licence and the required attribution in the notebook text.

## Python specifics

- `xarray` for labelled multi-dimensional data (NetCDF, Zarr, GRIB via `cfgrib`), `pandas` for tables, `matplotlib` (+ `cartopy` for maps) unless the style source uses another library.
- Open large files lazily (`chunks={}` with dask) and compute only what is plotted.
- Suppress warnings only for a specific, explained warning, never globally.

## R specifics

- `terra` or `stars` for rasters, `sf` for vectors, `ncdf4` or `tidync` for NetCDF, `ggplot2` for plots unless the style source uses others.
- Load packages with `library()` in the set-up cell; do not call `install.packages()` silently. If an install cell is needed, guard it with `if (!requireNamespace("pkg", quietly = TRUE))`.
- Kernel: IRkernel (`ir`). The environment file lists R packages as `r-<name>` (conda-forge) or in `renv.lock`.

## Before hand-over

- `scripts/check_notebook.py` reports no errors.
- `scripts/run_notebook.py` ran the notebook top to bottom without errors, or you list which cells could not run and why.
- No empty cells. Outputs kept (default) or cleared, as the author chose at intake.
