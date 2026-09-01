# Review packet — Round 3

External-review protocol for the PORTER manuscript. Round 3; rounds 1 and 2
are answered in `../responses_to_reviews.md`.

**Division of labour.** Copilot/GPT-5.6 is an independent referee that
returns *structured findings*, never a rewritten manuscript. Claude Code is a
version-controlled, evidence-constrained revision engine that converts
approved findings into minimal LaTeX diffs. The author is the scientific
authority: every `NEEDS_EVIDENCE` item is the author's alone to close.

## Contents

| File | Who writes it | Who reads it |
|---|---|---|
| `paper_brief.md` | Claude Code | Copilot (grounding) |
| `resolved_findings.md` | Claude Code | Copilot (exclusion list) |
| `prompt_A_technical.md` | Claude Code | Author pastes into Copilot |
| `prompt_B_editorial.md` | Claude Code | Author pastes into Copilot |
| `copilot_A_round3.md` | Copilot, saved **verbatim** | Claude Code |
| `copilot_B_round3.md` | Copilot, saved **verbatim** | Claude Code |
| `triage_round3.md` | Claude Code (no file edits) | Author approves |
| `changelog_round3.md` | Claude Code | Copilot (delta audit) |
| `prompt_C_delta.md` | Claude Code, after triage | Author pastes into Copilot |

## The loop

1. **Claude Code** — packet built, `git tag paper-round3-pre`. *(done)*
2. **Author** — two *separate fresh* Copilot chats. Attach `sfc.pdf`,
   `sfc_appendix.pdf`, `paper_brief.md`, `resolved_findings.md`.
   Chat A: paste `prompt_A_technical.md`. Chat B: paste `prompt_B_editorial.md`.
   Save both outputs verbatim; do not summarise them.
3. **Claude Code** — triage into `triage_round3.md`, **no file edits**.
4. **Author** — approve item IDs.
5. **Claude Code** — patch in risk-ordered batches, commit after each.
6. **Author** — delta audit in Copilot with `prompt_C_delta.md`.
7. **Claude Code** — final consistency sweep.

Fresh chats in step 2 matter: a second pass inside the same conversation
defends its first reading instead of re-reading the paper.

## Build chain — run after every batch, in this order

```bash
python gen_tables_selection.py --write   # generator FIRST
python verify_tex_tables.py              # LaTeX rows vs JSON
python verify_paper_numbers.py           # prose claims vs JSON + RouterConfig
pdflatex sfc && bibtex sfc && pdflatex sfc && pdflatex sfc
pdflatex sfc_appendix && bibtex sfc_appendix && pdflatex sfc_appendix   # needs sfc.aux (xr)
```

Generator before verifiers, or a batch passes verification on a stale table.
After any prose pass also run the orphaned-label sweep and
`grep -nE "\. +[a-z]" sections/*.tex` (excluding TikZ paths, `e.g.`, `i.e.`).

## Non-negotiable rules for the revision stage

- External LLM review is unverified reviewer feedback, not ground truth.
- **A finding that contradicts a pinned number is presumptively wrong.**
  `verify_paper_numbers.py` checks claims against released JSON and the live
  `RouterConfig`; `verify_tex_tables.py` parses every table row. Disproving a
  pin requires showing the pin itself is wrong, not asserting a different value.
- Never invent citations, experimental outcomes, numerical results or proofs.
- Never alter a theorem, algorithm, numerical result or conclusion without
  flagging the scientific consequence.
- Minimal LaTeX edits; preserve labels, `\ref`s, BibTeX keys and notation.
- Compile after every batch and report warnings.
