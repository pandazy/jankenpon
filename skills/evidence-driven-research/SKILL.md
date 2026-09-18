---
name: evidence-driven-research
description: End-to-end discipline for investigation, research, and any information-seeking request. Gather sources, reason over them with evidence-based-reasoning and harden the weak points with evidence-hardening-loop, then update beliefs with explicit Bayesian inference (prior → evidence → likelihood → posterior) so findings are quantified, not just asserted. Present results with high affordance — the right chart for the data shape (proportion→pie, trend→line, comparison→bar, distribution→dot, multi-dimensional→3-D when it helps) — and word every conclusion so an average reader understands it without a glossary. Use whenever asked to investigate, research, look something up, compare options, estimate a quantity, or explain "what does the data say".
version: 1.0.0
tags: [research, investigation, reasoning, evidence, bayesian, visualization, communication]
---

# Evidence-Driven Research

Turns a question into a trustworthy, quantified, *legible* answer. It is the pipeline you run for any investigation or research request: **gather → reason → harden → update beliefs Bayesian-style → visualize with the right chart → report in plain language.** Stages 2 and 3 delegate to the two reasoning skills alongside this one; this skill adds the gathering step, the Bayesian belief-update, the visualization discipline, and the reader-friendliness bar, and sequences all of it.

## When to invoke

- Any request to *investigate*, *research*, *find out*, *look up*, *compare*, *estimate*, or *"what does the data say about…"*.
- You are synthesizing findings from multiple sources and the user wants a defensible answer, not a hunch.
- A conclusion would benefit from a probability rather than a bare yes/no ("how likely is X given what we found").
- You are about to present numbers or findings the user will read and act on.

---

## The pipeline

### 1. Gather

Collect the sources that bear on the question — files, command output, metrics, documents, search results. Note each source's reliability as you go (you'll need it for likelihoods and for weak-vs-strong grading).

### 2. Reason — apply `evidence-based-reasoning`

Run [`evidence-based-reasoning`](../evidence-based-reasoning/SKILL.md): every conclusion carries its evidence and the explicit link; unsupported claims are labeled guesses; reconcile against prior conclusions. This produces conclusions with weak points honestly marked.

### 3. Harden — apply `evidence-hardening-loop`

Run [`evidence-hardening-loop`](../evidence-hardening-loop/SKILL.md) on the load-bearing weak points: drive each toward a direct observation, or declare the gap irreducible. Don't proceed to quantification while the roof rests on a guess.

### 4. Update beliefs — Bayesian inference

Where the answer is a matter of degree, make the belief update **explicit** rather than eyeballed:

1. **Prior** — state your belief *before* this evidence, as a probability or range, and where it came from (base rate, earlier finding, stated assumption). Label a made-up prior as such.
2. **Evidence** — the observation you're conditioning on (from stages 2–3).
3. **Likelihood** — how expected that evidence is *if the hypothesis is true* vs. *if it's false* (`P(E|H)` vs `P(E|¬H)`). This ratio, not the raw evidence, is what moves the needle.
4. **Posterior** — the updated belief. Show the direction and rough magnitude of the shift; give a number when the inputs support one, a qualitative shift ("weakly → strongly likely") when they don't.

Rules of the road:
- **Update, never prove.** Evidence shifts a belief; it rarely drives it to 0 or 1. Resist "this proves it."
- **Independence check.** Two sources that copy the same origin are one piece of evidence, not two — don't double-count.
- **Base-rate first.** A rare hypothesis needs strong evidence to become likely; state the base rate so a strong likelihood on a rare prior doesn't get over-read.
- **Sensitivity.** If the posterior swings wildly on a shaky prior or likelihood, say so and return to stage 3 to harden that input before reporting the number.

Keep the arithmetic simple and show your inputs — a transparent rough estimate is more useful than an opaque exact one.

### 5. Visualize — match the chart to the data shape

Every quantitative finding gets the chart that reveals it fastest. Chart choice by data shape:

| Data shape | Chart | Use when |
|---|---|---|
| Proportion / share of a whole | **Pie** (or donut) | parts sum to 100% and count is small |
| Trend over time / ordered axis | **Line** | showing change, trajectory, before/after |
| Comparison across categories | **Bar** (grouped/stacked as needed) | ranking or comparing discrete items |
| Distribution / spread | **Dot** plot (or strip/beeswarm) | showing where values cluster and scatter |
| Multi-dimensional relationships | **3-D** (scatter/surface) | ≥3 interacting dimensions where 2-D loses the story — and only when it *adds* clarity |
| Uncertainty around an estimate | error bars / band on any of the above | plotting a stage-4 posterior — show the range, never a bare point |

Don't hesitate to use 3-D for genuinely multi-dimensional data, but never for decoration — if a 2-D chart or small-multiples shows it more clearly, use that.

Render legibly regardless of tool: readable labels and units on every axis, a title stating what the chart shows, a colorblind-safe palette that also works in grayscale, and enough contrast to read in both light and dark backgrounds.

### 6. Report — reader-friendly, plain language

Word the answer so **any average reader** gets it without a glossary:

- **Lead with the answer** in one plain sentence, then the confidence ("likely — about 4 in 5, based on…").
- **Translate the math.** "Posterior ≈ 0.8" → "roughly a 4-in-5 chance." Put jargon and formulas in a footnote or appendix, not the headline.
- **Every chart earns a one-line takeaway** in words — the reader shouldn't have to decode the axes to get the point.
- **Keep guesses visibly separated** from verified findings (carried over from stage 2).
- **State what would change the conclusion** — the one piece of evidence that would move the posterior most.

---

## Quick procedure

1. **Gather** sources; note each one's reliability.
2. **Reason** — run `evidence-based-reasoning` (evidence + link + label + reconcile).
3. **Harden** — run `evidence-hardening-loop` on load-bearing weak points.
4. **Update** — prior → likelihood ratio → posterior, shown explicitly with uncertainty.
5. **Visualize** — chart matched to data shape (pie/line/bar/dot/3-D), rendered legibly.
6. **Report** — plain-language answer, confidence in everyday terms, per-chart takeaway, gaps flagged.

Stages 3–4 are a cycle, not a one-way step: a posterior that hinges on a shaky input sends you back to hardening before you report it.

---

## Anti-patterns (what this skill forbids)

- **Eyeballed probability.** "Probably about 80%" with no prior, no likelihood, no basis — do the explicit update or label it a guess.
- **False precision.** Reporting "posterior = 0.834" when the inputs were rough guesses — the digits imply a rigor the evidence doesn't support.
- **Chart–data mismatch.** A pie for a time trend, a line for unordered categories, a 3-D chart used for flair where a bar would be clearer.
- **Chart with no takeaway,** leaving the reader to reverse-engineer the point from the axes.
- **Jargon headline.** Leading with "posterior ≈ 0.8, KL-divergence…" instead of the plain-English answer.
- **Skipping the hardening loop** and quantifying a belief that still rests on an unverified inference.

## Related skills

- [`evidence-based-reasoning`](../evidence-based-reasoning/SKILL.md) — stage 2; how to reach and state a conclusion with its evidence.
- [`evidence-hardening-loop`](../evidence-hardening-loop/SKILL.md) — stage 3; the loop that drives weak points to confirmed before you quantify.
