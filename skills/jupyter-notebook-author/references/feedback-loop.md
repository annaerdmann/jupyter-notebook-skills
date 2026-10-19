# Feedback loop: learning from the author's edits

The skill improves when authors correct its notebooks. Each correction is a candidate rule. Only rules the author confirms are recorded.

## Steps

1. **Get both versions:** the notebook as you handed it over, and the author's edited version. Keep your original; do not overwrite it.
2. **Diff them:**
   ```bash
   python scripts/diff_notebooks.py original.ipynb edited.ipynb --out diff.md
   ```
   The report lists added, removed, moved and changed cells, with a text diff for changed cells and a word-level summary for Markdown.
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
