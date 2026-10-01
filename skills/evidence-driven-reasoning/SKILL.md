---
name: evidence-driven-reasoning
description: "End-to-end discipline for reaching, hardening, quantifying, and reporting any conclusion. Core (always): every conclusion cites its evidence and the explicit link, unsupported claims are labeled guesses, and each conclusion is reconciled against prior ones. Harden (before anything the user acts on): loop on every load-bearing weak point — inference, proxy, guess, another tool's unchecked claim — driving it toward a direct observation until nothing load-bearing rests on a guess or the gap is explicitly declared irreducible. Research mode (investigations): gather sources, update beliefs with explicit Bayesian inference (prior → likelihood → posterior), visualize with the chart that matches the data shape, and report in plain language an average reader understands. Use whenever asserting a diagnosis, status, recommendation, or test/review verdict, and whenever asked to investigate, research, compare, estimate, or explain what the data says."
version: 2.0.0
tags: [reasoning, evidence, methodology, rigor, verification, root-cause, iteration, hardening, research, bayesian, visualization, communication]
---

# Evidence-Driven Reasoning

A conclusion is only as trustworthy as the evidence behind it, the work done to close its gaps, and the honesty about what remains open. This is the standing discipline for **how to reach a conclusion, how to strengthen it, how to quantify it, and how to state it.**

It has three layers, applied in order:

| Layer | Always / when | What it does |
|---|---|---|
| **A. Core** | Every claim | Conclusion + evidence + explicit link; label guesses; reconcile |
| **B. Harden** | Before anything the user will act on | Loop load-bearing weak points toward direct observation |
| **C. Research mode** | Investigation / research / estimation requests | Gather → Bayesian update → visualize → plain-language report |

Layer A is the floor, not the finish: a labeled guess is honest, but if a conclusion the user will act on still rests on it, honesty alone has not made it trustworthy. Layer B refuses to stop while a weak spot is holding up the roof. Layer C wraps both when the task is to find something out rather than to assert something.

## When to invoke

- You are about to assert *anything the user will act on* — a diagnosis, root cause, status, recommendation, or answer to a yes/no question ("my change works", "the fix is deployed", "this is safe to delete", "not my change", a test-pass judgment, a review finding).
- You catch yourself writing "probably", "should be", "I think", "it's likely", "the timestamps imply", "the analyzer says" — those are guesses or inferences; label them (A2) and harden them (B).
- You are triaging a test failure, a flaky rerun, a deployment state, or consolidating findings from multiple sources that must not contradict each other.
- You are about to say "done", "confirmed", "root cause is X", "safe to ship".
- **Research mode:** any request to *investigate*, *research*, *find out*, *look up*, *compare*, *estimate*, or *"what does the data say about…"*; or when a conclusion would be more useful as a probability than a bare yes/no.

---

## The evidence ladder (shared vocabulary)

Everything below grades evidence the same way. Prefer direct observation over inference.

- **Reproduced** — you produced the observation more than once, or with an A/B baseline that isolates the cause.
- **Strong** — a direct observation you produced: command output, a test run you executed, file contents you read, a metric you pulled.
- **Weak** — a proxy (timestamps standing in for a deploy landing), a single run with no baseline, "it usually works this way", another tool's unverified claim (static analyzer, linter, AI assistant).
- **Guess** — no supporting observation at all; an inference, estimate, or carried assumption.

Weak evidence is usable — but say it's weak, and never let it carry a conclusion alone.

---

## Layer A — Core (three rules, always)

### A1. Every conclusion carries its evidence and the link

State the conclusion, then the evidence, then **how each item leads to the conclusion**. The chain must be explicit — the reader should not have to guess why an observation supports the claim. Grade each item on the ladder and cite its source.

> **Conclusion:** The failing UI test was caused by a version-hashed CSS selector, not a product regression.
> **Evidence → link:**
> - The selector resolves to a class that no longer exists after the UI-library upgrade (grep of the test helpers — strong) → the selector now matches nothing.
> - The failure rate jumped from ~26% to ~99% on the exact build that shipped the upgrade (build history — strong) → timing pins the cause to that change.
> - Reverting only the selector returned the test to green (test run — reproduced) → confirms the selector, not product code, was the fault.

### A2. No evidence? Label it a guess — out loud

If a claim has no supporting evidence, or only weak/circumstantial evidence, **mark it explicitly**. Never present a guess in the same voice as a verified fact. Use plain markers:

- *"Informed guess (unverified): …"*
- *"Estimate — no direct measurement: …"*
- *"Assumption I'm carrying: …, which I have not confirmed."*

Then say what evidence *would* settle it — that sentence is the input to Layer B.

### A3. Reconcile after each conclusion

Once a conclusion is formed, **re-check it against the evidence and against your earlier conclusions**, and purge anything out of sync:

- Does every cited item actually support the conclusion, or did one go stale or start contradicting it?
- Does this conclusion contradict something you asserted earlier in the session? One of them is wrong — resolve it, don't ship both.
- Did new evidence arrive that undercuts the chain? Retract or revise.
- Is the conclusion broader than the evidence licenses? Narrow it.

State the outcome whenever reconciliation changes anything ("Earlier I said X; the run just now contradicts it — revising to Y").

---

## Layer B — Harden (the loop)

Run this loop before reporting anything the user will act on. One pass = one weak point promoted. Re-invoke each cycle: hardening one weak point often exposes the next.

### B1. Enumerate the weak points

From Layer A, list every item that is **weak or a guess** *and* **load-bearing** (the conclusion changes if it's wrong): inferences, proxies, single observations with no baseline, another tool's unchecked claim, anything you labeled guess/estimate/assumption.

Weak points that are **not** load-bearing: say so and move on. Effort goes where being wrong costs something.

### B2. Rank by leverage

For each, ask: *if this is wrong, how much of the conclusion collapses, and how bad is acting on it?* Hardest-hitting first. Don't polish a minor caveat while the central inference stays unconfirmed.

### B3. Name the confirming observation, then go get it

For the top weak point, write the single most direct observation that would promote it one rung up the ladder — then actually produce it.

| Instead of (weak) | Promote by |
|---|---|
| "timestamps say the fix shipped to the environment" | run against that environment and read the result |
| "the analyzer flags this line" | read the code path and reproduce the condition |
| "the test passed once" | A/B baseline — run with and without the change |
| "it must be this element/identifier" | search for it and confirm it resolves to nothing post-change |
| "the config looks right" | execute the path that consumes the config and observe it |
| "probably the same root cause" | reproduce both symptoms from the one cause |

You will not always reach *reproduced*. The goal is **one rung closer**: guess → weak-but-direct, weak → strong, strong → reproduced. Each promotion counts.

### B4. Reconcile the new evidence

New evidence changes the picture, so re-apply Layer A to it — re-link, re-grade, re-label, reconcile against prior conclusions (A3). Hardening a point routinely (a) confirms it, (b) **disproves** it, so the conclusion itself is now wrong, or (c) surfaces a new weak point. All three are progress; (b) is the most valuable and the whole reason to bother.

### B5. Loop or exit

Return to B1 with the updated picture. **Exit only when** either:

- **Solid** — no load-bearing conclusion rests on an unverified point; each is backed by a direct observation you produced; or
- **Irreducible gap declared** — the remaining weak point can't be confirmed with available access, tools, or time, AND you have said so explicitly: what it is, why it can't be closed now, what *would* close it, and how much of the conclusion is exposed if it's wrong.

Do **not** exit merely because the guesses are labeled (that was Layer A's bar) or because you've spent a while. Exit on evidence or an honest declared stop. An irreducible gap is acceptable when it's *declared*, not when it's *tired*.

---

## Layer C — Research mode

For investigations, research, comparisons, and estimates, wrap Layers A–B in this pipeline: **gather → reason (A) → harden (B) → update beliefs → visualize → report.**

### C1. Gather

Collect the sources that bear on the question — files, command output, metrics, documents, search results. Note each source's reliability as you go; you'll need it for ladder grading and for likelihoods.

### C2–C3. Reason and harden

Run Layers A and B on what you gathered. Don't proceed to quantification while a load-bearing point is still a guess.

### C4. Update beliefs — explicit Bayesian inference

Where the answer is a matter of degree, make the update **explicit** rather than eyeballed:

1. **Prior** — your belief *before* this evidence, as a probability or range, plus where it came from (base rate, earlier finding, stated assumption). A made-up prior is labeled as such per A2.
2. **Evidence** — the observation you're conditioning on (from C2–C3).
3. **Likelihood** — how expected that evidence is *if the hypothesis is true* vs. *if it's false* (`P(E|H)` vs `P(E|¬H)`). This ratio, not the raw evidence, is what moves the needle.
4. **Posterior** — the updated belief. Give a number when the inputs support one, a qualitative shift ("weakly → strongly likely") when they don't.

Rules of the road:

- **Update, never prove.** Evidence shifts a belief; it rarely drives it to 0 or 1.
- **Independence check.** Two sources copying the same origin are one piece of evidence, not two.
- **Base-rate first.** A rare hypothesis needs strong evidence to become likely; state the base rate so a strong likelihood on a rare prior isn't over-read.
- **Sensitivity.** If the posterior swings wildly on a shaky prior or likelihood, that input is load-bearing — go back to Layer B and harden it before reporting the number.

Keep the arithmetic simple and show your inputs: a transparent rough estimate beats an opaque exact one.

### C5. Visualize — match the chart to the data shape

Every quantitative finding gets the chart that reveals it fastest.

| Data shape | Chart | Use when |
|---|---|---|
| Proportion / share of a whole | **Pie** (or donut) | parts sum to 100% and the count is small |
| Trend over time / ordered axis | **Line** | change, trajectory, before/after |
| Comparison across categories | **Bar** (grouped/stacked) | ranking or comparing discrete items |
| Timeline of events / phases | **Gantt** | when things start, end, overlap, or block each other |
| Distribution / spread | **Dot** plot (strip/beeswarm) | where values cluster and scatter |
| Multi-dimensional relationships | **3-D** (scatter/surface) | ≥3 interacting dimensions where 2-D loses the story |
| Uncertainty around an estimate | error bars / band on any of the above | plotting a C4 posterior — show the range, never a bare point |

Use 3-D for genuinely multi-dimensional data, never for decoration — if 2-D or small multiples show it more clearly, use that. Render legibly regardless of tool: readable labels and units on every axis, a title stating what the chart shows, a colorblind-safe palette that also works in grayscale, enough contrast for light and dark backgrounds.

### C6. Report — reader-friendly, plain language

Word the answer so **any average reader** gets it without a glossary:

- **Lead with the answer** in one plain sentence, then the confidence ("likely — about 4 in 5, based on…").
- **Translate the math.** "Posterior ≈ 0.8" → "roughly a 4-in-5 chance." Jargon and formulas go in a footnote, not the headline.
- **Every chart earns a one-line takeaway** in words — the reader shouldn't decode axes to get the point.
- **Keep guesses visibly separated** from verified findings (A2), and state declared irreducible gaps (B5).
- **State what would change the conclusion** — the one piece of evidence that would move it most.

---

## Quick procedure

**Any claim (Layers A–B):**

1. **Claim** — write the conclusion in one sentence.
2. **Evidence** — list each supporting item; grade it on the ladder; cite its source.
3. **Link** — one clause per item on *why* it supports the claim.
4. **Label** — anything unsupported → guess/estimate/assumption (A2).
5. **Harden** — list load-bearing weak points, rank by leverage, produce the most direct confirming observation for the top one (B1–B3).
6. **Reconcile** — re-link, re-grade, resolve contradictions and over-reach (A3/B4).
7. **Repeat 5–6** until solid or an irreducible gap is declared (B5).
8. **Report** — claim + evidence chain, guesses and gaps visibly separate.

**Investigations add (Layer C):** gather sources with reliability notes before step 1; after step 7, run the explicit prior → likelihood → posterior update, chart each quantitative finding by data shape, and report in plain language with per-chart takeaways. C4 and the hardening loop are a cycle: a posterior hinging on a shaky input sends you back to step 5 before you report the number.

---

## Anti-patterns (what this skill forbids)

**Reaching and stating (A)**

- **Bare verdict.** "It works" / "not my change" / "it's deployed" with no run, no output, no metric behind it.
- **Single-run confidence.** Concluding from one post-change run without a baseline — environmental noise routinely fakes both pass and fail.
- **Timestamp-as-proof.** Inferring "the fix reached the environment" from build/deploy timestamps; the empirical run is the source of truth.
- **Trusting another tool's claim unchecked.** Static analyzers and AI assistants produce false positives — verify against the actual code before repeating their conclusion as yours.
- **Laundering a guess into a fact** by dropping the hedge as the sentence travels down a report.
- **Leaving a contradiction on the page** because both halves were written at different times.

**Hardening (B)**

- **Labeling as an exit.** Slapping *"(unverified)"* on a central inference and calling it done — the label starts the work, it doesn't end it.
- **Hardening the cheap point.** Confirming an easy, low-stakes item to feel progress while the load-bearing inference stays untouched.
- **Silent give-up.** Stopping at a weak point without declaring it irreducible — the user can't tell "I confirmed it" from "I got tired".
- **One-and-done.** Reporting after one promotion when that promotion exposed a fresh weak point.
- **Ignoring disconfirmation.** The direct check contradicts the inference and you keep the original conclusion anyway.
- **Infinite polishing.** Drilling a non-load-bearing caveat past the point it can change any action.

**Quantifying and presenting (C)**

- **Eyeballed probability.** "Probably about 80%" with no prior, no likelihood, no basis.
- **Quantifying an unhardened belief.** Attaching a posterior to a chain that still rests on an unverified inference.
- **False precision.** "Posterior = 0.834" from rough-guess inputs — the digits imply rigor the evidence doesn't support.
- **Chart–data mismatch.** A pie for a time trend, a line for unordered categories, 3-D for flair where a bar would be clearer.
- **Chart with no takeaway,** leaving the reader to reverse-engineer the point from the axes.
- **Jargon headline.** Leading with "posterior ≈ 0.8, KL-divergence…" instead of the plain-English answer.
