# Independent Technical Referee Report

## Overall assessment

The manuscript presents a technically interesting distributed-quantum-circuit router and makes a serious effort to separate routing quality, initial-layout quality, operating protocol, and completion behaviour. The plan abstraction, explicit capacity management, controlled layout grid, negative TELEDATA-only result, and replay verification are all valuable. The presentation is unusually transparent about several limitations.

The remaining concerns are concentrated rather than diffuse. Most importantly, the asymptotic complexity argument does not bound the number of routing iterations by the circuit gate count; the discussion and conclusion still causally attribute portfolio and scale-up results to mechanisms that the experiments do not isolate; and the packet ablation converts a cost ratio into a percentage saving using the wrong denominator. There are also specification gaps in the pseudocode and machine model that would impede faithful reimplementation.

## Issues

### A01

- **Classification:** Major
- **Location:** Appendix I, p. 5 of the supplementary material, “Computational Complexity”; main paper, Section III-H, p. 6, “Progress and the Failure Model”
- **Triggering text:** Appendix I states, “Summing over \(N\) iterations gives \(T_{\mathrm{total}}=O(N(Mn+KM^2\log M))\) excluding precomputation.” Section III-H, however, describes preparation rounds, local SWAP iterations, relief actions, retries, and termination through iteration and repeated-state guards rather than through a monotone one-gate-per-iteration argument.
- **Why this concerns a sceptical reviewer:** The derivation assumes that the number of routing-loop iterations is \(O(N)\), where \(N\) is the number of circuit gates. That does not follow from the algorithm. An iteration can apply a local SWAP or a preparation SWAP without retiring a gate; relief can add further inter-core actions; and layouts may revisit broadly similar states before a guard fires. Correctness and termination under a configurable budget do not imply an \(O(N)\) iteration bound. In addition, the displayed total contains \(KM^2\log M\) inside the per-iteration factor despite saying that distance-table precomputation is excluded. The claimed asymptotic bound is therefore not established by the preceding analysis.
- **Smallest credible fix:** Parameterise the running time by the actual number \(I\) of routing iterations, preparation rounds, or emitted routing actions, and separate one-time precomputation explicitly. For example, state a bound of the form \(T_{\mathrm{pre}}+O(I\,C_{\mathrm{iter}})\), with all terms in \(C_{\mathrm{iter}}\) derived from the candidate counts and scoring costs. Do not replace \(I\) by \(N\) unless a proof is supplied.
- **Evidence needed:** A proof that \(I=O(N)\), or a corrected complexity statement retaining \(I\) as an independent quantity. The manuscript does **not** contain the former. No new experiment is required for the minimal correction.

### A02

- **Classification:** Major
- **Location:** Section VI, p. 12, opening discussion paragraph; Section VIII, p. 13, Conclusion; Section III-D, p. 4; Appendix K, p. 7 of the supplementary material
- **Triggering text:** Section VI says that the portfolio gap “means the plan-oriented stage, the relief tiers and the horizon reach circuits DSABRE’s hop-granular, fixed-horizon loop does not.” The conclusion says, “the ablations attribute these results rather than leaving them to the system as a whole,” and then attributes the observed outcomes to capacity relief, initial layout, and lookahead horizon. Elsewhere the manuscript explicitly states that no experiment isolates either the plan abstraction or commitment rule and that the reductions belong to the whole system.
- **Why this concerns a sceptical reviewer:** The oracle portfolio establishes diversity of realised outputs, not the cause of that diversity. PORTER and DSABRE differ simultaneously in action vocabulary, candidate granularity, preparation scoring, commitment, initial layout, horizon policy, and protocol budget. The cited portfolio cannot identify which differences “reach” the complementary instances. The conclusion’s broader statement that the ablations attribute “these results” is also too strong: the ablations are only on the 80-qubit suite, use one fixed layout and horizon, and do not isolate the plan abstraction, commitment rule, or the causal source of the end-to-end margins. The manuscript declares the mechanism-attribution limitation but then relies on a causal formulation anyway.
- **Smallest credible fix:** Replace causal mechanism language with an observational statement: the two complete compiler configurations produce complementary per-instance outcomes, while the present experiments do not identify which differing mechanisms cause the portfolio gain. In the conclusion, enumerate only the effects directly isolated by the reported ablations and controls, with their suite and protocol scope.
- **Evidence needed:** To retain the causal statement, factorial or otherwise targeted comparisons isolating the relevant differences would be needed. The manuscript does **not** contain that evidence. **This would require experiments that do not currently exist.** The minimal wording fix requires no additional experiment.

### A03

- **Classification:** Major
- **Location:** Section V-C, pp. 10–11, Table IV and “Packets”; paper brief claim C7; related summary language referring to packets saving 10.9%
- **Triggering text:** The manuscript states, “Disabling TELEGATEPACKET ... cost[s] 10.9% EPR,” while the corresponding geometric means are Full \(=484.9\) and No packets \(=537.9\). Elsewhere this result is described as packets saving 10.9% EPR.
- **Why this concerns a sceptical reviewer:** These are two different percentage statements. Relative to Full, disabling packets increases EPR by \(537.9/484.9-1\approx10.9\%\). Relative to No packets, enabling packets reduces EPR by \(1-484.9/537.9\approx9.9\%\). “Disabling costs 10.9%” is supported; “packets save 10.9%” is not. The issue is not arithmetic accuracy but whether the reported ratio supports the sentence built on it.
- **Smallest credible fix:** Use one formulation consistently: either “disabling packets increases the geometric-mean EPR count by 10.9%” or “packets reduce it by approximately 9.9%,” always stating the nine-instance 80-qubit fixed-layout, fixed-horizon basis.
- **Evidence needed:** None beyond Table IV, which already contains the necessary evidence. No new experiment is needed.

### A04

- **Classification:** Moderate
- **Location:** Section III, Algorithm 1, p. 3, especially lines 13 and 23; Sections III-D and III-H, pp. 4–6
- **Triggering text:** Algorithm 1 line 23 says, “apply \(p^*\)’s own preparation SWAPs until ready, then execute it.” The prose says a committed plan may instead be abandoned when no preparation SWAP improves readiness, and a repeated decision state “raises rather than loops.”
- **Why this concerns a sceptical reviewer:** The pseudocode presents unconditional eventual execution after commitment, whereas the prose admits two non-execution exits. It does not specify whether abandonment returns to plan generation at the same DAG state, whether the failed plan is temporarily excluded, whether the iteration counter advances, or how a repeated-state exception propagates to the four-way failure taxonomy. These details affect termination behaviour and are essential to reimplementation.
- **Smallest credible fix:** Expand line 23 into an explicit preparation loop with three exits: execute when ready; abandon and return to candidate generation when no improving SWAP exists; and terminate with the stated diagnostic when the decision state repeats or a budget is exhausted. Define whether an abandoned plan can be immediately selected again under an unchanged state.
- **Evidence needed:** A precise algorithmic description consistent with the implementation. The manuscript contains fragments of this behaviour but not a complete control-flow specification. No new experiment is needed.

### A05

- **Classification:** Moderate
- **Location:** Section V-B, pp. 9–10, Table III
- **Triggering text:** After observing that “the spread down a column is two to four times the spread across a row,” the manuscript concludes, “so the initial layout is the weaker component of both compilers rather than an advantage to either.”
- **Why this concerns a sceptical reviewer:** The stated comparison supports the opposite adjective: if variation across layouts within a routing column is two to four times variation across routing loops within a layout row, initial layout is the stronger observed source of variation in this grid. “Weaker component” conflicts with the immediately preceding evidence and with later language that the layout is the “dominant observed source” of the star gap.
- **Smallest credible fix:** Replace “weaker component” with a formulation such as “larger observed source of variation,” while preserving the separate conclusion that neither compiler enjoys a uniformly superior own layout.
- **Evidence needed:** Table III already provides the relevant evidence. No new experiment is needed.

### A06

- **Classification:** Moderate
- **Location:** Section VIII, p. 13, Conclusion; Sections IV-E1 and V-D, pp. 7–8 and 11
- **Triggering text:** The conclusion states that “the lookahead horizon is what carries PORTER past DSABRE as the machine grows.” Section IV-E1 reports that every scale-up instance selects the longest offered horizon, while also declaring that the horizon rule and candidate sets were fitted in-sample.
- **Why this concerns a sceptical reviewer:** Selecting \(L_{tp}=128\) on all six scale-up cases does not show that horizon selection causes the advantage over DSABRE. The comparison in Table V changes the entire compiler and its protocol, and there is no scale-up ablation against a fixed-horizon PORTER configuration. The evidence supports association and a useful selected operating point, not the causal phrase “is what carries.” The in-sample selection further weakens generalisation beyond QFT and QPEexact.
- **Smallest credible fix:** State that the scale-up advantage is observed under PORTER’s horizon-selection protocol and that all six cases selected \(128\); do not identify horizon selection as the cause.
- **Evidence needed:** To retain the causal attribution, report PORTER with and without horizon selection on the same scale-up instances, preferably with the comparison rule fixed in advance. The manuscript does **not** contain this evidence. **This would require an experiment that does not currently exist.**

### A07

- **Classification:** Moderate
- **Location:** Appendix I, p. 5 of the supplementary material; Sections V-F and Appendix J
- **Triggering text:** Appendix I says the complexity is “in line with other core-local distributed compilers,” while the review remit asks whether the complexity claims agree with measured runtime and scaling behaviour. The reported timing sections give protocol-level wall-clock measurements under different route counts and horizon schedules, including large horizon-dependent outliers.
- **Why this concerns a sceptical reviewer:** The manuscript provides no empirical scaling analysis that tests the proposed dependence on \(N,n,K,M\), and complete protocol time mixes layout generation, multiple routes, guarded speculative horizons, and implementation effects. The available timings therefore cannot validate the asymptotic expression. Appendix J also shows that parameter search can dominate runtime by orders of magnitude, which is outside the simplified one-pass account. The theoretical and empirical discussions can coexist, but “agree with measured scaling” is not demonstrated.
- **Smallest credible fix:** Explicitly label Appendix I as a per-pass operation-count analysis only, separate from the empirical complete-protocol timings, and withdraw any suggestion that the measurements validate the asymptotic bound.
- **Evidence needed:** For empirical validation, controlled scaling with relevant variables varied independently and route/iteration counts reported would be needed. The manuscript does **not** contain such evidence. **That validation would require additional experiments**, but the minimal scope correction does not.

### A08

- **Classification:** Moderate
- **Location:** Section II-A/B, pp. 2–3; Sections III-D/G/H, pp. 4–6; Appendix E, Fig. 2
- **Triggering text:** The machine is defined as cores with “inter-core links and designated communication ports,” and the cost is charged equally on every link. Plan readiness refers to “which ports must be free,” while relief searches only the core graph. The evaluated devices have particular port/link assignments, but the general formalisation does not state structural restrictions on them.
- **Why this concerns a sceptical reviewer:** Reimplementation requires knowing whether each core pair has at most one link, whether a physical port may serve multiple links, whether parallel links are allowed, whether a core can have several ports to the same neighbour, and how a plan chooses among admissible port pairs. These choices change readiness, preparation distance, reservation conflicts, and potentially candidate multiplicity and complexity. The paper later discusses richer interconnects as future work, but the present admissible machine class is not sharply delimited.
- **Smallest credible fix:** Define the inter-core topology as a port-labelled graph and state the restrictions assumed by the implementation and proofs, including uniqueness or multiplicity of links and ports and the deterministic rule for selecting a port pair.
- **Evidence needed:** A formal machine-model statement matching the released device files and implementation. The current figures illustrate examples but do not fully define the admissible class. No new experiment is needed.

### A09

- **Classification:** Moderate
- **Location:** Section III-G, p. 6, “Capacity Relief”; Algorithm 1 lines 15–18; Section III-D, p. 4
- **Triggering text:** Tail relief is described both as selecting the “best tail-relief plan seeded from \(B\)” and as relieving “\(B\)’s blocked destinations in ascending hop order.” Opportunistic relief first chooses the highest-scoring blocked plan, while the relief BFS then generates candidates in the penultimate core and orders them through the plan machinery.
- **Why this concerns a sceptical reviewer:** The exact optimisation order is not unambiguous. It is unclear whether tail relief first minimises reservoir hop distance globally, first takes the highest-utility blocked plan, or compares generated relief actions across blocked destinations. It is also unclear which score is attached to a relief TELEDATA: the blocked plan’s forgone gain, the moved relief qubit’s ordinary TELEDATA gain, or a composite. Different interpretations can produce different routes.
- **Smallest credible fix:** Give a lexicographic definition for each tier: how the blocked destination is selected, how reservoirs and shortest paths are tie-broken, how candidate relief qubits are scored, and which value appears in the final selection key. Reflect the same order in Algorithm 1.
- **Evidence needed:** A precise specification consistent with the implementation. The manuscript does not presently provide all tie and nesting rules. No new experiment is needed.

### A10

- **Classification:** Minor
- **Location:** Section I, pp. 1–2; Section II-C, pp. 2–3; Section VII, p. 13
- **Triggering text:** The abstract says PORTER “supports all three known inter-core primitives,” while the body defines TELEDATA, TELEGATE, and same-control TELEGATEPACKET and positions the packet relative to AutoComm.
- **Why this concerns a sceptical reviewer:** “All three known” reads as an exhaustive literature claim, but the related-work discussion does not establish that these are the only known inter-core communication primitives or primitive families relevant to DQC compilation. The actual contribution only needs the narrower claim that PORTER jointly supports the three primitives studied under this cost model.
- **Smallest credible fix:** Replace “all three known inter-core primitives” with “the three inter-core primitives considered here” or an equally scoped formulation.
- **Evidence needed:** None for the narrower wording. Retaining exhaustiveness would require a substantially more comprehensive literature basis than the manuscript currently provides.

## A. Five highest-priority revisions, ranked

1. **Correct the complexity analysis (A01).** Remove the unsupported substitution of gate count for routing-iteration count and separate precomputation from per-iteration cost.
2. **Remove unsupported causal attribution (A02).** The portfolio demonstrates complementary outputs, not that particular unisolated mechanisms cause them.
3. **Correct the packet percentage semantics (A03).** Distinguish a 10.9% increase on removal from an approximately 9.9% reduction on inclusion.
4. **Narrow the scale-up conclusion (A06).** Report the selected horizon and observed advantage without claiming that horizon selection caused it.
5. **Make the executable control flow and relief ordering precise (A04, A09).** The algorithm should expose abandonment, failure exits, and the exact nested selection rules.

## B. Claims insufficiently supported by the manuscript as it stands

1. **“Summing over \(N\) iterations” yields the stated total complexity.** Missing support: a proof that the number of router iterations, SWAP steps, and relief steps is \(O(N)\), or a revised bound parameterised by the actual iteration count.
2. **The portfolio gap means the plan-oriented stage, relief tiers, and horizon reach different circuits.** Missing support: experiments or analysis isolating those differences from vocabulary, layout, scoring, and protocol-budget differences.
3. **Packets save 10.9% EPR.** Missing support: none experimentally; the existing table supports a different denominator and therefore approximately 9.9% savings, or equivalently a 10.9% penalty when packets are disabled.
4. **The lookahead horizon carries PORTER past DSABRE as the machine grows.** Missing support: a fixed-horizon versus selected-horizon comparison on the same scale-up instances.
5. **The ablations attribute the end-to-end results rather than leaving them to the system as a whole.** Missing support: isolation of the plan abstraction and commitment rule, and mechanism ablations beyond the single 80-qubit fixed-layout, fixed-horizon setting.
6. **The asymptotic complexity agrees with measured runtime/scaling.** Missing support: controlled scaling evidence that separates problem size, emitted routing actions, horizon cost, and protocol route count.
7. **The implementation applies to the generally stated machine model without further connectivity restrictions.** Missing support: a formal port-labelled topology model and explicit restrictions on port/link multiplicity and selection.
8. **The three primitives are exhaustive of known inter-core primitives.** Missing support: a literature basis establishing exhaustiveness; the manuscript only needs a narrower claim.

## C. Questions the authors must answer before revision

1. What is the tightest quantity that bounds the number of routing-loop iterations: gate count, emitted operations, SWAP count, a configured budget, or the number of reachable decision states?
2. Why does the Appendix I total include \(KM^2\log M\) inside the factor multiplied by \(N\) while describing that term as precomputation?
3. After a committed plan has no improving preparation SWAP, exactly where does control return, and what prevents immediate reselection of the same plan under the same state?
4. What precise event maps a repeated preparation state to the failure taxonomy: abandonment, deadlock, livelock, or a separate exception?
5. In tail relief, is the primary key blocked-plan utility, reservoir distance, or relief-plan utility? What is the complete tie-break order?
6. What score is assigned to the TELEDATA action that performs relief: the blocked plan’s score, the evicted qubit’s ordinary move score, or another quantity?
7. Does the implementation permit multiple links between the same pair of cores, multiple candidate port pairs, or one physical port incident to multiple links? If so, how is a port pair selected and represented in the candidate set?
8. Is “packets save 10.9%” used anywhere in the manuscript, captions, abstract, supplementary material, or metadata? If so, will all occurrences be changed to preserve the correct denominator?
9. Which exact experimental comparison supports the causal statement that horizon selection, rather than another PORTER/DSABRE difference, produces the scale-up advantage?
10. Will the discussion and conclusion explicitly distinguish an oracle portfolio’s observed complementarity from causal attribution to PORTER’s unisolated mechanisms?
11. In Section V-B, is “the initial layout is the weaker component” a typographical inversion, and should it read “the larger observed source of variation”?
12. Which conclusions are intended to apply only to the 80-qubit ablation suite, and which are intended to generalise across widths and architectures? For each generalised conclusion, what evidence supplies that extension?
