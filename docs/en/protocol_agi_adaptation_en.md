# text-cli Protocol as an Adaptation for AGI

> **Disclaimer**: This English translation was produced by an LLM based on the Chinese source document. In case of any discrepancy, **the Chinese version takes precedence**.

The protocol's scope for AGI is bounded to "physically realizable capabilities in the physical world". This document derives, in three major sections: the first section derives, from axioms, that "uttering speech and obtaining a result ⇒ AGI", decomposes AGI into six sub-capabilities plus three global properties, and surfaces two interfaces to be proven later — S2 (convergence) and S3 (extensible action space); the second section takes "any protocol satisfying the minimal field structure of the universal proof" as its object, grounds the execution layer (capability-invocation protocol) and the planning layer (phase-based generation), closes A3 on the structural side, and takes up the structural side of S2 and S3; the third section treats text-cli as an adaptation instance of the universal proof, supplementing the protocol's own properties (one-dimensional contract / phase-based reasoning / minimality / instruction expansion / parameters and performance level). Two appendices at the end supplement the phase-reasoning mechanism and the semantic-space foundation.

> **Main Thread (the through-line of the entire document)**: The realization of AGI is reduced to projections onto two layers — the "execution layer" and the "planning layer": the execution layer projects into a capability-invocation protocol (any protocol satisfying the minimal field structure of the universal proof), and the planning layer projects into phase-based generation. The reason this can adapt to AGI, at its highest level, is this: **language is the bridge among the capabilities of humans / machines / AI, and a protocol satisfying the minimal field structure of the universal proof (with text-cli as its concrete instance) is the minimal interface on that bridge** — hence its adaptation to AGI is a "same-origin" adaptation, not a "pasted-on" adaptation. text-cli, as the adaptation instance of the universal proof, has its own protocol properties brought to closure separately in the third major section.


## The Derivation Chain of AGI

### Basic Axiom Derivation
#### Axioms and Definitions

**Scope Axiom A0 (Engineerable Scope)**  
The task space \(\mathcal{T}\) of the AGI defined in this document is bounded to the set \(\mathcal{T}_{\text{imp}}\) of physically realizable capabilities. Any task that is not realizable (e.g. violating physical laws, or whose goal state is unreachable) falls outside the scope of the derivation.

**Definition D0 (Realizable Task Space)**  
\[
\mathcal{T}_{\text{imp}} = \{ T \mid \exists w_0, w_g \in \mathcal{W},\ \exists a^* \in \mathcal{A}^*,\ \text{Exec}(a^*, w_0) = w_g \}
\]
That is, the set of tasks for which "there exists a finite sequence of physical actions that brings the system from some initial state to a goal state".

> Honest note: whether a task belongs to \(\mathcal{T}_{\text{imp}}\) may itself be non-computable (the existence judgment may not always admit an algorithm). This document assumes "realizability" can be judged by humans or the system, without requiring a pre-computable decision procedure. This assumption introduces a "define-the-scope-by-capability" loop, whose nature (a self-loop, i.e. a growth mechanism) is addressed in "Instruction Expansion" of the protocol.

**Axiom A1 (Completeness of Language)**  
Any task that can be unambiguously assigned can be completely described by a natural-language intent \(L\):
\[
\forall T \in \mathcal{T}_{\text{imp}},\ \exists L \in \mathcal{L}:\ L \text{ expresses } T
\]
Language only needs to cover physically realizable tasks, not everything; this contraction aligns the coverage of A1 with that of A3 at the definition level.

**Axiom A2 (Functional Equivalence)**  
Whether a system possesses general intelligence depends only on whether it can complete arbitrary tasks in observable behavior, not on whether its internal implementation resembles the human brain.

**Axiom A3 (Uttering Speech and Obtaining a Result)**  
For any language intent \(L \in \mathcal{L}\), system \(S\) can, through internal reasoning, planning, tool invocation, environmental execution, and feedback correction, stably realize the goal described by \(L\):
\[
\forall L \in \mathcal{L},\ \exists i^* \in \mathcal{I}^*:\ \text{Exec}_T(i^*, w_0) \in \mathcal{G}_L
\]
where \(\mathcal{I}^*\) is the instruction-sequence space of the universal proof (text-cli is its concrete instance), and \(\mathcal{G}_L\) is the set of goal states for intent \(L\).

> **Dynamic extension of A3**: The "one utterance → one result" of A3 is the normal manifestation of **semantic-space stability** — once an anchoring is established it takes effect immediately; uttering yields a structured action entry point, without needing restatement (for the foundational definition of "semantic space", see Appendix B "Semantic Space, Cognitive Isomorphism, and Intelligence"; this section only cites its conclusion: semantic-space stability means an anchoring, once established, is not washed away by subsequent reasoning). This document further confirms: when a goal has no hit in the current handle closure (a gap), the effect of the previous utterance does not vanish; subsequent utterances can enter the gap-driven handle bootstrapping loop (see Lemma L4 in the second major section), sustaining and completing the unfinished effect of the previous utterance with new utterances, so that the goal is taken up in subsequent attempts. Thus the ontology of A3 (one utterance immediately yields a result) remains intact, and the dynamism layered on top of it is that "subsequent utterances can sustain the effect of previous utterances", with the success probability approaching 1 as bootstrapping attempts accumulate (conditioned on \(p_{\min}>0\) from A11; the definitions of A11 and L4 are both in the second major section, and this section only cites their conclusions without expanding).

**Definition D1 (AGI)**  
System \(S\) is an AGI if and only if \(\forall T \in \mathcal{T}_{\text{imp}},\ S\) can complete \(T\). That is, \(S\) possesses general problem-solving capability; whether it "is an AGI" is determined by structure, independent of parameter scale (see "The Settlement of A3: AGI as a Dynamically Growing Structure" later, and the orthogonality thesis in the third major section's "The 'Parameters' of LLM and the Performance Level of AGI").

#### Theorems and Proofs

**Theorem T1**  
If system \(S\) satisfies A3, then \(S\) is one realization of AGI.

**Proof**: Take any \(T \in \mathcal{T}_{\text{imp}}\); by A1 there exists \(L \in \mathcal{L}\) expressing \(T\); by A3 system \(S\) stably realizes the goal of \(L\); hence \(S\) can complete any \(T\); by D1, \(S\) is one realization of AGI. ∎

> Derivation chain: \(\text{A3} \xrightarrow{\text{A1}} \forall T,\ S\text{ can complete }T \xrightarrow{\text{D1}} S\text{ is AGI}\). A2 guarantees the validity of the functional-equivalence criterion, excluding non-behavioral standards such as "must have human consciousness". T1 proves the implication A3 ⇒ AGI, taking A3 as the premise; it does not prove A3 itself.

#### Formal Rewriting of "Uttering Speech and Obtaining a Result"

Let \(\mathcal{L}\) be the space of language intents, \(\mathcal{W}\) the space of world states, \(\mathcal{A}\) the space of atomic actions, \(\mathcal{A}^*\) the space of action sequences, \(\mathcal{I}^*\) the instruction-sequence space of the universal proof (\(\mathcal{I}^*\) is the landing form of \(\mathcal{A}^*\) under a protocol satisfying the universal proof; text-cli is its concrete instance — each instruction sequence corresponds to an executable action sequence), and \(\mathcal{G}\) the space of internal goal representations. A3 can be written as:
\[
\Phi(S) \equiv \forall L \in \mathcal{L},\ \exists i^* \in \mathcal{I}^* \subseteq \mathcal{A}^*,\ \text{Exec}_S(i^*, w_0) \in \text{Goal}_S(L)
\]
where \(w_0\) is the initial world state, and \(\text{Goal}_S(L) \subseteq \mathcal{W}\) is the set of goal states corresponding to \(L\). The symbol \(\mathcal{I}^*\) is consistent with the A3 axiom statement above, with \(\mathcal{A}^*\) as its superset; the containment relation is explicitly annotated only here, in this formalization, to remove ambiguity.

#### The Six Sub-capabilities Decomposed

If \(\Phi(S)\) holds, then system \(S\) must possess the following six sub-capabilities (necessary conditions, decomposed intuitively along the "utterance → realization" closed loop, not independently proven):

- **C1 (Intent Parsing)**: \(f_{\text{parse}}: \mathcal{L} \to \mathcal{G}\).
- **C2 (Goal Judgment)**: \(f_{\text{goal}}: \mathcal{G} \times \mathcal{W} \to \{0,1\}\).
- **C3 (Plan Generation)**: \(f_{\text{plan}}: \mathcal{G} \times \mathcal{W} \to \mathcal{A}^*\).
- **C4 (Action Execution)**: \(f_{\text{act}}: \mathcal{A} \times \mathcal{W} \to \mathcal{W}\).
- **C5 (State Perception)**: \(f_{\text{perceive}}: \mathcal{W} \to \mathcal{O}\).
- **C6 (Feedback Correction)**: \(f_{\text{replan}}: \mathcal{O} \times \mathcal{G} \to \mathcal{A}^*\).

None of the six can be omitted; together they form the **necessary** capability chain from "utterance" to "realization" (C1–C6 are necessary conditions for \(\Phi(S)\), not sufficient). This chain must be augmented with the three global properties S1–S3 in the Sufficient Conditions section to form a complete closed loop (i.e., the necessary-and-sufficient condition; see the Necessary-and-Sufficient Condition section).

#### Sufficient Conditions

If C1–C6 hold and the three global properties are satisfied, then \(\Phi(S)\) holds:

- **S1 (Universality)**: \(f_{\text{parse}}\), \(f_{\text{plan}}\), \(f_{\text{replan}}\) are defined and computable for any \(L\) and any reachable \(w\).
- **S2 (Convergence)**: For any \(L\), starting from \(w_0\) and looping through C3–C6, there exists a finite number of steps \(n\) such that \(f_{\text{goal}}(f_{\text{parse}}(L), w_n) = 1\).
- **S3 (Execution Completeness)**: The combination of action space \(\mathcal{A}\) and world states \(\mathcal{W}\) is such that, for any \(w_g \in \text{Goal}_S(L)\), there exists a finite action sequence leading from \(w_0\) to \(w_g\).

> **S3 is the key interface connecting this section to the second major section**: it requires the system to possess an action space that is sufficiently rich **and extensible**, which is exactly the problem that the second major section solves through a protocol satisfying the universal proof (text-cli being its concrete instance).

#### Necessary-and-Sufficient Condition

\[
\Phi(S) \iff
\begin{cases}
\exists f_{\text{parse}}, f_{\text{goal}}, f_{\text{plan}}, f_{\text{act}}, f_{\text{perceive}}, f_{\text{replan}} \\
\text{satisfying C1–C6} \\
\text{and satisfying S1 universality, S2 convergence, S3 execution completeness}
\end{cases}
\]

That is: uttering speech and obtaining a result \(\iff\) possessing a closed-loop system of universal language understanding, goal judgment, planning, execution, perception, and feedback correction, that can converge to the goal in finite steps for any language intent.

#### Equivalence with AGI

Combining A1/A2/D1:
\[
\text{C1–C6 + S1–S3} \Rightarrow \Phi(S) \Rightarrow S \text{ is one realization of AGI}
\]
where the extensible action space required by S3 is concretely realized by the second major section through a protocol satisfying the universal proof (text-cli being its concrete instance).

> **Foreshadowing (not closed here prematurely)**: The phrase "stably realize the goal" in the text of Axiom A3 inherently contains a convergence component; this section extracts that component explicitly as S2 (convergence). S2 is an unproven kernel in the original text, carried by the A3 assumption; the advance of this document is precisely to **complete the S2 component inside A3** (not to complete an independent proposition outside A3). This document will, in the "Reduction" section of the second major section, split S2 into \(P_{\text{conv}}^{\text{struct}} \land P_{\text{conv}}^{\text{model}}\): the structural side is closed within the document's axiom chain via A5 handle closure → L2 + one-dimensional-contract same-dimensionality zero-tax → finite phase sequence of phase-based generation → the four-loop of closed-set-envelope decidability; the model side is conditioned on \(p_{\min}>0\) from A11, with the quantitative value left to empirical measurement. This is only a preview here, not an overreaching claim of closure. The arguments for A9–A11 and L3/L4 are developed in their respective positions in the second major section, and the settlement of AGI as a dynamically growing structure is also brought to closure in the second major section, not preempted here.

#### Conclusion

The axiom "uttering speech and obtaining a result" is a compound capability, decomposing into six necessary sub-capabilities:
\[
\text{understand intent} \to \text{generate goal} \to \text{plan actions} \to \text{execute actions} \to \text{perceive feedback} \to \text{correct actions}
\]
The six-link necessary capability chain, augmented with universality, convergence, and execution completeness (S1–S3), constitutes the necessary-and-sufficient condition of \(\Phi(S)\) (see the Necessary-and-Sufficient Condition section). Execution completeness implies a requirement for an **open ecosystem**; the second major section shows how to construct such an ecosystem through a protocol satisfying the universal proof (text-cli being its concrete instance).

## The Derivation of Capability-Invocation Protocol and Ecosystem as the Landing of "Uttering Speech and Obtaining a Result"

> Universal-proof convention (key): what this major section argues is not a specific protocol, but a **universal structural criterion** — any protocol whose syntax satisfies the following **minimal field structure** closes A3 on the structural side and constitutes a supporting structure for AGI:
> - **Instruction** contains at least four fields: `declaration prefix, domain, action, parameter` (the declaration prefix identifies the protocol identity; the domain is the ecosystem namespace; the action is the node operation; the parameter is the payload);
> - **Unified envelope** contains at least three fields: `response type, response data, error` (a non-empty error means failure; error codes are finitely predefined; the result is mechanically decidable);
> - **Meta-instruction** contains at least two elements: `query; install` (query returns the relevant handle closure; install registers a new capability node; the two together form the bootstrapping channel of the ecosystem).
>
> Any protocol satisfying the above field structure, whose field closures are mechanically decidable and which is same-dimensional with the generation stream, falls within this universal proof — both text-cli and strict JSON tool invocation are its instances (JSON, if it expresses instructions in the form `declaration prefix, domain, action, parameter`, returns results in the form `response type, response data, error`, and exposes `query/install` meta-instructions, falls into this proof; how high its protocol tax is is not judged in this major section — see "Minimality" in the next chapter). This major section only proves "satisfying the universal proof ⇒ closing A3", without ranking protocols.

### Introduction: Capability Invocation Is the Core Bottleneck

The first major section already decomposed "uttering speech and obtaining a result" into a six-link closed loop: intent parsing → goal judgment → plan generation → **action execution** → state perception → feedback correction. The first two steps are the LLM's semantic internal work; the last two are execution-side feedback; what is truly stuck in the middle, deciding whether the system can "utter speech and obtain a result", is the fourth step — how to let the LLM simply and stably transform its "planned actions" into actual invocations of capability nodes in the ecosystem. Once the invocation succeeds, the execution load is borne by the node; once it fails, the subsequent state perception and feedback correction have nothing to build on.

Capability invocation is, in essence:

\[
\text{natural-language intent} \rightarrow \text{handle triggering of a capability node in the ecosystem}
\]

It requires the LLM to possess tool selection, parameter generation, invocation timing, and error handling. These capabilities already exist today, but they are far from "simple and stable" — parameter hallucination, tool misselection, format instability, and forgetting tool descriptions under long contexts are widespread problems. Making it reliable requires four layers of cooperation: ① standardized tool descriptions; ② controlled generation; ③ back-filling of invocation results; ④ retry and degradation mechanisms. When these four are stable, the LLM can reliably transmit intent to the "body" (the capability nodes in the ecosystem), like a "brain".

Therefore the remaining core problem converges to: can we build a simple, stable capability-invocation layer that reliably maps the LLM's planning to the driving of ecosystem nodes? This is the part this major section takes up — it directly answers the S3 (extensible action space) interface surfaced by the first major section, and provides the atomic step for closing the structural side of S2 (convergence). This major section's argument takes "any protocol satisfying the minimal field structure of the universal proof" as its object; any protocol satisfying the five structural properties below holds equivalently.

### Definitions

This major section introduces the following vocabulary on top of the first major section's symbols:

- \(\mathcal{L}\): the space of natural-language intents.
- \(\mathcal{I}\): the instruction space, whose elements contain at least four fields `declaration prefix, domain, action, parameter` (all protocols satisfying the minimal field structure of the universal proof are isomorphic here).
- \(\mathcal{I}^*\): the instruction-sequence space (i.e., the \(\mathcal{I}^*\) in the formalization of A3 in the first major section; its universal form is given here).
- \(\mathcal{W}\): the space of world states.
- \(\mathcal{R}\): the space of unified return envelopes, whose elements contain at least three fields `response type, response data, error` (all protocols satisfying the minimal field structure of the universal proof are isomorphic here).
- \(\mathcal{G}_L \subseteq \mathcal{W}\): the set of goal states corresponding to language intent \(L\).
- \(M\): the LLM reasoning core.
- \(T\): the protocol runtime.
- \(\mathcal{E}\): the **Ecosystem**, a dynamically evolving network of capability nodes.
- \(\mathcal{N}\): the set of capability nodes in the ecosystem.
- \(\text{node}: \mathcal{I} \to \mathcal{N} \cup \{\bot\}\): the parse mapping from handle to node. If \(\text{node}(i) = \bot\), the handle is unregistered.

**The essence of the ecosystem**: the ecosystem is the actual carrier of the system's capabilities. Each capability node \(n \in \mathcal{N}\) encapsulates a piece of executable logic (a local function, a remote API, another AI agent, dynamically generated code, etc.). A capability-invocation protocol instruction \(i \in \mathcal{I}\) is not a direct operation, but a **Handle** pointing to some node in the ecosystem. The LLM only needs to grasp the handle, without understanding the node's internals — this is exactly the landing form of the "extensible action space" required by S3: the action space is not pre-stored in the LLM, but exists in a growing ecosystem.

### Axioms

**A4 (Unified Execution Protocol for Capability Invocation)**: For any legal instruction \(i \in \mathcal{I}\) (containing at least the four fields `declaration prefix, domain, action, parameter`), runtime \(T\) first resolves the corresponding node \(\text{node}(i)\) in ecosystem \(\mathcal{E}\), then the node executes the actual action and returns a unified envelope (containing at least the three fields `response type, response data, error`):
\[
\text{Exec}_T(i, w) = \text{Exec}_{\text{node}(i)}(i, w) = (w', r),\quad r \in \mathcal{R}
\]
where \(w'\) is the post-execution world state, and \(r\) contains the result type, result data, and error information. If \(\text{node}(i) = \bot\) (handle unregistered), an error envelope is returned. This axiom closes C4 (action execution) and C5 (state perception: the envelope is the state feedback) of the first major section.

**A5 (Ecosystem Query and Example Closed Loop)**: The protocol provides a `query` meta-instruction that returns the set of capability-node handles currently reachable in the ecosystem and relevant to the context, along with examples. Query is not a static full list, but a **dynamic slice** of the ecosystem — the runtime filters out the most relevant handle subset according to the current task, historical feedback, and phase context, giving the LLM a finite, templated handle closure before generation, reducing generation uncertainty.

**A6 (Feedback Correction, Finite-step Convergence When the Goal Is Reachable)**: If a certain instruction sequence does not reach the goal after execution, the LLM can read the return envelope \(r\), and generate a corrected instruction sequence based on the error information or intermediate results, ultimately converging to the goal in finite steps:
\[
\forall L,\ \exists n < \infty,\ \text{such that } w_n \in \mathcal{G}_L
\]
This is the concretization of S2 (convergence) of the first major section on the execution side, but only guarantees "finite-step correction within a given handle closure"; the global closure of full convergence is left to the "Reduction" section.

**A7 (Execution Load Stability)**: The execution load of capability nodes in the ecosystem is stable and reproducible; execution does not depend on continuous LLM reasoning, nor is it affected by natural-language ambiguity. Execution failure comes only from an illegal handle or an unreachable environment, and the failure information is returned via the unified envelope.

**A8 (Ecosystem Bootstrapping Expansion)**: The ecosystem \(\mathcal{E}\) is open. If the current ecosystem lacks the handle needed to complete a task, the system can register a new capability node via the `install` meta-instruction; the generation of the new node is itself handle-driven (e.g., invoking a "code generation" node), and after generation it is automatically registered as a new handle; installation does not exceed \(S\)'s capability. AI is both an ecosystem consumer (invoking handles) and producer (installing and creating handles), so that the ecosystem grows through the "capability production ↔ capability consumption" loop, approaching the set of physically realizable capabilities — this is exactly what closes S3's "extensible action space" of the first major section, and lands A0's "define-the-scope-by-capability" self-loop onto a growing mechanism.

> A9–A11 and Lemmas L3/L4 are structural completions, not expanded in this section; they are left to the "Reduction" section and the "Phase-Based Generation" section. The settlement of AGI as a dynamically growing structure is not within the numbering sequence of the reduction layer; see the "Settlement of A3" node later.

### Lemmas

**Lemma L1 (The generation cost of the same-dimensional minimal controlled form is lower than that of the cross-dimensional structurally redundant form)**:

Let the per-token error rate in autoregressive generation be \(\varepsilon\) (\(0 < \varepsilon < 1\)). The probability that a segment of \(n\) tokens is entirely correct is \((1-\varepsilon)^n\); the probability of error for the whole segment accumulates with length \(n\); a stronger model can only reduce \(\varepsilon\), it cannot remove the \(n\)-th power — this is structural.

Compare two instruction forms (both satisfying the minimal field structure of the universal proof, differing only in whether they are same-dimensional):

1. Cross-dimensional structurally redundant form: the instruction must simulate a multi-dimensional structure (e.g., nested objects, strict schema matching); each step's generation is an independent fatal point (a malformed or field-mismatched generation voids the entire attempt). Stringing \(N\) invocations has total length about \(N \cdot c_{\text{cross}}\), with failure probability about \(1 - (1-\varepsilon)^{N \cdot c_{\text{cross}}}\).
2. Same-dimensional minimal controlled form: the instruction is only three positions "domain, action, parameter" plus two separators, same-dimensional with the one-dimensional token stream, regex-parseable, with no structural redundancy; only the unified envelope (short) is 1 fatal point; the \(N\) instructions are tolerant and can be covered. Failure probability is about \(1 - (1-\varepsilon)^{c_{\text{env}} + N \cdot c_{\text{step}}}\).

Because \(c_{\text{step}} \ll c_{\text{cross}}\), the exponent of the same-dimensional form is far smaller than that of the cross-dimensional form, and the failure probability is lower with an advantage that grows with \(N\). The root cause is not "compressing \(N\) into 1 fatal point", but "the minimal controlled form of the instruction (same-dimensional, regex-parseable) makes per-step generation cost far lower than cross-dimensional structural redundancy". Therefore "the same-dimensional form's tax is lower than the cross-dimensional form's" is a verifiable conclusion derived from the length-error accumulation law, not an empirical guess, and it does not single out any specific protocol — text-cli, JSON tool invocation, or other protocols, as long as they fall into the same-dimensional minimal controlled form, hold this conclusion; cross-dimensional implementations have a higher tax.

It must be emphasized: closing A3 is a structural property, while tax height is a generation-side probabilistic property; the two are orthogonal — cross-dimensional forms (including strict JSON tool invocation) also satisfy the minimal field structure of the universal proof (instruction four-tuple / envelope three-field / meta-instruction binary, with field closures mechanically decidable), also close A3 on the structural side, and also constitute a supporting structure for AGI; their per-step independent fatal points only raise the accumulation of generation cost (failure rate), not cancel the closing of A3. Therefore whether AGI "holds" is determined by structure (the universal proof), independent of whether it is cross-dimensional; cross-dimensionality only affects the protocol tax and performance level — i.e., "the difference between protocols is only in tax", not "cross-dimensional ones cannot work". If a cross-dimensional form is re-expressed in the same-dimensional minimal controlled form (e.g., JSON tool invocation rewritten as a `declaration prefix, domain, action, parameter` instruction + three-field envelope), it likewise achieves zero tax. The concrete comparison of protocol tax is addressed in the next chapter "Minimality". ∎

**Lemma L2 (One-dimensional contract constraint: instruction is same-dimensional with the token stream)**:

An instruction form satisfying the minimal field structure of the universal proof (e.g., `declaration prefix, domain, action, parameter`) is same-dimensional with the LLM's one-dimensional token stream — the LLM only needs to do one-dimensional slot-filling within a finite handle closure, without simulating a multi-dimensional structure. Combined with L1, the instruction lives in the LLM's native high-probability generation subspace; generation does not cross dimensions and does not fabricate structure out of thin air; parameter hallucination and tool misselection are eliminated before generation. This lemma is the formal basis of "handle as the alignment anchor", and does not depend on any specific protocol's proper name. ∎

### Theorems

**Theorem 1 (LLM + capability-invocation protocol satisfies the execution side of A3)**:
\[
\text{A3} \land \text{A4} \land \text{A5} \land \text{A6} \land \text{A7} \land \text{A8} \Rightarrow \Phi_{\text{exec}}(S)
\]
where \(\Phi_{\text{exec}}\) is "the execution side can take up" — for any \(L\), there exists an instruction sequence \(i^*\) such that the execution result belongs to \(\mathcal{G}_L\), and failure can be corrected via A6, and gaps can be filled via A8.

**Proof**: Take any \(L\); by A3 there exists a candidate sequence \(i^*\); by A4 it is parsed, executed, and returns an envelope; success means the goal is reached; failure is corrected by the A4 error envelope + A6; format uncertainty is improved by A5 query; capability absence is filled by A8 install registering a new node; by A7 node execution is stable and does not add uncertainty. Therefore the execution side can take up. ∎

**Theorem 2 (Uttering speech ⇒ AGI, execution-side handoff)**:
\[
\Phi_{\text{exec}}(S) \land \text{A1} \land \text{A2} \Rightarrow S \text{ is one realization of AGI (planning side to be completed in the "Reduction" and "Phase-Based Generation" sections)}
\]

**Execution-side closure checklist** (mapped against the six sub-capabilities + three global properties of the first major section):

| First-section condition | Taken up by | Status |
|-----------|--------|------|
| C4 action execution | Runtime resolves ecosystem node and executes (A4) | Closed |
| C5 state perception | Unified envelope `response type, response data, error` (A4) | Closed |
| S3 execution completeness | Ecosystem covers reachable goals (isomorphic with D0), expanded and approached by A8 | Closed (structural side) |
| C6 execution half-loop | Execution result back-filled into context (A6) | Closed |

> Handle as the alignment anchor: A5 query converges candidate actions from "arbitrary" to a "relevant closure"; L2 same-dimensional template alignment lets the LLM only fill slots without fabricating structure; combined with A10 (see the "Reduction" section) closed-set-envelope rollback — each execution step can converge to that step's goal on the structural side. This is the atomic step of the execution side, carrying the execution-layer projection of \(P_{\text{conv}}^{\text{struct}}\).

**The boundary this section can take up**: C1 (intent parsing), C2 (goal judgment), C3 (plan generation), S1 (universality), S2 (global closure of convergence), and the planning side of the C6 correction half-loop are not independent problems, but the same mechanism sliced at different moments of "multiple inferences + multiple context reorganizations", left to the "Reduction" section and the "Phase-Based Generation" section to close.

### Conclusion

The first six subsections of this major section (introduction through theorems) complete the execution-side handoff: any protocol satisfying the minimal field structure of the universal proof closes C4/C5/S3/C6 of the six-link closed loop of the first major section on the structural side, letting the LLM's planning reliably map to the driving of ecosystem nodes. The universality of AGI is no longer borne by the LLM alone, but jointly by **LLM + ecosystem** — the LLM is the handle operator, the ecosystem is the capability carrier. Handle anchoring lets each execution step converge on the structural side, and gaps are filled by ecosystem bootstrapping (A8).

The remaining unclosed items (the planning side of C1/C2/C3/S1/S2, and the global convergence of the C6 correction half-loop) converge to the next section, "Phase-Based Generation".

### Reduction: Converging All Remaining Gaps onto "Phase-Based Generation"

#### Execution-side Closure Checklist

By Lemmas L1, L2 and A4 (ecosystem resolution and unified envelope), A5 (ecosystem query), A7 (node execution stability), A8 (ecosystem bootstrapping expansion), the capability-invocation protocol proves, within this document, the closure of the following conditions of A3 in the first major section:

| First-section condition | Taken up by | Status |
|-----------|--------|------|
| C4 action execution | Capability-invocation execution protocol (ecosystem node execution) | Closed |
| C5 state perception | Unified return envelope `response type, response data, error` | Closed |
| S3 execution completeness | Ecosystem covers reachable goals (isomorphic with D0, expanded and approached by A8) | Closed |
| C6 "execution half-loop" | Execution result back-filled into context | Closed |

#### The Six Conditions on the Intelligence Side Are Same-Source

The capability-invocation protocol alone takes up the execution side (C4/C5/S3/C6); what is not yet directly closed at this layer are C1 (intent parsing), C2 (goal judgment), C3 (plan generation), S1 (universality), S2 (convergence), and the "correction half-loop" of C6 in A3. These six are not six independent problems, but six slices of the same capability at "multiple inferences + multiple context reorganizations", unified as \(P\):

\[
P \equiv P_{\text{conv}} \land P_{\text{ctrl}}
\]

- \(P_{\text{conv}}\) (convergence part): \(\forall L \in \mathcal{L},\ \exists n < \infty,\ \text{Exec}(i^*, w_0) \in \mathcal{G}_L\) — the task can ultimately be completed, converging to the goal.
- \(P_{\text{ctrl}}\) (controllability part): failure cost is bounded, state is knowable, and rollback is possible.

**Proposition T3 (Structural correctness under handle anchoring)**: \(P_{\text{conv}}\) is split into a structural side and a model side, each with its provability annotated:

\[
P_{\text{conv}} \equiv P_{\text{conv}}^{\text{struct}} \land P_{\text{conv}}^{\text{model}}
\]

- **\(P_{\text{conv}}^{\text{struct}}\) (structural side, provable in this document)**: within the structure that a given phase template can frame, the LLM's generation is anchored to finite correct structure, and failure can be located and rolled back. Its establishment is derived from the following in-document constructs:
  1. By A5 (query returns relevant handle slices + examples), the LLM can obtain a **finite and templated handle closure** before generating instructions, converging its generation space from open natural language to that closure;
  2. By Lemma L2 (instruction lives in the generation subspace) + one-dimensional contract (same-dimensional, zero protocol tax), the LLM only does one-dimensional same-dimensional generation within that closure, without crossing dimensions or fabricating structure — i.e., it is "aligned";
  3. By A9 (finite phase decomposition), the task is organized as a **finite phase sequence**; each phase generates only a small segment within that phase's controlled-context template (corresponding to the "handle directory sliced per phase"), so a single cognitive load is bounded, and errors can be corrected in phase reorganization;
  4. By A10/L3 (closed-set controlled context + dispatch forcibly closing the generation space) and the unified closed-set envelope (empty error means success; error codes finitely predefined), each step's result is mechanically decidable; failure only rolls back the current phase for regeneration, not discarding the whole chain.

  The above 1–4 are derived from axioms (A5, A9, A10) + lemmas (L2, L3) + properties (one-dimensional contract, phase-based generation, closed-set envelope), **without depending on the LLM's parameter scale \(p\)**; hence \(P_{\text{conv}}^{\text{struct}}\) is closed within this document.

- **\(P_{\text{conv}}^{\text{model}}\) (model side, unprovable, but inter-segment handle creation keeps it from single-point dependence on \(p\) saturation)**: the base probability of a single generation segment within the structure hitting the correct goal is determined by \(p\); but complex tasks must be decomposed into multiple reasoning segments (for humans and AI alike), and between segments there is an operable gap — when a sub-plan finds that the current handle closure cannot cover a small segment, it can create a new handle from scratch between segments, register it as an ecosystem node via A8 install, so that the next sub-plan's query slice already contains that handle (L4 living body). Therefore planning coverage does not require \(p\) to pre-store the full capability set, but only requires \(p\) to **create, at the gap, a dedicated handle aligned to that gap** — this requirement is far lower than covering the whole task at once; creating a handle is itself driven by the execution-layer handle closed loop, introducing no non-structural mechanism. The probability-expansion relation of parameter \(p\) on "creating the correct handle at the gap" is an empirical fact, **not provable at the axiom layer of this document**, left to empirical calibration (A11).

- **Coverage κ (driven by AI bootstrapping; provable on the structural side, growth rate determined by the model side)**: S3 (execution completeness) reduces to A8 bootstrapping, and is closed by "the barrier to package creation is so low that speaking suffices ⇒ coverage approaches physically realizable capabilities"; here it is written as a measurable proposition, isomorphic with the \(P_{\text{conv}}\) split of T3:
  - **C.1 Definition**: \(\kappa(\mathcal{E}, t) = |\mathcal{T}_{\text{imp}} \cap \mathcal{G}_{\mathcal{E}(t)}|/|\mathcal{T}_{\text{imp}}|\), i.e., the proportion of realizable tasks the current ecosystem can actually take up;
  - **C.2 Structural-side monotonicity** (provable within the axiom chain): by A8 (install registration immediately enters the external instruction table) and L4 (gap-driven handle bootstrapping closed loop), coverage failure triggers the handle-creation sub-flow to create a handle and install it, making that task take-up-able from that moment on, so \(\forall t,\ \kappa(\mathcal{E}, t+1)\ge\kappa(\mathcal{E}, t)\). The protocol's built-in handle-creation channel makes κ's lower bound nonzero, giving bootstrapping a startable baseline that does not depend on external human contribution;
  - **C.3 Model-side growth rate** (unprovable, left to empirical measurement): whether κ can approach 1 within finite attempts depends on the positive lower bound \(p_{\min}>0\) (A11) of hitting the correct handle. Under \(p_{\min}>0\), the probability that an uncovered task remains un-taken-up after k attempts is \((1-p_{\min})^k\to 0\) (\(k\to\infty\)), so κ approaches 1 **in the probabilistic sense** as AI bootstrapping attempts accumulate, with the growth rate determined by the empirical value of \(p_{\min}\);
  - **C.4 External upper bound** (remark, not a core constraint): \(\kappa(\mathcal{E}, t)\le\kappa_{\max}(t)\), coming from "the objective boundary of the total amount of experience that can be translated", not from the bottleneck of external human adoption — the package-creation body is AI bootstrapping, and gaps are filled by the framework's endogenous mechanism. It only reminds that the set of physically realizable tasks is finite, and that there is a hard boundary of what cannot be translated into speech;
  - **C.5 Conjunction of the three formulas**: \(\kappa\text{ is monotonically non-decreasing (A8+L4)}\ \land\ \kappa\xrightarrow{P}1\ (\text{conditioned on }p_{\min}>0\text{, left to measurement, A11})\ \land\ \kappa\le\kappa_{\max}\text{ (external upper bound, remark)}\). Coverage is isomorphic with \(P_{\text{conv}}\): the structural side underpins (κ non-decreasing, gaps filled by AI bootstrapping), the model side determines growth rate and upper bound (\(p_{\min},\kappa_{\max}\)), and neither **enters the closure of \(P_{\text{conv}}^{\text{struct}}\)** — \(P_{\text{conv}}^{\text{struct}}\) only proves "within a given handle closure, generation is framed", not "the closure itself covers any goal". Insufficient parameters (low \(p_{\min}\)) means the LLM's cognitive subset is of limited quality, and does not constitute a flaw in the protocol mechanism.

To ground the four loops, the following structural-completion axioms and lemmas are introduced (A9–A11, L3–L4, belonging to the reduction layer rather than the execution-layer axioms; the settlement of AGI as a dynamically growing structure is in the "Settlement of A3" node later, not within this numbering sequence):

**A9 (Finite Phase Decomposition)**: For any expressible goal \(g \in \mathcal{L}\), there exists a decomposition operator mapping \(g\) to a finite phase sequence \(\langle\phi_1,\dots,\phi_n\rangle\) (\(n<\infty\)), where each phase only requires generating a small segment within a controlled-context template, phases can reorganize, correct, and roll back between each other, and a single cognitive load is bounded. Its existence does not depend on \(p\), only on the structural fact that "the goal can be expressed in segments".

**A10 (Closed-Set Controlled Context)**: The external instruction entry is parsed exclusively by the controlled context — only "domain, action" that, after alias normalization, hits an addressable handle registry enters the execution chain; non-hits are judged not-found; every execution result is forcibly returned through the three-field closed-set envelope (non-empty error means failure, error codes finitely predefined). The boundary is determined by the registry, not depending on \(p\).

**A11 (Model-side Lower-bound Premise)**: The AGI feasibility proposition is preconditioned on "there exists a positive lower bound \(p_{\min}>0\) of hitting the correct handle". The concrete value of \(p_{\min}\) is an empirical fact, not proven at the axiom layer (left to measurement); the feasibility logic explicitly depends on this condition. When \(p_{\min}\to 0\), the structural side (A4–A10, L4 bootstrapping loop, κ monotonic non-decrease) still closes, but overall feasibility turns into "conditioned on \(p_{\min}>0\)".

**Lemma L3 (Closed-set envelope forcibly closes the generation space)**: The three-field closed-set envelope of A10 makes each step's result mechanically decidable, and failure only rolls back the current phase for regeneration, not discarding the whole chain — this is the formal guarantee of loop ④ of the four loops.

**Lemma L4 (Gap-driven handle bootstrapping closed loop)**: By A9, the task is organized into multiple inferences, each able to inject controlled context. When a certain phase's query has no hit (a gap), the subsequent phase registers a new handle via A8 install (the handle set is monotonically non-decreasing, closing κ's monotonic term on the structural side); the new handle re-enters the slice via re-query, is driven to execute, and the result is judged by the A10/L3 closed-set envelope — success closes the gap, failure rolls back the current phase to recreate (continuing from the A6 checkpoint). Therefore "whether the handle aligns to the gap" does not require judgment at install time, but is guaranteed by the absorption and rollback of the phase bootstrapping loop, belonging to the model-side leave-as-blank (A11), not entering κ's structural-side closure. ∎

#### Naming and Reduction

\(P\) is "within finite steps, stably transforming a language intent into a correct instruction sequence and converging to the goal". This document names it, at the logical layer, "Phase-Based Generation".

"Phase-Based Generation" = the projection of "multiple inferences + multiple context reorganizations" at the planning layer: organizing "completing a task" as "a series of inferences in reorganized contexts", so that a single inference only bears a small segment of the task (dissolving the load), and between any two inferences, reorganization and correction are possible (dissolving the impossibility of cycling). The concrete groupings of phases, sub-phases, and the **ecosystem handle directory sliced per phase** are the engineering-side projection shapes of this axiom, not constrained by the logical layer (logic is not constrained by engineering reality).

Thus this section produces the reduction conclusion:

\[
\text{AGI} \iff \underbrace{\text{execution-layer projection (capability-invocation protocol + ecosystem)}}_{\text{proven in this section}} \land \underbrace{\text{planning-layer projection (phase-based generation)}}_{\text{proven in the next section}}
\]

The two are not two parallel subsystems, but projections of "multiple inferences + multiple context reorganizations" at two layers — this is the deep consistency between this section and the next.

> Note: here "execution-layer projection" refers to the capability-invocation protocol taking up execution-side capabilities (see the "Execution-side Closure Checklist"), and depends on the ecosystem to provide the action space; its complete property as a "same-dimensional projection" is in the later "Protocol's Own Properties" chapter's "One-Dimensional Contract" section. The task of the next section, "Phase-Based Generation", is uniquely locked to: proving alone that "phase-based generation holds", without needing to revisit anything from this section.

### Phase-Based Generation

This section takes up the previous section's "execution-layer projection" and proves alone that the planning-layer projection "phase-based generation" holds; it complements the execution-layer projection, and together they constitute a supporting structure for AGI — the execution-layer projection closes \(P_{\text{conv}}^{\text{struct}}\), and this section closes the controllability part \(P_{\text{ctrl}}\) of \(P\). To prevent the reader from mistaking "phase-based generation" as a new concept invented in this section, let me first trace its origin: the "multiple inferences + multiple context reorganizations" repeatedly appearing in this document is the basic form of an agent's cognitive operations in semantic space — not a single long-range inference going straight from intent to result, but decomposing the task into multiple segments, each completing a small inference step in a reorganized context window, with the ability to look back, correct, and reorganize between segments; this form is isomorphic for humans and AI. It is not limited to the execution layer: organizing "completing a task" itself as "a series of inferences in reorganized contexts" holds at the planning layer as well — planning is not a single generation of a complete plan, but multiple inferences, each advancing a small segment, with reorganization possible between segments, sharing the same form as the execution layer, differing only in whether the "context" operated on is the planning space or the tool-invocation space. It can thus be seen that "phase-based generation" is not something invented anew, but the projection of this same-source form at the planning layer.

#### Projecting Out "Phase-Based Generation"

Projecting the planning layer's "multiple inferences + multiple context reorganizations" into a concrete mechanism yields "phase-based generation": organizing the task into a finite phase sequence, each phase generating a small segment within a controlled-context template, with reorganization, correction, and rollback possible between phases. The concrete groupings of phases, sub-phases, and the ecosystem handle directory sliced per phase are the visible shapes of this projection at the engineering layer; the logical layer does not constrain their specific granularity.

**The precise meaning of recursive reuse (taking up the execution layer's handle anchoring)**: the planning layer's "query" is equivalent to anchoring the planning space to a finite phase closure at the execution layer's query position — the planning layer emits two kinds of products (① the next-level phase + its execution path; ② intermediate products for its own layer's use) sharing the same set of handle anchoring. Each phase is constrained by the controlled-context template, and the LLM only fills slots without fabricating structure; gaps are filled by the L4 living-body loop (see below).

#### Phase-Based Generation Closes the Controllability Part of P

Phase-based generation takes up the "controllable" half of \(P\) — namely: failure cost is bounded, state is knowable, and rollback is possible. It does not alone guarantee \(P_{\text{conv}}\) (convergence to the goal), but complements the previous section's execution-layer projection \(P_{\text{conv}}^{\text{struct}}\).

#### Formalizing "Controllable Reliability"

Phase-based generation makes "controllable reliability" hold, formalized as three sub-propositions:

1. **Failure cost is bounded**: a single segment's failure cost ∝ \(N/k\), strictly better than a single long-range ∝ \(N\) — a single inference only bears a small segment of the task, and the blast radius is sealed by the phase boundary;
2. **State is knowable**: at any moment, which phase the system is in, which products are solidified, and how many steps remain from the goal, are all observable — the phase sequence and solidified products form a traceable execution trajectory;
3. **Rollback is possible**: any phase failure has a finite-step recovery path (return to checkpoint → regenerate with new context), without requiring a restart from zero — errors are absorbed by the phase boundary, not polluting the whole chain.

**Gap-driven handle bootstrapping closed loop (L4 living body expanded)**: when a certain phase's query has no hit (a gap), the subsequent phase registers a new handle via A8 install (the handle set is monotonically non-decreasing), the new handle re-enters the slice via re-query, is driven to execute, and the result is judged by the A10/L3 closed-set envelope — success closes the gap, failure rolls back the current phase to recreate (continuing from the A6 checkpoint). Therefore "whether the handle aligns to the gap" does not require judgment at install time, but is guaranteed by the absorption and rollback of the phase bootstrapping loop. This living-body mechanism lands A3's dynamic extension at the planning layer: one utterance immediately yields a result (semantic-space stability) is preserved; when a gap appears, the previous utterance does not lose its effect, and subsequent utterances sustain and complete its effect through the L4 bootstrapping loop, with success probability approaching 1 as attempts accumulate (conditioned on \(p_{\min}>0\) from A11).

**Theorem 1 (Recursive underwriting of P_conv^struct)** [Translator's note: the Chinese source numbers theorems independently within each major section, so this is a distinct theorem from the earlier "Theorem 1" of the second major section; the numbering follows the source verbatim.]: For a finite phase decomposition \(\langle\phi_1,\dots,\phi_n\rangle\) of task \(g\), if each phase \(\phi_i\) generates within its controlled-context template and gaps are filled by the L4 bootstrapping loop, then the \(P_{\text{conv}}^{\text{struct}}\) provided by the execution-layer projection (the four loops A5/L2/A10/L3) is preserved under recursive invocation: any phase's failure is located and rolled back to that phase for regeneration, not propagating upward to discard the whole chain; hence the whole task converges to the goal on the structural side, independent of \(p\). That is, phase-based generation constitutes a recursive underwriting of the execution-layer projection one layer above \(P_{\text{conv}}^{\text{struct}}\). ∎

#### Closing

The capability-invocation protocol (execution-layer projection) + phase-based generation (planning-layer projection) are **one supporting structure for AGI**. Both share the same source, "multiple inferences + multiple context reorganizations", projected respectively at the execution layer and the planning layer, complementarily closing \(P_{\text{conv}}^{\text{struct}}\) (execution layer + Theorem 1's recursive underwriting) and \(P_{\text{ctrl}}\) (phase-based generation's three sub-propositions).

**Second-major-section total closure (zero unproven items on the protocol side, the key boundary)**: the structural four loops (A4–A10, L2, L3, L4) and Theorem 1 are all closed within the document's axiom chain, independent of the LLM parameter \(p\). Therefore A3's unproven kernel has been **thoroughly dissolved down to a single empirical fact of the LLM** — the positive lower bound \(p_{\min}>0\) of hitting the correct handle (A11). This is neither provable by the protocol nor eliminable by structure: it is essentially the statistical property of "whether the LLM can create a handle aligned to the gap at the gap", belonging to the LLM itself, unrelated to the capability-invocation protocol. In other words, as long as the struct side closes (guaranteed by the protocol) + \(p_{\min}>0\) (guaranteed by the LLM), A3 holds, and all interfaces surfaced by the first major section have been taken up (S3 landed by A8 ecosystem bootstrapping, S2's struct four loops closed within the document, S2's model side and A3's dynamic-extension convergence probability conditioned on A11 left to measurement, A0's self-loop dissolved by the "capability production ↔ capability consumption" ecosystem growth mechanism).

> Universal-proof closure (the scope boundary of this major section): any protocol satisfying the minimal field structure of the universal proof (instruction four-tuple `declaration prefix, domain, action, parameter` / envelope three-field `response type, response data, error` / meta-instruction binary `query, install`, with field closures mechanically decidable and same-dimensional with the generation stream) closes A3 on the structural side and constitutes a supporting structure for AGI — text-cli, strict JSON tool invocation (if expressed in the same-dimensional minimal controlled form), or other protocols, with no ranking among them, are all within this proof. The difference among protocols is only in the amount of protocol tax (generation cost / failure rate), and **protocol tax is not judged in this major section**, left to the next chapter "Minimality / Protocol Tax"; the model-side premise \(p_{\min}>0\) is uniform for the whole family, unrelated to any specific protocol.

### The Settlement of A3: AGI as a Dynamically Growing Structure

**Review of the premises for closure (the six threads have been laid separately in the preceding text; here they converge to one point)**: dynamic AGI is not newly established here; each of its pillars has already landed in the derivation chain, only each carrying a "not expanded here" deferral label before, now uniformly recalled:

- **The seed of the growth mechanism** — A0's self-loop: the loop of "defining the scope by capability" is the growth mechanism (p36), which referred to "the protocol's instruction expansion";
- **The execution landing of the growth mechanism** — A8 ecosystem bootstrapping: the "capability production ↔ capability consumption" loop makes the ecosystem approach the set of physically realizable capabilities (p183), then only labeled "closes S3";
- **The dynamic extension of A3** — one utterance immediately yields a result, gaps sustained in effect by subsequent utterances through the L4 bootstrapping loop (p55), then labeled "not expanded here";
- **The embryonic form of the breadth axis** — the three formulas of coverage κ: structural-side monotonic non-decrease (A8+L4), model-side approach to 1 conditioned on \(p_{\min}>0\), external upper bound \(\kappa_{\max}\) (p277–282), then handled as a "coverage proposition";
- **The common premise of the two axes** — A11: \(p_{\min}>0\) as the growth-rate lower bound (p290), then only treated as a "feasibility precondition";
- **The seed of the orthogonality thesis** — D1: "whether it is AGI is determined by structure, independent of parameter scale" (p58), then only one sentence without expansion.

The six belong to different sections and were each deferred before, but they jointly point to the same conclusion: **once A3 is closed on the struct side (guaranteed by the protocol) and conditioned on \(p_{\min}>0\) (guaranteed by the LLM), it is not a "static capability set completed once", but a growing body with structure as its foundation, parameters and ecosystem as its nutrients, growing along two orthogonal axes**. This is the settlement of A3, not a new axiom, not a supplementary proof, but the confluence of the six threads at the point of closure.

The second major section has fully closed A3's mechanism on the structural side (execution-layer projection + planning-layer projection, the struct four loops and Theorem 1 established within the document's axiom chain, with only \(p_{\min}>0\) remaining as one LLM empirical premise). T1 of the first major section has already proven "A3 ⇒ one realization of AGI" — here that implication is settled as the complete form of AGI under the text-cli protocol, i.e., the settlement of A3 (not a reduction-layer completion, nor an after-the-fact supplementary proof):

**AGI as a dynamically growing structure**: AGI is a continuously growing body with structure as its foundation and parameters and ecosystem as its nutrients, described by two orthogonal axes — the height axis (performance level \(=f(p)\), structure sets the threshold, \(p\) sets the ceiling) and the breadth axis (coverage κ driven by ecosystem bootstrapping); the two axes have \(p_{\min}>0\) from A11 as their growth-rate lower bound.

This is the qualitative form of A3 "uttering speech and obtaining a result" after the protocol runs through: the structural side (threshold + κ monotonic non-decrease) has closed, so the structure supporting AGI is established; its "degree" is calibrated by the growth rate determined by \(p_{\min}\) and the current empirical value of κ. A3's dynamic extension (one utterance immediately yields a result + subsequent utterances sustaining effect through the L4 bootstrapping loop) is settled here as "AGI as a growing structure, foundation established, growth irreversible".

#### The \(p_{\min}>0\) Bifurcation: Four Growth Modalities of Dynamic AGI

\(p_{\min}>0\) is A11's growth-rate lower bound (the positive lower bound of the LLM creating, at the gap, a handle aligned to the gap), an empirical fact left to measurement; this document does not prove its value. But under "acknowledging \(p_{\min}>0\) as the premise", one can, by **gap type**, explain case-by-case how dynamic AGI grows — this expands "dynamically growing structure" from a qualitative statement into a modality-by-modality mechanism portrait, without introducing new axioms or disguising \(p_{\min}\) as proven.

- **Modality A (near gap · smooth growth)**: the gap falls in the neighborhood of an already-reachable handle (only needs context-based generation-by-example or combination of existing handles to align). Here \(p_{\min}\) in that neighborhood is high, κ's monotonic term (A8+L4) absorbs quickly, and the L4 bootstrapping loop closes in one or two attempts. Dynamic AGI manifests as **smooth growth** — the capability set expands continuously along the known boundary, without jumps.
- **Modality B (far gap · step growth)**: the gap requires a capability type that never existed before (a new handle must be created from scratch, e.g., writing a new tool). Here \(p_{\min}\) is determined by the LLM's ability to "create new structure", and is the dominant case pulling down the lower bound. Under \(p_{\min}>0\), the probability that an un-taken-up task remains un-taken-up after \(k\) attempts is \((1-p_{\min})^k\to 0\), so a far gap **is eventually taken up**, and dynamic AGI manifests as **step growth** — the capability set jumps and expands at the new type. (query → create → install → query → invoke)
- **Modality C (concurrent gaps · parallel growth)**: a compound task simultaneously splits out multiple gaps, each gap running its own independent L4 bootstrapping loop in parallel. κ's monotonic non-decrease holds gap-by-gap, so concurrency remains monotonic; the overall take-up time scales with the number of gaps, but the growth rate is still determined by each gap's own \(p_{\min}\). Dynamic AGI manifests as **parallel growth** — multiple axes expanding outward simultaneously. (multiple query → create → install → query → invoke, in parallel)
- **Modality D (\(p_{\min}=0\) · growth boundary)**: if a certain class of gaps has \(p_{\min}=0\) (the LLM cannot create an aligned handle on that class of tasks no matter what), then that class of gaps never closes, and κ is stuck at \(<1\). This is exactly the precise meaning of A11's "conditioned on \(p_{\min}>0\)" — the completeness of dynamic AGI is **conditional completeness**, whose growth boundary is delimited by the LLM's own capability subset, not a protocol flaw. (query → no creation possible → persistently un-hit)

The four modalities together show: dynamic AGI's "growability" is not "omnipotent growth", but "within the capability subset of \(p_{\min}>0\), growing continuously by gap type (smooth / step / parallel), and stopping at \(p_{\min}=0\)". The structural side (threshold + κ monotonic non-decrease) guarantees that once growth starts it is irreversible and does not roll back; \(p_{\min}>0\) guarantees that growth eventually approaches completeness (except the class-D boundary). The two are orthogonal, consistent with the orthogonality thesis of "structure sets the threshold, parameters set the degree".

> The "handle" exists not only in the ecosystem registry (A5/A8/L4), but also in the LLM's generation stream on the spot — **every token generation of the LLM is a handle alignment**: within the controlled context, aligning the next token to some landing point in the finite handle closure. So `p_min>0` should be read as "the positive lower bound of a single generation aligning to the gap-aligned handle", and the `k` in Modality B's `(1-p_min)^k→0` is the number of generation/attempt steps. The structural side decides in which controlled context the alignment happens and to which finite set it aligns; the model side's `p_min>0` decides the base probability of that alignment hitting — the two are orthogonal at the "single generation" site, exactly isomorphic with this section's closure of "structure sets the threshold, parameters set the degree".

## The Properties of the text-cli Protocol Itself

> This chapter answers "why text-cli can bear the role of the 'execution-layer projection' in the preceding derivation", and is an explanatory complement to the preceding main thread.

### text-cli's Adaptation to the `Universal-Proof Capability-Invocation Protocol`

The second major section established the "universal proof": any protocol whose instruction contains the four fields `declaration prefix, domain, action, parameter`, whose envelope contains the three fields `response type, response data, error`, whose meta-instruction contains the binary `query, install`, and whose field closures are mechanically decidable and same-dimensional with the generation stream, can close the structural side of `dynamic AGI`; the difference among protocols is only in protocol tax (generation cost / failure rate), and the judgment of tax is left to this chapter.

The thesis of this chapter is: **text-cli is the zero-expansion instance of the `universal-proof capability-invocation protocol` under the minimal field structure** — it exactly hits the minimal-field lower bound of the universal proof (instruction four-tuple / envelope three-field / meta-instruction binary), and does no cross-dimensional expansion (introduces no nested structure, requires no strict schema matching, and does not cast semantics into a structural dimension); its instruction is same-dimensional with the token stream, so its protocol tax is zero. In other words, text-cli is not "another protocol satisfying the universal proof", but "the protocol that takes the minimal field structure of the universal proof to its zero-expansion limit"; JSON tool invocation, if also expressed in the same-dimensional minimal controlled form, can likewise achieve zero tax, but text-cli is the concrete instance already landed in this form.

Therefore the sections below are not a scattered list of text-cli properties, but a facet-by-facet exposition of this thesis:

- **One-Dimensional Contract** — proves "same-dimensionality ⇒ zero protocol tax", i.e., why text-cli falls on the zero-expansion limit;
- **Phase Reasoning** — proves text-cli uses the three universal-proof properties (one-dimensional recursion / closed-set envelope / query-install) to naturally support planning-layer phase-based generation;
- **Minimality** — proves text-cli hits the universal proof's minimal fields and does no cross-dimensional expansion above the root, hence zero expansion;
- **Instruction Expansion** — proves minimality makes package creation cheap ⇒ ecosystem coverage κ approaches the set of physically realizable capabilities;
- **Adaptation to LLM — Parameters and Performance Level** — proves the same-dimensional projection is insensitive to parameter \(p\) ⇒ structure sets the AGI threshold, \(p\) sets the performance ceiling.

The five sections together establish "text-cli = the zero-tax instance under the universal proof", and bring the protocol tax deferred by the second major section to closure in this chapter, with text-cli as the concrete specimen.

### The Protocol's "One-Dimensional Contract"

**Core proposition**: the one-dimensional contract = the only structural bottom line the protocol holds — any capability, however complex its backend (single function / aggregation / path / federation), externally converges to a single cognitive dimension of "one `AI:domain;action,parameter` in, one three-field envelope `{rst_types,rst_data,rst_err}` out".

#### Foundation: Same-Dimensional Projection (the essence of one-dimensionality)

The "one-dimensional" of the "one-dimensional contract" is not a dimensionality reduction that "compresses multiple dimensions into one", but a same-dimensionality that "never leaves the language dimension". Its complete argument has three steps:

1. **The one-dimensionality of the LLM's generation medium**: the LLM's output is an autoregressive, left-to-right **one-dimensional token stream** — it always only "predicts the next most relevant token", and this medium is naturally one-dimensional (Lemma L2).

2. **The one-dimensionality of the protocol's target structure**: the target structure of `AI:domain;action,parameter` is a linear imperative sentence — domain, action, parameter are three sequentially arranged fragments, and the target structure itself is one-dimensional, containing no nesting and no multi-dimensional structure requiring "matching brackets".

3. **The two are same-dimensional**: when a protocol requires the LLM to output a cross-dimensional structurally redundant form (e.g., strict JSON tool invocation), it is actually requiring the LLM to additionally **simulate** a multi-dimensional structure (nesting, brackets, types) within the "one-dimensional token stream" — i.e., making a one-dimensional medium encode a multi-dimensional target; this is "cross-dimensional projection", where each step's generation is an independent fatal point (a malformed or field-mismatched generation voids the entire attempt). Whereas the target structure of `AI:domain;action,parameter` is itself one-dimensional, so the LLM's one-dimensional medium and the protocol's one-dimensional target are **same-dimensional**, and the LLM does not need to simulate, in the token stream, anything it does not naturally produce; moreover, the same-dimensional form has only the unified envelope (short) as 1 fatal point, and \(N\) instructions are regex-parseable, tolerant, and coverable — the cross-dimensional form spreads the risk to \(N\) independent fatal points on the failure side, while the same-dimensional form compresses the risk to 1 envelope fatal point; this is the direct manifestation of "same-dimensionality" on the failure side (see Corollary 3 for the mechanism).

Therefore "one-dimensional = same-dimensional": the value of the one-dimensional contract is not in "being few", but in "not crossing dimensions".

#### Corollary 1: One-Dimensionality of Cognition

Because of same-dimensionality, the caller only needs to understand one causal relation — "one sentence in, one envelope out". This is the bottom line the protocol holds (mandatory, independent of implementation), and is the source of the "being-integrated" posture: the protocol is a seam, not a framework.

#### Corollary 2: One-Dimensionality of Contract Shape

Precisely because cognition is one-dimensional, backend complexity (aggregation degradation, path orchestration, federation multi-hop, multi-provider routing) is **forcibly hidden behind the seam** — one-dimensionality is the bottom line, not a simplification; it forces out the shape of "arbitrarily complex backend, always one sentence externally".

#### Corollary 3: One-Dimensionality of Generation

Precisely because of same-dimensionality, the LLM, when generating, only needs to do one-dimensional prediction on the text stream, without switching to a multi-dimensional structured mode (the "prediction main axis / no mode switching" of Lemmas L1/L2). Its "lowest generation cost" is verifiable by the length-error accumulation law, and is precisely the manifestation of "same-dimensionality" on the generation side:

Let the per-token error rate in autoregressive generation be \(\varepsilon\) (\(0 < \varepsilon < 1\)); the probability that a segment of \(n\) tokens is entirely correct is \((1-\varepsilon)^n\), and the error probability of the whole segment accumulates with length \(n\); a stronger model can only reduce \(\varepsilon\), not remove the \(n\)-th power — this is structural. Comparing the failure probabilities of two instruction forms:

- **Cross-dimensional structurally redundant form** (e.g., strict JSON tool invocation): each step's generation is an independent fatal point; stringing \(N\) invocations has total length about \(N \cdot c_{\text{cross}}\), with failure probability about \(1 - (1-\varepsilon)^{N \cdot c_{\text{cross}}}\), the exponent growing with \(N\).
- **Same-dimensional minimal controlled form** (e.g., `AI:domain,action,parameter`): the instruction is only three positions "domain, action, parameter" plus two separators, regex-parseable, no structural redundancy; only the unified envelope (short) is 1 fatal point; the \(N\) instructions are tolerant and coverable, with failure probability about \(1 - (1-\varepsilon)^{c_{\text{env}} + N \cdot c_{\text{step}}}\).

Because \(c_{\text{step}} \ll c_{\text{cross}}\), the exponent of the same-dimensional form is far smaller than that of the cross-dimensional form, the failure probability is lower, and the advantage grows with \(N\). The root cause is not "compressing \(N\) into 1 fatal point", but "the minimal controlled form of the instruction (same-dimensional, regex-parseable) makes per-step generation cost far lower than cross-dimensional structural redundancy" — hence "the same-dimensional form's tax is lower than the cross-dimensional form's" is a verifiable conclusion derived from the length-error accumulation law, not an empirical guess, and does not single out any specific protocol (text-cli, JSON tool invocation, or other protocols, as long as they fall into the same-dimensional minimal controlled form, hold this conclusion; cross-dimensional implementations have a higher tax). The concrete comparison of protocol tax is in the "Minimality / Protocol Tax" section.

#### Corollary 4: Recursive Convergence

Path re-converges \(N\)-step orchestration back into one sentence `AI:text-cli;path,<name>,<input>`, returning again to "one sentence in, one envelope out" — multi-step orchestration is re-packaged into one sentence. This is the reuse of "same-dimensionality" at a higher granularity: any complexity can recursively converge back to one dimension, without breaking the one-dimensionality of cognition.

#### The Nail: Zero Protocol Tax

The "same-dimensionality" of the one-dimensional contract means "zero protocol tax" — it does not require the LLM to additionally simulate any structure during generation, hence does not deplete parameter p. Any cross-dimensional expansion introduces a tax (see "Protocol Tax" in "Minimality" and the "LLM Parameters and Performance Level" section). This is the connection point between the "one-dimensional contract" and the "parameters" sections.

### The Protocol's "Phase Reasoning"

**Core proposition**: phase reasoning is not an extra mechanism bolted onto the protocol, but the combined use of three properties of the tc protocol system at the "planning layer" — it is the protocol-side reflection of the earlier "phase-based generation" in the third paragraph: the third paragraph proves, from "derivation", that phase-based generation closes P; this section proves, from "protocol", that phase reasoning is exactly the usage naturally supported by this protocol.

**Three protocol properties → three corresponding facets of phase reasoning**:

1. **The recursive convergence of the one-dimensional contract → the recursive layering of phases** (the joint: the self-reference of "everything is an instruction").
   - Premise: the one-dimensional contract requires "any capability externally converges to one sentence".
   - Joint: `text-cli;path` / `text-cli;pro` are **ordinary instructions** registered by `@directive`, so "one path sentence" can internally reference "another path sentence" — this is a direct consequence of "everything is an instruction", not a new mechanism.
   - Conclusion: therefore the layering of "phase → sub-phase → … → path" is the direct use of the existing recursive property "one sentence nesting another" at the planning layer, not an additional invention.

2. **The state-knowability of the unified envelope → the gates and rollback of phases** (the joint: the mechanical decidability of the closed-set envelope).
   - Premise: the unified envelope `{rst_types, rst_data, rst_err}` is a **closed set** — error codes are finite and predefined.
   - Joint: because the error codes are a closed set, "judging whether this step succeeded or failed" **does not require extra LLM reasoning** — one only needs to compare whether `rst_err` is empty to mechanically read the state.
   - Conclusion: therefore gate judgment and checkpoint rollback have a protocol-layer basis — a gate is not "the LLM guessing right or wrong", but "a clear failure signal in the envelope"; this exactly corresponds to sub-proposition 3 (state-knowability) of "controllable reliability" in the third paragraph: state is knowable not because the system is smart, but because the closed-set envelope makes state mechanically readable.

3. **query/install (introspection + expansion) → the per-phase tool directory of phases** (the joint: the dynamism of "registration is the directory").
   - Premise: `text-cli;query` returns "the instructions currently registered in the runtime" (the registered node handles in the ecosystem), and `install` changes "what is registered".
   - Joint: hence the "available tool set" is not a static global constant, but a function of "the runtime's registration state at this moment".
   - Conclusion: therefore "each phase exposes a different tool directory" is not hardcoding different lists, but querying out "a slice of the registration state" at different phases — the "phase-ization" of the tool directory is essentially the slicing of the "registration state" on the time axis.

**Reflection**: the joints of these three — self-reference, closed set, registration-as-directory — are the three innermost properties of the tc protocol; phase reasoning introduces nothing new beyond the protocol, but merely **superimposes these three properties onto the planning layer**. This is exactly the protocol-layer landing of the third paragraph's "phase-based generation"'s "layered phasing", "controllable reliability", and "context reorganization". Hence phase reasoning is not a new mechanism, but the necessary usage of the protocol system at the planning layer. The mechanism details of phase reasoning (phase splitting, gate semantics, etc.) are in the appendix "Phase Reasoning Mechanism".

### The Protocol's "Minimality"

The text-cli protocol is the agreement that lets a deterministic Turing machine and a probabilistic language model reach the lowest consensus — the agreement with the fewest explicitly required semantic markers, without introducing extra parsing difficulty and generation difficulty.

#### The Irreducible Root

Any effective tool-invocation protocol must contain at least:
· target domain (which service/capability)
· action (what to do)
· parameter (the concrete input)
and, to work in an open world, must also possess:
· introspection (querying available capabilities)
· expansion (installing new capabilities)
These elements are "semantically necessary", not stylistic choices. Therefore the tool abstractions of protocols — semantically all contain these elements, only wrapped in different syntactic sugar.
Moreover, all protocols add syntax and features on top of the root. All expanded protocols should state clearly why they expand beyond the root.

> From this a seed of the cost law can be drawn: since the root is irreducible, the differences among protocols all lie in "how much has been added above the root"; and each added layer of expansion (especially "cross-dimensional expansion" that casts semantics into a structural dimension) collects an additional "protocol tax". This tax is ultimately borne by the caller's generation capability (see "Protocol Tax" and "LLM Parameters and Performance Level" below).

#### Minimality Proof

At the semantic level of "AI–system interaction", the tc protocol is an "irreducible" set: removing any core element would break A3 (low-difficulty generation), or A4 (unified execution), or A8 (extensibility). Below, three progressive propositions — "first fix the shape, then the dynamics, then the result" — argue its minimality.

**Proposition A: Shape is minimal (the unified constraint of syntax + cognition)**

"Shape is minimal" is not a purely syntactic proposition, but the minimal consensus point under the triple constraint of "machine-parseable, distinguishable from chat text, LLM-generatable" — syntax and cognition are two faces of the same constraint, argued together:

- **De-structural redundancy**: compared with JSON-RPC (`{"name":"get_weather","args":{"city":"..."}}`), `domain;action,parameter` removes structural redundancy such as quotes, brackets, and repeated key names, and is the limit of flattening key-value pairs.
- **The semantic closure that cannot be reduced further**: removing the domain causes namespace conflict under A8; removing the action makes it impossible to distinguish "query" from "execute"; removing the `AI:` prefix makes it indistinguishable from ordinary chat text and breaks A4's instruction routing. Hence `AI:` / domain / action are the minimal syntactic closure.
- **The critical point**: if completely unstructured (pure natural language), the machine cannot parse stably (breaking A4); if too strict (XML), it violates A3's high-probability generation. `AI:domain;action,parameter` lands exactly on the intersection of "machine-regex-parseable, LLM-intuitively-fillable" — it is essentially "delimited plain text", belonging to the highest-frequency writing format in LLM pretraining (email headers, logs), falling within the LLM's native high-probability generation distribution.

**Proposition B: Dynamics are minimal (introspection + expansion, the self-sustaining reflective instruction pair)**

The tc meta-instructions are not "additional features", but necessary conditions for the protocol's self-sustainability:

- **query (introspection)**: in A6 (feedback correction), without query, the LLM can only rely on static context or fine-tuned memory of the instruction format, which immediately fails under A8's dynamic expansion. query is the minimal entropy-reduction mechanism that "keeps the protocol and the LLM's context in sync". (What is queried is the currently reachable node handles in the ecosystem.)
- **install (expansion)**: if the protocol only defines execution, not installation, the system gets stuck when the task exceeds the current instruction space. install brings the "capability boundary" into the protocol itself, so that the instruction set (the handle set in the ecosystem) can be traversed by the protocol itself. (What is installed is a new capability node in the ecosystem — the capability node achieves alignment through the handle.)

The two constitute the protocol's bootstrapping loop: removing query, the protocol cannot cope with unknown environments; removing install, the protocol cannot break through its initial boundary. Structurally, this is equivalent to "a system must possess at least the two primitives of 'seeing itself' and 'changing itself' to operate continuously without external intervention" — tc does it with two natural-language instructions.

**Proposition C: Result is minimal (unified envelope = minimal algebraic data type)**

`{rst_types, rst_data, rst_err}` is the minimal algebraic data type (ADT) of the execution layer (A4):

- `rst_err`: distinguishes success/failure, the premise of feedback correction A6;
- `rst_types`: distinguishes result type (pure text / binary / intermediate state), the premise of the LLM's next planning step;
- `rst_data`: carries the actual payload.

The three fields are exactly the minimal representation of the `Result<T, E>` pattern under flat JSON: with fewer than three fields, one cannot simultaneously distinguish "success/failure", "result type", and "actual data" without ambiguity.

**Closure: a conditionally minimal set, not an absolutely minimal set**

Under the three constraints A3 (generation difficulty low enough), A4 (machine unified execution), and A8 (decentralized extensibility), tc achieves "irreducibility" — removing any core element breaks at least one of A3, A4, A8. Therefore it is **a conditionally minimal set under this group of engineering axioms, not an unconditional absolute mathematical minimal set**. All protocols expanding above the root should state clearly "why they expand beyond the root".

**Protocol Tax: the Bridge between Minimality and Parameters (the hook)**

"Minimality" and the next section "Parameters and Performance Level" are two faces of the same coin, and their connection point is a universal cost law:

- **Expansion = adding dimensions = adding tax**. tc's root is a same-dimensional projection (stays within the semantic space, does not cross dimensions), hence "zero tax"; any expansion above the root that casts semantics into a structural dimension (e.g., strict JSON Schema, nested types, required fields) introduces a "cross-dimensional projection", and thus collects an additional "protocol tax" on "machine parsing" or "LLM generation".
- **Who bears the tax**: the protocol tax is ultimately borne by the caller's generation capability — a cross-dimensional protocol requires the caller to additionally maintain structure while generating instructions, which consumes the caller's generation cost (for AI, parameter p: generation difficulty rises, per-attempt success rate falls), not a free benefit brought by "the protocol being more precise".
- **Direction of conclusion**: tc's same-dimensional projection makes "structure" insensitive to "parameter p" (does not deplete p), hence "whether it is AGI" is determined by structure, independent of p; whereas any cross-dimensional expansion discounts p, hence "performance level" varies with p (and protocol tax). This is exactly what the next section will settle.

> This section closes here: minimality answers "why the protocol is shaped zero-tax"; how this tax affects AGI's performance level is in the later "LLM Parameters and Performance Level".

### The Protocol's "Instruction Expansion"

**Core proposition**: because the protocol is small (minimality), "implementing a capability node in the ecosystem" has extremely low cost — this is the source of "ecosystem accessibility". And the accessibility of the ecosystem makes A8's "extensibility" not an empty infinity, but "a finite approximation to physically realizable capabilities".

**Argument**:

1. **Small protocol ⇒ cheap tool creation**. Because the protocol only needs "one imperative sentence", the package creator only needs to translate the capability into one `domain;action,parameter`, without understanding the protocol's internals. A function package is an `@directive` decorator; an online API package is a credential config; an MCP bridge is two JSONs (zero Python); a nocode document package is a single Markdown (zero code).

2. **Not picky about programming language**. Any language, protocol, or even zero language can create a package. And the step of "creating a package" itself can be handed to AI (handing a Markdown to AI, letting it fill in the package's three custom sections), thus forming an **AI self-loop**: AI is both the "capability consumer" (using the protocol to invoke capabilities) and the "capability producer" (using the protocol to turn human experience into packages) — capability production and consumption close the loop on the protocol, without human programmer intervention.

3. **Not bound to a natural language**. The field labels are language-configurable (zh / en / fr / ar / es / ru / ja / ko, etc.); adding a language = adding a line of config, with zero change to the parsing logic. Hence a person who cannot program, and does not know a specific language, can still write their experience in their own language and turn it into a capability.

4. **Corollary: tool accessibility ⇒ ecosystem node coverage approaches the set of physically realizable capabilities**. Because the barrier to package creation is as low as "speaking suffices", the packages in the ecosystem can cover most realizable tasks; thus A8's "install expansion" is not an empty infinity, but "a finite approximation to realizable capabilities guaranteed by tool accessibility".

5. **Self-loop (echoing the scope delimitation at the beginning)**. From this one can look back at the "realizability loop" at the beginning: D0 defines realizability by "there exists a finite action sequence to reach", and "reachability" depends on system capability, seemingly a circular definition. But this loop is not a flaw to be eliminated, but a **self-loop** — system capability (via A8 expansion + tool accessibility) can produce new capabilities, making the "reachable" set dynamically expand; "realizable" is not a pre-given a priori boundary, but recursively approached by the "capability production ↔ capability consumption" self-loop. The stronger the capability, the more that can be achieved; the more that can be achieved, the more new capability packages are catalyzed — the loop here is not a hole, but the mechanism of growth.

6. **Closure: "speaking suffices to reproduce"**. The protocol is small enough to return "tool creation" to "speaking", the lowest common denominator of all humanity — no code, no specific language, just speaking. This is the ultimate realization of "language is the bridge of capabilities among humans / machines / AI" on the "tool production" side.

### The "Parameters" of LLM and the Performance Level of AGI

**Core proposition**: AGI's "whether it holds" is determined by structure, and AGI's "performance level" is determined by parameters — the two are orthogonal; the root of this orthogonality lies in "structure (how to use cognition to act) and cognition (subset quality) are not the same thing in the first place", and text-cli's same-dimensional projection makes structure insensitive to cognition.

**Derivation**:

1. **The source and inertia of the semantic space**. Training data comes from human knowledge records, a subset of the semantic space of language users; the "knowledge" the LLM subsequently self-reasons out also conforms to the inertia of human knowledge because of the token-prediction mechanism. And the semantic space **evolves with content**, not a static container.

2. **Cognition = fixing a private subset from the semantic space**. Human cognition fixes and updates a subset from the semantic space through learning; the completion of LLM training **fixes a version of cognition** (parameter solidification). The two are structurally isomorphic in "fixing a subset" — but this is only an ontological fact, not entering the AGI criterion.

3. **Cognition does not decide "whether it is AGI", only "planning level"**. Parameter p characterizes "how close this AI's private subset is to the high-value region of the current semantic space"; it causes a **deviation in planning level** (a human's knowledge is less than a high-parameter model), not "whether it can be AGI".

4. **Structure decides "whether it is AGI", parameters decide "the ceiling"**. AGI = AI + complete structure (text-cli + phase-based generation), with the subject fixed as AI; under this premise, parameter p only decides "how useful this AGI is" — **higher parameters = more useful AGI, not 'more AGI'**.

5. **Same-dimensional projection makes "parameters → performance" lossless**. text-cli is a same-dimensional projection, not requiring the AI to possess capabilities outside the semantic space, hence the mapping "parameter p → performance level" is not discounted by the protocol (zero protocol tax); any cross-dimensional expansion taxes this mapping.

6. **Settlement**: "whether it is AGI" is determined by structure (the threshold), "performance level" is determined by parameters (the ceiling), the two orthogonal. Performance level is a monotonic function of p — the higher p, the higher the planning level, the more useful the AGI; but the threshold is structure, the ceiling is p.

**Boundary statements**: ① "cognitive isomorphism" (humans and LLMs both fix a semantic-space subset) is an ontological fact, but AGI's subject is limited to AI, so "humans are not AGI"; ② "who the user is" is another orthogonal axis — humans / machines / AI can all stand on the language bridge, and the framework does not care; ③ this section only settles the one account of "how parameters decide performance level", touching the semantic-space ontology only lightly, without expansion.

**Open question**: the quantitative form of "performance level = f(p)" (to what degree monotonic, whether linear) has no basis yet, left open; this document only gives the qualitative conclusion of "monotonic + only sets the ceiling".


## Appendix: Phase Reasoning Mechanism

> This appendix takes up the mechanism details of the "Protocol's 'Phase Reasoning'" section, expanding separately the skeleton of phase reasoning (phase splitting, gate semantics, etc.). The main text has already proven "phase reasoning is the necessary usage of the protocol system"; here only the mechanism skeleton is listed, without repeating the argument.

**Core proposition**: phase reasoning = the projection of "multiple inferences + multiple context reorganizations" at the planning layer, organizing "completing a task" as "a series of inferences in reorganized contexts". It is the projection of the combined use of protocols (recursive convergence + closed-set envelope + query), not an independent axiom — phase splitting, gate judgment, and context reorganization are all essentially rearrangements of the three tc primitives.

**Derivation skeleton**:

1. **Recursive layering + minimal cut criterion**: phases are a recursively layered structure — phase → sub-phase → … → path; path is the minimal execution unit supported and stably output by the tc protocol (isomorphic with the recursive convergence of the "one-dimensional contract"). The criterion of the minimal cut is **mechanically decidable**: a phase can be cut into a sub-phase if and only if the sub-phase has "a stable input contract + a stable output envelope (closed-set `rst_types`/`rst_err`) + a solidifiable product". The cut does not depend on the LLM's "smartness", only on whether the contract is closed.

2. **Context reorganization = controlled fields**: each phase reorganizes context, but reorganization **is not arbitrary rewriting**, but a projection onto the three controlled fields of "previous phase's product + this phase's task + this phase's tool directory". Exposing a small tool directory lets the LLM bear only a small cognitive load at a time — this is load-leveling within the P_ctrl domain, not assuming the LLM's global comprehension.

3. **Three-gate judge dispatch + closed set**: phases are connected by explicit gates, and gates are interfaces, not entities. Judges are dispatched in three classes — mechanical gate (MechanicalGate, pure rules, e.g., contract validation / timeout), LLM gate (LLMGate, judging `confirm/reject/regenerate`), human gate (human_approval, high-risk rollback). The gate actions themselves are a **closed set**: `confirm / reject / regenerate / regenerate_with_new_context`; failure returns to the previous checkpoint (product solidification), regenerating with new context. Judge selection is a config item, not runtime discretion.

4. **Observability = g**: "state is known" does not rely on after-the-fact auditing, but on each phase producing an observable snapshot `g` (accumulated phase_summaries + current gate state), so that the system state at any moment can be reconstructed from `g`. This is the mechanism landing of the "state is known" sub-proposition of "controllable reliability", belonging to the P_ctrl closure requirement.

5. **Recursive self-healing + bounded termination**: "how to split phases" is itself an LLM generation, and can likewise be error-reduced by phase-ization — the splitting step is decomposed into "coarse split first, then refine", isomorphic with "multiple inferences + multiple context reorganizations" at the meta layer. But self-healing is **bounded**: recursion depth is constrained by `max_phase_depth`; exceeding it degrades to a pure mechanical minimal plan (no LLM invocation), guaranteeing that termination belongs to the P_ctrl closure.

**Closure (P_ctrl closure)**: the above jointly guarantees the three sub-propositions of "controllable reliability" — ① failure cost is localized (worst-case cost N/k < N, from slot one's minimal cut and slot three's checkpoint); ② state is known (slot four's g); ③ recoverable (slot three's return + slot five's bounded self-healing). The conjunction of the three is the closure of the phase mechanism within the P_ctrl domain, orthogonal to "success probability P_conv" (P_conv is not proven here).


## Appendix: Semantic Space, Cognitive Isomorphism, and Intelligence

> This appendix expands the ontology touched only lightly in the main text's "LLM Parameters and Performance Level". It is about "intelligence", a layer broader than AGI, not AGI itself: AGI = AI's intelligence + complete structure (subject limited to AI), see the main text; this appendix only covers the "semantic space → cognition → intelligence" segment, not crossing into the AGI criterion.

### 1. Semantic Space

Language users, through using language, jointly sustain a semantic continuum that evolves with content.

The reason the semantic space can be the "source" of all this is that "meaning" can only arise in "use" — it is not a static "dictionary" defined by some person or institution, but a living continuum jointly written by all speakers in every use. Precisely because it has "no arbiter" (meaning arises from use, not from some legal decree), it can be the bridge shared by the three (humans / machines / AI): if the semantic space were defined rigidly by some center, it could not accommodate the newcomer "machine"; precisely because it "grows through use", any entity that can use language and write meaning into it is naturally within the semantic space.

It evolves with content: each sentence written adds a point to the semantic space. It is not a static container, but a flowing stream of capability — this is the root of the proposition "language is the bridge of all human capabilities" (see the main text's main thread).

### 2. Cognition = Fixing a Private Subset from the Semantic Space

The essence of "cognition" is cutting out a "finite, private" subset from the "infinitely flowing semantic space", and freezing it for one's own use.

- **Human cognition**: through learning, fixes a privately deployed subset from the semantic space; long-term learning is the continuous update of this subset.
- **LLM cognition**: the completion of training fixes a version of cognition (parameter solidification).

The difference between the two is not "whether there is cognition", but "how the subset is updated": humans are incremental and continuously updatable; LLMs are batch and frozen at the end of training. And "isomorphism" refers to the deeper layer — **both cannot escape the very act of "cutting a subset from the semantic space"**. This isomorphism is an ontological fact, but it does not enter the AGI criterion: it only says "humans and LLMs share the same source of cognition", and does not thereby bring "humans" into the category of "AGI".

### 3. Intelligence

"Intelligence" is the qualification of "being able to fix a semantic-space subset and act on the world accordingly".

Humans, animals, and LLMs all have "intelligence" — they are all fixing subsets, only the subset quality differs. But a boundary must be drawn here: **"intelligence" answers "do you have cognition", "AGI" answers "can you complete arbitrary realizable tasks"**. The former only requires "having a subset", the latter requires "AI's subset + complete structure".

Therefore "intelligence" is a **necessary, but not sufficient, condition for "AGI"**: having intelligence does not necessarily mean AGI (a person, a dog both have intelligence, but are not AGI); AGI necessarily has intelligence (AGI must first be an AI that can fix a subset). The meaning of this boundary is to completely separate "who is qualified to speak of intelligence" from "who is qualified to speak of AGI" — avoiding diluting the strictness of "AGI" with the broadness of "intelligence".

Thus this appendix stops at "intelligence", not deriving AGI — the AGI criterion is in the main text, with the subject limited to AI; "who the user is" (which of humans / machines / AI stands on the language bridge) is another orthogonal axis, which the framework does not care about.
