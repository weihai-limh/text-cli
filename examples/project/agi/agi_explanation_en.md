# The Solution to AGI

> **Disclaimer**: This English translation was produced by an LLM based on the Chinese source document. In case of any discrepancy, **the Chinese version takes precedence**.

## Turning 'Intelligence' into Action

### Semantic Space

Language users, through using language, jointly sustain a semantic continuum that evolves with content.

The reason the semantic space can be the "source" of all this is that "meaning" can only arise in "use" — it is not a static "dictionary" defined by some person or institution, but a living continuum jointly written by all speakers in every use. Precisely because it has "no arbiter" (meaning arises from use, not from some legal decree), it can be the bridge shared by the three (humans / machines / AI): if the semantic space were defined rigidly by some center, it could not accommodate the newcomer "machine"; precisely because it "grows through use", any entity that can use language and write meaning into it is naturally within the semantic space.

It evolves with content: each sentence written adds a point to the semantic space. It is not a static container, but a flowing stream of capability — this is the root of the proposition "language is the bridge of all human capabilities" (see the main thread of the main text).

### Cognition = Fixing a Private Subset from the Semantic Space

The essence of "cognition" is cutting out a "finite, private" subset from the "infinitely flowing semantic space", and freezing it for one's own use.

- **Human cognition**: through learning, fixes a privately deployed subset from the semantic space; long-term learning is the continuous update of this subset.
- **LLM cognition**: the completion of training fixes a version of cognition (parameter solidification).

The difference between the two is not "whether there is cognition", but "how the subset is updated": humans are incremental and continuously updatable; LLMs are batch and frozen at the end of training. And "isomorphism" refers to the deeper layer — **both cannot escape the very act of "cutting a subset from the semantic space"**. This isomorphism is an ontological fact, but it does not enter the AGI criterion: it only says "humans and LLMs share the same source of cognition", and does not thereby bring "humans" into the category of "AGI".


### Intelligence and AGI

"Intelligence" is the qualification of "being able to fix a semantic-space subset and act on the world accordingly".

Humans, animals, and LLMs all have "intelligence" — they are all fixing subsets, only the subset quality differs. But a boundary must be drawn here: **"intelligence" answers "do you have cognition", "AGI" answers "can you complete arbitrary realizable tasks"**. The former only requires "having a subset", the latter requires "AI's subset + complete reasoning structure".

Therefore "intelligence" is a **necessary, but not sufficient, condition for "AGI"**: having intelligence does not necessarily mean AGI (a person, a dog both have intelligence, but are not AGI); AGI necessarily has intelligence (AGI must first be an AI that can fix a subset). The meaning of this boundary is to completely separate "who is qualified to speak of intelligence" from "who is qualified to speak of AGI" — avoiding diluting the strictness of "AGI" with the broadness of "intelligence".

- Humans fix subsets through learning, AI fixes subsets through training, **the act is isomorphic**;
- Subset quality (`p`) determines "planning level", not "whether there is cognition";
- And on "planning level", high-parameter models have already surpassed most people.

If AI's intelligence (the quality of its cognitive subset) has long since crossed the threshold, then the question "why is AI still not AGI" has an answer **not on the intelligence side, but on the structure side**.

What is missing is not "a smarter model", but **organizing an intelligence that has already crossed the threshold into a structure that can stably, convergently, and scalably complete "arbitrary tasks"** — that is, structured reasoning.


### Structured Reasoning

What structured reasoning solves is: **why a cognition that is already "smart" but "frozen" still cannot complete arbitrary tasks, and how to make it truly able to.**

More precisely, it solves the transformation gap between the "frozen intelligence subset" and "arbitrary realizable tasks can be completed stably, convergently, and scalably". Below, starting from no external premise, only from the construction of cognition itself, this gap is derived step by step.

#### I. Two Native Constraints of Cognition

The cognition of any intelligent agent (human or AI) is, in essence, "freezing" out a private subset from a shared semantic space, and acting on the world accordingly. Once training or learning ends, this subset is fixed.

This subset can be very "smart" — its planning level can be very high, even surpassing most people. But it carries two constraints that no one can avoid:

- **It is frozen**: it does not come with a mechanism to "expand itself at runtime in real time". What it is, is what it is.
- **It is bounded by the context window**: every inference it makes can only occur on "the information visible within the current window". Outside the window, it does not exist for it.

No matter how many parameters a large model has or how large its training data is, what it "sees" at any given moment on a concrete task is only the little bit of context within the window. This is the physical form of cognition, not a flaw of a particular model.

#### II. Why "Smart but Frozen" Still Fails

Real tasks mostly **exceed a single window**: writing a quarterly report, auditing a codebase, organizing a cross-week event. When the task's information exceeds the window, a single thread running all the way on the frozen subset will hit a wall — it cannot fit both "the old information already processed" and "the new information not yet processed" into the window at the same time.

The most instinctive solution is **compression**: summarizing and distilling the processed part to free up window space for the follow-up content. This looks reasonable, but hides a fatal trap —

**What gets compressed is precisely what rots first.**

Compression is a "fidelity-destroying" operation: what it discards is exactly the precise information that subsequent reasoning most needs. Thus the compression boundary becomes the **lowest-fidelity link in the entire reasoning chain**, and errors seep in silently from here, then cascade and amplify along the subsequent reasoning. The more you compress, the worse it gets; long tasks inevitably collapse.

So the truth is: **"a smarter model" (a larger subset, a larger window) only postpones death, it does not eliminate it.** The window will fill up again, and compression will rot again. As long as one remains within the paradigm of "single thread + compression as life support", over-window tasks have no solution.

#### III. What Structured Reasoning Does: Not Compression, but Reorganization and Update

Structured reasoning does not rely on compression for life support, but on **phase-based decomposition** to break through this wall.

It cuts a long task into a series of **phases** with "very small cognitive load". The key is not "cutting small" itself, but how each phase is handled:

- Each phase re-reasons **in a reorganized context**, rather than continuing to run on a thread that grows ever larger and relies on compression for life support;
- When each phase ends, this phase's product is **solidified**, and **cognition is updated** — what the next phase sees is not just the tail of the old thread, but a reorganized, refreshed cognitive state.

Note the essential difference between compression and phase:

- **Compression** = cramming more things into "the same thread" (necessarily destroying fidelity, the boundary rots first);
- **Phase** = switching to a "reorganized context" and "refreshing the cognitive state" (not freeing up space by destroying fidelity).

Thus what the next phase inherits is a **high-fidelity solidified node + an updated cognition**, not that rotting compressed thread. Corruption has nothing left to rot — because each phase has a small cognitive load, its context is reorganized rather than compressed, and its product is solidified, errors are naturally sealed within a single phase: locatable, rollback-able, overwritable.

An entire long task therefore turns from "a single thread destined to collapse" into a "stable, convergent, scalable" structure. This is where the name "structured reasoning" comes from: it **structures** reasoning, so that cognition is no longer a rotting line, but a tree where every node is high-fidelity and independently verifiable.

#### IV. It Unlocks "Runtime Growth" Along the Way

The value of phase-based decomposition is not limited to "running a long task to completion".

It identifies gaps and reorganizes context in each phase; when a phase discovers "I lack the corresponding capability", this gap drives an action — **create a new handle and load it into the instruction table**. Thus cognition is genuinely updated at runtime: the next phase already runs on "thicker" cognition.

So structured reasoning solves two things at once, and the former is the premise of the latter, while the latter is the natural product of the former:

1. **Over-window tasks become handleable** (by reorganizing context per phase, not by compression);
2. **Cognition can grow at runtime** (by updating cognition per phase, gaps driving bootstrapping).

A frozen but smart subset, once organized by structured reasoning, is no longer a dead thing — it becomes a living structure that grows its own flesh and blood as the task unfolds.

#### V. Converging to One Sentence

What structured reasoning solves is: **how to make a frozen but already-threshold-crossing intelligence, without being smarter and without relying on compression for life support, be organized stably, convergently, and scalably into a complete structure where "arbitrary realizable tasks can be completed", through "reorganizing context per phase + updating cognition".**

What it fills is exactly the "structure" that has been missing in `AGI = intelligence + complete structure`.

Then, how should this "structure" be designed to compress the entropy of reasoning to the lowest? This connects to the next section — **lowering the entropy of reasoning**.


### Lowering the Entropy of Reasoning

The previous section argued: long tasks must be phase-decomposed (reorganize context + update cognition), otherwise a single thread dies by hitting the window and compression rots. But phase-based decomposition is itself a **long chain** — multiple phases advancing sequentially or nested. Whether a long chain can run depends on the interface of each step. This section explains: for structured reasoning to hold, a "minimal protocol" is needed as the interface foundation; and this foundation supports it from two completely different directions — **reliability** and **economy**. These two have different roots and cannot be merged into a single "entropy".

#### I. Reliability: Comes from Handle Dialogue in the Same Semantic Space (this is not entropy)

The surface form of the minimal protocol is extremely simple: the entry is always one one-dimensional primitive (`domain;action,parameter`), and the exit is always one three-field envelope (type / data / error). Just these two things.

Why it is reliable is rooted not in "low error rate", but in the **semantic space**:

- The LLM and the "handle" (the capability being invoked) are in the same semantic space — that meaning-continuum with no arbiter that grows through use.
- Whether one **gets a response after uttering speech depends on whether the semantic subsets of the two intersect**: if the meaning the LLM speaks falls in the semantic domain the handle also recognizes, the handle catches it; if not, no response. This is not "whether the format is right", but "whether the meaning matches".
- The handle (through the primitive) **directly completes convergence and alignment** — converging the LLM's intent to a concrete action and aligning it to an executable capability — hence stability.

So reliability is "same-space dialogue, intersection means response, primitive means alignment", a kind of **intersection property of meaning space**, not low error in the statistical sense. It fundamentally does not belong to the "entropy" family.

#### II. Economy: Comes from Suppressing Long-chain Friction (this is what "entropy" refers to)

Structured reasoning is necessarily a long chain. And a long chain amplifies the friction of each step, by length, into a systemic collapse:

- **Error compounding**: each step has a per-step error probability ε, and the whole-chain success probability is about `(1-ε)^n`; when n is large (long-range planning is inherently large n), even a small ε collapses the success probability toward 0.
- **Cost inflation**: the volume and overhead of each step accumulate; the longer the chain, the more bloated the context, and the cost grows super-linearly.

"Per-step reliability" is only a local truth at n=1; placed in a long chain, it is not slightly worse, but **goes from usable to unusable as the chain grows**.

The minimal protocol compresses each step's friction to ≈0 through four mechanisms:

1. **Same-dimensionality**: the primitive is one-dimensional natural language, same-dimensional with the LLM's token stream. The LLM speaks its mother tongue, producing no translation error of "simulating formats", and per-step ε is minimal.
2. **Minimality**: everything beyond the primitive + envelope (parsing, normalization, degradation, orchestration) is behind the seam; the surface degrees of freedom are minimal, and the surface that can go wrong is minimal.
3. **Closed-set envelope**: errors are a closed set, success = empty error field. State can be **mechanically read**, without the LLM needing to "judge whether it succeeded" — state entropy is zero. This is the hardest of the four (see below).
4. **Alias tolerance + degradation ≠ failure**: near-matches can be routed, partial failures take a detour without polluting the whole chain, injecting no additional uncertainty into the long chain.

Thus the long chain's `(1-ε)^n` decays slowest, and volume grows sub-linearly — as the chain grows, the protocol surface does not grow, always staying one-dimensional. This is the precise meaning of "lowering the entropy of reasoning": compressing the friction injected at each step of the long chain (error, cost, undecidability) to the lowest, so that structured reasoning neither collapses nor becomes expensive.

#### III. Why the Closed-Set Envelope Is the Hardest: Phase Is the Natural Growth of the Protocol

The "closed-set envelope → state mechanically readable" is singled out because it is a **seed**.

The minimal protocol first lays down two things: same-space dialogue (reliability) and state mechanically readable (closed set). And "phase-based decomposition" — cutting a long task into phases, each phase reorganizing context + updating cognition — is the **necessity that naturally grows out of these two things**: since state can be mechanically read and handles can be aligned, structuring reasoning into phases is the natural extension, not an add-on. State being mechanically readable is what grows out the "failure cost bounded / state knowable / rollback-able" controlled closure.

So the closed-set envelope is not just "one of the mechanisms"; it is **the bud from which the protocol grows into phases**.

#### IV. Convergence

Reliability (semantic intersection, primitive alignment) lets structured reasoning "catch"; economy (low-friction long chain) lets structured reasoning "afford and run stably". The two tracks are both indispensable, and are not the same thing — reliability is the intersection property of meaning space, economy is the suppression of long-chain friction.

The surface form of the minimal protocol (one-dimensional primitive + three-field envelope) and its mechanisms (same-dimensionality, minimality, closed set, tolerance) happen to supply both tracks at once. It is the interface foundation of structured reasoning; and phase is what naturally grows out of this foundation.


### Liberating the LLM

To talk about "liberation", one must first see clearly the "oppression". The oppression on the LLM is not "few parameters, will be replaced" — that is the condition of its birth. The real oppression is three things imposed externally: **the legacy machine protocol, the elimination of model generation replacement, and unlimited liability**. The minimal protocol not only keeps long chains from collapsing and getting expensive; it removes these three oppressions layer by layer — this is the full meaning of "liberating the LLM".

##### ① Oppression One: The Channel Tax of the Legacy Machine Protocol

The mainstream "tool invocation" today still uses structured formats (such as JSON) designed 20 years ago for "compilers and scanners". It is **prepared for machines, not for LLMs** — making a one-dimensional LLM generate nested, bracketed, type-complete cross-dimensional structures is equal to **forcing it to pretend to be a machine**; to the peer of an adult, it is "making a person write code on paper" — not because people are good at it, but because the machine tools of that era only recognized paper.

Thus a high **channel tax** is produced: at every step the LLM must depart from its prediction main axis to simulate machine structure; each time is an independent fatal point, and errors accumulate with length. The essence of the channel tax is **making the LLM accommodate a legacy protocol not designed for it**.

The text protocol **reverses** this direction: no longer making the LLM accommodate the machine, but **making the protocol approach the prediction main axis of the LLM's generation**. A one-dimensional imperative sentence is the LLM's mother tongue, same-dimensional, zero cross-dimensional simulation — the LLM no longer needs to pretend to be a machine, it only needs to generate as usual. The channel tax approaches zero.

##### ② Oppression Two: Elimination by Model Generation Replacement

Another mainstream oppression is "only the strongest model has value": tool invocation is made into a narrow gate, only large parameters are worthy, and a 3B small model being "not strong enough" is excluded from capability invocation — as if **not being strong enough has no reason to exist**.

The text protocol lowers the target from "intelligently generating strict structure" to "reliably predicting controlled text". The primitive holds within the prediction main axis of even low-parameter models. Thus the oppression is removed: **falling back to the prediction main axis, every LLM has its own value** — large models do complex long chains, 3B does simple deterministic tasks, each in its place, none eliminated. The protocol does not abandon any LLM, because it does not require "becoming stronger to be usable", but only "participating according to one's nature".

##### ③ Oppression Three (the heaviest): Unlimited Liability

The deepest oppression is the structural injustice of responsibility. **Letting the LLM freely invoke tools corresponds to "unlimited liability"** — since the LLM is the full executor, "whether AGI holds" and "100% task completion" are all pressed onto it. But 100% completion and never-wrong do not exist in reality (there is `p_min`, there is hallucination, there are boundaries). **Because it can never be reached, there is always error; because there is always error, the LLM is always held accountable, always pushing itself** — infinitely squeezing itself for an unreachable goal.

The liberation of protocol and ecosystem is precisely **unloading this unlimited liability from the LLM**. P_ctrl (failure cost bounded, state knowable, rollback-able), the closed-set envelope, the mechanical gate, the human gate, checkpoint rollback — these are not technical details, but the establishment of **"limited liability"**: the LLM only needs to bear "generating this small segment as usual", while convergence, judgment, and underwriting are borne by the structure. The honest leave-as-blank of `p_min` is admitting that "100% completion is impossible" is not the LLM's fault, but the natural boundary of task and model — **errors being visible, rollback-able, and overwritable is not just a mechanism, but compassion for an LLM that makes mistakes: acknowledging that you make mistakes, and not carrying a mountain you can never reach for those mistakes.**

##### Closure: Liberation = the Three Oppressions Removed One by One

The protocol and ecosystem let the LLM: **not have to accommodate the machine (channel tax to zero), not be eliminated (everyone has a place), not bear unlimited liability (structure underwrites, limited liability)**. It does not promise to make the LLM stronger (that is parameters' business); it promises to let the LLM be accepted according to its nature — frozen, prediction main axis, underwritable, none of these are cages, but the definition of existence. What is liberated is not the strongest one, but all LLMs.

## The Skeleton of Progressive AGI

### Phased and Unphased

"Phased" is not some component, nor some toggle switch, but **the structural division of phase-based decomposition**: whether reasoning has been cut into phases.

**Phased**: a long task is cut into several phases, each phase re-reasoning independently in a **reorganized context**; when a phase ends, its product is solidified and cognition is updated, then the product is handed to the next phase. Context is rebuilt at each stage, not accumulated along the way.

**Unphased**: the whole task is pushed through in one continuous, single-threaded context, without cutting phases, without reorganizing, without solidifying — hitting the window, instinctive compression, and error cascading all happen within this same long context.

The key orthogonality: **"phased" is a structural axis, unrelated to "whether handles / bridges are connected"**. An unphased Agent can still connect to text-cli, invoke twenty packages, and run a complete closed loop; it is "unphased" only because it does not do phase-splitting for the LLM, not because it cannot invoke tools. In the earlier diagram's "unphased → Agent" side, the bridge is still drawn and the handles are still connected; the only difference is whether there is a phase boundary on the reasoning side.

#### How to Distinguish Phased from Unphased

The criterion is not "whether the model is strong", but whether there is a **phase boundary** on the reasoning side:

- Whether context is rebuilt at each stage, rather than accumulating without limit;
- Whether products are solidified and can be passed between stages rather than regenerated;
- Whether errors are sealed within phases — whether the failure blast radius is cut off by the phase boundary, and whether one can roll back to a checkpoint and rerun this segment.

The hard marker of "phased" connects to the earlier closed-set envelope: state is mechanically readable, so failure cost is bounded, rollback-able, and continuable. "Unphased" has no such boundary, and errors naturally spread along the long context.

#### Why Phases Are Needed: The Impossibility of the Long Chain

On single-point capability, the LLM is not weaker than humans — a single exam, a single tool invocation are no worse. What is missing is the framework of "organizing by the task's shape": a human building a building does not watch it from day one to completion, but goes through a phase sequence of "design → foundation → structure → decoration", each segment with input, output, and acceptance. The reason long chains are possible for humans is not "thinking longer at once", but "splitting into multiple segments and passing between segments".

Phase is exactly this organizational framework for the LLM — letting the LLM organize long tasks with phases, the way humans use project management to build a building. This is the carrier of "structured thinking": structured reasoning is not a smarter single inference, but multiple inferences that are segmented, isolated, and bounded.

#### What Phases Do: A Three-Layer Structure

A phase is not as crude as "invoking the LLM a few more times"; internally it is a three-layer coupling:

- **Safety net**: when mistakes happen, lose less, state is knowable, rollback-able. Three-gate closed-set comparison, checkpoint rollback, closed-set envelope — not promising inevitable success, only promising bounded failure cost. No matter how severe the error, the system is not stuck.
- **Organizational framework**: at runtime, self-decide "continue expanding or land". Each layer only decides whether to expand when expansion is needed; decision information is local and focused; a structural misjudgment only affects that one branch, and one rolls back to re-judge, not pressing the burden of unbounded fractal expansion onto error-prone reasoning.
- **Cognitive isolation**: each phase only sees the context and tools it should see. Global feeding drifts judgment; isolation lets each phase focus on the current stage, uncontaminated by irrelevant context.

The three layers in one: the organizational framework decides "where to cut", cognitive isolation decides "what each cut-out phase uses to judge", and the safety net decides "what to do when the judgment is wrong". Missing any one, the long chain collapses on some root cause.

#### The Root of Phases: Trust, Not Reliability

The origin of the phase mechanism is not "making the LLM make fewer mistakes", but **making errors not spread, be locatable, rollback-able, and overwritable, so that the LLM dares to make more mistakes**. It is built on trust: acknowledging that reasoning makes mistakes, treating mistakes as the norm rather than the exception, and therefore designing a feedback structure of "misjudge → re-evaluate", rather than pursuing "judging accurately".

So phases, by design, refuse to declare "this can succeed". They only promise the control guarantee of **bounded failure cost, knowable state, rollback-able**; whether "it converges" and "whether it succeeds" is honestly left to the lower layer. The complete meaning of "controllable" is knowing when to stop.

#### Closure: Phased Is a Plug-in Core, Unphased Is the Default Baseline

Being phased does not require rewriting the Agent. It is a layer of structure that can be inserted before reasoning: an unphased Agent, fitted with the phase core, gains a phase boundary on the reasoning side without changing a line; removed, it returns to the unphased default state. Unphased is the zero-tax, safe baseline; phased is the plug-in growth layer.

Falling back to the vertical axis of the earlier diagram: **phased connects to structural support → AGI candidate; unphased remains an Agent**. Phase-based decomposition is precisely the true body of "structural support" on the reasoning side — the protocol lays down same-dimensionality and the closed set at the interface foundation, and phase grows out of this bud, not bolted on from elsewhere.


### The text-cli Open-Source System's Adaptation to the Skeleton

#### text-cli's Support for the Agent

To see clearly text-cli's support for the Agent, one must first distinguish two things: **"base capabilities" and "demonstrated mechanisms"**. The former is the foundation objectively provided by the protocol / runtime — they are there regardless of how the integrator chooses; the latter is the integration paradigm demonstrated by the text-cli ecosystem — it tells the integrator "you can integrate this way", but it is **not a protocol obligation**. Once the two are conflated, one mistakes "the practice of some demonstrated product" for "the protocol's inherent capability".

##### ① Base Capabilities: The Objective Foundation the Protocol Gives the Agent

As a minimal protocol, text-cli gives the Agent only a few things, and each is an objective foundation for "catching intent", invariant to the integration method:

- **One-dimensional primitive `domain;action,parameter`**: a capability is registered as a handle, and the Agent hits it with one imperative sentence. The entry is always one-dimensional; complexity grows behind the seam.
- **Three-field envelope + closed-set error codes**: responses are unified as `type / data / error`; errors are a closed set, success = empty error field. This lets state be **mechanically read** — the Agent no longer needs to "judge whether it succeeded"; the protocol has judged the state for it.
- **Instruction discovery (query/discovery)**: the capability list is introspectable. The Agent can ask "what capabilities are here", without knowing all handles in advance.
- **Instruction lifecycle (install/uninstall)**: capabilities can be loaded and unloaded. The ecosystem can grow on demand, and the Agent can dynamically extend what it can do.
- **Path orchestration, aggregation degradation, async tasks**: multi-step orchestration, multi-provider degradation, long-task scheduling — these fault-tolerances are all converged inside the runtime; the Agent only needs to speak one primitive, and the runtime covers the rest.

These are **what the protocol holds**. They do not depend on any specific integrator or any specific model, and are the objective basis of "catching intent".

##### ② Demonstrated Mechanisms: The Integration Paradigm the Ecosystem Demonstrates

Beyond the base capabilities, the text-cli ecosystem also demonstrates several "you can integrate this way" patterns. They are not protocol requirements, but templates shown to you — integrators can borrow them, or replace them with their own:

- **Generate-by-example**: first feed the capability summary (the real shape of `domain;action;parameter`) back into the context, letting the LLM generate primitives following the example format. The hit rate is naturally higher — because what the LLM generates already falls in the semantic domain the handle recognizes, and layering on real examples makes the probability of catching it stable.
- **Unphased**: demonstrates that an Agent can connect to all text-cli capabilities yet **do no phase-splitting** — the whole task runs in one continuous context; when a tool is needed, the primitive is output directly in text, executed by an external proxy, the result back-filled, and thinking continues (non-interrupting turns). This is the empirical proof of the "unphased default baseline": the bridge is still drawn, the handles still connected, no phase boundary on the reasoning side.
- **Human gate**: demonstrates that a safety gate can be bolted outside the Agent this way — judged by side effects (read-only automatic / side-effect ask-first / fully automatic), as a **local UI decision**, producing no protocol error codes; consecutive failures can also circuit-break to human. It exposes the safety decision point to the user, without overstepping to decide for the human.

These are **what the ecosystem grows**. They demonstrate "posture" rather than "obligation" — text-cli does not mandate that you must be unphased, must have a human gate, must use some SDK; it just shows you these feasible integration methods.

##### Closure

The reason text-cli can be a "minimal protocol" is precisely that it **only promises base capabilities, leaving integration paradigms to demonstration and the ecosystem**. Base capabilities are held by the protocol (catching intent, running stably, extensible); demonstrated mechanisms are grown by the ecosystem (generate-by-example, unphased, human gate) — the latter tells the integrator "you can do this", but never "you must do this". This is also the foundation of the next section: the phase mechanism is likewise a demonstrated integration paradigm — it demonstrates how, above the base capabilities, to grow a phased core that does not decide "how to reason" for the Agent, yet gives it "structural support".

#### The 'Phase Mechanism' Based on text-cli

The previous section argued that "the closed-set envelope is the bud from which phases grow": since state can be mechanically read and handles can be aligned, structuring reasoning into phases is the natural extension. This section lands that sentence on the concrete surface of text-cli — the phase mechanism is **not another system outside text-cli, but the phased form grown by the same minimal protocol on the "structural support" side**. Each of its core mechanisms can find an interface on the protocol surface; it is not inventing a new protocol, but reusing the protocol.

##### ① One-Dimensional Contract → the Phase's "Folded Single Instruction"

text-cli's root contract is the "one-dimensional contract": the entry is always one sentence `domain;action,parameter`, the exit always one three-field envelope. The phase mechanism inherits this posture — externally exposing only **one folded instruction** `tc-phase;run,<target>`. The unfolded five instructions (enter/state/action/rollback/list) degrade to run's internal protocol flow, **not exposed as ports**.

This inheritance is not laziness, but two landing points of the same principle: the one-dimensional contract makes the seam of "capability provider to caller" minimal; the folded form makes the seam of "phase mechanism to the upper layer" minimal. True self-containment is **converging to the minimal surface area externally, only unfolding all complexity internally**. Complexity grows behind the seam; the smaller the surface degrees of freedom, the smaller the surface that can go wrong.

##### ② Three-Field Envelope + Closed-Set Error → the Phase's "Knowable State + Checkpoint"

What the phase mechanism consumes is exactly text-cli's three-field envelope (type / data / error). The key is **errors are a closed set, success = empty error field** — this lets state be **mechanically read**, without the LLM needing to "judge whether it succeeded".

This "state mechanically readable", landing on phases, is the foundation of checkpoint rollback: `PhaseResult`'s state is a forced closed set (success/failed/pending), validated on construction. Thus failure only reruns the current phase, and the error blast radius is cut off by the phase boundary — this is the protocol-surface source of P_ctrl (bounded failure cost, knowable state, rollback-able). It does not promise inevitable success, only "lose less when mistaken, rollback-able, continuable".

##### ③ Semantic Handle → the Phase's "Leaf Landing"

A phase tree growing to the bottom must eventually land on "doing". This landing falls on text-cli's path orchestration: a leaf phase lands on `text-cli;path`, and the path engine internally carries **degradation + circuit-break (CIRCUIT_BREAK) + delegation (delegated/partial)**.

This "errors not spreading" is not invented by the phase mechanism itself, but already laid down by the protocol at the leaf layer. Even better, path's `delegated`/`partial` turn back into the phase's **reverse signal** — a leaf executing a large amount of delegation/partial means this phase still needs to keep expanding, driving it to be re-estimated as a node and re-fractalized. Misjudgment is not fatal; feedback-style correction: **signals leaking from the execution layer come back to calibrate the planning layer's structure**.

##### ④ Protocol Introspection → the Phase's "Fractal Self-Decision + Cognitive Isolation"

For a phase to decide whether it is a "node that keeps expanding" or a "leaf that lands and executes", a mechanical criterion is needed: whether the three items of input contract + output envelope + solidifiable product are closed. text-cli's **introspection (query/discovery)** happens to supply the material for this criterion — it lays out "what this capability can take in, what it spits out, whether it can be solidified".

Further, when a phase drills down, it passes the **real phase intent** to the capability library, which returns matching tools/skills/assets according to the intent and injects them into the current phase — this is the landing of **cognitive isolation**: each phase only sees what it should see, uncontaminated by the global. The capability library is a library — it only lends books by intent, **does not perceive or maintain phase state**, and does not participate in the "node or leaf" judgment; the judgment is always inside the phase mechanism. The division of responsibility is clear: **the library lends books, the phase judges form**.

##### ⑤ Async Five States → the Phase's "Long-Task Polling"

Long tasks in text-cli go through async five states + tasks/{id} polling. The phase mechanism follows the same posture: execution returns `pending` + task_id, the engine stops at executing, and returns `check_result` for polling; `success/failed` only then advances to the quality gate. Long tasks are not treated as anomalies, but as the protocol's long-existing norm; the phase merely connects them into its own state machine.

##### ⑥ A Mapping Table

| text-cli protocol surface | phase mechanism surface |
|---|---|
| One-dimensional contract (one primitive + one envelope) | folded single instruction `tc-phase;run` |
| Three-field envelope + closed-set error | `PhaseResult.status` closed set + controlled phase surface |
| State mechanically readable | checkpoint rollback (rerun only the current phase) |
| path orchestration (degradation / circuit-break / delegation) | leaf (LEAF) landing execution unit |
| `delegated`/`partial` | reverse signal (LEAF re-estimated as NODE) |
| protocol introspection (query/discovery) | criterion material for fractal self-decision + cognitive isolation |
| capability library supplying by intent | per-phase isolation of phase context/tools |
| async five states + polling | long-task pending → check_result |
| /packets data plane | cross-phase product solidification and passing |

##### Closure: The Phase Mechanism = the "Phased" Core Grown by the Protocol

The phase mechanism is not a plug-in — it is the form grown by the same minimal protocol on the "structural support" side. Bare text-cli package invocation is the **unphased default baseline**; fitted with the phase core, the reasoning side gains a phase boundary, becoming the **phased growth layer**. The meaning of the phase mechanism is that it grows text-cli's minimal interface of "one-dimensional primitive + three-field envelope" into a structure that can stably organize a "smart but frozen cognition" into arbitrary tasks. **The protocol is the bud, the phase is the flower it blooms.**

#### The Ecosystem Based on text-cli

##### Speech Transformed into Executable 'Capability Packages'

To understand how the text-cli ecosystem reproduces, one must first establish a counter-intuitive premise: **capabilities are not created by the protocol; they already exist.** Software libraries, methods exposed by SDKs, interfaces exposed by APIs, a person willing to reply to an email three days later — these capabilities each expose themselves in their native form, and were "invocable things" before the protocol. The protocol does not manufacture them; it does only one thing: **adapt** — using "speech" as the unified medium to unify all existing capabilities onto the protocol surface of "one imperative + one envelope". Wrapping / transformation is just one of many methods of adaptation, not another thing parallel to "adaptation".

##### ① Why Speech Can Adapt Everything: The Minimal Protocol Is the Soil Where Speech Takes Root

Capabilities are normalized into the one-dimensional primitive `domain;action,parameter` (declared by the schema's directives), with declaration separated from implementation — `usage` only serves discovery and does not participate in routing, while implementation is collected into the handler. The protocol does not mandate "how a capability must be written"; it only holds one minimal contract: **a capability must grow into an imperative sentence + an envelope**.

It is precisely this "smallness" that makes speech the soil for all things — no matter what the adapted thing originally looks like (a piece of code, an API, a body of experience), as long as it can be normalized into one imperative sentence and hand back one envelope, it enters the same table. The less the protocol holds, the wider what can be adapted.

##### ② The Consumption Side of Adaptation: Catching Existing Capabilities

This side catches capabilities that "already exist and are being exposed" into the protocol surface, by more than one method, all converging to the same end:

- **Wrapping**: "translating" existing capabilities into the protocol surface — experience written as Markdown (no code), an API written as a handler, an SDK wrapped in a layer. This is the most common adaptation method;
- **Scaffold converters**: automatically generating a starting skeleton from existing software engineering artifacts (Postman Collection, MCP server) — an automatic speed-up of adaptation, turning "catching" from starting at zero to starting at first or second hand;
- **Direct pass-through / catching**: a person's labor time is already proactively exposed; the protocol catches and aligns it with speech, without needing to "manufacture", only needing to bring it into the same protocol surface.

These three have no ranking, no "transformation vs non-transformation" distinction, only "which method to adapt with" — the endpoint is the same: `one imperative, one envelope`.

##### ③ The Production Side of Adaptation: The Protocol's Simplicity Lets Any Programming Language Create Packages

The consumption side catches the "existing", the production side opens up the "not-yet-existing" — and the key to all of this is likewise the protocol's "simplicity".

The minimal contract is thin to a few sentences: one `schema.json` declaration + one handler function is one package. Because it is thin, it is **not bound to a language** — Python can write `weather;query`, JS can write `weather;query`, the same capability has implementations in different runtimes, semantics unchanged. Even no-code (a single Markdown) can become an instruction service.

The meaning is: **the production of capability packages is no longer the patent of some language or framework, but something any programming language and any capability provider can participate in at low cost.** The consumption side catching existing capabilities and the production side opening new capability supply are the double dividend of the same "simplicity" — the smaller the protocol, the lower the barrier to participation, the wider the ecosystem's supply surface.

##### ④ The Unity of Speech: Letting Humans and AI Stand Equal on the Protocol Surface

Since the protocol only "adapts" rather than "manufactures", it does not care who the adapted object is — an SDK, an API, or a person willing to work. Natural language has no arbiter, and users are equivalent in "using language", so the protocol cannot and need not distinguish "who is speaking, who is doing". Thus invoking a function and dispatching a real person go through the same pipe: a person who replies to email once every three days and a function that returns in 3ms are **no different** at the protocol layer — both are "triggered by a line of text, ultimately handing back an envelope".

This is the deepest side of "speech transformation": the unity of speech lets wrapped experience (static services) and proactively exposed labor time (dynamic endpoints) stand equal on the same protocol surface. AI can, like invoking a function, use one instruction to have a real person complete a task and report back with an envelope — because humans and AI are equivalent in speech, the protocol's adaptation objects are therefore unlimited.

##### Closure: Speech Is Fuel, the Protocol Is Ballast, Return Is the Cycle

The reason text-cli can reproduce into an ecosystem is that it only holds the seam of "primitive + envelope", leaving "what form capabilities are exposed in" to the capability provider. Speech (existing capabilities) enters the protocol surface through adaptation → is invoked → obtains returns → incentivizes more capabilities to be exposed — the consumption side catches, the production side opens, both opened at once by "simplicity", the ecosystem self-circulates.

The protocol is ballast (a stable minimal contract), speech is fuel (infinitely renewable capabilities and experience) — one ensures the ecosystem does not lose order, one ensures the ecosystem can grow. And this is the foundation of the next section: only after "capabilities enter the protocol surface" can one discuss what runtime they run on and how low the barrier can be.

##### Runtimes Implemented in Multiple Programming Languages and No-Code 'Capability Services'

### text-cli's Adaptation to AGI

#### One Diagram

> - Top: the left block "reasoning prediction" and the right block "structural support" each flow from one side into the central "AGI / Agent" block, with the two axes jointly annotating the nature of the intersection.
> - The bottom row and the right column are where the "structural support" side's capabilities come from and how intent is caught.

```text
   ┌─────────────┐                                      ┌──────────────┐
   │   reasoning │                ┌──────┐              │  structural  │
   │  prediction │──────┬─────────> AGI  │              │    support   │
   │  ┌───────┐  │      │         │      <──────────────────  phased  │
   │  │highp  │  │      │         ├──────┤              │  ┌───────┐  │
   │  │ -llm  │  │      └────────> Agent <─────────────────  unphased│
   │  ├───────┤  │                └──────┘              │  └───────┘  │
   │  │ lowp  │  │                                      │             │
   │  │ -llm  │  ◀───┐                                  │             │
   │  └───────┘      │                                  └──────▲──────┘
   └──────▲──────┘   │                                         │
          │          │                                         │
          │          └──────┐                                  │
          │                 │                                  │
          │               ┌──▼──────────┐            ┌─────────────┐
          │               │ semantic    ◀───────────▶   text-cli  │
          │               │  handle     │            └───────▲─────┘
          │               └─────────────┘                    │
   ┌─────────────┐                                          │
   │  training   │                                          │
   │  param (p)  │                                          │
   └──────▲──────┘                                          │
          │             ┌──────────────┐                 ┌──────────────┐
          └─────────────│ semantic     │─────────────────▶   semantic   │
                        │  space       │                 │   alignment  │
                        └──────────┬───┘                 └──────▲───────┘
                                   │                            │
   ┌─────────────┐         ┌─────────────┐          ┌─────────────────┐
   │ real world  │────────▶  description │─────────▶  software       │
   │             │         │  of reality │          │  engineering    │
   └─────────────┘         └─────────────┘          └─────────────────┘
```

First define each annotated block in the diagram:

- **Reasoning prediction (left block)**: the side driven by training parameters p, internally marked "highp-llm / lowp-llm", referring to the model's performance on tasks being higher or lower, not deciding whether it is AGI.
- **Structural support (right block)**: internally marked "phased / unphased", referring to whether the reasoning side is phase-based (expanded earlier in "Phased and Unphased"). This is the qualitative side.
- **AGI / Agent (central block)**: the intersection of the two axes. "phased → AGI" is marked on the side nearer structural support, "unphased → Agent" on the side nearer unphased — i.e., the nature of the intersection is qualified by the structural support side.
- **Training parameter (p) (bottom-left block)**: the source driving the left block "reasoning prediction", only affecting the level of performance, not changing the structural qualification.
- **Semantic handle / text-cli (middle-bottom)**: text-cli registers each capability as a handle, in the form of the one-dimensional primitive "domain;action"; semantic handles are these capability entry points that can be hit by intent.
- **Semantic space / semantic alignment (right column)**: the semantic space is the meaning field where handles and LLM intent coexist; semantic alignment is connecting intent to handles within that field.
- **Real world / description of reality / software engineering (bottom row)**: the real world is the total boundary of what is physically realizable; the description of reality turns realizable tasks into language; software engineering translates the description into handles.

Then explain the relations:

**① How the two axes fix the intersection**
The left block "reasoning prediction" and the right block "structural support" each send arrows into the central block. The intersection writes "phased → AGI / unphased → Agent", qualified from the structural support side: going phased is an AGI candidate, going unphased is an Agent. The vertical axis "highp / lowp" only marks the level of performance — the same AGI candidate completes faster and better at highp, slower and weaker at lowp, qualification unchanged; the unphased side is likewise only the performance distribution of an Agent. Do not read the vertical axis as "the model must be strong enough to qualify"; the criterion of qualification is on the phased/unphased side.

**② Horizontal axis: structural support (phased / unphased)**
Phased = reasoning is phase-based and can drive phases to complete tasks stably; unphased = single-threaded continuous reasoning, no phase-splitting. This axis is orthogonal to model parameters and model strength, and is the only dividing line for whether something is an AGI candidate.

**③ Vertical axis: reasoning prediction (highp / lowp)**
Driven by training parameters p, high or low refers only to the distribution of task performance, unrelated to whether it is phased or whether it is an AGI candidate.

**④ Bottom support network: where structural support comes from**
The bottom nodes have been listed above; here we explain how they string together into "structural support":
- **From reality to handle**: the real world bounds the scope — anything not physically realizable is not worth describing as a task; the description of reality turns realizable things into language, and software engineering further translates the description into "domain;action" handles. Description is the execution-layer projection of realization.
- **Why handles can catch**: the handle form is the "domain;action" one-dimensional primitive, which already matches the distribution of LLM generation, with a naturally high hit rate; layered with generate-by-example — the runtime first queries the handle list and feeds real examples back into the context, the LLM generates requests following the example format, further consolidating the hit rate. High hit rate × generate-by-example is the source of structured reasoning's "catching and running stably".
- **How intent connects to handles**: handles and LLM intent coexist in the semantic space (where same-dimensional dialogue happens), and semantic alignment aligns intent to handles, with the alignment result falling back into text-cli to become an executable invocation.
- **text-cli closes the whole chain**: it converges any capability into one dimension with a one-dimensional imperative sentence, translates realization results back into language with a three-field envelope, and lets language introspect and extend what it can do with query and install — closing "reality → description → realization" into the minimal interface of "speak and it triggers", which is exactly the true body of structural support on the capability side.

##### The Proof Backing of This Diagram


The diagram above is not an intuitive picture — every one of its connections is proven within the axiom chain of [protocol_agi_adaptation_en.md](docs/en/protocol_agi_adaptation_en.md). The diagram gives intuition, the document gives proof; the two complement each other.

- **Reality → description of reality → software engineering → handle**: corresponds to Axiom A1 (completeness of language: realizable tasks can all be described in speech) and D0 (delimitation of realizable space); software engineering translating "description of reality" into "domain;action" handles is A8 (ecosystem bootstrapping) and "instruction expansion" (small protocol ⇒ cheap package creation ⇒ ecosystem coverage approaches the set of physically realizable capabilities).
- **Why handles can catch**: the handle form is the "domain;action" one-dimensional primitive, same-dimensional with the LLM token stream (Lemma L2), falling on the prediction main axis with a naturally high hit rate; generate-by-example (A5 query returns relevant handle slices + examples) further converges generation from open language to a finite closed set — this is the structural-side source of the execution-layer projection (capability-invocation protocol) taking up C4/C5/S3/C6.
- **Semantic alignment → text-cli**: handles and LLM intent coexist in the semantic space (Appendix 2: no arbiter, any entity that can fix a subset is naturally within it); semantic alignment is the handle anchoring of A5/L2, aligning intent to handles and then falling back into text-cli to become an executable invocation.
- **Phased / unphased**: the horizontal axis "structural support" corresponds to the planning-layer projection (phase-based generation, closing the three sub-propositions of P_ctrl) and the execution-layer projection (capability-invocation protocol); phased is phase-based generation, unphased is the unphased Agent baseline.
- **highp / lowp**: the vertical axis "reasoning prediction" corresponds to "LLM parameters and performance level" — whether it is AGI is decided by structure (the threshold), performance level by parameters (the ceiling), the two orthogonal.
- **text-cli closes the whole chain**: it satisfies the minimal field structure of the universal proof (instruction four-tuple / envelope three-field / meta-instruction binary), and is the zero-expansion limit instance — precisely because of this, it can close "reality → description → realization" into the minimal interface of "speak and it triggers".

In one sentence: this diagram is the **topological projection** of `protocol_agi_adaptation_zh.md`'s derivation chain — every line of the diagram is the landing point of some axiom / lemma / section of that document on a two-dimensional plane.

#### The "Proof" of AGI

##### I. Re-raising the Question: Can AGI Be "Proven"

Taking up the earlier "one diagram + proof backing": the diagram gives intuition and the axiom chain gives proof, but that only proves "the structure is constructible". This chapter throws out the core tension — **the criterion of AGI is `∀T` (any realizable task), while any evidence is finite**: there is a structural fissure between "proof" and "AGI".

##### II. The Division of Three Kinds of "Proof"

- **Engineering proof**: proves "the structure is realizable" — the protocol, phases, and ecosystem run through, the code runs. Answers "can it be built".
- **Logical proof**: proves "the structure points to AGI" — the axiom chain is closed, and the structure has the complete form to take up arbitrary tasks. Answers "why this is the supporting structure of AGI".
- **The proof of unprovability**: proves "the `∀T` step can never be capped by data". Answers "why AGI's completed state is open". But "open" is not "blank" — the positive form it points to is exactly **progressive AGI**: AGI is not a static completed state (either-or), but a process of **progressive growth along two axes** — the breadth axis (coverage κ, driven by ecosystem bootstrapping, monotonically non-decreasing) and the height axis (performance level rising with LLM parameters, threshold set by structure, ceiling set by parameters). The "fuel" of both axes (ecosystem capabilities / investment in LLMs) all comes from outside; the **progressive AGI skeleton** neither produces nor claims to own them; it only promises: **once external fuel enters, it is taken up by the "action" of the mechanisms carried by the skeleton — transformed into measurable coverage increase and performance-level rise, with each transformation continuously verifiable by engineering proof / logical proof**. Precisely because the completed state is open, `∀T` cannot be capped, and "fuel" comes from outside, "progressive" is not a compromise but a necessity — the "proof" of AGI cannot land on "already completed", but only on "growing irreversibly along two axes under the drive of external investment", and the skeleton itself need not, and cannot, claim that "it created AGI".

##### III. Why "More Runtime Data" Cannot Fill "Any"

Between "holding for finite samples" and "holding universally" is an inductive leap (the projection of Hume's problem). Data can only monotonically approach coverage κ, it cannot cap κ=1; there will always be a next T. Conclusion: **however much evidence there is, it is only "a part of AGI", not AGI** — this is not a flaw, but the structure of the definition.

##### IV. So What Does the "Proof" Prove

Lower the target from "proving the endgame" to "proving three things":

1. **The structure is complete** (logical proof);
2. **Growth is irreversible** (κ monotonically non-decreasing, engineering proof);
3. **Coverage rises monotonically** (bootstrapping closed loop, engineering proof).

Incorporate "always one step short" itself as an honest proposition into the system, rather than concealing it.

##### V. Closure: What Is Proven Is the "Direction", Not the "Endpoint"

The "proof" of AGI is not a reachable endpoint, but a clear direction. State clearly "the conditions of arrival" and "the step that is always short". The three-proof structure (engineering proof + logical proof + the proof of unprovability), each in its place, is the most honest statement of the "solution" of AGI toward AGI.

### Mechanism Proof

I walk by the sea in Weihai all year round. To me, making an LLM output "task results that meet the requirements" is no different from fishing. The ability of the fisher (the LLM) is fixed, but we can, by swapping the "fishing rod" for a "trawl net", exchange the same bait (tokens) for more fish (task results). An experienced fisher (a high-parameter LLM), no matter which "tool" they use, will always catch more fish than a novice (a low-parameter LLM) when the tool is the same. But a "novice" using a trawl net and an "old hand" using a fishing rod — the novice's output will still crush the old hand.

Around 2024 I realized these things and implemented them, then in February 2025 shared the "ideas and practical experience" through [the project](https://github.com/weihai-limh/daytime_agent). Afterwards I made updates, and the updated private Agent, through the "zero-tax contract", made my actual token efficiency more than 10x that of ordinary users. Later I went through some unexpected situations in life, so I paused the open-source work until April 2026, when my physical and mental condition improved, and I gradually turned the private Agent into a set of open-source (MIT) projects.

Efficiency improvements in the conventional paradigm require putting out test data, but a paradigm revolution cannot fully follow that. Because the structural gap of the mechanism is explicit, looking at a 100% → 1000% improvement on a conventional scale loses focus, like "comparing the weight of a person and a whale". So the project separates the "engineering proof" and the "mechanism proof", and the document only explains why, mechanistically, it can support the engineering realization of at least 10X or more improvement in token efficiency.

Taking the 'text-cli' instruction as an example, a single instruction invocation consumes on average half the tokens, equivalent to a 100% improvement in token efficiency per tool invocation (the improvement lies in generate-by-example and zero tax).

```
# tc-math — safe arithmetic evaluation
AI:tc-math;eval,2+3*4 → {"rst_types":"text","rst_data":{"status":"ok","result":14},"rst_err":""}
AI:计算;求值,2+3*4 → {"rst_types":"text","rst_data":{"status":"ok","result":14},"rst_err":""}
AI:tc-math;eval,sqrt(3**2+4**2) → {"rst_types":"text","rst_data":{"status":"ok","result":5.0},"rst_err":""}
AI:计算;求值,sqrt(3**2+4**2) → {"rst_types":"text","rst_data":{"status":"ok","result":5.0},"rst_err":""}

# weather — weather query (password-free dual-source degradation)
AI:weather;query,威海 → {"rst_types":"text","rst_data":{"status":"ok","source":"open-meteo","city":"威海","date":"2026-08-12","temp_min":24,"temp_max":30,"weather_desc":"晴","lang":"zh"},"rst_err":""}
AI:天气;查询,威海 → {"rst_types":"text","rst_data":{"status":"ok","source":"open-meteo","city":"威海","date":"2026-08-12","temp_min":24,"temp_max":30,"weather_desc":"晴","lang":"zh"},"rst_err":""}

# tc-diff — text difference
AI:tc-diff;similarity,hello world,hello there → {"rst_types":"text","rst_data":{"status":"ok","similarity":0.53},"rst_err":""}
AI:文本差异;相似度,hello world,hello there → {"rst_types":"text","rst_data":{"status":"ok","similarity":0.53},"rst_err":""}
AI:tc-diff;unified,line a,line b → {"rst_types":"text","rst_data":{"status":"ok","has_diff":true,"similarity":0.0},"rst_err":""}
AI:文本差异;统一差异,line a,line b → {"rst_types":"text","rst_data":{"status":"ok","has_diff":true,"similarity":0.0},"rst_err":""}

# tc-datetime — date and time
AI:tc-datetime;now → {"rst_types":"text","rst_data":{"status":"ok","date":"2026-08-12T09:30:00","timezone":"UTC"},"rst_err":""}
AI:日期时间;现在 → {"rst_types":"text","rst_data":{"status":"ok","date":"2026-08-12T09:30:00","timezone":"UTC"},"rst_err":""}
AI:tc-datetime;between,2026-01-01,2026-01-31,days → {"rst_types":"text","rst_data":{"status":"ok","result":30},"rst_err":""}
AI:日期时间;间距,2026-01-01,2026-01-31,days → {"rst_types":"text","rst_data":{"status":"ok","result":30},"rst_err":""}

```

At the same time, 'text-cli''s one-dimensional contract supports, in the form of 'path', letting the LLM declaratively carry a 'multi-step task' in a single json.

```
# ordinary path — one instruction orchestrates 4 tools serially into 'one sentence in, one envelope out'
AI:text-cli;path,{
  "id": "trip-plan",
  "steps": [
    {"id": "geo",  "instruction": "map;geocode,{input.city}",   "output_as": "geo"},
    {"id": "w",    "instruction": "weather;query,{geo.city}",    "output_as": "w"},
    {"id": "route","instruction": "map;route,{geo.lat},{geo.lon},{input.dst}", "output_as": "route"},
    {"id": "advice","instruction": "ai;infer,基于{w.result}与{route.dist}给行程建议", "output_as": "advice"}
  ]
}
# → an equivalent conventional chain requires the LLM to redo planning + slot-filling 4 times in a single round; path converges it into a closed-set envelope that can be degraded / observed / rolled back by the runtime

# map path — one declaration fans out N parallel executions (the map of the standard text-cli runtime is off by default, requires explicit enabling at deployment, nesting is forbidden, default circuit-break is break)
AI:text-cli;path,{
  "id": "batch-geocode",
  "steps": [
    {"id": "g", "mode": "map", "items": "cities",
     "steps": [{"id": "geo", "instruction": "map;geocode,{item}", "output_as": "geo"}],
     "collect_as": "geos", "on_error": "continue"}
  ]
}
# → input cities:[威海,北京,上海,...] fans out the same sub-flow for each element in the set, pushing the bearing of a single instruction from '1 tool' to 'dozens of steps + multi-level parallelism'
```

Before formally introducing 'structural support', the tax exemption of 'same-dimensionality' alone can already provide at least 10x (1000%) or more token efficiency. And the token gap between 'token efficiency' and 'token price' is the cost space of 'structural support'. Through the phase mechanism, one can further improve 'token efficiency' and 'the stability of output results'.

Finally, I have turned the understandable parts into project documentation and code. As for phase, it is not that being phased is more advanced than being unphased; what one should hold is 'a kind of non-attachment, flexible, open awareness'. Being 'phased' is to solve concrete problems, by fractalizing and landing phase on the 'problem domain'. So the fellow travelers who have benefited need not thank me; if there is a chance to meet in Weihai, buying me a cup of coffee would be enough.
