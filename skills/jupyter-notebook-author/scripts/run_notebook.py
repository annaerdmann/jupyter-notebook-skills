#!/usr/bin/env python3
"""Execute a notebook top to bottom in a given kernel and report every failing cell.

Usage:
    python run_notebook.py NOTEBOOK.ipynb --kernel NAME [--out executed.ipynb] [--report report.md] [--timeout 1200]

Runs from the notebook's folder, continues after errors, writes the executed
notebook and <name>.run_report.md next to it (--out NOTEBOOK.ipynb executes in place).
Exit code 0 only if every cell succeeded.
"""

import argparse
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError, DeadKernelError


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("notebook")
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--out")
    ap.add_argument("--timeout", type=int, default=1200, help="seconds per cell")
    ap.add_argument("--report", help="run report path (default: next to --out)")
    a = ap.parse_args()

    path = Path(a.notebook).resolve()
    nb = nbformat.read(path, as_version=4)
    client = NotebookClient(
        nb, kernel_name=a.kernel, timeout=a.timeout, allow_errors=True,
        resources={"metadata": {"path": str(path.parent)}},
    )
    rows, start = [], time.time()
    try:
        with client.setup_kernel():
            for i, cell in enumerate(nb.cells):
                if cell.cell_type != "code":
                    continue
                t0 = time.time()
                try:
                    client.execute_cell(cell, i)
                except (CellExecutionError, DeadKernelError) as e:  # kernel death or timeout
                    rows.append((i, "error", time.time() - t0, str(e).splitlines()[0][:200]))
                    if isinstance(e, DeadKernelError):
                        break
                    continue
                errs = [o for o in cell.get("outputs", []) if o.get("output_type") == "error"]
                if errs:
                    rows.append((i, "error", time.time() - t0, f"{errs[0]['ename']}: {errs[0]['evalue']}"[:200]))
                else:
                    rows.append((i, "ok", time.time() - t0, ""))
    except Exception as e:  # kernel could not start
        print(f"Kernel '{a.kernel}' failed to start: {e}", file=sys.stderr)
        sys.exit(3)

    out = Path(a.out) if a.out else path.with_suffix(".executed.ipynb")
    # kernelspec stays as in the source (the publication kernel); the test kernel is in the report
    nbformat.write(nb, out)
    failed = [r for r in rows if r[1] != "ok"]
    report = [
        f"# Run report: `{path.name}`", "",
        f"- Kernel: `{a.kernel}`",
        f"- Code cells run: {len(rows)}, failed: {len(failed)}, total time: {time.time() - start:.0f} s",
        f"- Executed notebook: `{out}`", "",
        "| Cell | Status | Seconds | Error |", "|---|---|---|---|",
    ]
    report += [f"| {i} | {s} | {d:.1f} | {e.replace('|', '/')} |" for i, s, d, e in rows]
    stem = out.name[: -len(".ipynb")] if out.name.endswith(".ipynb") else out.stem
    stem = stem[: -len(".executed")] if stem.endswith(".executed") else stem
    rep_path = Path(a.report) if a.report else out.with_name(stem + ".run_report.md")
    rep_path.write_text("\n".join(report) + "\n")
    print("\n".join(report))
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
