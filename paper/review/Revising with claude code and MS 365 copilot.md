<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# I am revising a scientific paper with claude code. I want ask GPT 5.6 through microsoft 365 copilot (chat) to proofread and review, and return its review report to claude code and revise, and then send the response and revised manuscript to ms 365 copilot again. Are there more optimised protocol to use both?

Yes. Your proposed loop—**Claude Code drafts/revises → Copilot/GPT-5.6 reviews → Claude Code revises → Copilot re-reviews**—is sound, but it will be more effective if you make it an **artifact-driven, role-separated protocol** rather than passing an entire manuscript back and forth as free-form chat.

GPT‑5.6 is available in Microsoft 365 Copilot Chat, and Copilot Chat can be grounded on uploaded or OneDrive/SharePoint files; Claude Code can retain a compact project-specific workflow through `CLAUDE.md`.[^1_1][^1_2][^1_3]

## Recommended division of labour

Use each system for a deliberately different job:


| System | Primary role | Avoid using it for |
| :-- | :-- | :-- |
| **Claude Code** | Manuscript-aware editor and implementer: parses LaTeX repository, tracks cross-references/citations, applies changes as a Git diff, runs compilation and checks | Acting as the only independent reviewer |
| **GPT‑5.6 in Copilot Chat** | Independent referee/editor: identifies unclear reasoning, missing definitions, reader confusion, excessive claims, presentation issues, and likely reviewer objections | Directly rewriting the whole LaTeX source without a controlled diff |
| **You** | Scientific authority and gatekeeper: decide whether critique is valid, whether a claim is supported, and whether a change alters the technical contribution | Mechanically accepting every model suggestion |

The critical point is: **Copilot should return structured review data, not a rewritten manuscript.** Claude Code should convert selected findings into minimal, testable repository edits. That preserves authorship, change traceability, and LaTeX integrity.

## A better iterative protocol

### 0. Create a stable review packet

Keep a small set of versioned artifacts in the paper repository, for example:

```text
paper/
  main.tex
  sections/
  bibliography.bib
  figures/
  CLAUDE.md
  review/
    paper_brief.md
    review_rubric.md
    claims_ledger.md
    gpt_review_round_01.md
    triage_round_01.md
    revision_plan_round_01.md
    response_to_reviewers.md
```

Use Git tags or commits at every external-review boundary:

```bash
git tag pre-gpt-review-r1
```

This is better than treating a Copilot chat history as the record of review. Chat context is convenient but not a reproducible scholarly artifact.

### 1. Ask Claude Code to prepare the packet

Before involving Copilot, ask Claude Code to generate:

- A **paper brief**: problem, contribution, assumptions, theorem/algorithm dependencies, evaluation claims, and intended venue/audience.
- A **claims ledger**: each substantive claim; where it appears; supporting theorem, derivation, experiment, or citation; and any stated limitation.
- A **clean review copy**: preferably PDF plus a readable Word/Markdown version if your LaTeX source is awkward for Copilot.
- A **review rubric** tailored to your field.

For a quantum compilation paper, the rubric should explicitly ask about:

- Problem formalization and hardware/connectivity assumptions.
- Correctness and termination of the mapping/routing method.
- Complexity claims versus measured runtime/scaling.
- Fairness and reproducibility of baseline comparisons.
- Whether circuit families, coupling maps, noise assumptions, and metrics are adequately specified.
- Whether claimed gains are statistically or practically meaningful.
- Whether commutativity, look-ahead, deadlock resolution, or SWAP-count claims are overgeneralized.
- Threats to validity and scope boundaries.

This upfront step supplies grounding. Microsoft’s documentation specifically describes grounding on file content as a way to increase the specificity and actionability of Copilot’s answers.[^1_4][^1_5]

### 2. Run two independent Copilot passes

Do **not** start by asking “please proofread this paper.” It tends to produce broad, low-value editing and can mix technical claims with superficial style suggestions.

Run separate fresh Copilot conversations, each grounded in the manuscript and paper brief. Copilot Chat supports both file uploads and cloud-file references; for a working manuscript, use a versioned copy in OneDrive/SharePoint or upload the exact exported review copy.[^1_2][^1_6][^1_7]

#### Pass A: technical referee report

Use a strict evidence requirement:

```text
You are an exacting reviewer for a quantum computing / circuit compilation venue.

Review the attached manuscript and paper brief as an independent technical referee.
Do not rewrite the manuscript. Do not invent missing experiments, citations, results,
or implementation details.

For every issue:
1. classify it as Major / Moderate / Minor;
2. give section, page, theorem/algorithm/figure/table identifier where possible;
3. quote or precisely paraphrase the triggering text;
4. explain why it could concern a skeptical expert reviewer;
5. propose the smallest credible fix;
6. state what evidence would be needed to substantiate the fix.

Assess:
- novelty and relation to prior routing/mapping methods;
- formal definitions, assumptions, correctness, and complexity;
- experimental design, baseline fairness, statistical reporting, and reproducibility;
- scope of claims and threats to validity.

End with:
A. five highest-priority revisions;
B. claims that appear insufficiently supported;
C. questions the authors must answer before revision.

Return Markdown only, using the specified headings and table format.
```


#### Pass B: reader/editor report

Use another new chat. Fresh context reduces the tendency to defend its own earlier interpretation.

```text
Act as a specialist scientific editor reading this manuscript for the first time.

Focus only on:
- abstract, introduction, related work, contribution framing;
- logical flow between sections;
- undefined notation and terminology;
- ambiguous antecedents and overloaded terms;
- consistency between prose, algorithms, figures, tables, and conclusions;
- overclaiming, hedging, and academic English.

Do not assess novelty beyond what is visible in the manuscript.
Do not rewrite whole sections.

For each issue, report:
severity | exact location | issue | reader impact | minimal revision direction.

Then give:
1. a proposed one-sentence contribution statement;
2. a list of 10 sentences or passages most worth rewriting;
3. an abstract-specific critique.
```

This separation is important: technical validity and editorial clarity are different tasks, and mixed prompts usually blur them.

### 3. Normalize and triage in Claude Code

Save Copilot’s output verbatim as `review/gpt_review_round_01.md`, then ask Claude Code **not to edit yet**:

```text
Read:
- the current LaTeX manuscript,
- review/gpt_review_round_01.md,
- review/paper_brief.md,
- review/claims_ledger.md.

Create review/triage_round_01.md. For every review item, label exactly one:
ACCEPT, ACCEPT_WITH_SCOPE_CHANGE, NEEDS_EVIDENCE, REJECT, or UNCERTAIN.

For each item:
- locate the exact manuscript source files and line ranges;
- check whether the criticism is factually valid from the manuscript and repository;
- distinguish a real defect from a request for new research;
- identify dependencies and risk of changing technical claims;
- propose a minimal patch plan.

Do not change any files.
```

That is the key optimization missing from a simple ping-pong loop: you insert an **adversarial verification/triage stage** before modifying your paper.

A useful rule:


| Triage label | Meaning | Default action |
| :-- | :-- | :-- |
| `ACCEPT` | Valid and fixable from existing work/evidence | Revise |
| `ACCEPT_WITH_SCOPE_CHANGE` | Valid but only safely resolved by narrowing/rephrasing a claim | Revise, usually conservatively |
| `NEEDS_EVIDENCE` | Would require an experiment, proof, ablation, or literature verification | Do not write it as resolved until you supply the evidence |
| `REJECT` | Incorrect, unsupported by the manuscript, or based on a misreading | Preserve rationale; do not apply |
| `UNCERTAIN` | Potentially important but cannot be verified automatically | You decide |

For a technical paper, `NEEDS_EVIDENCE` deserves special care. Never let either model “solve” such a point by manufacturing an experimental interpretation, a citation, a theorem justification, or a performance claim.

### 4. Revise in small, reviewable batches

Do not ask Claude Code to apply all accepted comments in one opaque operation. Split revisions by risk:

1. **Low-risk language pass**\
Grammar, notation consistency, captions, terminology, transitions, internal references.
2. **Claim-scope pass**\
Qualify conclusions, state assumptions, add limitations, distinguish empirical results from general guarantees.
3. **Technical exposition pass**\
Clarify definitions, pseudocode, proof sketches, complexity arguments, baseline descriptions, and reproducibility details.
4. **Evidence pass**\
Add only results, tests, citations, or proofs that you have actually checked.

For each batch:

```text
Implement only items T01–T08 marked ACCEPT in review/triage_round_01.md.

Constraints:
- Make minimal edits to the LaTeX source.
- Do not alter numerical results, theorem statements, citations, or experimental claims
  unless an item explicitly authorizes it.
- Preserve labels, cross-references, bibliography keys, and notation conventions.
- Compile the manuscript.
- Return:
  1. a concise changed-files summary;
  2. a diff-oriented explanation;
  3. compilation warnings/errors;
  4. unresolved items and questions for the author.
```

Commit after each coherent batch. Claude Code’s persistent `CLAUDE.md` mechanism is useful here because it is loaded as project context; keep it concise and store detailed task-specific guidance in separate files rather than bloating the always-loaded instructions.[^1_3][^1_8]

### 5. Send a delta review, not another full open-ended review

Your second Copilot pass should receive:

- The revised manuscript.
- The original structured review.
- The triage.
- A concise change log or unified diff.
- An unresolved-issues list.

Then ask it to test whether the **revision actually fixed the selected weaknesses**, rather than generating a wholly new review:

```text
You previously identified issues in this manuscript. The attached package contains:
(1) revised manuscript,
(2) prior review,
(3) author triage,
(4) change log.

Audit the revision only.

For each prior issue, return one status:
RESOLVED | PARTIALLY_RESOLVED | NOT_RESOLVED | REJECTED_WITH_JUSTIFICATION.

For RESOLVED and PARTIALLY_RESOLVED items, verify that the repair does not:
- introduce a new overclaim;
- contradict another section, theorem, table, or figure;
- claim evidence not contained in the manuscript;
- make the abstract/conclusion inconsistent with the body.

Identify at most five genuinely new high-impact issues. Do not repeat cosmetic edits.
Return a Markdown table with exact locations.
```

This is much more token- and attention-efficient than uploading the full paper repeatedly and asking for an unrestricted review every time.

## Put the protocol in CLAUDE.md

I would add a compact manuscript-specific contract such as:

```md
# Manuscript workflow

## Non-negotiable rules
- Treat external LLM review as unverified reviewer feedback, not ground truth.
- Never invent citations, experimental outcomes, numerical results, proofs, or claims.
- Never modify a theorem, algorithm, experimental result, or conclusion without
  explicitly flagging the scientific consequence.
- Make minimal LaTeX changes and preserve all labels, refs, and BibTeX keys.
- Compile after source edits and report warnings.

## Review artifacts
- Save verbatim external reviews under review/.
- Before edits, create a triage table with:
  ID, severity, location, classification, evidence, proposed action, author decision.
- Use ACCEPT / ACCEPT_WITH_SCOPE_CHANGE / NEEDS_EVIDENCE / REJECT / UNCERTAIN.
- Apply only author-approved IDs.
- Produce a change log mapping each edit to review IDs.

## Paper style
- Preserve terminology and notation already established in the manuscript.
- Prefer precise, qualified claims over broad marketing language.
- State assumptions and limitations at the point where they matter.
```

This helps Claude Code behave as a disciplined implementation agent rather than a second uncontrolled reviewer. `CLAUDE.md` is explicitly designed to provide persistent project instructions and is loaded into Claude Code’s working context.[^1_3]

## What not to do

- **Do not make either model the final scientific adjudicator.** They can spot ambiguity and gaps, but they cannot validate a proof, establish novelty exhaustively, or certify an experiment.
- **Do not send raw Copilot prose directly to Claude Code with “fix everything.”** That invites changes based on hallucinated or misplaced critique.
- **Do not request fabricated peer-review simulation.** Ask for text-grounded concerns with locations and evidence.
- **Do not allow automatic bibliography additions.** Verify every citation in a primary source and against its actual contribution.
- **Do not repeatedly use the same long chat as the only context.** Copilot supports attaching specific files and folders, but a versioned review packet gives better reproducibility and avoids accumulating stale manuscript versions.[^1_6]
- **Do not conflate stylistic polish with technical revision.** A beautiful rewrite can accidentally weaken a precise claim or disconnect it from a theorem/experiment.


## Best practical cadence

For a 12–14 page technical manuscript, I would use this schedule:

1. Claude Code: repository audit, compilation, paper brief, claims ledger.
2. Copilot/GPT‑5.6: one technical referee report and one editorial/readability report.
3. Claude Code: normalize, verify, and triage the findings.
4. You: approve the technical revision plan—especially all `NEEDS_EVIDENCE` and scope-changing items.
5. Claude Code: make staged, committed revisions and compile after each stage.
6. Copilot/GPT‑5.6: delta audit of only the revised manuscript against the prior report and change log.
7. Claude Code: final consistency audit—abstract/body/conclusion alignment, notation, references, floats, and build warnings.
8. You: final theorem/result/citation verification and submission-readiness pass.

In short: use **Copilot as a fresh, structured external referee** and **Claude Code as a version-controlled, evidence-constrained revision engine**. The “review → triage → minimal patch → delta audit” cycle will outperform a generic back-and-forth rewrite loop, especially for a mathematically and experimentally dense quantum-compilation paper.

<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_16][^1_17][^1_18][^1_19][^1_20][^1_21][^1_22][^1_23][^1_24][^1_25][^1_26][^1_27][^1_28][^1_29][^1_30][^1_31][^1_32][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://techcommunity.microsoft.com/blog/microsoft365copilotblog/available-today-openai’s-gpt-5-6-in-microsoft-365-copilot/4533152

[^1_2]: https://support.microsoft.com/en-us/microsoft-365-copilot/add-content-to-microsoft-365-copilot-chat-prompts

[^1_3]: https://docs.anthropic.com/en/docs/claude-code/memory

[^1_4]: https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-architecture

[^1_5]: https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/prompt-engineering

[^1_6]: https://support.microsoft.com/en-us/microsoft-365-copilot/refer-to-specific-files-and-more-in-microsoft-365-copilot

[^1_7]: https://support.microsoft.com/en-us/microsoft-365-copilot/file-formats-supported-by-microsoft-365-copilot

[^1_8]: https://docs.anthropic.com/en/docs/claude-code/features-overview

[^1_9]: https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-quotas

[^1_10]: https://learn.microsoft.com/en-us/answers/questions/5811267/copilot-changes

[^1_11]: https://community.powerplatform.com/forums/thread/details/?threadid=659ffcec-a013-f111-8406-7ced8dcd240d

[^1_12]: https://www.builder.io/blog/claude-md-guide

[^1_13]: https://openai.com/index/gpt-5-6-preferred-model-microsoft-365-copilot/

[^1_14]: https://learn.microsoft.com/en-us/microsoft-copilot-studio/image-input-analysis

[^1_15]: https://techcommunity.microsoft.com/discussions/copilot-studio/file-uploads-not-passed-to-custom-engine-agent-in-microsoft-365-copilot-chat/4526460

[^1_16]: https://www.tembo.io/blog/how-to-write-a-great-claude-md

[^1_17]: https://www.reddit.com/r/ClaudeAI/comments/1o98c8f/tell_us_your_best_practices_for_coding_with/

[^1_18]: https://dometrain.com/blog/creating-the-perfect-claudemd-for-claude-code/

[^1_19]: https://www.linkedin.com/posts/openai_gpt-56-is-now-the-preferred-model-in-microsoft-activity-7481376177023176706-3zgu

[^1_20]: https://invitenetworks.com/microsoft-365-copilots-july-shake-up-what-gpt-5-6-and-claude-mean-for-your-it-strategy/

[^1_21]: https://www.datastudios.org/post/microsoft-copilot-file-upload-and-reading-supported-formats-limits-and-enterprise-behavior

[^1_22]: https://www.humanlayer.dev/blog/writing-a-good-claude-md

[^1_23]: https://support.microsoft.com/en-us/microsoft-365-copilot/get-started-with-microsoft-365-copilot-chat

[^1_24]: https://support.microsoft.com/en-us/microsoft-365-copilot/get-instant-answers-with-microsoft-365-copilot-chat

[^1_25]: https://docs.anthropic.com/fr/docs/claude-code/sdk/modifying-system-prompts

[^1_26]: https://support.microsoft.com/en-us/microsoft-365-copilot/catch-up-on-work-quickly-using-microsoft-365-copilot-chat

[^1_27]: https://docs.anthropic.com/en/docs/claude-code/skills

[^1_28]: https://learn.microsoft.com/en-us/ai-builder/use-a-custom-prompt-in-mcs

[^1_29]: https://learn.microsoft.com/en-us/microsoft-365/copilot/release-notes

[^1_30]: https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-privacy

[^1_31]: projects.quantum_compilation.claude_usage

[^1_32]: writing.paper_style.safe_mode_wording

