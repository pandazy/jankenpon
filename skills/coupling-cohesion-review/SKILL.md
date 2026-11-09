---
name: coupling-cohesion-review
description: "Review any codebase for coupling and cohesion. Map the units (packages, folders, files, classes, functions), classify each notable coupling and cohesion by its classic type, score it green / yellow / red, give practical fixes for red items, and check green items for over-engineering — preferring KISS and Occam's Razor over chasing the theoretical best. Works for any language, framework, domain or team. Read-only: it reports, it does not refactor. Ships two optional standard-library Python scripts: one collects signals (import graph, cycles, folder direction, unused files, shared state, flag parameters, change history), one checks the finished report. Every finding cites code and its evidence grade, and the report opens with the answer in plain words. Use when asked to assess design quality, modularity, coupling, cohesion, architecture health, dependency tangles, refactoring targets, or 'is this over-engineered?'."
version: 1.0.0
tags: [architecture, design, coupling, cohesion, modularity, refactoring, code-review, dependencies, kiss, occams-razor, over-engineering]
---

# Coupling & Cohesion Review

Find where the code is tangled (high coupling) or scattered (low cohesion). Say how bad each spot is and what to do about it, without pushing the code into needless abstraction.

- **Coupling** — how much one unit depends on another. Lower is better.
- **Cohesion** — how well the parts inside one unit belong together. Higher is better.

A **unit** is whatever boundary the codebase uses: a package, folder, module, file, class or function. Pick the level that fits the question (Step 1).

## Hard rules

1. **Read-only.** Do not edit the reviewed code. The output is a report.
2. **Context-agnostic.** Assume nothing about the language, framework, build tool, hosting, team or company. Learn the conventions from the repo itself (its docs, config and layout). If the repo states its own rules, judge against them, and cite them.
3. **Business-agnostic.** Judge structure, not domain. In the report, describe units by their role ("the task list", "the cache", "the save service"), not by what the business does. Do not reward or penalize a design because of the product it serves.
4. **Own words, no copied material.** The type names below are standard, public vocabulary from the structured-design literature. Describe them in your own words. Do not paste definitions or examples from articles, books, courses or vendor docs. Quote the reviewed code only as far as needed to prove a finding (a `file:line` reference or a short excerpt). Do not put secrets, credentials, personal data or large code blocks from the repo into the report.
5. **Evidence or label.** Every finding cites `file:line` and an evidence grade (see "Evidence"). A **red** finding must rest on code you read, never on a name, a count or a script result alone.
6. **Plain report.** Answer first, short sentences, one term per idea, no method labels (see "Report").

---

## The scales

Each type has a **score from 0 to 10** (10 = best). The score sets the color.

| Color | Score | Meaning |
|---|---|---|
| 🟢 green | 7–10 | At or near the best end. Check for over-engineering (Step 6). |
| 🟡 yellow | 4–6 | Middle. Acceptable; fix it when someone works on that code anyway. |
| 🔴 red | 0–3 | At or near the worst end. Give a fix (Step 5). |

### Coupling types (best → worst)

| Type | Score | What it looks like | Typical signals |
|---|---|---|---|
| **None / message** | 10 | Units talk only through a narrow, published contract (events, a queue, a versioned API) and share nothing else. | Publish/subscribe; versioned endpoints; no shared imports beyond the contract. |
| **Data** | 9 | A caller passes only the plain values the callee needs. | Short parameter lists of simple values; dependencies passed in as parameters. |
| **Stamp** | 7 | A caller passes a whole record, but the callee uses only part of it. | `fn(user)` that reads only `user.id`; wide objects threaded through many layers. |
| **Control** | 5 | A caller passes a flag that decides *what* the callee does. | Boolean / mode / kind parameters that pick a branch. |
| **External** | 4 | Units share a format, protocol, device or outside API that none of them owns, and each one handles it directly. | Many units build calls to the same outside client or parse the same file format themselves. |
| **Common (global)** | 2 | Units read **and write** the same shared mutable state. | Mutable module-level variables or singletons written from many places. |
| **Content** | 0 | One unit reaches into another's internals or changes its private state or code. | Access to private fields from outside; monkey-patching; reflection into internals; relying on another unit's internal ordering. |

More forms to flag. Score each one with the closest classic type:

- **Temporal** — calls must happen in a hidden order (`init()` before `use()` with no guard). Score like control (5). If shared state is the only thing that enforces the order, score like common (2).
- **Cycle, run time** — A imports B and B imports A, directly or through a chain, and the imports are live when the code runs. Score 3. A cycle across package or service boundaries is red (−1).
- **Cycle, type only** — the loop exists only through type imports that the build removes. Score 3, +1 because nothing loops at run time, which gives 4 (yellow).
- **Cycle between folders or layers** — no single file loops, but folder A depends on B and B depends on A. Score 3. Use this score when the minority direction pulls in real logic. When it pulls in only types or small pure helpers, add +1, which gives 4.
- **Change coupling** — files that change together again and again in version history, with no import between them. This usually means a rule is copied in both places. Score 4 (like external), −1 when both files are hotspots. Version-history evidence is needed.

**Shared state is common coupling only when many units write it.** Treat state as **encapsulated module state** (score 8) when all of these are true:

- It sits at module level, but only its own module writes it.
- Every other unit goes through that module's functions.
- The sharing is deliberate (for example, one process-wide client, one shared rate limiter, or a cache with a single owner).

Score it as common (2) only when other units write it directly, or when callers must know about it.

### Cohesion types (worst → best)

| Type | Score | What it looks like | Typical signals |
|---|---|---|---|
| **Coincidental** | 0 | Parts share a unit for no reason. | Grab-bag files (`utils`, `helpers`, `misc`, `common`) of unrelated functions. |
| **Logical** | 2 | Parts do the same *kind* of thing for unrelated purposes; a flag picks one. | One function with a big switch on "kind"; one file of every unrelated validator. |
| **Temporal** | 4 | Parts are grouped because they run at the same time. | `startup()` / `cleanup()` that touches many unrelated subsystems. |
| **Procedural** | 5 | Parts run in a fixed order, or on the same screen or request, but work on different data. | A long routine or a large UI component where each section serves a different concern. |
| **Communicational** | 6 | Parts work on the same data but do different jobs with it. | A class or component whose sections all use one record but produce unrelated outputs. |
| **Sequential** | 8 | One part's output is the next part's input. | A clean pipeline: parse → transform → format. |
| **Functional** | 10 | Every part serves one well-defined job. | A unit you can describe in one sentence with no "and". |

### Score adjustments

Start from the type score, then adjust by at most ±1, and say why:

- **−1** when the problem is wide: many dependents, it crosses a package or service boundary, or it sits on a change hotspot.
- **+1** when it is contained: private to one small file, type-only, test-only, generated code, or a documented, deliberate adapter.

An adjustment never moves red into green or green into red. If it seems it should, re-classify the type instead.

---

## Evidence

Grade every finding with one of these:

- **Reproduced** — the same pattern seen in several separate places or commits, or confirmed by running something.
- **Strong** — you read the code at the cited lines.
- **Weak** — a proxy: a file name, a count, an outline, a script result, another tool's claim.
- **Guess** — no supporting observation. Say so, and say what would confirm it.

Before reporting, re-check every red item and every over-engineering flag. If one rests on weak evidence, open the code and confirm it. If you cannot confirm it, it is not red: list it as *suspected* under "Limits", with the check that would settle it. If a later observation contradicts an earlier finding, change the finding. Never keep both.

(This follows the public [evidence-driven-reasoning](https://github.com/pandazy/jankenpon/blob/main/skills/evidence-driven-reasoning/SKILL.md) skill. The rules above are enough on their own if that skill is not available.)

---

## Procedure

### Step 1 — Scope and map

1. Get the **scope** from the request: the whole repo, one package, one folder, or a diff.
2. Read the repo's own docs (README, contributor or agent guides, architecture notes). They often name the layers, the intended dependency direction, and deliberate exceptions.
3. Pick the **unit level**: packages or folders for a large repo, files or classes for a package, functions for one file.
4. For a large scope, do not read everything. Sample in this order, and record what you sampled:
   - entry points (main functions, request handlers, routes, CLI commands);
   - the units with the most dependents (fan-in) and the most dependencies (fan-out);
   - the files that change most often, if version history exists;
   - every unit in a cycle, and every import that goes against the folder direction;
   - grab-bag names (`utils`, `helpers`, `common`, `misc`, `manager`, `base`).

### Step 2 — Gather signals

**With the script (optional, recommended).** `signals.py` lives in this skill's `scripts/` folder. In the commands below, `SKILL_DIR` means the folder that holds this `SKILL.md`. Replace it with the real path, since the review usually runs from inside the reviewed repo. The script needs Python 3.8+ and the standard library only. It reads code and git history and writes nothing, except the file you pass to `--json`. `-I` runs Python in isolated mode, so files in the reviewed repo cannot change how the script behaves.

```bash
# 1. First pass: everything, 25 rows per section, full results saved as JSON.
python3 -I SKILL_DIR/scripts/signals.py <repo-or-package> --top 25 --json /tmp/signals.json

# 2. Focus on a few sections.
python3 -I SKILL_DIR/scripts/signals.py <path> --only cycles_runtime,folders_both_ways,cochange_without_import

# 3. Folders as nodes (good for Go, or to see cycles between folders).
python3 -I SKILL_DIR/scripts/signals.py <path> --unit dir

# 4. The repo documents a layer order (high to low): list imports that go upward.
python3 -I SKILL_DIR/scripts/signals.py <path> --layers "ui>features>services>core"

# All options and their defaults:
python3 -I SKILL_DIR/scripts/signals.py --help
```

| Option | Use it when |
|---|---|
| `--top N` | You want more or fewer rows per section in the printed summary (default 25). The JSON file always has every row. |
| `--only a,b` | You need only some sections. Section names are listed in the table below. |
| `--json PATH` | You want to search or count results later without re-running the scan. |
| `--unit file\|dir` | `file` (default) for file-level findings; `dir` for folder-level cycles and for Go packages. |
| `--layers A>B>C` | The repo states which folders may depend on which. Imports from a lower folder to a higher one go to `upward_imports`. |
| `--folder-depth N` | Folder results group at the wrong level. By default the script uses the level just below the folder that holds most of the files (for example `src/`); `0` means the top level. |
| `--exclude GLOB` | You need to skip generated code, fixtures or vendored copies the default skip list misses. You can repeat it. |
| `--include-tests` | You also want test files counted (they are skipped by default). |
| `--commits N` | You want to read more or less history (default 500 recent commits). |
| `--max-commit-files N` | Big commits make co-change results noisy. Commits touching more than N files (default 20) do not count toward pairs. |

**Testing the scripts.** If you change either script, run its tests first. They use the standard library only, run in about two seconds, and build their sample projects in a temp folder. The git-history tests skip themselves when git is not installed.

```bash
python3 -I -m unittest discover -s SKILL_DIR/scripts/tests -t SKILL_DIR/scripts/tests

# Same tests, plus line coverage per script and the uncovered line numbers.
# Exits 1 if a test fails, 2 if coverage is below --fail-under.
python3 -I SKILL_DIR/scripts/tests/coverage_report.py --fail-under 99
```

The coverage runner uses the standard library only. It runs the command-line tests inside its own process, so their lines count too. The only lines it cannot see are each script's final `sys.exit(main())` line, which runs only when the script is started directly. The normal test run covers that line.

**Reading the output.** Each section prints one JSON object per row. Use the rows as a reading list, not as findings: open the cited files, then classify (Step 3). If the root has no git history, the history sections say so and everything else still works.

The script finds the import graph for JavaScript/TypeScript (including path aliases from `tsconfig`/`jsconfig`, dynamic imports and `new URL(...)` workers), Python, Java, Kotlin and Go. It reports these sections:

| Section | Points to |
|---|---|
| `fan_in`, `fan_out`, `largest`, `most_declarations` | Where to sample; large units with many jobs |
| `cycles_runtime`, `cycles_type_only` | Cycles, already split by kind |
| `folders_both_ways`, `upward_imports` | Folders that depend on each other; the minority direction is usually the misplaced code |
| `unused_candidates` | Files with no importer (with places that mention the name, to catch dynamic loading) |
| `module_mutable_state` | Candidates for common coupling or encapsulated state |
| `flag_parameters` | Candidates for control coupling or logical cohesion |
| `grab_bag_names` | Candidates for coincidental cohesion |
| `external_spread` | Outside dependencies used directly by many files (external coupling) |
| `churn`, `cochange_without_import` | Hotspots; change coupling |

**Without the script,** collect the same signals with plain search: import statements, module-level mutable variables, boolean or mode parameters, access to private members, grab-bag file names, and `git log --name-only` for files that change together.

**Known blind spots.** Treat every signal as weak evidence:

- Imports are found by pattern matching, not by the compiler. Unusual syntax, generated code and loading by string name (plugins, reflection, dependency-injection config) can be missed.
- In Java, Kotlin and Go, units in the same package need no import, so fan-in is undercounted and unused-file detection is off.
- In a **library**, public modules often have no internal importer. "Unused" there may mean "public API".
- Co-change pairs are noisy around large sweeps. The script skips big commits, but read the commit messages before you trust a pair.
- A boolean parameter in a UI component prop or a constructor option is often fine. Only flags that pick between different behaviors count.

### Step 3 — Classify

For each candidate:

1. Read the code at the cited lines.
2. Pick **one** type: the worst one that clearly applies. If two apply, record the worse one and mention the other.
3. Write the reason in one plain sentence: "`report.ts:88` writes the cache's private list directly, so any change to the cache's layout breaks the report."

One design problem is one finding, not one finding per line. Skip trivial items.

### Step 4 — Score and confirm

1. Apply the type score and any ±1 adjustment.
2. Grade the evidence.
3. Confirm every red item and every over-engineering flag from the code (see "Evidence").

### Step 5 — Fix red items

For each red item, give the **cheapest fix that moves it to at least yellow**, not the fix that reaches the theoretical best. State the cost (small / medium / large) and the risk.

| Problem | Practical fix |
|---|---|
| Content coupling | Add a small public method on the owner; route the outside access through it. |
| Common (global) coupling | Pass the state in, or put it behind one owner that controls every write. Make it read-only where possible. |
| External coupling spread over many units | Put the outside API behind one small module that follows the shape of the repo's existing wrappers. Switch callers over one at a time. |
| Run-time cycle | Move the shared piece into a third unit both can import, or import the specific module instead of an index file that re-exports everything. |
| Cycle between folders or layers | Move the code that the lower folder needs out of the higher folder, into the lower one or a shared folder. Do not add an interface just to break the loop. |
| Change coupling (a copied rule) | Extract the shared rule into one plain function or module that both call. Keep the two callers separate unless they are truly the same thing. |
| Control coupling (red after adjustment) | Split into one function per mode, or pass the behavior instead of a flag. |
| Coincidental or logical cohesion | Move each function next to its only caller, or into a unit named for its job. Delete what nobody calls. |
| Temporal cohesion | Let each subsystem own its own setup and cleanup; keep the top-level routine as a short list of calls. |

Prefer fixes that **move or delete** code over fixes that **add layers**.

### Step 6 — Over-engineering check

Low coupling and high cohesion are means, not goals. When code sits at the best end, check whether it paid too much to get there. Signs:

- **Single-use abstraction** — an interface, base class or factory with one implementation and no real test need.
- **Pass-through layers** — a layer or file whose only job is to forward or re-export the next one, so the same thing has two import paths.
- **Mapping chains** — the same data copied between near-identical types across layers. A mapping that combines several sources into one view shape does real work, and passes this check.
- **Unused flexibility** — dependency injection, plugin registries, events, config switches or exported helpers that nothing changes or calls.
- **Confetti modules** — one tiny function per file, so one change touches many files. Cohesion per file is high, but change coupling is high too.
- **Speculative generality** — options, hooks or parameters no caller uses.
- **A message bus inside one process** — events or a queue between two parts that always run together and always change together.

When a sign is present, weigh what it buys **now** (a real second implementation, a real test need, a real team or deploy boundary) against what it costs **now** (files touched per change, concepts to learn, lines to read). If the cost is higher, mark it **🟢⚠ over-engineered** and recommend the simpler shape. KISS and Occam's Razor win when they conflict with a purer score. Recommend the extreme only when it costs nothing extra in simplicity.

Apply this check to your own Step 5 fixes too: a fix that adds more structure than the problem it solves is not a fix.

### Step 7 — Unused code

List files and exports that nothing imports, with their sizes. This is not a coupling type, but it makes units look less cohesive than they are, and it hides the real structure. Grade "nothing imports it" as strong only after a search for the name across code and config. Grade "safe to delete" as a guess, and tell the reader to confirm with the owners.

---

## Report

Default to the chat. Write a file (HTML or Markdown) only when asked. Write in plain words: answer first, short active sentences, one term per idea, and each technical term defined the first time it appears. No headings or phrases that name the writing method. (This follows the public [crystal-clear](https://github.com/pandazy/jankenpon/blob/main/skills/crystal-clear/SKILL.md) skill. These rules are enough on their own.)

Structure:

1. **Answer** — two or three sentences: overall health, the worst problem, the one change that helps most.
2. **Terms used** — one line each for coupling, cohesion, the score colors and the evidence grades.
3. **Scorecard** — counts by color for coupling and cohesion. If the report is a file, add one chart per quantitative point, for example a stacked bar of colors or a bar of the files that change most. Give each chart a one-line takeaway.
4. **🔴 Red** — worst first, each with its fix, cost and risk.
5. **🟡 Yellow** — short, with a "when you next touch it" hint.
6. **🟢 Green** — good boundaries worth keeping; a sub-list of **🟢⚠** items with the simpler shape.
7. **Unused code** — Step 7.
8. **Limits** — what was sampled and what was skipped, what is only suspected, the script's blind spots that applied here, and the one observation that would change the red list most.

Finding table columns:

| # | Kind / type | Score | Where | What is wrong (plain) | Evidence | Fix (cost) |
|---|---|---|---|---|---|---|
| 1 | Coupling · Content | 0 | `a/report.ts:88` → `b/cache.ts` | The report writes the cache's private list directly. | Strong — read both files | Add `cache.add()`; use it at `report.ts:88` (small) |

**Check a report file before you hand it over.** Use `SKILL_DIR/scripts/check_report.py` (Python 3.8+, standard library only, read-only):

```bash
python3 -I SKILL_DIR/scripts/check_report.py report.html --require "Red,Yellow,Green,Limits"
python3 -I SKILL_DIR/scripts/check_report.py report.md   --require "Red,Yellow,Green,Limits"
python3 -I SKILL_DIR/scripts/check_report.py --help
```

| Option | Use it when |
|---|---|
| `--require a,b` | Each word must appear in some heading. Pass the section names your report uses. |
| `--forbid a,b` | You want a different list of banned phrases. The default list holds common method labels. Passing this option replaces the list. |
| `--min-answer-words N` | You need a different minimum for the text before the first section heading (default 20). Set `0` to skip this check. |

The script detects HTML or Markdown from the file. HTML checks are unbalanced tags, duplicate ids, table rows with the wrong number of cells (`colspan` counts), empty headings, images without alt text and empty links. Markdown checks are table rows with the wrong number of columns (code blocks are ignored). Both formats are also checked for the required headings, banned phrases, and an opening answer.

Each problem prints as a `FAIL` line with its line number. The script exits with `0` when the report passes and `1` when it does not. Fix every `FAIL`, then run it again until it prints `OK`.

## Anti-patterns

- **Script-only verdicts** — calling something red from a count, a name or a scanner row without reading the code.
- **Treating owned state as global state** — scoring a deliberate single-owner module variable as common coupling.
- **Treating type-only loops as run-time loops** — they cost less, so score them lower.
- **One finding per line** — listing every flag parameter separately. One design problem is one finding.
- **Purity over practicality** — recommending interfaces, layers or events to fix a yellow item, or to push a green item further.
- **A fix with no cost** — every fix states its size and risk.
- **Refactoring during review** — editing code instead of reporting.
- **Domain talk** — describing what the business does instead of how the code is shaped.
- **Copied text** — pasting definitions or examples from outside sources instead of writing them plainly in your own words.
