# Background: how and why coupling-cohesion-review was built

This note records where the skill came from, which ideas shaped it, and the choices made along the way. You don't need it to run the skill. Read it before you change the skill, so a change doesn't undo a decision that was made on purpose.

Built on 2026-11-09 in one working session. This note was written on 2026-11-23 from that session's record and from the two sessions that used it afterwards. Where the record doesn't say *why* something was chosen, the note says the reason is reconstructed.

---

## 1. How it started

Two weeks earlier, during routine coding work, the requester set a priority: **prioritize coupling and cohesion of functionality over syntactic beauty.** The skill turns that priority into a repeatable review.

The request asked for a skill that would:

- go through a codebase and list its couplings and cohesions, each sorted into its proper classic type and scored;
- color each score: **green** near the best end, **yellow** around the middle, **red** near or at the worst end;
- give practical fixes for red items;
- check green items for **over-engineering**, preferring KISS and Occam's Razor over extreme decoupling unless the principles don't conflict, and give cheaper, practical advice when they do;
- be generic, business-agnostic and free of IP problems;
- write its report by two companion skills: [**evidence-driven-reasoning**](https://github.com/pandazy/jankenpon/blob/main/skills/evidence-driven-reasoning/SKILL.md) and [**crystal-clear**](https://github.com/pandazy/jankenpon/blob/main/skills/crystal-clear/SKILL.md).

---

## 2. Sources and what each one contributed

Grades: **Read** means the source was opened during the building session. **Given** means the requester supplied it but it wasn't opened. **Not cited** means the idea matches classic literature that the session didn't name. Those attributions were added in this note, from memory, so check them before citing formally.

| Source | Grade | What it gave the skill |
|---|---|---|
| **The classic coupling and cohesion types** from structured design: coupling ordered best to worst as none/message, data, stamp, control, external, common, content; cohesion ordered worst to best as coincidental, logical, temporal, procedural, communicational, sequential, functional. Usually traced to Stevens, Myers & Constantine (1974), Myers (1978) and Yourdon & Constantine (1979). | Given as a public tutorial page summarizing the types; not opened. Classic origins: not cited. | The **two type scales** and their order. Hard rule 4 requires every definition in the skill's own words, with nothing pasted from articles, books or courses, so the vocabulary is used and no text is copied. |
| **evidence-driven-reasoning** (companion skill) | Read | The evidence grades (reproduced, strong, weak, guess), the rule that a red finding must rest on code that was read, and the "suspected, with the check that would settle it" handling in Limits. |
| **crystal-clear** (companion skill) | Read | The report style: answer first, short sentences, one term per idea, each term defined on first use, and no headings that name the writing method. `check_report.py` enforces the last two. |
| [**coding-principles**](https://github.com/pandazy/jankenpon/blob/main/skills/coding-principles/SKILL.md) (companion skill) | Read | KISS, Occam's Razor and fitting into existing code. These drive the over-engineering check and the "cheapest fix that reaches yellow" rule. |
| **Change coupling from version history.** Files that change together with no import between them (logical coupling, as in Gall et al., 1998); change hotspots. | Not cited | The **change coupling** form and the `churn` and `cochange_without_import` signals. |
| **Acyclic dependencies.** Dependency cycles between units or layers make them hard to change on their own (Martin's package principles). | Not cited | The **cycle** forms, scored by kind (run-time, type-only, between folders), and the `--layers` check for upward imports. |
| **Code smells such as Speculative Generality and Middle Man** (Fowler, *Refactoring*) | Not cited | The **over-engineering signs**: single-use abstraction, pass-through layers, speculative generality, unused flexibility, mapping chains, confetti modules, and a message bus inside one process. |
| **The first trial review** (section 6) | Observed | Five rules the first draft lacked: encapsulated module state vs. global state; cycles between folders or layers; type-only cycles; an unused-code section; and the blind spots of text-based import scanning. |

---

## 3. Trade-off decisions

The decisions below are visible in the skill text. Their reasons come from the session record where it has them, and are otherwise reconstructed (marked *reconstructed*).

| Decision | Chosen | Given up | Why |
|---|---|---|---|
| Scope of the output | A report; read-only | Refactoring during review | Reporting keeps the review neutral, and fixes become separate, reviewable work. The second trial did exactly that: its findings became a separate cleanup plan. |
| Score scale | Every type has a fixed score from 0 to 10; green 7–10, yellow 4–6, red 0–3 | Free-form judgement | It turns the requester's three colors into a rule two reviewers would apply the same way. *Reconstructed:* a number allows a small, bounded adjustment, and a color alone doesn't. |
| Adjustments | ±1 at most, with a reason: −1 when the problem is wide, +1 when it is contained; an adjustment never flips red and green | Context-heavy rescoring | It keeps the type as the main signal. If an adjustment seems to need more, the type is wrong and gets re-classified. |
| One type per finding | The worst type that clearly applies, with the other mentioned | Multiple labels | It keeps the scorecard countable, and one design problem stays one finding. |
| Shared state | Encapsulated module state (one writer, used through its functions, shared on purpose) scores 8; common coupling (many writers) scores 2 | Treating all module-level state as global | The first trial showed the difference. A deliberate single-owner cache isn't the same risk as state that many units write. |
| Cycles | Run-time cycles score 3 (red), type-only cycles 4 (yellow), and cycles across package or service boundaries 2 | One cycle rule | Cycles that exist only in types cost less, and cycles across deploy boundaries cost more. The first trial needed the distinction. |
| Red fixes | The **cheapest** fix that reaches at least yellow, with cost and risk; moving or deleting code preferred over adding layers | The theoretically best design | This is the requester's practicality requirement. The second trial's cleanup followed it: move or delete only, no new interfaces, layers or folders. |
| Over-engineering | Green items are checked; a 🟢⚠ mark when the structure costs more now than it buys now; the skill's own fixes are checked too | Rewarding maximum decoupling | KISS and Occam's Razor win when they conflict with a purer score, as the requester asked. |
| Evidence | A red finding must rest on code that was read; a script row, a name or a count alone can't make something red | Script verdicts | Signals mislead. In the first trial, two false positives came from imports inside comments and from `new URL(...)` loaders. |
| Scripts | Two optional scripts, standard library only, read-only, with tests and line coverage | No tooling, or a third-party analyzer | The scripts written during the first trial turned out to be reusable. The two generic ones were kept and the two project-specific ones dropped. Standard library only means they run anywhere without installs. |
| Signal scanner scope | Import graphs for JS/TS, Python, Java, Kotlin and Go by pattern matching, with blind spots listed | A compiler-grade parser per language | Pattern matching works without builds or installs. Its limits (dynamic loading, same-package imports, public API that looks unused) are stated, and every row counts as weak evidence. |
| Report checker | Fails on broken structure (tags, ids, table cells), missing sections, method-naming labels and a missing opening answer | Trusting the writer | It enforces the crystal-clear and structure rules mechanically. It replaced a first-trial checker that needed an extra JavaScript install. |
| Tests | Deliberate breaks to prove the tests can fail; line coverage measured with a standard-library runner | Coverage numbers alone | Every deliberate break was caught. Measuring coverage also found unreachable code, which was removed, and untested logic, which got 7 new tests. |
| Wording | Business-agnostic and context-agnostic; units described by role; no copied definitions | Domain examples | The requester asked for it twice. Hard rules 2–4 make it part of the skill, not just its style. |

---

## 4. The reasoning behind the method

1. **Name the shape, then judge it.** Each notable coupling or cohesion gets one classic type, and the type sets a fixed score. Judgement is limited to one small, explained adjustment.
2. **Signals point, reading decides.** The scanner finds where to look: imports, cycles, shared state, flag parameters, files that change together. Only code that has been read can make a finding red.
3. **Fix cheaply, not perfectly.** A red item needs the smallest fix that reaches yellow, preferably by moving or deleting code. Adding structure is the last resort.
4. **The best end has a price.** Very low coupling and very high cohesion can cost more files, more layers and more concepts than they save. The over-engineering check weighs what a structure buys now against what it costs now, and simplicity wins ties.
5. **The report is for a reader.** Answer first, plain words and a scorecard, with every finding tied to `file:line` and an evidence grade. Limits say what wasn't read.

---

## 5. How it was checked when built

- **First trial and its five gaps:** the first trial (section 6) exposed five gaps in the draft, and the skill was revised to close them.
- **Scripts generalized:** the trial's scripts were reworked into a language-neutral scanner with per-language import rules, and into a standard-library report checker.
- **Scanner checked on real and sample code:**
  - it reproduced the first trial's findings without the two false positives;
  - it found a real three-module cycle in Python's built-in `email` package;
  - it handled small Java, Kotlin and Go sample projects.
- **Unit tests:** 39 tests were written, then 46 once coverage was measured. Six deliberate breaks each made at least one test fail.
- **Coverage:** line coverage went from 95.9% to 99.7%. The only lines not covered are the two `sys.exit(main())` entry points.
- **Usage docs:** `SKILL.md` was updated with every option, how to read the output, and how to run the tests.

---

## 6. How it was used, and what that use showed

- **First trial (2026-11-09):** a TypeScript web front end of about 460 files and 92,000 lines.
  - It found three red items: a missing shared service, so several UI files built the same API calls themselves; filter rules copied in two places, which the version history showed changing together; and a service importing from the UI layer.
  - It also found six yellow items, two over-engineered items, and about 2,000 lines of unused code.
  - Running it exposed the five gaps listed in section 2.
- **Second trial (2026-11-17):** a TypeScript background service of 40 files.
  - No red items, with ten yellow ones in all. Examples: copied default values, a contract between processes written out in three places, two folders importing each other, and one file that nearly every feature edited.
  - It found two over-engineered items: an interface never used as a type, and a function called only by tests.
  - The findings became a refactoring plan whose ground rule came straight from the skill: behaviour unchanged, move or delete code only, one commit per item. It landed as 14 small commits.
- **Ongoing:** the [**github-dev-squad**](https://github.com/pandazy/jankenpon/blob/main/skills/github-dev-squad/SKILL.md) workflow (and its specific version) runs this review after each group of tasks. The [**performance-review**](https://github.com/pandazy/jankenpon/blob/main/skills/performance-review/SKILL.md) skill then checks each suggestion for its performance cost, so a structural fix doesn't quietly slow a hot path. Performance-review also borrows this skill's coupling vocabulary.

Ideas for later, none of them decided:

- a worked example in `SKILL.md`;
- an optional HTML report template;
- re-checking the classic-literature attributions in section 2 against the original sources.
