# Prompt C — delta audit (use after the revision batches land)

Paste into a **fresh** Copilot chat with the revised `sfc.pdf`,
`sfc_appendix.pdf`, the prior review (`copilot_A_round3.md` and/or
`copilot_B_round3.md`), `triage_round3.md` and `changelog_round3.md`
attached.

Not for use until the revision batches are committed.

---

A prior review of this manuscript identified numbered issues. The attached
package contains: (1) the revised manuscript and appendix, (2) that review,
(3) the authors' triage of it, and (4) a change log mapping each edit to
review IDs.

**Audit the revision only.** Do not produce a fresh general review.

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

Then identify **at most five** genuinely new high-impact issues introduced by
the revision or newly visible because of it. Do not repeat cosmetic edits and
do not re-open items you previously raised and the authors resolved.

Return a Markdown table with columns:

`ID | status | location in revised text | verification note | residual risk`

followed by the new-issues section in the same per-issue format as the
original review. Markdown only.
