#!/usr/bin/env python3
"""Find the current ID of a WEkEO dataset whose ID no longer works (HDA API).

Lists the datasets of the WEkEO catalogue with the `hda` client and ranks them by similarity to the
old ID and optional keywords (product name, variable, provider). Prints the best candidates with
their titles. Reports a "clear match" only when one candidate is clearly better than the rest;
otherwise the notebook owner must choose.

Login: the hda client reads ~/.hdarc itself. Never read, print or ask for credentials.

    python find_dataset.py "EO:ECMWF:DAT:CAMS_EUROPE_AIR_QUALITY_FORECASTS" --keyword "air quality"
    python find_dataset.py OLD_ID --check      # only check whether OLD_ID still exists
"""

import argparse
import difflib
import json
import re
import sys


def tokens(text):
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 1}


def entry_id(d):
    return d.get("dataset_id") or d.get("datasetId") or d.get("id") or ""


def entry_title(d):
    meta = d.get("metadata") or {}
    src = meta.get("_source") or meta
    # hda 2.40: the readable title is metadata.datasetTitle; metadata.title only repeats the ID.
    return (d.get("title") or src.get("datasetTitle") or src.get("datasetInfo", {}).get("title")
            or src.get("title") or "")


def old_names(old_id):
    """Lower-case forms of an old ID that a renamed dataset may list among its identifiers:
    the full ID, the part after EO:PROVIDER:DAT:, and that part without a format suffix
    (CLMS IDs had one, e.g. ..._DAILY-CYCLE_NETCDF; the identifier is ..._daily-cycle)."""
    name = old_id.split(":")[-1].lower()
    return {old_id.lower(), name, re.sub(r"_(netcdf|geotiff|cog|zarr|hdf5?)$", "", name)}


def is_alias(old, d):
    """True if the dataset lists the old ID among its identifiers (metadata.ident_identifier)."""
    idents = (d.get("metadata") or {}).get("ident_identifier") or []
    idents = [idents] if isinstance(idents, str) else idents
    return bool(old_names(old) & {str(i).lower() for i in idents})


def score(old, keywords, d):
    did, title = entry_id(d), entry_title(d)
    ratio = difflib.SequenceMatcher(None, old.lower(), did.lower()).ratio()
    old_t, kw_t = tokens(old), tokens(" ".join(keywords))
    cand_t = tokens(did + " " + title)
    overlap = len(old_t & cand_t) / max(len(old_t), 1)
    kw = len(kw_t & cand_t) / max(len(kw_t), 1) if kw_t else 0
    return round(0.5 * ratio + 0.3 * overlap + 0.2 * kw, 3)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("old_id")
    ap.add_argument("--keyword", action="append", default=[], help="extra words from the notebook (repeatable)")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--check", action="store_true", help="only check whether the ID exists")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        from hda import Client
    except ImportError:
        print("The hda package is missing: pip install hda", file=sys.stderr)
        return 2
    client = Client(progress=False)
    if a.check:
        try:
            client.dataset(a.old_id)
            print(f"{a.old_id} exists.")
            return 0
        except Exception as e:  # noqa: BLE001  (HTTP errors differ between hda versions)
            print(f"{a.old_id} not found ({type(e).__name__}).")
            return 1
    datasets = client.datasets()
    ranked = sorted(((score(a.old_id, a.keyword, d), entry_id(d), entry_title(d)) for d in datasets), reverse=True)
    top = ranked[: a.top]
    exact = [r for r in ranked if r[1] == a.old_id]
    # A dataset that lists the old ID as one of its identifiers is the renamed dataset, if it is the only one.
    aliases = [(1.0, entry_id(d), entry_title(d)) for d in datasets if is_alias(a.old_id, d)]
    if len(aliases) == 1 and not exact:
        top = aliases + [r for r in top if r[1] != aliases[0][1]][: a.top - 1]
    clear = bool(top) and not exact and (len(aliases) == 1 or (
        top[0][0] >= 0.6 and (len(top) == 1 or top[0][0] - top[1][0] >= 0.1)))
    if a.json:
        print(json.dumps({"old_id": a.old_id, "still_exists": bool(exact), "clear_match": top[0][1] if clear else None,
                          "old_id_listed_by": [i for _, i, _ in aliases],
                          "candidates": [{"score": s, "dataset_id": i, "title": t} for s, i, t in top]}, indent=2))
    else:
        if exact:
            print(f"{a.old_id} is still in the catalogue: the error has another cause.")
        for _, i, _ in aliases:
            print(f"  {i} lists the old ID among its identifiers")
        for s, i, t in top:
            print(f"  {s:.3f}  {i}  {t}")
        print(f"Clear match: {top[0][1]}" if clear else
              "No clear match: do not change the ID; list the candidates for the owner (nbfix.py mark --candidates).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
