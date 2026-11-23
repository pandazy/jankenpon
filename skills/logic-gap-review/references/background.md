# Background: how and why logic-gap-review was built

This note records where the skill came from, which sources shaped it, and the choices made along the way. You don't need it to run the skill. Read it before you change the skill, so a change doesn't undo a decision that was made on purpose.

Built on 2026-11-18 in one working session, then tried on two real reviews.

---

## 1. How it started

The first question was: "Is there a universal principle for checking that code's logic stays within its proper boundary?" The first answer used contracts (preconditions, postconditions, invariants): state the contract, then test its edges. The requester then narrowed the question. They didn't want spec-first verification. They wanted to **start from the logic the code already contains, find the branches it never wrote, and push inputs into them until a bug shows up**.

That shift set the shape of the skill:

- **Input:** the code itself (its conditions, operations and data flow). A spec is not required.
- **Output:** a list of loopholes. The requester said the list feeds other work (fixes, false-negative triage, escalation), and that this work is **not** part of the skill.

---

## 2. Sources and what each one contributed

Evidence grades follow the skill's own scale. **Primary** means the source itself was read during the session. **Secondary** means it was read through a summary. **Recalled** means it was cited from memory and not re-read. Treat recalled authors and years as leads to check.

| Source | Grade | What it gave the skill |
|---|---|---|
| **Rice's theorem**: no algorithm decides any non-trivial behavioural property for every program | Recalled (standard result) | No tool can verify logic for all programs, so the skill is a **method with graded evidence**, not a verifier. It is also why the skill keeps **Suspected** and **Limits** sections: some gaps can't be closed and have to be named. |
| **Hoare logic** `{P} C {Q}` and **Design by Contract** | Recalled | The first framing: correctness is relative to a stated contract. The requester moved away from spec-first work, so this survives only as the **oracle problem**. Code alone can't tell a correct result from a consistently wrong one, so every loophole must name a bad outcome (categories C1–C10). |
| **McCabe, "A Complexity Measure"**, IEEE Transactions on Software Engineering, December 1976 | Secondary (via Wikipedia, and the bibliography of the next source) | The requester pointed out that McCabe's work also proposes a way to explore paths. It gave the skill **cyclomatic complexity** `v(G)`: the number of independent paths, which is the decision count plus one. |
| **Watson & McCabe, *Structured Testing: A Testing Methodology Using the Cyclomatic Complexity Metric*, NIST Special Publication 500-235**, September 1996 | **Primary** (text extracted and read) | The most direct influence. The section numbers below are this report's. |
| **Domain testing** (White & Cohen, 1980) | Recalled | Each path has an input domain bounded by its conditions. Test ON points (on the border) and OFF points (just across it). This became Step 3.2, **boundary values**. |
| **Boundary-value analysis and equivalence partitioning** (popularized by Myers, *The Art of Software Testing*, 1979) | Recalled | The practical form of domain testing. Together with domain testing it gave the **gaps and overlaps** check (Step 3.1). |
| **MC/DC** (Chilenski & Miller, 1994) | Recalled | Flip each part of a compound condition on its own (Step 3.3). Path counting treats `a && b \|\| c` as one decision, so this covers what it misses. |
| **Data-flow testing** (Rapps & Weyuker, 1985) | Recalled | Cover each definition-to-use path. This became Step 3.5 and the script's `maybe-unassigned` check. It caught the worked example's bug independently of the path methods. |
| **Mutation testing** (DeMillo, Lipton & Sayward, 1978); **symbolic execution** (King, 1976); **fuzzing** (Miller et al., 1990); **property-based testing** (QuickCheck, Claessen & Hughes, 2000); **metamorphic testing** (Chen et al., 1998) | Recalled | Considered and **left out** of the procedure (see section 4). They remain good next steps for whoever acts on the loophole list. |
| [**evidence-driven-reasoning**](https://github.com/pandazy/jankenpon/blob/main/skills/evidence-driven-reasoning/SKILL.md) and [**coupling-cohesion-review**](https://github.com/pandazy/jankenpon/blob/main/skills/coupling-cohesion-review/SKILL.md) (companion skills) | Read | The evidence grades, the "suspected, not red" rule, the answer-first report, and the shape of the two stdlib scripts with their tests and coverage runner. |
| **Practitioner experience** | Guess (no source) | The hidden-branch checklist (division, lookup, parse, NaN, timeout…), JavaScript coercion (the requester's own `'undefined'` example) and **sibling comparison**. No paper was used for these, and the skill doesn't claim one. |

### What the primary source changed

Reading the primary source confirmed four claims and added three ideas:

- **§5.1:** the criterion is to "test a basis set of paths". The source also says it "is not a procedure to identify test cases or generate test data inputs". That is why path coverage alone isn't enough, and why the skill adds boundary values, gaps and data flow.
- **§5.2:** structured testing "subsumes branch and statement coverage", and the minimum number of tests is exactly `v(G)`. This corrected an earlier mistake in the session (see section 3).
- **§5.4:** in the "count" example, tests with full branch coverage miss the bug, and any basis set finds it. This is the case for basis paths over plain branch coverage.
- **§5.7:** for critical software, "give special attention to testing the boundary values of all data, particularly decision predicates, along that path". The original author recommends combining basis paths with boundary values, which is the core of Step 3.
- **§2.5:** a complexity limit of 10, with up to 15 under extra safeguards. This became Step 1's "above 10 is a common warning line".
- **§9.1:** *actual* vs *realizable* complexity. When no input can reach a path, it signals a control dependency, and deciding reachability in general is undecidable. This became Step 3.4's "a path no input can take is a finding", and part of why reachability needs human judgement (Step 4).
- **§6.2–6.5:** the baseline method (start from a typical path, flip one decision at a time), and filling gaps after functional tests. This shaped how Step 3.4 builds basis paths.

---

## 3. A correction that shaped the method

The worked example (a function with `if size < 5 … elif size > 5 …` and no `else`) was first used to argue that "coverage misses `size == 5`". Checking it more carefully showed that claim held for **statement** coverage only. Branch coverage, and basis paths with it, must take the implicit "neither" edge, so they do find the bug. NIST §5.2 confirmed this.

The correction split "missing branches" into three kinds. That split is the reason for several parts of the skill:

| Kind | Example | Seen by branch coverage or basis paths? |
|---|---|---|
| Untested branch that was written | an `except` block no test reaches | Yes |
| Implicit fall-through | `if/elif` with no `else` | Yes |
| **Missing condition** | NaN never considered; a rule never coded | **No.** No structural method sees code that doesn't exist |

The third row is why the skill has the hidden-branch checklist, sibling comparison and the error-path review, and why its Limits always name what reading alone can't close.

---

## 4. Trade-off decisions

| Decision | Chosen | Given up | Why |
|---|---|---|---|
| Scope of the output | A graded list of loopholes; read-only | Fixing, triage, escalation | The requester defined the list as input to other work. Keeping fixes out keeps the review honest: it reports, it doesn't change code. |
| Reachability | Required before severity; blocked cases go to **Dismissed** with the blocking check | A shorter list | Without reachability, every unchecked `if` is a "bug" and the list is noise. The Dismissed list is kept because it shows protection that rests on one check, which helps false-negative triage. |
| Evidence vs status | Critical and high need strong or reproduced evidence; weak means medium at most; a guess can only be suspected (capped at medium) | Faster ratings | The rule stops a pattern match from being escalated as a critical bug. The checker script enforces it. |
| Reproduction | Local only, with harmless markers for injection | Confirming against real systems | Safety. The cost: in both trials some items stayed *strong* and couldn't be *reproduced*. That is acceptable, because the gap is stated. |
| Techniques in the procedure | Gaps and overlaps, boundary values, MC/DC, basis paths, data flow, hidden branches, siblings, error paths: all done by reading | Mutation testing, fuzzing, symbolic execution, property-based testing | Those need tooling, harnesses or long runs. The skill stays a reading method that works in any repo, and heavy tools belong to whoever acts on the list. |
| Consequence categories | Ten (C1–C10). The requester picked C1–C3; C4–C10 were proposed and the requester kept them all | A shorter list | Every loophole must name an outcome. The categories act as the oracle that code-only exploration lacks. |
| Severity | Four levels, adjusted by at most one level | Finer scales | The requester confirmed four levels fit their triage. Capping the adjustment keeps ratings comparable between reviews. |
| Script language support | Python exact (ast); JS/TS, Java, Kotlin and Go approximate (patterns), marked `approx` | A parser per language | Standard library only, no installs, runs anywhere. The approximation is labelled, and its rows count as weak evidence. |
| What the scripts detect | Seven node families | State-and-order, string/number `+`, most concurrency | These need semantic knowledge the scripts don't have. The skill says they must be found by reading. |
| Rank score | `(v(G) − 1) + 3 × sinks + 2 × sources + 0.5 × min(commits, 10) + fix commits` | A tuned or learned score | It is transparent and easy to argue with. It only orders the reading list and never sets severity. |
| Sinks | Flagged only when the argument looks built or variable | Flagging every call | Fewer false alarms. The cost, seen in a trial: a process spawned through a variable function wasn't flagged, and was found by reading. |
| Report format | JSON first; the Markdown tables are printed from the JSON | Writing the tables by hand | The tables and the machine-readable list can't drift apart. |
| Trigger inputs | Must be concrete values; the checker rejects descriptions | Easier writing | A trigger is what makes a loophole reproducible downstream. In both trials the checker rejected vague triggers in the reviewer's own list. |
| Wording | No product, business, vendor, credential-format, institution or person names in `SKILL.md` or the scripts | Credit inside the skill itself | The requester asked for neutral wording. Credit and history live in this note. |
| Description length | Short `description` front matter | A fuller description | The skill packaging format limits the description to 1,024 characters. |

---

## 5. The reasoning behind the method

The skill is one idea applied in layers:

1. **Every condition splits the input space into regions.** Bugs gather on the edges of regions, in the gaps between them, and in branches hidden inside operations. Steps 2–3 enumerate all three on purpose.
2. **No single technique sees everything, so they are layered.** Basis paths choose *which paths*. Boundary values, domain testing and MC/DC choose *which values* on each path. Data flow checks *how values travel*. The hidden-branch checklist and sibling comparison look for *conditions that were never written*. Each layer covers a blind spot of the one before. The worked example shows it: four techniques each catch the `size == 5` bug, and only the checklist catches the NaN case.
3. **Reaching a branch is not a bug.** A missing case becomes a loophole only when a real input can reach it (Step 4) and it leads to a named bad outcome (Step 5). This answers the oracle problem as far as reading can.
4. **Every claim carries its evidence.** The evidence grades, the status rules and the checker keep a guess from being reported as a fact, and turn "I couldn't confirm it" into a visible *Suspected* item instead of a silent omission.
5. **The limits are stated, not hidden.** Path explosion, the oracle problem and missing conditions can't be closed by reading code alone. The report's Limits section exists so readers know what wasn't checked.

---

## 6. What the first two trials taught

- **Review of a process-runner module (about 850 lines of TypeScript):** 8 loopholes, 2 suspected, 4 dismissed. The worst was a policy check that matched only the first word of a command line.
  - The rank script found 0 sinks, because processes were spawned through a variable function. That confirmed the "sinks only when the argument looks variable" blind spot.
  - The checker rejected 2 vague triggers in the reviewer's own list.
- **Review of a small UI change (5 files):** 0 loopholes, 3 suspected, 4 dismissed. Every open question depended on a backend the reviewer couldn't read.
  - This was the method working as intended: the skill reported "suspected, here is what would settle it" instead of guessing.

Things to consider next, none of them decided:

- detecting sinks called through a variable function;
- an optional mutation-testing hand-off for downstream fix work;
- a `meta.json`-driven HTML report renderer kept inside the skill.
