# Prompt C — delta audit (use after the revision batches land)

Paste into a **fresh** Copilot chat with the revised `sfc.pdf`,
`sfc_appendix.pdf`, the prior review (`copilot_A_round3.md` **or**
`copilot_B_round3.md` — run one audit per report, in separate chats),
`triage_round3.md` and `changelog_round3.md` attached. Optionally also
`probe_horizon_budget.py`, which one item's evidence rests on.

A fresh chat matters here as much as it did for the original passes: a
conversation that remembers writing a finding tends to accept the fix as
adequate rather than re-read the manuscript.

---

A prior review of this manuscript identified numbered issues. The attached
package contains: (1) the revised manuscript and appendix, (2) that review,
(3) the authors' triage of it, and (4) a change log mapping each edit to
review IDs.

**Audit the revision only.** Do not produce a fresh general review.

**Changed text is marked.** Every passage altered in this revision is
typeset in dark red. Unmarked text is unchanged from the version you
reviewed, so the red is a complete map of what to check — but a repair can
still break something in unmarked text, and the regression checks below
apply to the whole manuscript.

**Three things the change log will show that the prior review did not
anticipate**, all of which are in scope for this audit:

1. One item was answered with **new measurements rather than a wording
   change**, contradicting the prior review's assertion that the required
   experiment did not exist. The numbers come from released results files
   plus a confirming re-run, and a probe script reproducing them is released
   with the paper. Judge the evidence rather than the earlier premise; if
   you still find it insufficient, say so and say what is missing.
2. The revision **adds a limitation the prior review did not raise** — a
   disclosure in the Methodology about one instance whose result depends on
   a wall-clock budget. Audit it as you would any other passage. It is the
   place a sceptical reader is most likely to push.
3. One item was **rejected on the grounds that the manuscript does not say
   what the review attributed to it**. Check the manuscript text before
   accepting or contesting that.

For **each** prior issue, return exactly one status:

`RESOLVED` | `PARTIALLY_RESOLVED` | `NOT_RESOLVED` | `REJECTED_WITH_JUSTIFICATION`

Use `REJECTED_WITH_JUSTIFICATION` where the authors declined the item and
gave a reason in the triage; state in one line whether you accept the reason.
Where an item was marked `NEEDS_EVIDENCE` and the evidence was not produced,
the correct status is `NOT_RESOLVED`, not `REJECTED` — say what remains
outstanding.

For every `RESOLVED` and `PARTIALLY_RESOLVED` item, verify that the repair
does not:

- introduce a new overclaim, or move an old one to a new location;
- contradict another section, theorem, table or figure;
- claim evidence the manuscript does not contain;
- leave the abstract or conclusion inconsistent with the body;
- orphan a cross-reference, or leave a pointer to material that moved.

Disagreement is useful: a status of `NOT_RESOLVED` or a contested
justification is a more valuable output than an accepted fix, and nothing
above is an argument that the repairs are adequate.

Then identify **at most five** genuinely new high-impact issues introduced by
the revision or newly visible because of it. Do not repeat cosmetic edits and
do not re-open items you previously raised and the authors resolved.

Return a Markdown table with columns:

`ID | status | location in revised text | verification note | residual risk`

followed by the new-issues section in the same per-issue format as the
original review. Markdown only.
