# Paper sections

`../sfc.tex` is now a driver: preamble, title block, `\input` lines, bibliography.
Everything between the title and the bibliography lives here, one file per section.

| file | section |
|------|---------|
| `00-abstract.tex` | Abstract + IEEE keywords |
| `01-introduction.tex` | I. Introduction |
| `02-background.tex` | II. Model, Primitives, and Problem Formulation |
| `03-porter-compiler.tex` | III. The PORTER Compiler (single routing pass only) |
| `04-methodology.tex` | IV. Experimental Methodology (RQs, protocols, budgets, metrics) |
| `05-results.tex` | V. Results, organised RQ1-RQ4 (holds all five data tables) |
| `06-discussion.tex` | VI. Discussion and Limitations (incl. threats to validity) |
| `07-related-work.tex` | VII. Related Work |
| `08-conclusion.tex` | VIII. Conclusion |
| `09-acknowledgments.tex` | Acknowledgments (starred) |

Two boundaries are deliberate and worth preserving:

- **Section III describes one routing pass.** The multi-pass protocols
  (horizon selection, backward refinement, the gamma-search) are
  evaluation-time strategies that invoke the router repeatedly, so they live
  in `04-methodology.tex`, not in the algorithm.
- **Section III states no results.** Numbers, win/loss records and
  forward references to outcomes belong in `05-results.tex`; interpretation
  that spans several results belongs in `06-discussion.tex`.

## Revising or replacing a section

Edit or overwrite the file. Nothing else needs to change — section numbering,
`\ref`s and appendix letters all resolve at compile time. To drop or reorder a
section, edit only the `\input` lines in `../sfc.tex`.

Three things to keep in mind:

- **Macros stay in the driver.** `\PORTER`, `\dSABRE`, `\TeleData`, `\appTables`
  and the rest are defined in `../sfc.tex`'s preamble, so a section file is not
  independently compilable. Draft against the whole document.
- **Cross-references span files.** A `\label` in one section is fair game for a
  `\ref` in another; LaTeX resolves them on the second pass. If you delete a
  section, grep the others for `\ref`s into it first.
- **Appendix letters are hardcoded**, but main-paper numbers are not. `\app*`
  in the driver's preamble map to `../sfc_appendix.tex`'s section order (A–I),
  so re-check them if that file gains or reorders a section. The reverse
  direction is automatic: the appendix reads `sfc.aux` through `xr`, so
  renumbering the main paper needs no edits there — but compile `sfc.tex`
  before `sfc_appendix.tex`, or its cross-references render as `??`.

## After editing, always

```bash
python verify_paper_numbers.py && python verify_tex_tables.py
```

The first checks what the paper is *supposed* to say against the results JSONs;
the second parses the LaTeX rows that will actually typeset, concatenating
`../sfc.tex` with every `*.tex` here, so a table found in any section is checked.
Neither catches stale *prose*: a number in a sentence is only guarded if it has
an explicit check in `verify_paper_numbers.py`. Add one when you write one.

`gen_tables_selection.py` regenerates the data tables in place; it locates each
by `\label`, so tables may move between sections freely. It is a no-op when the
tables are current, which makes `--write` a safe way to check they are.
