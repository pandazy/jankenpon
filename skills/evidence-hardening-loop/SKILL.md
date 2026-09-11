---
name: evidence-hardening-loop
description: The iterative follow-up pass to evidence-based-reasoning. After an evidence-based-reasoning pass leaves a conclusion resting on any weak point — an inference, a proxy, a guess, another tool's unverified claim — do not mark it done. Loop: find each weak point, dig for direct evidence that promotes it toward a confirmed point, and repeat until nothing load-bearing rests on a guess (or the remaining gap is explicitly declared irreducible). Use after evidence-based-reasoning, before reporting a diagnosis/status/"done" the user will act on.
version: 1.0.0
tags: [reasoning, evidence, methodology, rigor, verification, iteration, hardening]
---

# Evidence-Hardening Loop

`evidence-based-reasoning` gets you a conclusion with its evidence chain and its guesses honestly labeled. That is the *floor*, not the finish. A labeled guess is honest — but if a conclusion the user will act on still rests on it, honesty alone hasn't made the conclusion trustworthy. **This skill is the loop that runs after each evidence-based-reasoning pass to drive every load-bearing weak point closer to a confirmed point before you mark anything complete.**

Think of it as: EBR labels the weak spots; this skill refuses to stop while a weak spot is still holding up the roof.

## When to invoke

- Immediately **after** an [`evidence-based-reasoning`](../evidence-based-reasoning/SKILL.md) pass, whenever that pass left any conclusion supported by weak evidence or a labeled guess.
- Before you say "done", "confirmed", "root cause is X", "safe to ship" — anything the user will act on.
- When a diagnosis hinges on an inference ("the timestamps imply…", "the analyzer says…", "it usually…") and you have not yet tried to replace that inference with a direct observation.
- Re-invoke it each cycle: hardening one weak point often exposes the next.

---

## The loop

Run this until the exit condition is met. One pass = one weak point promoted.

### 1. Enumerate the weak points

From the evidence-based-reasoning output, list every item that is **weak or unverified** and **load-bearing** (the conclusion changes if it's wrong):

- inferences / deductions ("therefore it must be…")
- proxies ("timestamps show the deploy landed")
- single observations with no baseline
- another tool's claim you haven't checked (a static analyzer, a linter, an AI assistant)
- anything you labeled *guess / estimate / assumption*

Ignore weak points that are **not** load-bearing — say so and move on. Effort goes where being wrong costs something.

### 2. Rank by leverage

For each load-bearing weak point, ask: *if this is wrong, how much of the conclusion collapses, and how bad is acting on it?* Hardest-hitting first. Don't polish a minor caveat while the central inference stays unconfirmed.

### 3. Name the confirming evidence, then go get it

For the top weak point, write the single most direct observation that would promote it from *inferred* to *confirmed* — then actually produce it:

| Instead of (weak) | Get closer to confirmed by |
|---|---|
| "timestamps say the fix shipped to the environment" | run against that environment and read the result |
| "the analyzer flags this line" | read the code path and reproduce the condition |
| "the test passed once" | A/B baseline — run with and without the change |
| "it must be this element/identifier" | search for it and confirm it resolves to nothing post-change |
| "the config looks right" | execute the path that consumes the config and observe it |
| "probably the same root cause" | reproduce both symptoms from the one cause |

You will not always reach *fully confirmed*. The goal is **closer**: turn a bare guess into weak-but-direct evidence, weak into strong, strong into reproduced. Each promotion counts.

### 4. Re-run evidence-based-reasoning on the result

New evidence changes the picture. Re-apply the three EBR rules — re-link, re-label, **reconcile against prior conclusions**. Hardening one point routinely (a) confirms it, (b) demotes it further (the direct check *disproved* the inference — now the conclusion itself is wrong), or (c) surfaces a new weak point. Any of these is progress; case (b) is the most valuable and the whole reason to bother.

### 5. Loop or exit

Go back to step 1 with the updated picture. **Exit when** either:

- **Solid:** no load-bearing conclusion rests on an unverified point — every one is backed by a direct observation you produced; or
- **Irreducible gap declared:** the remaining weak point cannot be confirmed with available access/time/tools, AND you have said so explicitly — what it is, why it can't be closed now, what *would* close it, and how much of the conclusion is exposed if it's wrong. An irreducible gap is only acceptable when it's *declared*, not when it's *tired*.

Do **not** exit merely because the guesses are labeled (that was EBR's bar) or because you've spent a while. Exit on evidence or an honest declared stop.

---

## Quick procedure

1. **List** load-bearing weak points from the EBR pass.
2. **Rank** by how much breaks if each is wrong.
3. **Target** the top one; write the direct observation that would confirm it.
4. **Get** that observation (run it, read it, reproduce it).
5. **Reconcile** — re-run EBR; confirm, retract, or narrow.
6. **Repeat** until solid or an irreducible gap is explicitly declared.

---

## Anti-patterns (what this skill forbids)

- **Labeling as an exit.** Slapping *"(unverified)"* on a central inference and calling it done — the label was the start of the work, not the end of it.
- **Hardening the cheap point.** Confirming an easy, low-stakes item to feel progress while the load-bearing inference stays untouched.
- **Silent give-up.** Stopping at a weak point without declaring it irreducible — the user can't tell "I confirmed it" from "I got tired".
- **One-and-done.** Hardening a single point and reporting, when its confirmation exposed a fresh weak point you didn't loop back on.
- **Ignoring disconfirmation.** The direct check contradicts the inference, and you keep the original conclusion anyway. A promotion that *breaks* the conclusion is the point, not a nuisance.
- **Infinite polishing.** Drilling a non-load-bearing caveat past the point it can change any action.

## Related skills

- [`evidence-based-reasoning`](../evidence-based-reasoning/SKILL.md) — the pass this loop runs after; it produces the labeled weak points this skill then hardens.
