# Paper sections

`../sfc.tex` is now a driver: preamble, title block, `\input` lines, bibliography.
Everything between the title and the bibliography lives here, one file per section.

| file | section |
|------|---------|
| `00-abstract.tex` | Abstract + IEEE keywords |
| `01-introduction.tex` | I. Introduction |
| `02-background.tex` | II. Background |
| `03-porter-compiler.tex` | III. The PORTER Compiler |
| `04-evaluation.tex` | IV. Experimental Evaluation (holds all five data tables) |
| `05-related-work.tex` | V. Related Work |
| `06-conclusion.tex` | VI. Conclusion |
| `07-acknowledgments.tex` | Acknowledgments (starred) |

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
- **Appendix letters are hardcoded.** `\app*` in the driver's preamble map to
  `../sfc_appendix.tex`'s section order (A–I). Re-check them if that file gains
  or reorders a section.

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
