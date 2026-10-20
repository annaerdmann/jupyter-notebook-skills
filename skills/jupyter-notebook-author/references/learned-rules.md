# Learned rules

Rules confirmed by authors after editing notebooks this skill created. Read this file at the start of every session. These rules override the general guidelines in the other reference files.

Format: `- YYYY-MM-DD – <rule in the imperative>. Example: <one line>.`

## Style

- 2026-10-14 – Write data and image paths for the published layout, `data/` and `img/` next to the notebook. Example: `DATA_DIR = Path("data")`, not `../../input/data`.
- 2026-10-14 – Deliver the notebook executed with all outputs unless the author asks for cleared outputs. Example: catalogue notebooks show their figures on GitHub.

## Code

- 2026-10-19 – Ask the author under which licence the notebook will be published, before writing anything; never assume a default. Choose only packages that fit that licence, and run the licence check before hand-over. Example: "Licence?" is a required intake answer; GPL packages in an MIT notebook need the author's explicit OK.
- 2026-10-14 – Make a download leave exactly the file the notebook opens. Example: compare the folder before and after, then unzip and rename.
- 2026-10-14 – Take packages from conda-forge first; rebuild the environment from the delivered file and run in it. Example: `hda` from conda-forge, no `pip:` section.
- 2026-10-14 – Mark a data request that could not be checked with a visible warning box. Example: "Untested: compare the keys with Show API request in the WEkEO Viewer."
- 2026-10-14 – Guard credential prompts and downloads with a switch that is off when the data are provided. Example: `DOWNLOAD_DATA = False`.
- 2026-10-14 – Merge trivial steps into the cell they belong to. Example: `nc_close()` in the same cell as the read.
- 2026-10-14 – Label map axes as 165°W / 70°N and size map figures from the area's aspect ratio. Example: colour bar below each panel.
- 2026-10-14 – Name copyleft packages and their licences in the set-up section; the decision to use them stays with the author. Example: "`ncdf4` (GPL ≥ 3)".

## Text

- 2026-10-14 – Do not start step texts with "The next cell …". Example: "Open the reanalysis file and select 2017."
- 2026-10-14 – Quote numbers and locations only from printed output or a plain figure, with coordinates. Example: "SO2 peaks near Huelva (37.5° N, 6.5° W)."
- 2026-10-14 – Check absolute statements against extreme values. Example: "stays below or at about 0 °C", not "stays below 0 °C".
- 2026-10-14 – In the dataset table, give period, time step and area read from the files. Example: "2 Jan 2013 to 2 Jan 2023, daily, 00:00 UTC".
- 2026-10-14 – Explain request parameters that change how data are read. Example: one sentence on true solar time.
- 2026-10-14 – Justify a statistic in one sentence when another is plausible. Example: why daily maxima, not daily sums.
- 2026-10-14 – End the conclusion box with what the results suggest, with the causation caveat. Example: "Soil warms in May and October; this does not prove the cause."
