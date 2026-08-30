# Progressive AGI Solution Examples Based on text-cli

> **Disclaimer**: This English translation was produced by an LLM based on the Chinese source document. In case of any discrepancy, **the Chinese version takes precedence**.

## What Problems It Can Solve

### The Flow:
```
problem -> problem triage -> query strategy -> LLM generates an instruction sequence based on the 'strategy' -> text-cli runtime executes the instruction sequence -> the 'instruction sequence' responds with the final result based on the problem
```

### The Basic Open-Source Solution:

This section gives the minimal runnable template of the text-cli family's "basic open-source solution", whose core is an open-source project called **synth-loop** — a "task-processing hub" exposed in the form of an LLM gateway: externally compatible with OpenAI / Anthropic endpoints, internally doing classification, routing, context assembly, and multi-step reasoning for each request, ultimately converging to a single reasoning landing point.

In concrete task processing, synth-loop dispatches in three directions: **strata-match** supplies strategy, tools, and resources (deciding "how to think"), the **downstream LLM API** supplies reasoning (deciding "how well to think"), and **text-cli** is the instruction execution engine (deciding "what can be accomplished") — the `domain;action,parameter` you write is exactly what gets truly executed here, with a three-field envelope returned. In other words, text-cli sits at the "execution end" of the chain, the layer where capability actually lands; the other components only organize intent into instruction sequences it recognizes.

[**synth-loop**](https://github.com/weihai-limh/synth-loop)

[**strata-match**](https://github.com/weihai-limh/strata-match)

```
┌──────────────┐     OpenAI/Anthropic      ┌──────────────────┐
│   any Agent  │ ──────────────────────→   │   synth-loop     │
│   (client)   │                           │  localhost:13155 │
└──────────────┘                           └────────┬─────────┘
                                                    │
                          ┌─────────────────────────┼─────────────────────┐
                          ▼                         ▼                     ▼
              ┌────────────────────┐    ┌────────────────────┐  ┌──────────────────┐
              │   strata-match     │    │  downstream LLM API│  │    text-cli       │
              │   localhost:13156  │    │  OpenAI/Anthropic  │  │  instruction      │
              │ strategy+prompt+   │    │                    │  │  execution engine │
              │      tool          │    │                    │  │                   │
              └────────────────────┘    └────────────────────┘  └──────────────────┘
```

**Stand up the three-piece set in one sentence.** Give the reader an anchor — **synth-loop is the brain** (organizing the whole task), **strata-match is the advisor** (deciding "how to think", supplying strategy and tools), **text-cli is the hands and feet** (truly making intent happen). In one sentence: strata-match teaches it how to think, synth-loop organizes how it acts, text-cli makes the thing happen for it.

**Minimal example: a full round trip of one instruction.** Look at a minimal request that is understandable without installation, establishing the intuition of "speak and it triggers":

```text
The reader asks: how much is 2+3*4?
synth-loop classifies → lands on execution → LLM generates one instruction → AI:tc-math;eval,2+3*4
text-cli executes →        {"status":"ok","result":14}
LLM answers with this result →  "It equals 14."
```

This time only one tool is invoked, one envelope at a time. One sentence goes in from the reader, and what comes out is the envelope returned by text-cli, which the LLM then organizes into an answer — this is "speak and it triggers".

**Cross-tool example: multi-step processing of one problem.** Look at a task that needs to cross multiple tools — checking tomorrow's weather in Beijing:

```text
The reader asks: what's the weather in Beijing tomorrow?

LLM generates a path →  AI:text-cli;path,{
  "id": "tomorrow-weather",
  "type": "pipeline",
  "version": "1.0.0",
  "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
  "requires": ["map;geocode", "weather;query"],
  "steps": [
    {"id": "geo", "instruction": "map;geocode,{input.city}", "output_as": "geo"},
    {"id": "wx",  "instruction": "weather;query,{geo.city},tomorrow", "output_as": "wx"}
  ]
},{"city":"Beijing"}

text-cli executes both steps at once → one envelope returns → LLM organizes it into the final answer
```

The first step `map;geocode` locates "Beijing" into coordinates stored in `{geo.city}`, and the second step `weather;query` uses it to query the weather. Multiple steps are converged back into one `text-cli;path` and one envelope — this is the landing form of cross-tool orchestration.

**Chained-phase example (corresponding to medium-complexity tasks): root triage, sub-branches directly output path.** For a medium-complexity task (like "organize a business trip report"), the root is triaged into several phases, each phase directly landing on path execution — **no further deep drilling down**. The focus of the chained flow is "the gates inside each phase":

```text
root triage → [phase 1] → [phase 2] → [phase 3] → done
                  │            │
            (execute·solidify)  (execute·solidify)
                  │            │
                [gate]        [gate]
```

A gate is not "a door between phases", but **a controlled advance point inside each phase** — it decides "whether this phase executes successfully and is qualified to solidify and advance". The same phase passes through several gates in sequence during execution:

- **Pre-execution path confirmation gate** (optional): the execution plan generated by the LLM first waits for confirmation before acting, preventing execution before review;
- **Post-execution quality gate**: after execution, success or failure is judged **mechanically by the closed-set envelope** — success or failure is not judged by the LLM itself, but by comparing the state field in the envelope; **state being knowable is not "smartness", but "mechanically readable"**;
- **Human approval gate** (high-risk phases): the result is handed to a human for approval, who can pass it, reject it for retry, or abort the whole tree.

If any gate does not pass, it **only rolls back and redoes the current single phase** (back to the checkpoint), not discarding the whole chain. This is the chained form: **the task is cut into several sequential phases, each phase being reliably passed or blocked at its own internal gates, directly outputting path execution.**

**Structured-phase example (corresponding to complex tasks): LLM autonomous triage.** For a complex task (like "organize a cross-week event"), after the root is triaged, **whether it is ready to land is judged by the LLM itself** — if a phase cannot yet be solved directly, it continues to be refined into several sub-phases; sub-phases may be further refined:

```text
root triage
  ├─ judged ready to land → output path execution
  └─ judged still needing refinement → drill down into sub-phases:
        ├─ sub-phase A: create handle
        ├─ sub-phase B: install handle
        └─ sub-phase C: use handle
            (each sub-phase likewise self-decides: ready → land, not ready → drill down)
```

The core of the structured form is **LLM autonomous triage** — as it advances, it judges "can this be solved? or should it be refined into several sub-phases to separately create the handle, install the handle, and use the handle". Thus the task grows into a tree that grows as needed, able to take on the most complex tasks. The mechanical gate only provides final backstop (preventing runaway).

**Closure: this template corresponds to exactly a part of the "complete structure" described later.** One `domain;action,parameter` in and one envelope out is the minimal template that the three-piece set runs through together; but the complete structure is more than this one chain — it consists of two parts: **problem triage** (first look at how complex the problem is and decide which path to take; the two examples above are the "heavy paths" it selects) and **phases** (the most complex tasks, how to grow into a tree and carry the hard task to the end). What this section sees is the surface of "one sentence in, one envelope out"; the later "Why It Claims to Be Progressive AGI" will explain this structure thoroughly.

### Advanced Open-Source Solution:


## Why It Claims to Be a 'Progressive AGI Solution'

### The Mainstream Understanding: What AGI Is

When people mention "AGI (Artificial General Intelligence)", the picture in most minds is: a **single model that can do everything like a human** — writing articles, writing code, planning, commanding robots, all handled by one thing. Hence we habitually think of AGI as an **either-or switch**: either it is AGI, or it is not, with no intermediate state.

Following this picture, AGI's fate is almost entirely tied to one thing: **whether the model is strong enough**. More parameters and larger training data bring it closer to AGI; if not strong enough, it is still one breath short. Thus "pursuing AGI" in many people's minds is equivalent to "desperately building a smarter model" — as if stacking single-point capability would make AGI come naturally.

### The Dilemma of the Mainstream Understanding

But the problem with this path is deeper than "not catching up" — it may have **been chasing the wrong direction from the very beginning**.

The mainstream narrative defaults to "the stronger the model, the closer to AGI". Yet the larger the parameters, the stronger the "stability tension" solidified by training data among the model's weights: it becomes increasingly good at doing local optima **within existing cognition and behavior patterns** — an extremely good **conservative planner**; give it a pattern, and it can execute it to perfection. But precisely because this pattern is locked dead by the weights, it can hardly break through on its own — **a large model bound by weights cannot break through the "existing cognition and behavior patterns" solidified by its training**. And what AGI needs is exactly to break this set of existing patterns itself. **Larger parameters make a better conservative planner, not something that can bring cognitive revolution; the existing patterns locked dead by weights can only push AGI further away.**

So the real revolution is not at the "parameter" layer (the more you stack, the more conservative), but at the "context" layer. Single-point capability is no longer the bottleneck — today's large models, looking at a single conversation, a single reasoning, a single tool invocation, can already excellently complete a large number of intellectual tasks. What is stuck for us is never "some model is not smart enough", but **how to make an already-smart-enough model stably, convergently, and scalably complete "arbitrary" tasks**. The former relies on parameters, the latter relies on: structure. And what structure truly needs to do is not make the model stronger, but make three things happen to it at the current layer —

**Layer one: use the facts of context to create tension, overcoming conservatism.** The model cannot jump out of the existing cognition locked by weights on its own, so let the external structure **inject the facts of the present and the specific information of the task into the context** — these facts fall outside the weights, creating **tension** with the model's solidified inertia patterns. This tension is the force that overrides its conservative tendency at this very moment. Overcoming conservatism does not rely on making the model stronger, but on using fresh facts in the local context to temporarily rewrite the inertia in its weights.

**Layer two: in the local context space, amplify the value of parameters.** A model shaped by weights only truly puts its already-threshold-crossing single-point capability to use, aimed at the current task, when placed in a **local, focused, reorganized context space** (each phase only sees the piece it should see, uncontaminated by the global). The same parameters, in a carefully organized local context, produce far more than in a chaotic global one — **structure amplifies the existing value of parameters in the local space**.

**Layer three: thus output exceeds cost, becoming a real, self-sustaining capability.** These three layers together flip the relationship between structure and "output vs cost" from negative-sum and zero-sum to **positive-sum**: not by stacking parameters, not by the model breaking through on its own, but by "injecting facts to create tension + amplifying parameters in the local space", exchanging more and better products per unit cost. Only this kind of capability whose output exceeds cost and can self-sustain is worthy of being the cornerstone of AGI landing — just like LLM code, precisely because writing code still has positive returns after deducting costs, it went from "demonstration" to "infrastructure".

### The Convergence of the Solution: AGI = Intelligence + Complete Structure

So this solution splits AGI into two orthogonal parts:

> **AGI = intelligence (the cognitive capability the model already possesses) + complete structure (organizing it into the form where "any realizable task can be completed")**

- **Intelligence** answers "is it smart" — on this point, today's LLMs have already crossed the threshold;
- **Complete structure** answers "can it stably finish, make, and carry a long task to the end" — this is exactly what the text-cli family is doing.

#### The Phase Mechanism Based on text-cli

The first half of the complete structure is "phase" — it answers "how to organizationally carry the most complex task to the end". Its visible form is a **tree that grows on the spot according to the task, self-decided by the LLM at each layer, with mechanical backstop**:

```text
one sentence comes in
   │
   ▼
  LLM planning: first "phase the whole problem" — split it into segments strung together and advanced in sequence
   │   (these segments are the "first layer" of this tree)
   ▼
  the first phase
   │  "LLM self-decision": based on the current context and the tools/contracts found by sm query, judge by itself
   │     —— is this ready to land? or does it need to drill down? the mechanical gate only backstops at the end
   ├─ judged ready to land ────────→ lands as a "leaf" → handed to text-cli for execution
   │                        one domain;action,parameter in, one envelope out
   └─ judged still needing drill-down → stays as a "node" → recursively drills down sub-phases, self-deciding layer by layer…
        │                          (each sub-phase repeats the same self-decision)
        ▼
   the deepest leaf → text-cli execution → envelope returns → quality gate judgment
   │
   ├─ pass → solidify product, update cognition, continue to the next leaf
   ├─ fail → only roll back to the current checkpoint, rerun this branch, not discarding the whole tree
   └─ result has a large amount of "delegation / partial completion" → reverse signal → re-estimate as a "node" and re-triage
   ▼
one result goes out
```

The key of this structure is that every step is **self-decided by the LLM in the reorganized local context of the moment**, not pre-orchestrated:

- **"Self-decision"**: whether each layer "continues triage" or "lands and executes" is judged **by the LLM itself** — based on the current phase context and the capabilities and contracts injected by sm query, it decides whether this is ready to land or needs to drill down. As the task changes, the LLM's judgment lets the tree naturally grow into different shapes. Mechanical closed-set validation only provides the **final backstop**: after the LLM judges, it seals errors, forces landing at the ceiling, and backstops missing contracts, preventing triage from running away — **the decision is the LLM's, the mechanical part is responsible for backstop**.
- **"Recursion"**: nodes can drill down layer by layer to arbitrary depth, until landing on a truly executable leaf; the depth is decided by the LLM's judgment of task complexity, not written as a fixed number of steps.
- **"Reverse signal"**: if a "leaf" after execution reveals that it cannot yet land (a large amount of delegation / partial completion), it is **re-estimated as a node** and re-tried — acknowledging that the LLM's first judgment may be wrong, and wrong judgments can be corrected.
- **"Local rollback"**: if a leaf is wrong, it only rolls back to the checkpoint and reruns this branch, errors cut off by the phase boundary, not discarding the whole tree.

This is the "complete structure": **it does not rely on the model getting stronger, but on organizing one inference into a tree that can grow by self-decision, recurse, be re-estimated in reverse, and be rolled back locally.** Phase-based decomposition is responsible for "how this tree grows", text-cli is responsible for "how each leaf lands", and the two together let an already-smart model **take on arbitrary tasks, run stably, and roll back**.

Thus there is a key distinction: **"whether it is AGI" is decided by structure, "how useful it is" by parameters, the two orthogonal**. Parameters decide how fast and how well the same AGI completes tasks, but the qualification itself is given by structure.


#### Problem Triage and Task Chains Based on text-cli

The complete structure does not have only the "phase" half. Before entering phases, there is a **problem triage** — it first looks at how complex this problem is, then decides which path to take. This is the other half of the complete structure, and also the path most requests actually take. (Phases themselves are in the previous section; this section does not touch them.)

**Complexity classification: first ask "how complex is this problem".** This is the first gate of problem triage. When any sentence comes in, the system first classifies its complexity — judging whether it is an offhand question, needs to look up material, needs to invoke tools, or needs to run a long task. Different complexity means vastly different resource investment: a "hello" should not consume the full orchestration of a long task.

**Triage routing: choose a path by complexity.** The result of complexity classification decides which path to take. The key is — problem triage even counts "direct answer" as a path:

- **Ordinary conversation → direct answer**: simplest, directly answered by the LLM, **invoking no tools and walking no chain**;
- **Strategy conversation → inject strategy + tool loop**: when expert experience / tools are needed, inject the corresponding strategy, and the LLM advances step by step in repeated tool loops;
- **Task chain → split-chain execution**: when multiple steps need to be handled at once, organize the task into an execution chain.

**Not all requests invoke tools or tool chains.** This is the key to "problem triage being complete": **the LLM judges, based on the task, whether to "directly answer" or to use tools and create an async task chain**. Problem triage is "complete" precisely because it recognizes these "light requests" at the very front and handles them in the lightest way, leaving resources for what truly needs heavy processing. Those that invoke tools / tool chains (strategy conversation, task chain) are only a small part after triage.

**The two paths that invoke text-cli both land on text-cli in the end.** The two "heavy" paths organize text-cli differently, but both rest on the same instruction contract — only the invocation method differs:

- **Strategy conversation = one text-cli instruction at a time**: invoke one at a time — one `domain;action,parameter` in, one envelope out, the result back-filled into context, and the LLM decides the next step. This is "single instruction, multiple iterations";
- **Task chain = compose a path**: the LLM first generates a text-cli path (stringing multi-step instructions into one executable orchestration), and this path executes multiple steps at once with one envelope returned. This is "multiple instructions, one orchestration".

In one sentence: **strategy conversation invokes text-cli one instruction at a time, task chain runs text-cli with a path; ordinary conversation answers directly without touching text-cli.** Whether "single instruction" or "path multi-step", both are uniformly collected by text-cli under "one sentence in, one envelope out".

Below, two examples land "single instruction" and "path multi-step" onto visible objects.

**Single tool invocation — the "single instruction" in strategy conversation: one envelope at a time.**

```text
The reader asks: how much is 2+3*4?
LLM generates one instruction →   AI:tc-math;eval,2+3*4
text-cli executes →        {"status":"ok","result":14}
LLM answers with this result →  "It equals 14."
```

This time only one tool is invoked, one envelope at a time. Strategy conversation is this "single instruction" — the LLM goes step by step, generating one `domain;action,parameter` per step, getting back one envelope, and deciding the next step.

**Path multi-step — the "one orchestration" in task chain: one instruction, one envelope.**

When the LLM directly generates a path instruction, it treats the declaration and the input data as two independent parameters, one `text-cli;path` in and one envelope returned:

```text
AI:text-cli;path,{
  "id": "tomorrow-weather",
  "type": "pipeline",
  "version": "1.0.0",
  "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
  "requires": ["map;geocode", "weather;query"],
  "steps": [
    {"id": "geo", "instruction": "map;geocode,{input.city}", "output_as": "geo"},
    {"id": "wx",  "instruction": "weather;query,{geo.city},tomorrow", "output_as": "wx"}
  ]
},{"city":"Beijing"}
→  text-cli executes both steps at once → one envelope returns →  LLM organizes it into the final answer
```

A parameter starting with `{` is recognized as an inline path declaration; the `{"city":"Beijing"}` after the comma is the independent input data. Two steps are strung into one path: the first step `map;geocode` locates "Beijing" into coordinates stored in `{geo.city}`, and the second step `weather;query` uses `{geo.city}` to query Beijing's tomorrow weather. This is "path multi-step" — the task chain converges multi-step orchestration back into one `text-cli;path`, one execution, one envelope.

**Closure: problem triage + phases, together they are the complete structure.** Problem triage (outside phases) decides "which path to take, light or heavy, whether to touch text-cli"; phases (inside phases) decide "after entering phases, how the task grows into a tree and how to carry the hardest to the end". The two are both indispensable — **without problem triage, all requests squeeze into heavy processing, and cost and complexity spiral out of control together; without phases, the most complex tasks have no backstop that can go deep.** Thus the whole chain converges to: **problem triage selects the path → light ones answer directly, heavy ones invoke text-cli either singly or by path → one envelope converges.**


### Where "Progressive" Is: AGI Is Not an Endpoint, but Growth Along Two Axes

Treating AGI as "intelligence + complete structure", it is no longer a static completed state, but a process **continuously growing along two directions**:

- **Breadth axis (coverage κ)**: the structure can take on more and more tasks. It expands continuously along two paths:
  - **Extremely low production barrier**: a capability package is minimally "a Markdown" (no code at all) or "a schema + a handler". The barrier is as low as "just being able to speak" — producers expand from "developers" to "anyone who can express" (a florist, a bonsai enthusiast). More people able to produce capabilities means a continuous supply of coverage.
  - **Small and complete, bidirectionally convertible with any protocol**: the tc handle is a **minimal contract** small enough with clear boundaries (one `domain;action,parameter` + one three-field envelope), so in theory any other protocol (MCP, function calling, custom schema…) can be bidirectionally converted with it — external capabilities can be bridged into tc handles, and tc handles can be converted out. This lets the breadth axis not only rely on human production, but also on **protocol bridges** to directly fill in existing ecosystems, with coverage only increasing, monotonically rising.
- **Height axis (completion quality)**: the same task is completed more and more accurately and well under structural scheduling.

But the height axis **is not "the stronger the model, the better the completion"** — that is exactly the mainstream narrative denied earlier. Here one must first separate the two dimensions of AGI: the **"paradigm-breaking" dimension** — whether it can jump out of existing cognition and create new things, on which the conservatism of large parameters is negative (locked by weights, can only be broken through by structure at the context layer, i.e., the earlier "can only push AGI further away"); the **"landing execution" dimension** — whether it can precisely do known tasks right, on which the conservatism of large parameters is exactly positive — **more conservative means better completion of known tasks, able to align handles more precisely and make executable handles**. This is exactly the "positive edge" most needed for AGI landing.

So parameters are not the "ceiling", but **the gears in structure's hands**: let different parameter sizes each sit in their place — high-parameter models (conservative but precise) handle planning, handle alignment, and complex tasks; small-parameter models (cheap and adequate) handle summarization, degradation, and lightweight tasks. **It is structure that decides which parameter size does which thing, not parameters deciding how high AGI is.**

So both axes are led by structure, not independent of each other: **the breadth axis relies on structure to expand the ecosystem (make packages, cover tasks), the height axis relies on structure to schedule parameters (put each gear where it belongs).** The two axes feed each other and advance simultaneously. This is the original meaning of "progressive": **AGI is not an "either it is or it isn't" switch, but a process that grows continuously and irreversibly along breadth and height.**

### Closure: Why "Progressive" Is a Necessity, Not a Compromise

Perhaps you would ask: why not directly declare "this is AGI", why must we add "progressive"?

First, AGI cannot be built in one day — it cannot suddenly appear one morning upon waking. It can only steadily make the product value of one task after another higher than its cost.

On a deeper level, the structural nature of the goal "any realizable task" determines this: **there will always be a next task popping up, and any finite data and training cannot cap this "any"**. Therefore, a "completed-state" AGI cannot logically be proven reachable — precisely because there is no "moment of completion", there is no "suddenly AGI one morning".

But the necessity of "progressive" lies not only in philosophy, but in economics. **Growth is not free**: making a package has a cost, maintaining the ecosystem has a cost, running every phase and every path has computational cost. Only when the value of a product is **steadily and continuously higher than its landing cost (positive-sum)** is growth sustainable and irreversible; otherwise — value cannot cover cost — the ecosystem shrinks, coverage falls, and "irreversible growth" collapses. So "progressive" is not "I am not good enough so I take it slow", but **"only by steadily making product value higher than cost can growth continue"** — this is the only form of sustainable growth.

And the progressive AGI solution based on text-cli is precisely the mechanism that pursues "value > cost" being able to hold repeatedly: low handle production barrier, same-dimensional zero-tax making consumption cheap, path converging multiple steps into one cost, structure amplifying parameter value in the local context — **making "making product higher than cost" something that can be repeated and stably occur every day**.

So this declaration is honest and enterprising: **it does not claim "AGI has been built", but claims "AGI is a direction that, relying on structure and handles, continuously makes product value higher than cost, thereby sustainably accumulating".** Progressive is not a retreat to second-best, but the form jointly required by the two natures of "any task cannot be capped" and "growth must be positive-sum".

### Related Documents

The examples are the **landing expression** of the "progressive AGI solution" — landing structural support onto concrete examples, so that readers who do not understand protocol details can also understand. The complete argument is not here, but in two original documents:

- **agi_explanation_en.md- [online](https://github.com/weihai-limh/text-cli/blob/main/examples/project/agi/agi_explanation_en.md) or [relative](examples/project/agi/agi_explanation_en.md)** — mechanism explanation: why AGI lacks not a smarter model but a complete structure; what "intelligence + complete structure" and progressive AGI are.
- **protocol_agi_adaptation_en.md-[online](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/ecosystem/protocol_agi_adaptation_en.md) or [relative](./docs/en/protocol_agi_adaptation_en.md)** — axiom proof chain: how the text-cli protocol closes the AGI criterion of "uttering speech and obtaining a result" on the structural side (execution layer + planning layer).



