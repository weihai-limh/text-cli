# text-cli Protocol Adaptation to LLMs

> **Language note:** This English text is a translation of the normative Chinese specification (`protocol_llm_adaptation_zh.md`). Where this translation and the Chinese original differ or are ambiguous, the Chinese version is authoritative.

> This article answers only one narrower, harder question: why is the text-cli protocol adapted to language models? Issues such as centralization, copyright, and ecosystem operations belong to upper-layer governance and are out of scope.

## 0. One-line Thesis

The protocol hands the **most expensive step (inference)** to the form the LLM is best at (one controlled imperative template), and throws the **cheapest step (parsing and normalization)** to the machine. The rigor of the schema does not disappear — it is merely layered: the rigor of **parsing and normalization** is moved to the machine side (parser/registry), while the rigor of **input validation** is left to the provider inside its handler.

Any tool call that "requires the LLM to strictly produce a JSON object matching inputSchema" does the opposite: it makes the LLM leave "speaking human language" to generate a strictly structured JSON with field types that must be correct, pushing the serialization burden onto the inference side. The difference between the two paths is not a matter of style — it is a difference in **which side absorbs the impedance mismatch**.

The analysis is unfolded layer by layer below.

---

## 1. What the LLM Is Doing: Relevance-Based Token Prediction

To argue "adaptation to the LLM", one must first honestly state what the LLM is doing. A one-line mechanistic description:

**The LLM's output is relevance-based token prediction, emitting meaningful textual connections.**

This is not translation, nor execution. The LLM does not "understand the intent and then switch to a structured mode to generate JSON"; it is always doing the same thing — given a context, predict the next most relevant token, connecting them into a coherent, meaningful, statistically lawful text.

This mechanistic fact directly determines why the protocol holds:

- **A directive is a subspace of "generating text", not a "mode switch".** When an upper-layer LLM does orchestration inside the text-cli architecture, it is merely emitting the imperative template `AI:domain;action,params` as part of the predicted text, within the very "controlled text prediction" space it is already running in. The imperative template already lives in this space (it is a minimal controlled subset of natural language), so the LLM predicts it effortlessly, without leaving the "speaking human language" mode.
- **Adaptation is architectural and universal, not dependent on the strongest model.** The source of this adaptation is the shape of the protocol itself, not some special capability of a flagship model. Even a smaller model, as long as it can reliably predict controlled text, can use the protocol. This is important: many "adapted to LLM" designs actually only hold for the strongest models, whereas this protocol nails the target at the tier of "being able to emit controlled text is enough".

---

## 2. Protocol Primitive: A Controlled Template Living on the Main Axis of the Prediction Distribution

The previous section says "a directive is a subspace of generating text, not a mode switch"; this section lands that claim on a concrete distribution position — which segment of the main axis the imperative template lives on.

The protocol primitive is:

```
AI:domain;action,params
```

This is a **minimal controlled subset of the imperative sentence**. It is not the full set of natural language, but neither is it another format (such as binary or some RPC shape).

For the LLM, generating this sentence falls on the **trunk** of its prediction distribution, not the edge. Contrast with "a JSON tool call that strictly matches inputSchema": that call requires the LLM, while generating text, to additionally maintain a JSON structure — exact field names, correct types, complete required fields, correct nesting levels, no missing quotes or brackets. This is a **mode switch**, where the inference task and the serialization task compete for attention in the same context; once serialization misses a single bracket, the whole round is void, tokens are re-burned, and it must be retried.

But `AI:math;eval,1+2*3` is different. This sentence is itself an imperative; the LLM naturally emits it in the "controlled text prediction" space, without needing to "switch to a structured mode".

To clarify: this is not the full freedom of "natural language", but a **light gear** on the controlled spectrum. Stating this clearly is to dismantle a common false dichotomy — see the next section.

---

## 3. Controlled Spectrum: Dismantling the False Dichotomy of "JSON = controlled / natural language = free"

When discussing "controlled template vs natural language", it is easiest to slip into an empty dichotomy: take JSON Schema as the "controlled / rigorous" pole, and natural language as the "uncontrolled / free" pole, then say text-cli descends from free to controlled. This dichotomy is empty and must be dismantled.

**Fundamental fact: there is no uncontrolled spectrum; natural language itself is also a controlled expression. Only a controlled expression carries meaning.** Symbols completely detached from all constraints are not "free" but noise — they carry no meaning. The value of a symbol comes from opposition and difference within a system; meaning is precisely born from constraint.

Under this framework, all "capability-calling formats" fall on the **same controlled spectrum**, only at different gears:

| Gear | Source of constraint | Who enforces | Main cost |
|------|---------------------|--------------|-----------|
| Natural language | Social convention / statistical regularity | Intelligence (human brain or LLM understanding) | Ambiguity, needs high intelligence to parse |
| text-cli template | Explicit light syntax `AI:domain;action,params` | Cheaply parsed by both human and machine + server-side normalization fallback | Weak type enforcement |
| Strict JSON tool call | Explicit heavy form (inputSchema) | Machine validation | Verbose, consumes context, requires mode switch |

None of the three is **outside the spectrum**. In particular, **the strict JSON tool call itself is a controlled template** — params must strictly match a fixed structure, field types, required fields; it is also a "controlled structure filled by format", not free natural language. So text-cli template and JSON tool call are not the two poles of "controlled vs free", but **two light/heavy gears within the same spectrum**: one light and token-saving; one heavy and context-consuming.

This clarification voids two erroneous narratives:

- "text-cli is less expressive than JSON tool calls" — wrong in conflating "strength of constraint" with "whether there is an expressiveness dimension". The parameter body of text-cli itself can carry structured data; the protocol uses **bracket-depth tracking** to handle commas inside parameters, so complex parameters need not be forcibly "flattened" — its expressiveness is not inherently narrower.
- "text-cli descends from free natural language to controlled" — wrong. text-cli is not choosing between "free" and "controlled"; it is picking a "cheap for both human and machine" cut point **within the controlled spectrum**.

---

## 4. Protocol-Layer Ports for LLM Consumption

The protocol's adaptation to the LLM is not only in "the shape of the call" (the controlled template of §2 lands on the main axis of the prediction distribution), but also in "how the model knows what it can call and how to call it right". text-cli's directive packages leave three kinds of ports for the LLM at the protocol layer, making the model a **native reader** of the schema rather than an **obedient follower**. Together, the three open directly to the model the three things "discover capability, hit the spec, read the expectation accurately" — this is exactly the watershed between "AI-native" and "designed for machine RPC, then bridged to AI" (see §4.4; root cause in §4.5).

### 4.1 Discovery (query): Let the model read out "what is here"

The standard runtime provides `query,json`, returning the **enumerable contract** of currently registered directives (`directives[]` and each item's `domain` / `action` / `params`). This means the model does not have to hard-code any directive name into its weights or prompts: it can **ask** the runtime "what can you do" before calling, then bring the answer into context to generate the next step. Discovery is a protocol-layer primitive, not external docs, nor manually hard-written knowledge — capability becomes **visible to the model** as packages register, and disappears as packages uninstall.

### 4.2 Alias Normalization: Putting the Fault-Tolerant Surface of Constraints at the Entry Layer

Mechanism:

- **Canonical name (domain / action) is always ASCII and is the sole routing primary key.**
- All non-ASCII forms (Chinese, other-language aliases) are normalized back to the canonical name by the runtime via alias mapping before participating in routing.
- Aliases are **bidirectional, case-insensitive**, but are merely access entries to the canonical name and do not change the routing primary key.

Example (from real code of the standard weather directive package):

```python
@directive("weather", "query", domain_alias="天气", action_aliases={"query": "查询"})
def query(params: list[str]) -> dict:
    ...
```

Thus `AI:weather;query,威海,明天`, `AI:天气;查询,威海,明天`, even with wrong case or mixed Chinese/English, the server can normalize to `weather;query` before routing. The constraint still holds (routing primary key is the ASCII canonical name), but **the fault-tolerant surface of the constraint is enlarged to the entry layer**.

Meaning for the LLM: it **does not need to precisely hit a strongly typed schema**, only needs to fall within the tolerant range of the controlled template. It does not need to remember `weather` or `Weather`, `query` or `查询` — any valid alias hits. This is exactly where the LLM is most comfortable: it only needs to approximately hit, and normalization is covered by the machine.

### 4.3 Registration Metadata: Install Means "Declare What I Expect"

When a directive package is installed, it registers with the runtime, declaring its name, aliases, and parameter shape. This metadata is **model-readable**: what the model gets from `query` is not just "there is a weather", but "it wants `location` and `date`". **The expected shape arrives at the model with the package, rather than being buried inside the framework.** This is the opposite of the traditional approach — the latter locks the contract on the code / framework side, and the model can only guess from training memory or manual prompts what the params should look like.

### 4.4 Fundamental Difference from Strict JSON Tool Calls

Looking at the three ports together, the difference is not in "who validates more strongly", but in **who is the native consumer of the schema**:

- The `inputSchema` of a **strict JSON tool call** is a contract designed for machine RPC; the AI arrives only **via a bridge**. Its native consumer is the **validator (machine)** — the framework uses the schema at the boundary for machine validation, and the LLM is merely the *generator* bridged in: it generates arguments, and the validator on the other side decides whether to accept. The model does not "natively consume" that schema; the framework consumes it, then judges life and death for it.
- **text-cli**, conversely, opens the three ports — discovery, aliases, registration metadata — **directly to the model at the protocol layer**, letting the model read accurately rather than be rejected. The model is the **native reader** of the schema: it asks the runtime what it has (§4.1), hits the canonical name with near-natural-language aliases (§4.2), and reads the expected shape from registration metadata (§4.3).

This is the other side of the article's spine: the protocol **catches the model where the model is** — not forcing the model through a machine-contract bridge and then having the validator judge its life and death, but supplying "the information needed to call right" directly to the model as protocol-layer ports. This shares the same origin as sections 2, 3, 8: the impedance mismatch is absorbed by the machine side (parsing/normalization in §2, spectrum cut point in §3), and the position of "assisting the model to be correct" is placed where the model side can consume it.

### 4.5 Call Equality: Natural Language Makes Calls Equal

The above (§4.4) lands the difference of "native reader vs bridged follower" on "who is the native consumer of the schema". This section traces to a deeper origin: it is not in engineering choices, but in natural language itself.

**What is the equality of language.** In natural language there is no arbiter with final say over meaning. Two speakers are equal peers in "using language": meaning arises from use, not from a decree of either party; no one is granted by language itself the privileged position of "you are wrong, I do not recognize it". This is not the politeness of a community, but a property of language as a substrate — it is born flat, centerless, any speaker can participate. Precisely for this reason, there is no gate in language of "who is qualified to speak": as long as you are using language, you are in language, standing equal with others. This "naturalness" is so ordinary that it is often overlooked, but it is the starting point of everything below.

**Equality of calls.** text-cli is a text protocol living in language, so it inherits the shape of language: flat namespace, no arbiter. Thus it can open the three ports — discovery, aliases, registration metadata — directly to the model, without first putting it through a machine-validation bridge and then taking the model in as a follower — because the model and the human are equal peers in "using language", and the protocol has no way, nor need, to distinguish "who is speaking". The model can become the native reader of the schema, not a privilege granted by the protocol, but the LLM's output mechanism gives the LLM the ability to use the protocol equally, and the protocol merely realizes it as operable ports; the byte-level non-distinction of human / AI (call identity in §10) is exactly the embodiment of this, not a design preference, but the projection of the language substrate in the protocol structure.

Looking at the above watershed together with the three ports of §4, the protocol actually presents "a capability exists" as a **confirmable promise**: install means declaring the promise, discovery means confirming the promise is present. Thus the three ports exactly correspond to the three points the model can consume in the lifecycle of this promise:

- **§4.3 registration metadata = promise visible**: install means declaring "what I expect", essentially the runtime laying out a capability promise for the model to read;
- **§4.1 discovery (query) = promise confirmable**: the model asks "is this promise still here right now", and the protocol confirms its presence in real time, rather than giving an expiring manual;
- **§4.2 alias normalization = fault-tolerant entry of the promise**: the model does not need to precisely hit the canonical name; any near-natural-language alias can land on the primary key of the promise.

Together, the three ports are exactly the protocol opening the segment of "promise — confirmation" directly to the model, letting it read accurately, hit, and confirm a capability before calling — this is the underlying reason for the watershed of "native reader vs bridged follower" in §4.4: the bridge is prepared for "consumers not in language", while the LLM is always in language, inherently a peer in the promise network.

**The protocol does not impose centralized directive semantic constraints.** In the evolving protocol project, its normalization mechanism tries to make the vector space of aliases close to the vector space of canonical names at the same dimension.

This decentralization has a structural manifestation on the mesh: a runtime that receives a directive can likewise delegate the directive to another runtime in exactly the same wire format. The protocol does not distinguish "directives issued by the user" and "directives forwarded by the runtime" — both go through the same pipe, receive the same envelope. The LLM does not need to know how many times the directive was forwarded or through which runtimes — for the LLM it is always "one sentence in, one envelope out". The caller only needs to present a token to the peer it directly entrusts; the credentials for each subsequent hop in the chain are handled by each hop node itself — the flow of the directive is not orchestrated by some center, but determined by each hop node's own routing declaration.

---

## 5. Law of Error Accumulation by Length: The Structural Disadvantage of JSON-Type Calls on Long Chains

This is the sharpest and most verifiable mechanistic argument of the whole article; its judgment is based on mathematical derivation, not any "ecosystem narrative".

Mechanistic fact: in autoregressive generation, the per-token error rate is ε, the probability that all n tokens are correct is approx `(1-ε)^n`, and **the probability that the whole segment is wrong is approx `1 - (1-ε)^n`**. The error rate **accumulates** with length.

Each "strict JSON tool call" is an **independent fatal point**: once the JSON is malformed, or some field does not match the schema, the whole call fails and needs retry. Stringing N JSON tool calls to complete one thing equals having **N independent fatal generation points**.

The key: **a strong model only makes ε smaller, it cannot remove that n-th power.** This is structural, not rhetoric. Do the math:

- ε = 1% (1% error per token), N = 30 calls: failure probability approx `1 - 0.99³⁰ ≈ 26%`
- ε = 2%, N = 30: failure probability approx `1 - 0.98³⁰ ≈ 45%`

That is to say, even a fairly strong model has a high probability of flipping at some link when stringing 30 strict JSON calls. And doubling the model's strength only halves ε; the n-th power is still there — the longer the chain is a hard requirement, the more this tax cannot be collected away.

---

## 6. Path Orchestration: Compressing N Fatal Points into 1

text-cli's path declares "multi-step calls" as **one generation**: a json-format path envelope, inside of which is a string of steps (tolerant directive sequence). The path is not Turing-complete, but supports conditional judgment (`if`), single-level loop (`mode:"map"`), and parallel (`mode:"parallel"`); the step's `mode` field takes one of three values: `toolchain` (serial, default) | `parallel` (parallel) | `map` (loop iteration).

Mechanistic consequence:

- **Fatal points compressed from N to 1** (the path envelope itself), the step body is tolerant and can be fallback-covered.
- Contrast with §5: the long chain of JSON-type tool calls is N independent fatal points; text-cli's long chain is 1 fatal point + N tolerant steps.

**Honest correction: it is N→1, not N→0.** The path envelope itself is a strictly structured (with `requires` / `steps[]` / `if` objects) longer generation; a 30-step path is a **longer** generation, its single-point risk higher than a short JSON tool call. So the accurate statement is "fatal points N→1, and the step body can be fallback-covered", not "almost never triggers accumulated tax". The total failure probability changes from `1-(1-ε)ⁿ` (N independent fatal) to "probability the path envelope is malformed" (1 fatal) — still far better than N independent JSON calls, but non-zero.

**Tailwind argument: the stronger the model, the more text-cli's advantage "should not shrink", rather than "grow".** Mathematically, the failure probability of a strict JSON long chain is approx `N·ε`, and the failure probability of the path is approx `c·N·ε` (`c` is the average length multiple of the path envelope relative to a single JSON call); both decline linearly with ε, the ratio ≈ `c` — i.e. **the relative advantage is basically constant**, not "growing" as the model strengthens. The truly defensible statement is: text-cli constantly maintains a multiplicative advantage on long chains, and the failure probability of the JSON chain remains stubbornly high for realistic model strengths (ε not extremely small), so the protocol "does not become obsolete with model generations". The only legal premise under which the absolute advantage also "grows" with the model is: a stronger model makes people dare to orchestrate longer chains (N increases), and then the absolute difference `(c-1)·N·ε` widens with N — this is exactly the real root of the protocol "growing stronger rather than being eliminated as models upgrade".

**Further substantiation in the iteration scenario**: the protocol's `mode:"map"` makes variable-length iteration no longer inflate the path envelope — the cost of a 50-element loop drops from O(N) step declarations to 1 map step. The advantage of N→1 is widened in the iteration dimension: the accumulated tax of originally "stringing N JSON calls" is now also collected away by "inflation of the path envelope stringing N steps". Must restate §11 #1: the map step itself is still 1 fatal point — it is a stronger version of N→1, not N→0.

---

## 7. Natural Injection Resistance of the Orchestration Layer

Mechanism: after data returns from one directive, it can only land in the **param position**, and cannot escape into the **instruction position** (data cannot escape the instruction position).

In path orchestration, this is a real security property: the step's `instruction` string is **fixed at declaration**, and interpolation only enters the param position. Thus in the orchestration text generated by the LLM, data from the previous step is hard to be "flipped" into an instruction to pollute subsequent steps — pollution is locked in the param position.

The mental-load reduction for the LLM is real: it does not need to guard at every step against "the returned data hides a malicious text that can be used as an instruction". The security cost is moved behind the seam.

**A boundary must be added:** this protects the **orchestration layer**, not the **execution layer**. If the interpolated params are spliced by the handler into shell or SQL, the injection happens in the handler, which the protocol cannot control. The protocol honestly separates "orchestration isolation" and "execution isolation" — conflating the two would make people mistakenly think the whole is safe.

---

## 8. One-Dimensional Contract and Closed-Set Error Envelope

Mechanism: one imperative at the entry, one result envelope at the exit `{rst_types, rst_data, rst_err}`. Aggregation, path, degradation, federation are all **invisible** behind the seam.

For the LLM, this means it only needs to understand an extremely simple causality: "**one sentence in, one envelope out**". The real shape of the backend — whether it is a single function, an aggregation, a cross-network degradation, or a federated mesh — is invisible to the caller. The LLM does not need to pay context or inference cost for "the backend may be a string of complex chains".

The closed-set property further reinforces this: the shape of the error envelope is **finite, predictable** (`rst_types` / `rst_data` / `rst_err` three fields, business errors uniformly go through the `reason` field). The LLM does not need to face an open, bizarre error format set. It can stably expect "what an error will look like", rather than re-parsing the error every time.

---

## 9. Tracked Tasks: The Deepest End Can Be a Real Human

Mechanism: the tracked task opens the endpoint of "remote capability" to async / human at the protocol layer. A person who replies to email only once every three days, and a function that returns in 3ms, are **no different** at the protocol layer — both are "triggered by one line of text, eventually returning an envelope".

Meaning for the LLM: what it can normally schedule is by default framed in "code / function". This design removes that frame — orchestration can cross the "code boundary" and extend to services in the real world beyond bytes. From the protocol perspective, human-in-the-loop is not a special case, just another endpoint triggered by one line of text and eventually returning an envelope.

(By the way: precisely because the primitive layer does not distinguish "initiated by human" and "initiated by LLM", the protocol cannot distinguish at the wire layer whether a directive is authorized by a trusted human or hallucinated by an LLM. This is the real cost paid for topological symmetry; how it is caught — protocol gives a seam, upper layer completes, human gate holds — see §10.)

---

## 10. How the Mechanism Supports a Human-Machine Collaboration Mode: What Human Reviews Is What Runs

§9 points out that the primitive layer does not distinguish "human-initiated" from "LLM-initiated", and the protocol cannot tell at the wire layer whether a directive comes from a trusted human or an LLM hallucination. This article does not treat this as a protocol defect: it precisely lets a collaboration mode hold structurally — what human reviews is what runs; and accountability is caught by the seam of token association (protocol restrainedly provides, upper layer completes).

A natural human-machine collaboration loop is: human issues directive in natural language → LLM prepares text-cli directive or path → **human reviews the same bytes** → executes after approval. Its honesty does not come from "the system can distinguish human and AI", but from "what the human reviews is what the machine will run".

**Two layers of authorization, catching the cost at the mechanism layer and the mode layer respectively:**

- **First authorization (token association: protocol gives a seam, upper layer completes).** Exposing a capability to the AI (install / register, making it discoverable by `query`) is the first authorization: you authorize that capability to be callable under the authorized caller of this runtime. But the protocol is restrained here — it **does not manage the credential lifecycle**: key distribution, rotation, and revocation are the upper application's business. The protocol only provides a seam: the token associates one call with the authorized subject, and the standard runtime uses this for metering tracking on the caller side; the no-code nocode document-type directives also **plug into this association**, rather than bringing their own credential system. How keys are issued, when they rotate, what fine-grained scope the token binds to, are completed by the upper layer through a **custom runtime**: the upper layer completes the "association" into a full authorization mechanism on this seam.
- **Second authorization (collaboration mode layer, human gate).** The human reviews the same bytes and approves before execution, which is the second authorization. The reason it is possible relies entirely on the mechanism properties above: the controlled spectrum is close to natural language (§3) making text-cli readable, the one-dimensional contract (§8) making the path readable, and the consumer ports left for the LLM at the protocol layer (§4) making the semantics reachable. What the human reviews is the bytes themselves, not a rendered summary.

Key: **the protocol does not resolve danger by "distinguishing human / AI in the bytes" (that cannot be done, and is by design), nor does it underwrite safety.** What it gives is the seam of token association — the upper layer completes accountability (caller-side metering + per-call human approval) on this seam into a single edge. The first authorization is completed and underwrites accountability by the upper layer through a custom runtime, and the second authorization underwrites execution at the control plane.

**Contrast with strict JSON tool calls:** in that loop, what the human approves is a summary rendered by the system, and what executes is another byte re-materialized, with a drift gap between the two (see §3 on the controlled spectrum). On the text-cli side there is no such seam — the approved object and the executed object are byte-identical.

**Efficiency is not eaten by the gate:** the human gate is inserted between "prepare" and "execute", not increasing the LLM's generation count. The LLM still generates only one path, the N→1 tax of §6 is retained, and the cost is only human latency — and risky operations should pay this price.

**1:N authorization asymmetry (new risk introduced by map):** after `mode:"map"` appears, what the human reviews is a template (1 byte), but what executes is N real side effects (e.g. sending one email to each of 50 users). The protocol-layer guarantee is unchanged: byte identity — what is reviewed is what the machine will run. But the authorization surface expands from 1 to N — reviewing one template does not equal reviewing N consequences. The control plane's visibility and circuit-break capability over N is the responsibility of the upper layer service. The protocol's honesty lies in not pretending to cover this authorization gap itself.

This section is "the mechanism makes this collaboration mode possible", not "you should use this mode". Token association as the protocol's restrained primitive, its unfolding ends here: it proves that the protocol provides a seam completable by the upper layer, not an underwriting credential system. The boundary of the human-gate mode itself (e.g. whether review truly happens) belongs to upper-layer application engineering, not within this protocol's mechanism boundary.

---

## 11. Boundaries and Common Misreadings

The scattered boundaries above are summarized here, with a separate category of "common misreadings" — erroneous views easily mislisted as protocol defects are laid out as-is and responded to one by one, so that readers do not misattribute upper-layer or general responsibilities to protocol properties.

### Part 1: Boundaries at the Protocol Layer

1. **Fatal points N→1, not N→0.** The path envelope itself is strict and may be long; single-point risk is non-zero.
2. **Injection resistance is at the orchestration layer, not the execution layer.** When the handler splices params into shell/SQL, injection happens in the handler.
3. **Reactive loops are still not a strength of declarative paths.** The protocol provides first-class support for iterating over a fixed-template variable-length collection via `mode:"map"` — both the per-step tax and the length tax are dissolved. But a reactive loop where "the next step of each element depends on that element's result" (e.g. running a tool per element, deciding the next tool based on the return value) is still unsuitable for the fixed structure of declarative `steps[]` — this is a shape difference, not an implementation omission.
4. **Validation is inside the handler, judged by the provider.** The protocol layer does no boundary validation; params pass through as-is; type, required, enum, nesting validation are all handed to the provider inside its registered handler, and whether it is sufficient is judged by the provider, not a protocol-layer property. This shares the same origin as §4 "the model is the native reader of the schema": the protocol does not centralize validation at its own boundary, but leaves completion to the provider. Trade-off: the protocol does not intercept errors at the boundary for the caller; error detection is deferred to the handler; low-risk calls are worthwhile, high-risk calls require the provider to self-complete validation in the handler.

### Part 2: Common Misreadings (lay out the erroneous view and respond one by one)

The following three are often mislisted as the protocol's "mechanism defects". Their respective conditions of validity and attribution layers differ; here the erroneous views are laid out as-is and responded to one by one, to avoid repeating.

- **Misreading 1: The tolerant syntax makes "parseable ≠ semantically reliable", so text-cli is unreliable.**
  *Erroneous view:* A parseable directive does not mean it is semantically right, safe, or conforms to the caller's intent, so the protocol is unreliable.
  *Response:* At call time it executes exactly according to the caller's intent, no different from calling any strict JSON tool — `AI:math;eval,1+2*3` is the calculation of your intent, and the system does it. Whether the intent itself is right is the caller's business, common to all tool calls, not a protocol-specific mechanism defect of text-cli. What text-cli truly specializes in is "no machine validation at the boundary, validation handed to the handler" (see §11 Part 1 #4), which is honestly listed; expanding the caller's own intent problem into "semantically unreliable" is misattributing a general responsibility to a protocol property.

- **Misreading 2: "What human reviews is what runs" depends on the human actually reading; a rubber stamp voids the gate, so the danger of symmetric topology is exposed.**
  *Erroneous view:* The human gate does not guarantee review happens; if the human clicks approve without reading (rubber stamp), the danger pointed out in §9 is re-exposed.
  *Response:* Whether review truly happens is upper-layer application engineering (review process, operational culture), not a protocol mechanism boundary, nor the responsibility this protocol should bear. The protocol provides the readable primitive of "what human reviews is what runs", making the gate structurally honest (approved object = executed object byte-identical); but "whether the human truly reviews" happens on the deployment side, which the mechanism cannot and should not control. This is the same as §11 Part 1 #4: which layer completes the responsibility, the protocol does not underwrite.

- **Misreading 3: A complex path is a text wall, "readable bytes ≠ human can read through every step", so text-cli is uncontrollable in complex scenarios.**
  *Erroneous view:* A 30-step path has reduced readability; the human cannot read through every step's consequence, so the protocol is unreadable / uncontrollable.
  *Response:* How the path is rendered into a readable tree, graph, or step list is the presentation responsibility of the upper-layer integration application, not a protocol mechanism. The protocol only defines the envelope format; the structural property of "what human reviews is what runs" (approval = executed byte-identical) does not change with the presentation method. Its mechanism core — a long path envelope = single-point risk — is covered in Part 1 #1. Saying "the upper-layer rendering is not done well" is "the protocol is unreadable" is a misattribution.

- **Misreading 4: Recursive reference is a security hole, "the protocol allows infinite recursion, call loops are uncontrollable".**
  *Erroneous view:* The self-referential recursion of path/pro (everything is an instruction is a recursive structure) forms call loops, and the protocol does not impose any restriction on this, so it is unsafe.
  *Response:* The protocol allowing path/pro self-reference is a structural property (instructions take instructions as raw material), and does not set a recursion depth limit. Detecting real loops (`A→…→A`) is a runtime security behavior, not part of the protocol interoperability boundary — just as the SPEC repeatedly uses `>` to mark "implementation reference" and does not write mechanism details into the protocol body. Each runtime should close call loops at the `dispatch` funnel layer by the parsing target key, while retaining any legal deep recursion; but this is the runtime's own defense engineering, not a mandatory compliance requirement of the protocol.

---

## 12. Closing

Back to the opening question: why is the protocol adapted to the LLM? After twelve sections of argument, the answer can be closed into one sentence —

**The protocol moves the "expensive and error-prone" work to the cheap side to complete, and never locks capability to the model ceiling of some era.** Parsing and normalization go to the machine (parser/registry of §2), "the information needed to call right" is directly supplied through ports the model can read (§4), and the accumulated tax of long chains is compressed into one generation (§6). Every adaptation is an instance of this same judgment.

The source of this judgment is in the LLM's own generation mechanism (§1–§2): the LLM is always doing relevance-based token prediction; a directive is not generated by "switching to a structured mode", it is itself a subspace of "generating text"; the imperative template `AI:domain;action,params` happens to live on the trunk of this subspace, not the edge. So "adaptation" is not the protocol adding some capability to the LLM, but the protocol **not making the LLM leave the thing it was already doing** — it is still just predicting the next relevant token. This is the root of all adaptations in the article. This root can be pushed one layer deeper: the reason the LLM can always stay in "generating text" and be treated as an equal caller is that natural language itself has no arbiter, and users are equal in "using language" — a protocol living in language can only inherit this shape, so the model as a language user naturally sits at the protocol's table (§4.5).

Breaking the source of adaptation into several pillars, they are the concrete shape of the sentence above:

1. **The call shape lands on the prediction main axis, and the topology is symmetric (§2–§3).** The imperative template is the minimal controlled subset of "natural language"; humans and LLMs produce exactly the same bytes, hit the same dispatch; the LLM is naturally a legal caller, needing no translation layer to bridge it out of natural language; the protocol picks the "cheap for both human and machine" gear on the same controlled spectrum (natural language / light template / strict JSON) — canonical name ASCII as primary key, aliases put the fault-tolerant surface at the entry layer, the LLM only needs to approximately hit.
2. **Consumer ports make the model a native reader of the schema, not a bridged follower (§4).** This is the most fundamental divide from "JSON tool calls that require strict inputSchema matching": the latter's `inputSchema` is a contract designed for machine RPC, the AI arrives only via a bridge, its native consumer is the validator (machine), and the model is merely the generator bridged in; text-cli conversely opens the three ports — discovery, aliases, registration metadata — directly to the model at the protocol layer, letting the model read accurately rather than be rejected. The second pillar of adaptation lies precisely in "the position of assisting the model to be correct is placed where the model side can consume it", rather than forcing the model through a machine-contract bridge and then having the validator judge its life and death.
3. **The long-chain tax is compressed from N to 1, and the advantage is constant and does not disappear with model generations (§5–§6).** Stringing N strict JSON calls equals N independent fatal generation points; the error rate accumulates with length, and a strong model cannot remove that n-th power; the path compresses fatal points into 1 envelope + N tolerant steps. More importantly this is a "tailwind": the relative advantage is constantly maintained (the ratio of failure probabilities of the two ≈ constant), and the JSON chain remains stubbornly error-prone for realistic model strengths — so the protocol does not become obsolete with model generations.
4. **Mental-load reduction is moved behind the seam, and orchestration is extended to the real world beyond bytes (§7–§10).** The orchestration layer's data cannot escape the instruction position (§7), the exit is a closed-set error envelope (§8), the LLM does not need to guard against injection at every step, nor pay context for the backend's complex chains; tracked tasks open the capability endpoint to async / human (§9), the collaboration mode of "what human reviews is what runs" lets the human gate at the control plane catch the cost of symmetric topology (§10) — its accountability is caught by the seam of token association (protocol restrainedly provides, upper layer completes), not underwritten by the protocol.

The premise for all this to hold is that the protocol remains restrained: it only gives the seam of "primitive + envelope", and does not preempt the credential system, discovery directory, or execution sandbox (these are completed by the upper-layer runtime, see §10), nor does it take on itself how the path is rendered into a readable tree or graph (that is the integration application's business, see §11). The conclusion "does not become obsolete with model generations" is given in Pillar 3; here only its premise is added: smallness is intentional.

One sentence: **the protocol assumes the machine should adapt to the language model's actual behavior of "predicting text", rather than the reverse requiring the language model to adapt to the machine's structured conventions.** The adaptation direction is reversed; this is the entire root of the protocol adapting to the LLM. The core is clean to the point of almost no further reduction: a 119-line parser is the physical volume of this judgment.

---

## Appendix: Explicit Derivation Chain from text-cli Axioms → Clauses

> The appendix answers only one narrower, harder question: from which axiom is each mandatory clause of the text-cli protocol mechanically derived? Issues such as boundaries, ecosystem operations, and implementation references belong to the upper layer and are out of scope.

### 0. One-line Thesis

The protocol first establishes axioms (two mechanistic facts about "what the language model is doing" and "what natural language is"), then makes each protocol clause an inevitable corollary of some axiom. This article explicitly writes out the derivation step of "axiom X → therefore clause Y must be like this" — not listing conclusions, but listing derivations.

Questions like "why does the protocol require a three-field envelope" and "why is the entry tolerant, validation pushed into the handler" have answers not in aesthetics, but downstream of the axioms. The derivations are unfolded one by one below.

---

### 1. Two Axioms (the starting point of the derivation chain within this article)

**Axiom A (LLM mechanism fact):** The LLM's output is relevance-based token prediction, always doing the one thing of "generating text"; it does not "understand intent and then switch to a structured mode to generate JSON". A directive is a subspace of "generating text", not a "mode switch".

**Axiom B (natural language mechanism fact):** Natural language itself has no semantic arbiter; users are equal in "using language"; meaning arises from use, not from a decree of either party. And natural language is not "uncontrolled" — it is also a gear on the controlled spectrum, with constraints from social convention and statistical regularity.

A and B themselves are not design choices, but mechanistic facts; all clauses of the protocol are downstream of these two facts. And A, B themselves are downstream projections of the root axiom Ω (see Appendix Ω).

---

### 2. Axiom A → Call Shape Clause

**Derivation:** Since the LLM is always predicting controlled text (Axiom A), the protocol's call primitive must live on the trunk of this prediction distribution, not the edge — otherwise it forces the LLM to "switch mode", pushing the serialization burden back to the inference side.

**Therefore clause Y1 (call shape of the one-dimensional contract):** The protocol primitive is set to `AI:domain;action,params`, the minimal controlled subset of the natural language imperative. The LLM generates it effortlessly, without leaving "speaking human language".

**Therefore clause Y2 (canonical name ASCII, alias entry fault tolerance):** The routing primary key must be ASCII cheaply parseable by the machine (`domain;action`), but the fault-tolerant surface must be placed at the entry layer — non-ASCII aliases are normalized back to the canonical name by the runtime. This exactly puts the LLM at the position of "approximately hitting is enough" (the most comfortable point for the LLM under Axiom A), with normalization covered by the machine.

If Y1/Y2 are violated (e.g. requiring the LLM to output JSON strictly matching inputSchema), it directly hits the opposite of Axiom A — forcing the LLM to switch mode, and a serialization error voids the whole round. Thus Y1/Y2 are inevitable from Axiom A.

---

### 3. Axiom A → Validation Position Clause

**Derivation:** Axiom A says the LLM emits text, not guaranteeing strict structure. Then if the "rigor of input validation" is placed at the protocol boundary (like strict JSON calls doing hard validation at the boundary with schema, rejecting on error), it equals pushing back to the inference side what should be done by the machine — opposite to the adaptation direction of Axiom A.

**Therefore clause Y3 (validation inside the handler, no interception at boundary):** The protocol layer does no boundary validation; params pass through as-is; type, required, enum, nesting validation are all handed to the provider inside its registered handler. The protocol only keeps the rigor of "parsing and normalization" on the machine side (parser/registry normalizes text to the canonical name), and leaves the rigor of "input validation" to the handler.

This is the difference in which side absorbs the impedance mismatch: Axiom A requires giving the expensive and error-prone step (parsing) to the machine, and leaving the cheap "LLM only needs to emit tolerant text" on the inference side. Y3 is an instance of this judgment.

---

### 4. Axiom A + Long-Chain Math → Path and Envelope Clauses

**Derivation:** In autoregressive generation, the per-token error rate is ε, the probability that n tokens are all correct ≈ (1-ε)ⁿ, the whole segment wrong ≈ 1-(1-ε)ⁿ. Stringing N independent JSON calls = N independent fatal points; a strong model only makes ε smaller, cannot remove the n-th power. Under Axiom A the LLM still inevitably errs, so the long chain must be "compressed into one generation".

**Therefore clause Y4 (declarative path + fatal points N→1):** The protocol provides path — one declarative envelope internally stringing N tolerant steps; the LLM pays only one inference cost, the runtime deterministically `dispatch()`-es N steps. Fatal points compressed from N to 1 path envelope.

**Therefore clause Y5 (closed-set error envelope):** The exit must be a finite, predictable shape `{rst_types, rst_data, rst_err}`, business errors uniformly go through `reason`. Otherwise the LLM has to re-parse bizarre error formats every time, violating the "let the model save effort" orientation under Axiom A.

Honest correction (inheriting adaptation doc §6): it is N→1, not N→0. The path envelope itself is strict and may be long; single-point risk is non-zero. But still far better than N independent JSON fatal points, and the relative advantage is constant and does not disappear with model generations.

---

### 5. Axiom B → Human-Machine Same Plane and Decentralization Clauses

**Derivation:** Axiom B says natural language has no arbiter, users are equal. The protocol primitive lives in the natural language spectrum, so it inherits this shape: flat namespace, no center, any speaker is a peer. Thus the protocol has no way, nor need, to distinguish "who is speaking".

**Therefore clause Y6 (byte identity: no distinction of human / AI initiation):** The protocol does not distinguish at the wire layer whether a directive comes from a trusted human or an LLM. What human reviews is what runs — the human reviews the same bytes, and after approval executes the same bytes.

**Therefore clause Y7 (decentralized structural property):** User directives and runtime-forwarded directives go through the same pipe, receive the same envelope; the protocol does not require a central directory. A runtime `install`-ing a package = registering `domain;action` into the local semantic table ("learning a word"), no central lexicon push. This is the projection of Axiom B on the protocol topology, not an operational choice.

**Therefore clause Y8 (development not visible through a center):** Due to Y7, each runtime self-hosts, semantic table is local, discovery directory is optional, deployment needs no registration with any center. A local nocode service will not appear on any global map — "cannot count the nodes" does not equal "no nodes". This is the inevitable methodological consequence of Axiom B's decentralized shape.

---

### 6. Axiom B → Semantic Interoperability Clause (inherited, not manufactured)

**Derivation:** Axiom B says meaning arises from use, no arbiter. The protocol nails the primitive on natural language, automatically inheriting natural language's semantic plane — that humans and AI conversing in the same language can continue is the evidence that semantic interoperability exists.

**Therefore clause Y9 (protocol does not impose centralized semantic constraints):** The protocol only unifies the coordinates of call syntax, discovery, reporting, and supply; it does not guarantee cross-runtime semantic consistency. Whether semantics are right is the upper-layer/provider responsibility (judged inside the handler). The protocol "inherits" semantic interoperability, not "manufactures" it — so "breaking walls" should be expressed as "naturally dissolving by inheriting the natural language plane", not "the protocol pushed down the wall".

---

### 7. Derivation Chain Summary Table

| Axiom | Derivation step | Mandatory protocol clause |
|-------|-----------------|---------------------------|
| A (LLM emits text, no mode switch) | Primitive must live on prediction main axis | Y1 one-dimensional contract `AI:domain;action,params` |
| A | Fault-tolerant surface at entry layer | Y2 canonical name ASCII + alias normalization |
| A | Pushing validation back to inference side violates adaptation direction | Y3 validation inside handler, no boundary interception |
| A + long-chain math | Long chain must be one generation | Y4 declarative path, fatal points N→1 |
| A | Model saves effort parsing errors | Y5 closed-set three-field envelope |
| B (natural language no arbiter, equal) | No distinction of speaker | Y6 byte identity (human/AI same initiation) |
| B | No-center projection | Y7 same-pipe forwarding, no central directory |
| B | Self-hosting is integration | Y8 development not visible through center |
| B | Inherit semantic plane | Y9 no centralized semantic constraint imposed |

---

### 8. Closing

Back to the opening: each mandatory clause of the protocol can be traced to the mechanical derivation of Axiom A or B.

The four pillars (primitive dividend / consumer ports / long-chain N→1 / human-machine same plane) are not parallel "features", but different downstreams of the same two axioms. Any new clause that cannot be hooked back to the derivation chain of A or B should not enter the protocol mandatory baseline — it can only be a convenience mechanism of the reference implementation (evolution only adds convenience, does not change the baseline, see README "boundary between protocol and project").

One sentence: **the protocol's smallness is derived, not cut.** Every layer deleted can point back to some axiom saying "this layer violates the adaptation direction"; every layer retained can also point back to some axiom saying "this layer is inevitable". The derivation chain closes, and the protocol closes into the minimal protocol.

---

**Root Axiom Ω (semantic space isomorphism):** Once a problem domain is described in natural language, it falls in a semantic space **isomorphic** to the LLM's representation space; modeling / structuring is not necessary, but an extra "tax". Therefore the adaptation direction must reverse — not regularizing the problem into a machine format to feed the LLM, but letting the machine in turn adapt to the semantic space the LLM is already in (README "most expensive inference to LLM, cheapest parsing to machine" is the landing of this reversal).

**Why Ω is the root, yet placed in the appendix:**

- Ω is a counter-intuitive claim. Before the reader has walked through A/B → Y1–Y9 and personally confirmed "every layer cut can point back to an axiom", Ω has no empirical base to attach to, and will only be seen as an arrogant slogan — and this is exactly why it cannot be spoken at the beginning.
- Thus this article deliberately leaves Ω to the end: first give the downstream projections A, B directly verifiable from the protocol text, letting the reader walk to the top on the verifiable ladder, then look back — the whole chain points to Ω. Ω goes from "claim" to "closing".

**How Ω closes A, B:**

- **A is Ω's slice on the "LLM side":** since the problem domain is already in the LLM's semantic space, the LLM always predicting controlled text, no mode switch, is the inevitable mechanistic fact under isomorphism — thus the primitive must live on the prediction main axis (Y1/Y2), validation pushed to handler (Y3), long chain compressed into one generation (Y4/Y5).
- **B is Ω's slice on the "natural language side":** since the semantic space is carried by natural language, no arbiter, the users of natural language are naturally peers, distribution is naturally topology — thus byte identity (Y6), decentralization (Y7/Y8), inheriting semantic interoperability (Y9) are all projections of isomorphism on the protocol topology.

**Closing sentence:** A, B are not parallel starting points, but two orthogonal slices of Ω; Y1–Y9 are not nine independent clauses, but nine inevitable projections of Ω through the two slices A, B at the protocol layer. The article body derives from the slices (verifiable), the appendix returns to the root (receivable) — this is exactly the reading-order realization of "axiomatize → not laughed at → receivable → teachable" within a single document.
