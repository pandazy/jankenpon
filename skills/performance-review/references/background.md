# Background: how and why performance-review was built

This note records where the skill came from, which ideas shaped it, and the choices made along the way. You don't need it to run the skill. Read it before you change the skill, so a change doesn't undo a decision that was made on purpose.

Built on 2026-11-21 in one working session. This note was written on 2026-11-23 from that session's record: the questions asked, the answers given, the review passes, and the skill text. Where the record doesn't say *why* something was chosen, the note says the reason is reconstructed.

---

## 1. How it started

It began with a research question: "Is there a thesis or research paper on how to evaluate a code piece's performance while taking software-engineering practice, such as coupling and cohesion optimization, into account?"

The answer surveyed several research areas and found a gap. Most work either **optimizes design metrics with performance as a constraint**, or **measures how refactoring changes performance**. There is little on judging one piece of code for both at once.

The requester then asked for a skill that:

- evaluates the performance of specified code, then finds and ranks its flaws;
- **above all, explains the symptoms and the culprits;**
- expects performance flaws to **coexist with coupling and cohesion refactoring** as standard engineering practice, so neither goal silently overrides the other;
- is as generic as possible, tied to no business, intellectual property, ideology or group of people;
- is checked for inconsistency, contradiction and redundancy, with the check repeated until none is left.

---

## 2. Sources and what each one contributed

Every source below was **cited from memory** in the building session, and none was opened or re-read. Treat authors, titles and years as leads to check before citing them formally. The "how it shows in the skill" column is **reconstructed**: it compares the skill's text with each idea, because the session didn't record which idea led to which rule.

| Area and sources (recalled) | Idea | How it shows in the skill |
|---|---|---|
| **Refactoring vs. run time.** Traini, Di Pompeo, Tucci, Cortellessa et al., "How Software Refactoring Impacts Execution Time" (ACM TOSEM, about 2022); Demeyer, "Refactor Conditionals into Polymorphism: What's the Performance Cost of Introducing Virtual Calls?" (ICSM 2005) | Changes made for maintainability often have a measurable run-time cost. | Flaw type **P10, abstraction overhead**, and the **reverse check** in "Design tension": a refactor done for modularity is reviewed for new costs on hot paths, and is kept when the cost is off the hot path. |
| **Multi-objective design optimization.** Mancoridis et al. (the Bunch tool and its MQ metric, late 1990s); Praditwong, Harman & Yao (IEEE TSE 2011); Harman & Tratt, Pareto-optimal refactoring (GECCO 2007); Ouni, Kessentini et al. (NSGA-II, about 2016); Mkaouer et al. (NSGA-III, about 2015); Cortellessa, Di Pompeo, Arcelli et al. | Modularity and performance are separate goals that trade off. Good designs sit on a frontier where one goal can't improve without the other getting worse. | Not adopted as an algorithm. The skill keeps the idea that **both goals are real and the trade-off must be visible**. Each finding gets a **boundary relation**, and any fix that costs modularity must say which coupling it adds and what it costs to maintain. |
| **Performance antipatterns.** Smith & Williams, "Software Performance Antipatterns" (WOSP 2000) and *Performance Solutions* (2002); Cortellessa, Trubiani et al. | Recurring design shapes cause recurring performance problems, so naming them makes them findable. | The **flaw-type taxonomy P1–P10**, written in the skill's own words as public engineering vocabulary (hard rule 5), with no catalogue copied. |
| **Quality-attribute trade-off frameworks.** ISO/IEC 25010 (performance efficiency and maintainability as separate characteristics); ATAM (Kazman, Klein, Clements, about 2000); Bass, Clements & Kazman, *Software Architecture in Practice* | Performance and modifiability are separate attributes. Analysis should state the trade-off, not hide it. | "Treats both as standard engineering goals and makes every trade-off explicit"; when no boundary-keeping fix is good enough, **state the trade-off and let the reader choose**. |
| **Coupling and cohesion measurement.** Chidamber & Kemerer (1994: CBO, LCOM); Briand, Daly & Wüst (coupling, TSE 1999; cohesion, EMSE 1998) | Coupling and cohesion can be named and compared. | The skill borrows its coupling vocabulary from the [**coupling-cohesion-review**](https://github.com/pandazy/jankenpon/blob/main/skills/coupling-cohesion-review/SKILL.md) companion skill instead of defining its own, so the two skills speak the same language. |
| **The limit on overall speed-up** (the classic bound usually attributed to Amdahl) | Speeding up a part that takes a fraction `f` of the time by `s` saves at most `f × (1 − 1/s)`. | Used without the name: within one severity, findings rank by **share of the total cost**. This argument also lies behind "hot path first" and the low cap off the hot path. |
| **Companion skills:** [logic-gap-review](https://github.com/pandazy/jankenpon/blob/main/skills/logic-gap-review/SKILL.md) and [coupling-cohesion-review](https://github.com/pandazy/jankenpon/blob/main/skills/coupling-cohesion-review/SKILL.md) | Read in full while the skill was drafted. | The evidence grades and the evidence-to-status table (weak means medium at most; a guess can only be suspected), the read-only and local-only rules, the answer-first report, the `suspected` section, the JSON field table, and the over-engineering check (here, the **over-optimization** check). |
| **Practitioner experience** (no source) | The N+1 query pattern; benchmarking practice (warm up, repeat, report median and spread, test two input sizes, count operations as well as time); unbounded caches and stampedes. | Steps 3 and 5 and the P3, P5 and P9 rows. No paper is claimed for these. |

---

## 3. Trade-off decisions

The decisions below are visible in the skill text. Their reasons come from the session record where it has them, and are otherwise reconstructed (marked *reconstructed*).

| Decision | Chosen | Given up | Why |
|---|---|---|---|
| Scope of the output | A ranked report; read-only | Optimizing the code | It matches the companion review skills. Fixes are proposed with cost, risk and expected gain, and applying them is separate work. |
| Symptom and culprit | Required for every finding, with a chain when they are far apart | Shorter findings | This was the requester's main ask. A symptom without a culprit can't be fixed, and a culprit without a symptom can't be ranked. |
| Who a culprit is | Code only: unit, line, mechanism. Never people or groups; version history shows *when*, not *who* | Blame from history | The requester asked to tie the skill to no group of people. Naming code keeps the review about the cause, not the author. |
| Severity model | Impact × frequency × growth; growth counts only when the input can really be large; adjust by one level at most | A single score or a measured-only rule | It works by reading when nothing can run, and it stops a theoretical O(n²) on a list capped at 10 from being rated critical. |
| Hot path first | Off the hot path, severity is capped at low | Treating all code alike | *Reconstructed:* the speed-up bound in section 2 means work off the hot path can't save much overall. |
| Ranking inside a severity | By share of the total cost | By count or by type | Same bound: a 10× gain on 5% of the time saves at most 4.5%. |
| Evidence vs. status | Measured or strong for critical and high; weak means medium at most; a guess can only be suspected | Faster ratings | It keeps a pattern match from becoming a critical finding. The rules are the same as logic-gap-review's, so both skills can feed the same auditor. |
| Measurement | Local only, at least two input sizes, warm-up, median and spread, counts as well as times | Load tests against shared systems | Safety. Counts were preferred because, as the skill says, they are stable across machines and times are not. |
| Boundary relation | Three relations: independent, boundary-caused, fix crosses a boundary | Ignoring structure | This is the requester's coexistence requirement. Every finding states how it relates to module boundaries. |
| Fix order | Fix inside the owner → widen the contract (a batch method) → cache behind the owner → move work to the data → remove a layer that does no work | Fastest fix first | It removes most of the cost while keeping the boundary. A fix that costs modularity is allowed only for a measured critical or high finding, and must name the coupling it adds. |
| Reverse check | Refactors done for modularity are reviewed for new hot-path costs | Reviewing performance code only | Taken from the refactoring-cost research (section 2). Off the hot path, the refactor is kept. |
| Over-optimization check | Existing over-optimized code is marked; the reviewer's own fixes are revised, not marked; simplicity beats a small speed-up | Only adding speed | Speed is a means, not a goal. The rule about the reviewer's own fixes came from a review pass that found the skill flagging its own proposals. |
| Scripts | None. Use the platform's standard profiler | A bundled tool like the companion skills have | *Reconstructed:* profilers depend on the language and runtime, and a reading-based method works in any repo. |
| Wording | Generic: no product, vendor, business, ideology or group names | Concrete local examples | The requester asked for it. Examples use neutral roles (the list loader, the export job). |

---

## 4. The reasoning behind the method

1. **A performance flaw is a symptom joined to a culprit.** What an observer sees (slow page, growing memory) must be traced to exact code with a mechanism and a trigger, or it can't be fixed or ranked.
2. **Cost is impact × frequency × growth, on hot paths.** One cheap line run per item on a growing list can outweigh an expensive line run once. Bounded input turns growth into a constant.
3. **Rank by share.** The speed-up bound decides what's worth fixing first. Fixing small shares wastes effort however clever the fix.
4. **Modularity and performance are both goals.** Most fixes can keep boundaries: batch methods, owned caches, moving work to the data. A fix that breaks a boundary must earn it with a measured, serious finding and name its cost. The reverse holds too: a refactor for modularity must not quietly add hot-path cost.
5. **Every claim carries its evidence.** Measured, strong, weak and guess decide what can be reported as a flaw, so a guess is visible as a *suspected* item and not presented as a fact.
6. **Simplicity wins ties.** The over-optimization check keeps the review from trading readable code for speed nobody needs.

---

## 5. How it was checked when built

The requester asked for a loop until no inconsistency, contradiction or redundancy remained. The record shows four passes:

1. **Self-review: 5 issues.** The main ones were a rule about rarely run code that contradicted the severity table, and an anti-patterns section that only repeated the hard rules. The section was removed.
2. **Independent review: 13 issues.** Examples: three different ranking rules, a field name used nowhere else, a risk asked for but missing from the report, no fallback when code can't run locally, and two severity rules that contradicted each other.
3. **Re-review: 3 issues introduced by the fixes.** The `guess` grade was missing from the JSON format, the table and JSON ids didn't match, and the skill flagged its own proposed fixes as over-optimized.
4. **Final pass: 0 issues.**

The package build passed after the final pass.

---

## 6. How it is used, and what that use showed

The squad workflow, today [**github-dev-squad**](https://github.com/pandazy/jankenpon/blob/main/skills/github-dev-squad/SKILL.md) (and its specific version), uses this skill. On the same day it was built, the squad's auditor got three performance duties:

- run this skill on each task's code;
- rate the performance cost of every coupling and cohesion suggestion, rejecting any suggestion that would cause a critical performance issue but keeping it in the record with the reason;
- report critical issues for approval.

A day later the escalation was narrowed. Only issues whose effect or fix reaches beyond the change go to the human for approval. Issues contained in the change are fixed without being reported.

In the first squad runs after that (2026-11-22 and 2026-11-23, on a configuration hot-reload change in a background service), the auditor checked several rounds of structure-review suggestions:

- It found no critical performance cost, and no suggestion was rejected.
- It raised one item as a *guess*: a slow home folder could slow a per-message file read. The design's earlier timing on real data answered it.
- One performance check was lost when a long background job hit the job time limit. It was re-run, and that was an operational lesson, not a flaw in the skill.

Ideas for later, none of them decided:

- a small optional script that counts round trips, such as queries or calls per entry point, the way the companion skills ship signal collectors;
- a worked example with measured numbers at two input sizes;
- re-reading the recalled sources and upgrading their grades in this note.
