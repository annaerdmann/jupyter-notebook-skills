#!/usr/bin/env python3
"""Bookkeeping for the automated-notebook-test skill.

The LLM diagnoses and edits notebooks; this script does everything that must not depend on the LLM
remembering it: the baseline run, sorting failing notebooks into "try to fix" and "not fixable",
the fix branch, single-notebook reruns with a hard limit of tries, refusing to rerun notebooks that
passed, clearing outputs of changed cells, flagging suspicious edits, and the final report.

It never commits, pushes or opens pull requests.

Subcommands (run `nbfix.py SUBCOMMAND -h` for options):
    setup-check   Python, notebook-test, git, credential files, clean working trees
    baseline      full run of all notebooks with notebook-test; starts the state file
    triage        sort failing notebooks into "fix" and "not fixable"
    branch        create the fix branch in every repository that has a notebook to fix (no commit)
    rerun         rerun one notebook after a fix and record the try (at most --max-tries)
    mark          record that a notebook cannot be fixed, with the reason
    revert        undo all changes to one notebook
    clear-outputs clear stored outputs of changed cells in changed notebooks
    check-diff    list edits that may hide an error or change the science, for review
    summary       write fix-report.md/.json, PR texts, diffs; copy the tool reports

State lives in OUT/fix-state.json. All paths in it are absolute.
Needs Python 3.10+, git, and notebook-test (https://github.com/annaerdmann/notebook-test-automation).
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("nbfix.py needs Python 3.10 or newer")

import nbformat
import yaml

# Labels of notebook-test whose errors the LLM must not try to fix (decided by the owner, 2026-10-22).
NOT_FIXABLE = {
    "service_unavailable": "a service was down or unreachable",
    "quota_exceeded": "a service quota was exceeded",
    "platform": "needs a platform service that is not available here (GPU, Dask Gateway, ...)",
}
# Not fixable when the user did not allow changes to environment files.
ENV_LABELS = {"missing_package": "a package is missing from the environment, and environment fixes are not allowed"}
IGNORED = {"follow_on"}
DEFAULT_MAX_TRIES = 5
STATE = "fix-state.json"
CREDENTIAL_FILES = ["~/.hdarc", "~/.cdsapirc", "~/.ecmwfdatastoresrc", "~/.netrc", "~/.eumdac/credentials"]


# ---------------------------------------------------------------- helpers

def sh(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(map(str, cmd))}\n{r.stderr.strip()}")
    return r


def git(repo, *args, check=True):
    return sh(["git", "-C", str(repo), *args], check=check)


def git_root(path):
    r = git(Path(path).parent, "rev-parse", "--show-toplevel", check=False)
    return Path(r.stdout.strip()) if r.returncode == 0 else None


def load_state(out):
    p = Path(out) / STATE
    if not p.is_file():
        raise SystemExit(f"no {STATE} in {out}; run `nbfix.py baseline` first")
    return json.loads(p.read_text())


def save_state(out, state):
    (Path(out) / STATE).write_text(json.dumps(state, indent=2))


def now():
    return dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def first_error(result):
    """The first cell error that is not a follow-on error, or None."""
    for e in result.get("cell_errors", []):
        if e.get("label") not in IGNORED:
            return e
    return None


def nb_key(repo_name, rel):
    return f"{repo_name}/{rel}"


def find_nb(state, key):
    if key in state["notebooks"]:
        return key, state["notebooks"][key]
    hits = [k for k in state["notebooks"] if k.endswith("/" + key) or k.endswith(key)]
    if len(hits) == 1:
        return hits[0], state["notebooks"][hits[0]]
    raise SystemExit(f"notebook {key!r} not found or ambiguous; use the key shown by `nbfix.py triage`")


def describe(result):
    e = first_error(result)
    if not e:
        return "passed"
    tb = "\n      ".join((e.get("traceback_last_lines") or "").splitlines()[-6:])
    return (f"cell {e.get('cell_number')} [{e.get('label')}] {e.get('error_name')}: "
            f"{(e.get('error_value') or '')[:300]}\n      {tb}")


def copy_report(json_path, out):
    dest = Path(out) / "tool-reports"
    dest.mkdir(parents=True, exist_ok=True)
    for p in (Path(json_path), Path(json_path).with_suffix(".md")):
        if p.is_file():
            shutil.copy2(p, dest / p.name)
    return str(dest / Path(json_path).name)


def test_root(state, nb):
    """The folder notebook-test ran for this notebook's repository in the baseline (a superproject for submodules)."""
    cfg = yaml.safe_load((Path(state["out"]) / "notebook-test-config.yml").read_text())
    for e in cfg["repos"]:
        root = Path(e["path"]) if "path" in e else Path(state["workdir"]) / "repos" / Path(e["url"].rstrip("/")).stem
        if root.name == nb["repo"]:
            return root if root.is_dir() else root.parent
    return Path(nb["git_root"]) if nb["git_root"] else Path(nb["path"]).parent


def newest_report(workdir, name):
    reports = Path(workdir) / "reports"
    hits = sorted(reports.glob(f"{name}*.json"), key=lambda p: p.stat().st_mtime)
    if not hits:
        raise SystemExit(f"notebook-test wrote no report named {name}* in {reports}")
    return hits[-1]


# ---------------------------------------------------------------- setup-check

def cmd_setup_check(a):
    problems, notes = [], []
    notes.append(f"Python {sys.version.split()[0]}")
    if not shutil.which("git"):
        problems.append("git is not installed")
    nt = shutil.which("notebook-test")
    if not nt:
        problems.append("notebook-test is not installed: pip install git+https://github.com/annaerdmann/notebook-test-automation")
    else:
        notes.append(f"notebook-test at {nt}")
    if a.environments == "build" and not any(shutil.which(t) for t in ("micromamba", "mamba", "conda")):
        problems.append("environments: build needs micromamba, mamba or conda")
    for f in CREDENTIAL_FILES:
        p = Path(f).expanduser()
        # Only existence is checked. Never read or print credential files.
        notes.append(f"{f}: {'present' if p.is_file() else 'missing'}")
    if a.profile == "wekeo" and not Path("~/.hdarc").expanduser().is_file():
        problems.append("~/.hdarc is missing: WEkEO notebooks need it for unattended login (the user creates it; never ask for the password in chat)")
    for repo in a.repo or []:
        p = Path(repo).expanduser()
        if p.exists():
            root = git_root(p / "x") if p.is_dir() else git_root(p)
            if not root:
                problems.append(f"{repo} is not inside a git repository")
                continue
            dirty = git(root, "status", "--porcelain", "--untracked-files=no").stdout.strip()
            if dirty and a.fixes == "yes":
                problems.append(f"{root} has uncommitted changes; the user must commit or stash them before fixes")
    for n in notes:
        print("  " + n)
    if problems:
        print("\nNOT READY:")
        for p in problems:
            print("  - " + p)
        return 1
    print("\nReady.")
    return 0


# ---------------------------------------------------------------- baseline

def cmd_baseline(a):
    out = Path(a.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    workdir = Path(a.workdir).expanduser().resolve()
    if (out / STATE).exists() and not a.force:
        raise SystemExit(f"{out / STATE} exists; use a new --out folder (or --force to start over)")
    entries = []
    for r in a.repo:
        p = Path(r).expanduser()
        entry = {"url": r} if not p.exists() else {"path": str(p.resolve())}
        if a.environments == "build":
            entry["environments"] = "build"
        entries.append(entry)
    cfg = {"profile": a.profile, "workdir": str(workdir), "kernel": "auto", "repos": entries}
    if a.timeout:
        cfg["timeout"] = a.timeout
    cfg_path = out / "notebook-test-config.yml"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"Running notebook-test on {len(entries)} repository(ies); this can take hours.", flush=True)
    r = subprocess.run(["notebook-test", "run", str(cfg_path), "--report-name", "baseline"])
    report = newest_report(workdir, "baseline")
    data = json.loads(report.read_text())
    state = {
        "created": now(), "out": str(out), "workdir": str(workdir), "profile": a.profile,
        "fixes": a.fixes, "env_fixes": a.env_fixes, "max_tries": a.max_tries,
        "baseline_report": copy_report(report, out), "tool_reports": [], "repos": {}, "notebooks": {},
    }
    state["tool_reports"].append(state["baseline_report"])
    for repo in data["repos"]:
        name = repo["repo"]
        base = workdir / "repos" / name if repo.get("url") else None
        for res in repo["results"]:
            if base is None:
                src = next(Path(e["path"]) for e in entries if "path" in e and Path(e["path"]).name == name)
                nb_path = (src if src.is_dir() else src.parent) / res["notebook"]
            else:
                nb_path = base / res["notebook"]
            key = nb_key(name, res["notebook"])
            state["notebooks"][key] = {
                "path": str(nb_path.resolve()), "repo": name,
                "git_root": str(git_root(nb_path) or ""),
                "baseline": res["status"], "baseline_labels": res.get("labels", {}),
                "baseline_error": describe(res), "verdict": "passed" if res["status"] == "ok" else "pending",
                "reason": "", "tries": [], "env_rerun_done": False,
            }
    save_state(out, state)
    ok = sum(n["baseline"] == "ok" for n in state["notebooks"].values())
    print(f"\nBaseline: {ok} of {len(state['notebooks'])} notebooks passed. State: {out / STATE}")
    print(f"Tool report: {state['baseline_report']}")
    return 0 if r.returncode in (0, 1) else r.returncode


# ---------------------------------------------------------------- triage

def classify(state, nb):
    """('fix', '') or ('not_fixable', reason) from the latest result's first real error."""
    labels = nb.get("current_first_label") or nb.get("baseline_first_label")
    if labels in NOT_FIXABLE:
        return "not_fixable", NOT_FIXABLE[labels]
    if labels in ENV_LABELS and state["env_fixes"] != "yes":
        return "not_fixable", ENV_LABELS[labels]
    return "fix", ""


def cmd_triage(a):
    state = load_state(a.out)
    report = json.loads(Path(state["baseline_report"]).read_text())
    by_key = {nb_key(r["repo"], res["notebook"]): res for r in report["repos"] for res in r["results"]}
    fix, nofix, passed = [], [], []
    for key, nb in state["notebooks"].items():
        if nb["baseline"] == "ok":
            passed.append(key)
            continue
        e = first_error(by_key[key])
        nb["baseline_first_label"] = e.get("label") if e else None
        if nb["verdict"] == "pending":
            kind, reason = classify(state, nb)
            if kind == "not_fixable":
                nb["verdict"], nb["reason"] = "not_fixable", reason
        (fix if nb["verdict"] == "pending" else nofix).append(key)
    save_state(a.out, state)
    print(f"Passed in the baseline ({len(passed)}), never rerun:")
    for k in passed:
        print(f"  ✔ {k}")
    print(f"\nNot fixable ({len(nofix)}):")
    for k in nofix:
        print(f"  ✖ {k}: {state['notebooks'][k]['reason']}")
    print(f"\nTo fix ({len(fix)}){'' if state['fixes'] == 'yes' else ' (fixes not requested: report only)'}:")
    for k in fix:
        print(f"  • {k}\n      {state['notebooks'][k]['baseline_error']}")
    return 0


# ---------------------------------------------------------------- branch

def cmd_branch(a):
    state = load_state(a.out)
    if state["fixes"] != "yes":
        raise SystemExit("fixes were not requested (baseline --fixes no); nothing to branch")
    # Running `branch` again (e.g. the next day) keeps the branch created first.
    known = [info["branch"] for info in state["repos"].values()]
    name = a.name or (known[0] if known else f"notebook-test-fixes/{dt.date.today().isoformat()}")
    pending = [nb for nb in state["notebooks"].values() if nb["verdict"] == "pending" and nb["git_root"]]
    roots = {nb["git_root"] for nb in pending}
    if state["env_fixes"] == "yes":
        # A notebook in a submodule can use the superproject's environment file: branch that repository too.
        for nb in pending:
            env = env_file_for(nb["path"], test_root(state, nb))
            if env and git_root(env):
                roots.add(str(git_root(env)))
    roots = sorted(roots)
    for root in roots:
        if root in state["repos"]:
            continue
        cur = git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        head = git(root, "rev-parse", "HEAD").stdout.strip()
        if cur != name:
            exists = git(root, "rev-parse", "--verify", "--quiet", name, check=False).returncode == 0
            git(root, "switch", name) if exists else git(root, "switch", "-c", name)
        upstream = remote_url(root)
        state["repos"][root] = {"branch": name, "base_commit": head, "base_branch": cur, "remote": upstream}
        print(f"  {root}: branch {name} (from {cur} {head[:7]}){'  upstream ' + upstream if upstream else ''}")
    save_state(a.out, state)
    print("No commit was made. The user reviews, commits and opens the pull requests.")
    return 0


def remote_url(root):
    r = git(root, "remote", "get-url", "origin", check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


# ---------------------------------------------------------------- rerun

def env_file_for(nb_path, root):
    folder = Path(nb_path).parent
    root = Path(root)
    while True:
        for n in ("environment.yml", "environment.yaml"):
            if (folder / n).is_file():
                return folder / n
        if folder == root or root not in folder.parents:
            return None
        folder = folder.parent


def env_changed(state, nb):
    if not nb["git_root"]:
        return None
    # Search up to the folder notebook-test ran on: in a submodule, the environment can be the superproject's.
    env = env_file_for(nb["path"], test_root(state, nb))
    if env and git(git_root(env), "diff", "--quiet", "HEAD", "--", str(env), check=False).returncode == 1:
        return env
    return None


def run_one(state, nb, name):
    """Run one notebook with notebook-test, with the same environment lookup as the baseline."""
    root = test_root(state, nb)
    if not nb["git_root"] or Path(nb["git_root"]) == root:
        return subprocess.run(["notebook-test", "run", "--path", nb["path"], "--workdir", state["workdir"],
                               "--profile", state["profile"], "--kernel", "auto", "--report-name", name])
    # In a submodule, `--path NOTEBOOK` would only look for environment files inside the submodule.
    # Run the baseline folder instead and skip every other notebook.
    rel = os.path.relpath(nb["path"], root)
    skip = [k.split("/", 1)[1] for k, o in state["notebooks"].items() if o["repo"] == nb["repo"] and o is not nb]
    cfg = {"profile": state["profile"], "workdir": state["workdir"], "kernel": "auto",
           "repos": [{"path": str(root), "environments": "build", "skip": [glob_escape(s) for s in skip]}]}
    cfg_path = Path(state["out"]) / f"rerun-config-{re.sub(r'[^A-Za-z0-9]+', '-', rel)[-60:]}.yml"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    try:
        return subprocess.run(["notebook-test", "run", str(cfg_path), "--report-name", name])
    finally:
        cfg_path.unlink()


def glob_escape(s):
    return re.sub(r"([*?\[])", r"[\1]", s)


def cmd_rerun(a):
    state = load_state(a.out)
    key, nb = find_nb(state, a.notebook)
    after_env = False
    if nb["baseline"] == "ok":
        env = env_changed(state, nb)
        if not (a.after_env_change and env and not nb["env_rerun_done"]):
            raise SystemExit(f"{key} passed in the baseline and is not rerun"
                             + ("" if env else " (its environment file is unchanged)"))
        after_env = True
    elif nb["verdict"] in ("not_fixable", "gave_up", "fixed"):
        raise SystemExit(f"{key} is already '{nb['verdict']}'; not rerun")
    elif len(nb["tries"]) >= state["max_tries"]:
        nb["verdict"], nb["reason"] = "gave_up", f"still failing after {state['max_tries']} tries"
        save_state(a.out, state)
        raise SystemExit(f"{key}: limit of {state['max_tries']} tries reached; marked gave_up")
    if not a.note and not after_env:
        raise SystemExit("--note is required: say in one line what you changed")
    n = len(nb["tries"]) + 1
    name = f"rerun-{re.sub(r'[^A-Za-z0-9]+', '-', key).strip('-')[-60:]}-{'env' if after_env else n}"
    what = "after environment change" if after_env else f"try {n} of {state['max_tries']}"
    print(f"Rerunning {key} ({what})", flush=True)
    run_one(state, nb, name)
    report = newest_report(state["workdir"], name)
    data = json.loads(report.read_text())
    res = data["repos"][0]["results"][0]
    state["tool_reports"].append(copy_report(report, a.out))
    e = first_error(res)
    entry = {"n": n, "at": now(), "note": a.note or "rerun after environment change",
             "status": res["status"], "labels": res.get("labels", {}), "error": describe(res),
             "report": state["tool_reports"][-1]}
    if after_env:
        nb["env_rerun_done"] = True
        nb.setdefault("env_reruns", []).append(entry)
        if res["status"] != "ok":
            nb["verdict"], nb["reason"] = "broken_by_env_change", describe(res)
        print(f"  {'✔ still passes' if res['status'] == 'ok' else '✖ FAILS after the environment change: ' + describe(res)}")
        save_state(a.out, state)
        return 0
    nb["tries"].append(entry)
    nb["current_first_label"] = e.get("label") if e else None
    if res["status"] == "ok":
        nb["verdict"] = "fixed"
        print("  ✔ passes now. Verdict: fixed.")
    else:
        kind, reason = classify(state, nb)
        if kind == "not_fixable":
            nb["verdict"], nb["reason"] = "not_fixable", reason
            print(f"  ✖ stops: {reason}. Verdict: not fixable.\n      {describe(res)}")
        elif n >= state["max_tries"]:
            nb["verdict"], nb["reason"] = "gave_up", f"still failing after {state['max_tries']} tries"
            print(f"  ✖ limit of {state['max_tries']} tries reached. Verdict: gave up.\n      {describe(res)}")
        else:
            print(f"  ✖ still failing ({state['max_tries'] - n} tries left):\n      {describe(res)}")
    save_state(a.out, state)
    return 0


# ---------------------------------------------------------------- mark

def cmd_mark(a):
    state = load_state(a.out)
    key, nb = find_nb(state, a.notebook)
    if nb["baseline"] == "ok":
        raise SystemExit(f"{key} passed; nothing to mark")
    nb["verdict"], nb["reason"] = "not_fixable", a.reason
    if a.candidates:
        nb["candidates"] = a.candidates
    save_state(a.out, state)
    print(f"{key}: not fixable – {a.reason}")
    return 0


def cmd_revert(a):
    state = load_state(a.out)
    key, nb = find_nb(state, a.notebook)
    if not nb["git_root"]:
        raise SystemExit(f"{key} is not in a git repository")
    git(nb["git_root"], "checkout", "HEAD", "--", nb["path"])
    print(f"{key}: reverted to the committed version")
    return 0


# ---------------------------------------------------------------- changed notebooks

def changed_files(root):
    # Submodules are separate entries in state["repos"]; do not list them as changed files of the superproject.
    r = git(root, "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=all")
    files = []
    for line in r.stdout.splitlines():
        path = line[3:].split(" -> ")[-1].strip('"')
        files.append(Path(root) / path)
    return files


def head_notebook(root, path):
    rel = os.path.relpath(path, root)
    r = git(root, "show", f"HEAD:{rel}", check=False)
    return nbformat.reads(r.stdout, as_version=4) if r.returncode == 0 else None


def cell_key(cell):
    return cell.get("id") or None


def changed_cells(old, new):
    """Indices of cells in `new` whose source differs from the matching cell in `old` (by id, else position)."""
    old_by_id = {c.get("id"): c for c in old.cells if c.get("id")} if old else {}
    out = []
    for i, c in enumerate(new.cells):
        ref = old_by_id.get(cell_key(c)) if cell_key(c) else (old.cells[i] if old and i < len(old.cells) else None)
        if ref is None or ref.source != c.source or ref.cell_type != c.cell_type:
            out.append(i)
    return out


def json_indent(raw):
    """Indentation of a JSON file (the spaces before its first key)."""
    m = re.match(r'\{\n( +)"', raw)
    return len(m.group(1)) if m else 1


def cmd_clear_outputs(a):
    state = load_state(a.out)
    total = 0
    for root in state["repos"]:
        for f in changed_files(root):
            if f.suffix != ".ipynb" or not f.is_file():
                continue
            old, new = head_notebook(root, f), nbformat.read(f, as_version=4)
            idx = [i for i in changed_cells(old, new) if new.cells[i].cell_type == "code"]
            if idx:
                # Edit the JSON as it is and keep its layout: nbformat.write would re-indent the whole file
                # (e.g. 4 spaces -> 1) and bury the real change in the diff.
                raw = f.read_text(encoding="utf-8")
                data = json.loads(raw)
                for i in idx:
                    data["cells"][i]["outputs"] = []
                    data["cells"][i]["execution_count"] = None
                f.write_text(json.dumps(data, indent=json_indent(raw), ensure_ascii=False)
                             + ("\n" if raw.endswith("\n") else ""), encoding="utf-8")
                total += len(idx)
                print(f"  {os.path.relpath(f, root)}: cleared outputs of {len(idx)} changed cell(s)")
    print(f"Cleared {total} cell output(s). Other stored outputs are unchanged.")
    return 0


HIDE_RE = re.compile(r"except[^:\n]*:\s*(\n\s*)?(pass|continue|\.\.\.)\b")
SCIENCE_RE = re.compile(r"\b(bbox|bounding|lat|lon|latitude|longitude|start|end|date|time|variable|product_type|threshold|resolution)\b", re.I)
DOWNLOAD_RE = re.compile(r"(download|retrieve|search\(|open_dataset|open_mfdataset|requests\.get|hda\.|Client\()", re.I)
SECRET_RE = re.compile(r"(eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}|access_token[\"']?\s*[:=]\s*[\"'][A-Za-z0-9._-]{16,}|password\s*=\s*[\"'][^\"'<>{}]{4,}[\"'])")


def review_notebook(root, f):
    flags = []
    old, new = head_notebook(root, f), nbformat.read(f, as_version=4)
    if old is None:
        return [f"new notebook {os.path.relpath(f, root)}: fixes must not add notebooks"]
    old_code = [c for c in old.cells if c.cell_type == "code"]
    new_code = [c for c in new.cells if c.cell_type == "code"]
    if len(new_code) < len(old_code):
        flags.append(f"{len(old_code) - len(new_code)} code cell(s) removed (forbidden unless the cell was an exact duplicate)")
    new_ids = {c.get("id") for c in new.cells}
    for c in old_code:
        if c.get("id") and c.get("id") not in new_ids:
            flags.append(f"cell removed: {c.source.strip().splitlines()[0][:80] if c.source.strip() else '(empty)'}")
    old_by_id = {x.get("id"): x for x in old.cells if x.get("id")}
    for i in changed_cells(old, new):
        c = new.cells[i]
        # Same matching as changed_cells: by id, else by position (notebooks before nbformat 4.5 have no ids).
        ref = old_by_id.get(c.get("id")) if c.get("id") else (old.cells[i] if i < len(old.cells) else None)
        before = ref.source if ref is not None else ""
        if HIDE_RE.search(c.source) and not HIDE_RE.search(before):
            flags.append(f"cell {i + 1}: new except that swallows the error (forbidden)")
        removed = set(before.splitlines()) - set(c.source.splitlines())
        added = set(c.source.splitlines()) - set(before.splitlines())
        if any(DOWNLOAD_RE.search(l) for l in removed) and not any(DOWNLOAD_RE.search(l) for l in added):
            flags.append(f"cell {i + 1}: a download or data access line was removed (forbidden)")
        sci = [l.strip() for l in removed if SCIENCE_RE.search(l)]
        if sci:
            flags.append(f"cell {i + 1}: changed scientific parameters, check they mean the same: {sci[0][:100]}")
        if re.search(r"^\s*#.*$", "\n".join(added), re.M) and all(l.strip().startswith("#") for l in added if l.strip()) and removed:
            flags.append(f"cell {i + 1}: code was commented out (forbidden)")
        if SECRET_RE.search(c.source) or any(SECRET_RE.search(json.dumps(o)) for o in c.get("outputs", [])):
            flags.append(f"cell {i + 1}: looks like a secret (token or password)")
    for i, c in enumerate(new.cells):
        if c.cell_type == "code" and any(SECRET_RE.search(json.dumps(o)) for o in c.get("outputs", [])):
            flags.append(f"cell {i + 1}: stored output looks like a secret")
    return flags


def cmd_check_diff(a):
    state = load_state(a.out)
    found = 0
    for root in state["repos"]:
        for f in changed_files(root):
            rel = os.path.relpath(f, root)
            if f.suffix == ".ipynb" and f.is_file():
                flags = review_notebook(root, f)
            elif f.name.startswith("environment.") and state["env_fixes"] != "yes":
                flags = ["environment file changed although environment fixes are not allowed"]
            elif f.name.startswith("environment.") or not f.exists():
                flags = [] if f.exists() else ["file deleted (forbidden)"]
            else:
                flags = [f"other file changed: {rel} (only notebooks and environment files may change)"]
            for fl in flags:
                print(f"  ⚠ {rel}: {fl}")
            found += len(flags)
    print(f"{found} point(s) to review." if found else "No suspicious edits found.")
    return 1 if found else 0


# ---------------------------------------------------------------- summary

VERDICT_TEXT = {
    "passed": "passed (not rerun)", "fixed": "fixed", "not_fixable": "not fixable by the LLM",
    "gave_up": "still failing after the try limit", "pending": "not worked on",
    "broken_by_env_change": "broke after an environment change",
}


def cmd_summary(a):
    state = load_state(a.out)
    out = Path(a.out)
    nbs = state["notebooks"]
    counts = {}
    for nb in nbs.values():
        counts[nb["verdict"]] = counts.get(nb["verdict"], 0) + 1
    problems = []
    for root, info in state["repos"].items():
        head = git(root, "rev-parse", "HEAD").stdout.strip()
        if head != info["base_commit"]:
            problems.append(f"{root}: HEAD moved from {info['base_commit'][:7]} to {head[:7]} (no commits allowed)")
    lines = [f"# Notebook test and fixes – {dt.date.today().isoformat()}", "",
             f"Profile `{state['profile']}`, fixes: {state['fixes']}, environment fixes: {state['env_fixes']}, "
             f"max {state['max_tries']} tries per notebook.", "",
             "| Result | Notebooks |", "|---|---|"]
    for v in ("passed", "fixed", "not_fixable", "gave_up", "broken_by_env_change", "pending"):
        if counts.get(v):
            lines.append(f"| {VERDICT_TEXT[v]} | {counts[v]} |")
    if problems:
        lines += ["", "**Problems:**"] + [f"- {p}" for p in problems]
    lines += ["", "## Per notebook", ""]
    for key, nb in sorted(nbs.items()):
        lines.append(f"### {key}")
        lines.append(f"- Baseline: {'passed' if nb['baseline'] == 'ok' else nb['baseline_error'].splitlines()[0]}")
        lines.append(f"- Result: **{VERDICT_TEXT[nb['verdict']]}**" + (f" – {nb['reason']}" if nb["reason"] else ""))
        for t in nb["tries"]:
            lines.append(f"- Try {t['n']}: {t['note']} → {'passed' if t['status'] == 'ok' else t['error'].splitlines()[0]}")
        for t in nb.get("env_reruns", []):
            lines.append(f"- Rerun after environment change: {'passed' if t['status'] == 'ok' else t['error'].splitlines()[0]}")
        if nb.get("candidates"):
            lines.append(f"- Candidates for the owner: {', '.join(nb['candidates'])}")
        lines.append("")
    lines += ["## Tool reports", ""] + [f"- `{os.path.relpath(p, out)}`" for p in state["tool_reports"]]
    review = []
    if state["repos"]:
        (out / "diffs").mkdir(exist_ok=True)
        (out / "pr").mkdir(exist_ok=True)
        lines += ["", "## Branches (not committed)", ""]
        for root, info in state["repos"].items():
            name = Path(root).name
            files = changed_files(root)
            if not files:
                # A branch without changes needs no diff and no pull request.
                lines.append(f"- `{root}` on `{info['branch']}`: no changes (the branch can be deleted)")
                continue
            diff = git(root, "diff", "--ignore-submodules=all", "HEAD").stdout
            (out / "diffs" / f"{name}.diff").write_text(diff)
            for f in files:
                if f.suffix == ".ipynb" and f.is_file():
                    review += [f"{name}/{os.path.relpath(f, root)}: {x}" for x in review_notebook(root, f)]
            lines.append(f"- `{root}` on `{info['branch']}`: {len(files)} changed file(s), diff in `diffs/{name}.diff`"
                         + (f", upstream {info['remote']}" if info["remote"] else ""))
            (out / "pr" / f"{name}.md").write_text(pr_text(state, root, info, files))
    for key, nb in nbs.items():
        if nb["verdict"] != "fixed" and nb["git_root"] in state["repos"] and \
                Path(nb["path"]).resolve() in {f.resolve() for f in changed_files(nb["git_root"])}:
            review.append(f"{key}: changed but not fixed ({VERDICT_TEXT[nb['verdict']]}); keep only if the change "
                          f"fixes a real error on its own, else `nbfix.py revert`")
    if review:
        lines += ["", "## Points to review before committing", ""] + [f"- {r}" for r in review]
    (out / "fix-report.md").write_text("\n".join(lines) + "\n")
    (out / "fix-report.json").write_text(json.dumps({"generated": now(), **state, "problems": problems,
                                                     "review": review}, indent=2))
    print(f"Wrote {out / 'fix-report.md'}" + (f", PR texts in {out / 'pr'}" if state["repos"] else ""))
    for p in problems:
        print("  PROBLEM: " + p)
    return 1 if problems else 0


def fixed_by(state, nb, changed):
    """True if one of the changed files fixed this notebook: the notebook itself or its environment file."""
    if Path(nb["path"]).resolve() in changed:
        return True
    env = env_file_for(nb["path"], test_root(state, nb))
    return bool(env) and env.resolve() in changed


def fix_note(nb):
    """The notes of the tries whose changes made the notebook pass; superseded tries are left out."""
    notes, before, prev = [], nb["baseline_error"].splitlines()[0], ""
    for x in nb["tries"]:
        after = "passed" if x["status"] == "ok" else x["error"].splitlines()[0]
        note = x.get("note") or ""
        # A "same change; ..." retry repeats the previous try's change: list that change once.
        if note.lower().startswith("same change"):
            note = prev
        # A try that left the same first error did not help and was undone (superseded by a later try).
        if after != before and note and note not in notes:
            notes.append(note)
        before, prev = after, note
    return "; ".join(notes) or "fixed"


def pr_text(state, root, info, files):
    # The PR lists only what it fixes; remaining errors stay in fix-report.md.
    # A notebook is credited to the repository whose changes fixed it, e.g. a submodule notebook
    # fixed through the superproject's environment file goes to the superproject's PR.
    changed = {f.resolve() for f in files}
    fixed = [(k, nb) for k, nb in state["notebooks"].items()
             if nb["verdict"] == "fixed" and fixed_by(state, nb, changed)]
    t = [f"Before: {'this notebook' if len(fixed) == 1 else f'these {len(fixed)} notebooks'} failed in the "
         f"automated notebook test (notebook-test, profile `{state['profile']}`).", "",
         f"After: {'it runs' if len(fixed) == 1 else 'they run'} without errors.", "", "Fixes:"]
    for k, nb in fixed:
        t.append(f"- `{k.split('/', 1)[1]}`: {fix_note(nb)}")
    if not fixed:
        t[:4] = []
        t += [f"- `{os.path.relpath(f, root)}`: changed" for f in files]
    if any(f.suffix == ".ipynb" for f in files):
        t += ["", "Outputs of changed cells were cleared; all other stored outputs are unchanged."]
    return "\n".join(t) + "\n"


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(prog="nbfix.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("setup-check")
    p.add_argument("--repo", action="append", help="local clone (or URL; URLs are only noted)")
    p.add_argument("--profile", default="wekeo")
    p.add_argument("--fixes", choices=["yes", "no"], default="no")
    p.add_argument("--environments", choices=["build", "none"], default="build")
    p.set_defaults(func=cmd_setup_check)

    p = sub.add_parser("baseline")
    p.add_argument("--repo", action="append", required=True, help="repository URL or local clone (repeatable)")
    p.add_argument("--out", required=True, help="folder for the state, reports and hand-over")
    p.add_argument("--workdir", default="~/notebook-test-work", help="notebook-test work folder")
    p.add_argument("--profile", default="wekeo")
    p.add_argument("--fixes", choices=["yes", "no"], required=True)
    p.add_argument("--env-fixes", choices=["yes", "no"], default="no")
    p.add_argument("--max-tries", type=int, default=DEFAULT_MAX_TRIES)
    p.add_argument("--environments", choices=["build", "none"], default="build")
    p.add_argument("--timeout", type=int, help="seconds per cell")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_baseline)

    for name, func in (("triage", cmd_triage), ("clear-outputs", cmd_clear_outputs),
                       ("check-diff", cmd_check_diff), ("summary", cmd_summary)):
        p = sub.add_parser(name)
        p.add_argument("--out", required=True)
        p.set_defaults(func=func)

    p = sub.add_parser("branch")
    p.add_argument("--out", required=True)
    p.add_argument("--name", help="branch name (default notebook-test-fixes/YYYY-MM-DD)")
    p.set_defaults(func=cmd_branch)

    p = sub.add_parser("rerun")
    p.add_argument("--out", required=True)
    p.add_argument("notebook", help="key from triage (repo/path.ipynb) or a unique end of it")
    p.add_argument("--note", help="one line: what was changed before this rerun")
    p.add_argument("--after-env-change", action="store_true",
                   help="rerun a notebook that passed, once, because its environment file changed")
    p.set_defaults(func=cmd_rerun)

    p = sub.add_parser("revert", help="undo all changes to one notebook")
    p.add_argument("--out", required=True)
    p.add_argument("notebook")
    p.set_defaults(func=cmd_revert)

    p = sub.add_parser("mark")
    p.add_argument("--out", required=True)
    p.add_argument("notebook")
    p.add_argument("--reason", required=True)
    p.add_argument("--candidates", nargs="*", help="e.g. possible new dataset IDs for the owner to choose")
    p.set_defaults(func=cmd_mark)

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
