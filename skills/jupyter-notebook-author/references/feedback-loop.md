# Feedback loop: learning from the author's edits

The skill improves when authors correct its notebooks. Each correction is a candidate rule. Only rules the author confirms are recorded.

Feedback comes in two forms:
- **An edited notebook**: follow "Steps" below.
- **A written list of requests** (a message, a document, review comments): follow "Written feedback" first, then steps 3 to 7.

## Written feedback

1. **Keep the delivered round unchanged.** Rounds live in folders next to each other: `round1/`, `round2/`, … Copy `roundN/` to `roundN+1/` and work only in the new folder.
2. **Number the requests** as the author wrote them. Ask only about requests that are unclear or conflict with each other or with a learned rule.
3. **Apply them**, then run phases 5 and 6 again in `roundN+1/` (fresh environment from the delivered file, run in place, checks, fact-check of changed text).
4. **Write `changes.md`** in `roundN+1/`, one row per request:

   | # | Request | Before | After | Cells |
   |---|---|---|---|---|
   | 1 | Use `data/` paths | `../../input/data/x.nc` | `data/x.nc` | 3, 8 |
   | 2 | Explain true solar time | (none) | three sentences | 12 |

   Mark a request "partly" or "not done" and say why (for example: needs a service that is unreachable). Add a section "Other changes" for anything you changed beyond the requests.
5. **Diff the rounds for the record:**
   ```bash
   python scripts/diff_notebooks.py round1/notebook.ipynb round2/notebook.ipynb --out round2/diff_round1_round2.md
   ```
6. Continue with step 3 below: each request is a candidate rule.

## Steps

1. **Get both versions:** the notebook as you handed it over, and the author's edited version. Keep your original; do not overwrite it.
2. **Diff them:**
   ```bash
   python scripts/diff_notebooks.py original.ipynb edited.ipynb --out diff.md
   ```
   Cells are paired by content, not by position. The report lists changed cells with a text diff, moved cells, merged cells (old text now inside another cell), and added and removed cells.
3. **Classify each change** as style, code or text. Ignore changes that only reflect the specific content (a different dataset date) unless the author says otherwise.
4. **Turn changes into general rules.** One rule per pattern, in the imperative, with a short example:
   - Edit: "We will now load the data." → "Open the dataset with `xarray`."
     Rule (text): "Start step descriptions with the action verb; no 'we will'."
   - Edit: plotting cell split in two, first computes, second plots.
     Rule (code): "Separate computation and plotting into two cells."
   - Edit: author removed the 'Contents' list.
     Ask: is this a rule for all notebooks, or only this one?
5. **Ask the author** to confirm, change or reject each proposed rule. Present them as a numbered list so they can answer "keep 1, 3; drop 2".
6. **Record confirmed rules** in `references/learned-rules.md` under the right heading, with the date and a one-line example. Do not record names of people.
7. **Apply** the new rules from the next notebook on. If a learned rule contradicts a general guideline, the learned rule wins.

## During a test session

When several test notebooks are created in a row:
- Keep a list of open rule proposals across notebooks.
- If the same edit appears in two or more notebooks, say so: it is a stronger candidate.
- At the end, give one consolidated list for confirmation.
