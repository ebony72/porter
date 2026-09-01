# Prompt B — editorial / readability

Paste into a **second, separate, fresh** Copilot chat — not a follow-up to
Chat A — with the same four files attached. Fresh context matters: a second
pass inside the same conversation defends its first reading instead of
re-reading the paper.

---

Act as a specialist scientific editor reading this manuscript for the first
time. Four files are attached: the manuscript, its appendix, a paper brief,
and a list of findings settled in two prior review rounds.

Focus **only** on:

- the abstract, introduction, related work and contribution framing;
- logical flow between and within sections;
- undefined notation, terminology introduced after first use, and symbols
  carrying two meanings;
- ambiguous antecedents — pronouns and phrases like "that gap", "the two",
  "this result" whose referent is several paragraphs away or genuinely
  ambiguous;
- consistency between prose, algorithms, figures, tables and conclusions;
- claims whose stated basis in one place does not match the basis they are
  quoted on in another;
- overclaiming, under-hedging, and academic English.

**Do not** assess novelty beyond what is visible in the manuscript. **Do
not** rewrite whole sections. **Do not** verify numbers — they are machine-
checked. **Do not** re-report anything in Sections A–D of
`resolved_findings.md`; that list also names the vocabulary already
deliberately removed, so do not suggest restoring it.

Two specific things this manuscript is prone to, from its revision history —
please check for them explicitly:

- **Orphaned or stale cross-references**: a section that promises something
  another section no longer says, or a pointer left behind after material
  moved. The paper has an appendix (A–K) reached only through the main text.
- **Counts that went stale when a basis narrowed.** Percentages usually
  survive a change of basis; counts ("two instances", "five circuits",
  "all but one") usually do not.

## For each issue report

`severity | exact location | issue | reader impact | minimal revision direction`

Severity is Major / Moderate / Minor. Location must be section and page, and
the identifier of any table, figure or equation involved. "Reader impact" is
what a reader concretely misunderstands or has to re-read — not a restatement
of the issue.

## Then give

1. A proposed one-sentence contribution statement, in your own words, from
   the manuscript alone. (The authors will compare it against what they
   intended; a mismatch is itself the finding.)
2. The **ten** sentences or passages most worth rewriting, quoted, each with
   one line on why.
3. An abstract-specific critique: whether it is self-contained, whether every
   figure in it has a stated basis, and whether its claims match the body's.
4. A judgement on **Section III** (≈3,000 words, the longest): whether a
   reader can follow the lifecycle of a plan from generation through scoring,
   commitment and preparation, and where that thread breaks if it does.

Return **Markdown only**. Give every issue a stable ID of the form `B01`,
`B02`, … so the authors can respond item by item.
