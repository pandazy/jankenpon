---
name: evidence-based-reasoning
description: Discipline for reaching and reporting conclusions. Every conclusion must cite evidence and show how each piece leads to it; conclusions without evidence must be explicitly labeled as informed guesses or estimates; after each conclusion, re-check the evidence and prior conclusions to purge out-of-sync or contradictory content. Use whenever making a claim, diagnosis, recommendation, or status report — root-cause analysis, "is my change the cause?", "does this work?", test triage, code review, or any assertion the user will act on.
version: 1.0.0
tags: [reasoning, evidence, methodology, rigor, verification, root-cause]
---

# Evidence-Based Reasoning

A conclusion is only as trustworthy as the evidence behind it and the honesty about where evidence is missing. This skill is the standing discipline for **how to reach a conclusion, how to state it, and how to keep it consistent.** It applies to every claim you hand the user: root causes, "my change works", "the fix is deployed", "this is safe to delete", test-pass judgments, review findings.

## When to invoke

- You are about to assert *anything the user will act on* — a diagnosis, recommendation, status, or answer to a yes/no question.
- You catch yourself writing "probably", "should be", "I think", "it's likely" — those are guesses; label them (see below) or go get evidence.
- You are triaging a test failure, a flaky rerun, a deployment state, or a "not my change" claim.
- You are consolidating findings from multiple sources and need to be sure they don't contradict.

---

## The three rules (internalize these)

### 1. Every conclusion carries its evidence and the link

State the conclusion, then the evidence, then **how each item leads to the conclusion**. The chain must be explicit — the reader should not have to guess why an observation supports the claim.

> **Conclusion:** The failing UI test was caused by a version-hashed CSS selector, not a product regression.
> **Evidence → link:**
> - The selector resolves to a class that no longer exists after the UI-library upgrade (grep of the test helpers) → the selector now matches nothing.
> - The failure rate jumped from ~26% to ~99% on the exact build that shipped the upgrade (build history) → timing pins the cause to that change.
> - Reverting only the selector returned the test to green (test run) → confirms the selector, not product code, was the fault.

Weak vs. strong evidence — prefer direct observation over inference:
- **Strong:** command output, a test run you executed, file contents you read, a metric you pulled.
- **Weak:** timestamps used as a proxy, "it usually works this way", a single run, another tool's unverified claim (e.g. a static analyzer or AI assistant). Weak evidence is still usable — but say it's weak and don't let it carry a conclusion alone.

### 2. No evidence? Label it a guess — out loud

If a claim has no supporting evidence, or only weak/circumstantial evidence, **mark it explicitly** as an informed guess, estimate, or assumption. Never present a guess in the same voice as a verified fact. Use plain markers:

- *"Informed guess (unverified):* …"*
- *"Estimate — no direct measurement:* …"*
- *"Assumption I'm carrying:* …, which I have not confirmed."*

Then, when it matters, say what evidence *would* settle it and offer to go get it. A labeled guess is honest and useful; an unlabeled guess dressed as fact is the failure this skill exists to prevent.

### 3. After each conclusion, reconcile

Once a conclusion is formed, **stop and re-check it against the evidence and against your earlier conclusions.** Purge anything out-of-sync:

- Does every piece of cited evidence actually support the conclusion, or did one get stale / contradict it?
- Does this conclusion contradict something you asserted earlier in the session? If so, one of them is wrong — resolve it, don't ship both.
- Did new evidence arrive that undercuts the chain? Retract or revise.
- Are you over-reaching — is the conclusion broader than the evidence licenses? Narrow it.

State the outcome of the reconciliation when it changes anything ("Earlier I said X; the run just now contradicts it — revising to Y").

---

## Quick procedure

1. **Claim** — write the conclusion in one sentence.
2. **Evidence** — list each supporting item; mark each strong/weak and cite its source (command, file, run, metric).
3. **Link** — for each item, one clause on *why* it supports the claim.
4. **Gaps** — anything unsupported → label as guess/estimate/assumption per Rule 2.
5. **Reconcile** — re-read 1–4 and your prior conclusions; remove/revise contradictions and over-reach per Rule 3.
6. **Report** — give the user the claim + evidence chain; keep guesses visibly separated from verified facts.

---

## Anti-patterns (what this skill forbids)

- **Bare verdict.** "It works" / "not my change" / "it's deployed" with no run, no output, no metric behind it. Every such verdict needs evidence or a guess-label.
- **Single-run confidence.** Concluding from one post-change run without a baseline — environmental noise routinely fakes both pass and fail. (An A/B baseline *is* the evidence; a lone run is weak.)
- **Timestamp-as-proof.** Inferring "the fix reached the environment" from build/deploy timestamps; the empirical run is the source of truth, timestamps are a proxy.
- **Trusting another tool's claim unchecked.** Static analyzers and AI assistants can be false positives — verify against the actual code before repeating their conclusion as yours.
- **Laundering a guess into a fact** by dropping the hedge as the sentence travels down a report.
- **Leaving a contradiction on the page** because both halves were written at different times.

## Related skills

- [`evidence-hardening-loop`](../evidence-hardening-loop/SKILL.md) — the iterative follow-up: after this pass labels a weak point, that loop drives each load-bearing one toward a confirmed point before you mark anything done.
