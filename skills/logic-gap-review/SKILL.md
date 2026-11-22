---
name: logic-gap-review
description: "Find bugs in the cases code never wrote down. Pick a review candidate, map its logic nodes (decisions, hidden branches, coercion, data flow, trust boundaries, resources, error paths, state), work out what each node leaves out, check what a real input can reach, and classify the outcome: crash, injection, wrong result (such as 'undefined' or NaN), security bypass, data corruption, hang, concurrency fault, silent failure, data exposure or resource leak. Uses boundary values, gap checks, basis paths, MC/DC, data flow and sibling comparison. Read-only; outputs a graded list of loopholes with concrete trigger inputs for fix or triage work elsewhere. Any language. Optional stdlib Python scripts rank candidates, list nodes, and check the list. Use to hunt edge-case bugs, find missing branches, review logic for loopholes, or answer 'what inputs break this?'."
version: 1.0.0
tags: [code-review, bugs, edge-cases, boundary-testing, branch-coverage, cyclomatic-complexity, mcdc, data-flow, injection, security, robustness]
---

# Logic Gap Review

Code fails most often in the cases it never wrote down. This skill finds those cases and says what each one breaks.

- A **logic node** is any point where behaviour depends on input or state: an `if`, a loop or a `catch`, and also a division, a lookup, a parse, a string join or a database call.
- A **missing case** is an input or state that a logic node does not handle on purpose.
- A **loophole** is a missing case that a real input can reach and that leads to a bad outcome.

The output is a list of loopholes. What happens next (a fix, a false-alarm review, an escalation) is done by whoever reads the list. This skill does not do that work.

## Hard rules

1. **Read-only.** Do not edit the reviewed code. Write reproductions only in a temporary folder outside the reviewed repo.
2. **Local reproduction only.** Run reproductions only against local code: a unit test, a REPL or a local build. Never send a trigger input to a shared or deployed system. To show an injection risk, use a **harmless marker**, such as a payload that only changes a returned string, to prove the input reaches the sink unescaped. Never use a payload that deletes, leaks or runs anything.
3. **Reachability before severity.** A missing case is a loophole only if a real input can reach it. Trace it back to an entry point. If an upstream check blocks it, mark it *dismissed* and cite that check. Never drop a case silently.
4. **Evidence or label.** Every loophole cites `file:line`, a concrete trigger input and an evidence grade (see "Evidence"). A **critical** or **high** loophole must rest on code you read end to end or a run you observed, never on a pattern match alone.
5. **No secrets in the output.** Do not copy credentials, tokens or personal data from the code or its config. Cite the location instead.
6. **Context-agnostic.** Assume nothing about the language, framework, product or domain. Describe code by its role ("the input parser", "the save handler"), not by what the product does. Learn conventions from the repo. Where the repo has its own validation, error handling or escaping layer, check that it works rather than assuming it does.

---

## Consequence categories

Classify each loophole by its **worst plausible outcome**. Give it one category: pick the worst, and mention the others in the outcome text.

| # | Category | What it looks like | Examples |
|---|---|---|---|
| C1 | **Crash** | An unhandled error stops the request, job or process. | Null or undefined dereference; integer division by zero; index out of range; uncaught parse error; failed assertion; stack overflow from unbounded recursion. |
| C2 | **Injection** | Untrusted input reaches an interpreter without escaping or parameters. | Query built by string join; shell command built from input; HTML or script output without encoding; file path built from input (path traversal); template injection; unsafe deserialization; log injection; prototype pollution through a merge of input objects. |
| C3 | **Wrong result** | The code returns or stores a wrong value with no error. | `"undefined"`, `"null"`, `"NaN"` or `"[object Object]"` in output; `"10" + 2 === "102"`; off-by-one; float rounding on stored totals; integer overflow; time-zone or daylight-saving shift; truncation; a default used where the real value was missing. |
| C4 | **Security bypass** | A permission, ownership or limit check is skipped, or *fails open*, on some path. | A check that an error path skips; `if (role !== 'admin')` when `role` is undefined; an ownership check present on one handler but missing on its twin; a limit enforced on create but not on update. |
| C5 | **Data corruption or loss** | Stored data ends up partial, inconsistent or gone. | A multi-step write with no transaction or rollback; an exception between two writes; a lost update (read, change, write with no version check); silent truncation at a column limit; a delete that matches more than intended. |
| C6 | **Hang or resource exhaustion** | The code stops responding, or uses unbounded memory, CPU or connections. | A loop whose exit is never reached for some input; a regex with catastrophic backtracking (ReDoS); an allocation sized by the input; a network call with no timeout; a retry loop with no limit or backoff. |
| C7 | **Concurrency fault** | The result depends on timing. | A race on shared state; check-then-act (TOCTOU) on files or records; a deadlock from lock order; a duplicate request or message applied twice. |
| C8 | **Silent failure** | An error is hidden, so the caller believes it worked. | A `catch` that logs and continues; an error turned into an empty list or a default; a success status after a failed write; a promise with no `await` or rejection handler. |
| C9 | **Sensitive data exposure** | Secrets or personal data leak through a side channel. | Stack traces or internal errors returned to the client; tokens or personal data in logs; an error message that reveals whether a record or account exists. |
| C10 | **Resource leak** | Something acquired is not released on every path. | A file handle, connection, lock or temporary file not closed on the error path; a listener or timer never removed. |

### Severity

Set the severity from the category and from how easy the trigger is.

| Severity | Rule of thumb |
|---|---|
| **Critical** | C2 or C4 reachable by an outside caller with no special access; C5 on important data with no recovery. |
| **High** | C1, C6 or C7 reachable by an outside caller (one request takes down a worker or blocks a queue); C3 on stored values, limits or permission data; C9 that exposes secrets. |
| **Medium** | Needs unusual but valid input, or an internal caller; C3 on displayed values; C8 that hides a real failure; C10 on a busy path. |
| **Low** | Needs input that only another bug or a misconfiguration could produce; a cosmetic wrong result. |

Adjust by **one level at most**, and say why. **Raise** it when a normal user action triggers it, or the code runs on every request. **Lower** it when the trigger needs an administrator or a trusted internal caller, or when an upstream check makes it unlikely but not impossible.

---

## Evidence

Grade every item:

- **Reproduced**: you ran the trigger input locally and saw the bad outcome.
- **Strong**: you read the full path from the entry point to the node, and no check on that path blocks the trigger.
- **Weak**: you read the node but not the whole path; or the item comes from a pattern match, a script row or another tool's claim.
- **Guess**: no supporting observation. Say what would confirm it.

Status follows from the evidence:

| Evidence | Allowed status |
|---|---|
| Reproduced, strong | loophole, at any severity |
| Weak | loophole at medium or low only; otherwise suspected |
| Guess | suspected only |

Before you report, re-check every critical and high loophole. If one rests on weak evidence, read the path or reproduce it. If you cannot, mark it *suspected* (rated medium at most) with the check that would settle it. If a later observation contradicts an item, change it or dismiss it. Never keep both versions.

---

## Procedure

### Step 1: Pick the review candidate

If the user names the code (a file, function, diff or change request), use it. Otherwise rank candidates and review the top few. Record what you picked and why.

Rank higher when the code:

1. **takes untrusted input**, for example request handlers, command-line parsing, file and message consumers, callbacks from outside;
2. **reaches a dangerous sink**, for example query building, shell or process calls, HTML output, file paths, dynamic code, deserialization;
3. **computes values that are stored or enforced**, for example totals, quotas, limits, permissions, dates, counters;
4. **has many decisions**: cyclomatic complexity above 10 is a common warning line;
5. **changed recently or changes often**, since new code and hotspots carry most new bugs;
6. **sits near a past bug fix**, since bugs cluster and fixes often miss sibling cases.

`nodes.py rank` scores points 1, 2, 4, 5 and 6 for you (see "Scripts"). Point 3 needs reading. Then read the repo's docs and the candidate's callers, so you know which inputs reach it and which checks run upstream.

### Step 2: Map the logic nodes

Find as many logic nodes as you can. Go through every family and list each node with its `file:line`. `nodes.py nodes` produces this list for the first seven families.

| Family | Look for |
|---|---|
| **Decisions** | `if`/`else if`/`else`, `switch` and `match` (and a missing `default`), ternaries, `&&`/`\|\|` short circuits, `??`, guard clauses, early returns, loop conditions, `catch` clauses, `break`/`continue`. |
| **Hidden branches** | Division and modulo; indexing and key lookup; parsing and number conversion; arithmetic overflow; floating point (NaN, infinity, rounding); regex matching; I/O, network and database calls (timeout, partial result, empty result, duplicate); recursion; endless loops. |
| **Type coercion** (dynamic languages) | `+` between strings and numbers; `==` versus `===`; truthy and falsy checks on `0`, `""`, `[]` or `NaN`; template literals and optional chaining over possibly missing values; parsed data used without a shape check; `parseInt` without a radix. |
| **Data flow** | A variable assigned on some paths but used on all of them; a value reassigned inside a branch; a default that hides a missing value; a mutable default or shared object changed in place. |
| **Trust boundaries** | Where outside data enters (**sources**) and where it reaches an interpreter, the file system, the network or a privileged action (**sinks**). Each source-to-sink route is a node. |
| **Resources** | Every acquire (open, connect, lock, allocate, subscribe) and its release on **every** exit, including error paths. |
| **Error paths** | Each `catch`, error return and early exit: what it hides, what it returns, and what state it leaves behind. |
| **State and order** | Status fields and state machines; "call A before B" rules; retry and idempotency; shared state touched by concurrent callers. The script does not detect these. Find them by reading. |

**Completeness check.** For each function, compute the cyclomatic complexity, `v(G) = decisions + 1`. This is the number of independent paths through it. If the decisions you listed add up to fewer than `v(G) - 1`, you missed a node. Go back and find it.

### Step 3: Work out the missing cases

For each node, list the inputs and states it does not handle on purpose. Use all of these techniques. Each one finds gaps the others miss.

1. **Gaps and overlaps.** Combine every condition that guards the same value. A **gap** is an input that no branch claims, such as `x < 0` and `x > 0` with nothing for `0`. An **overlap** is an input that two branches both claim, so the order of the checks decides the result.
2. **Boundary values.** Test each condition on its border and just past it. For `x > 5`, use 5 and 6. Add the type's extremes: 0, -1, maximum, minimum, empty, one item, and for floats NaN and infinity.
3. **Each part of a compound condition (MC/DC).** For `a && b || c`, find inputs where each part alone flips the outcome. A part that can never flip it is dead code or a mistake.
4. **Basis paths.** Choose `v(G)` independent paths. Start from a typical path, then flip one decision at a time. If no input can take a path, that is a finding: dead code or two checks that contradict each other.
5. **Data flow.** On every path, check that each variable is assigned before use and still holds the value the code expects.
6. **Hidden-branch checklist.** For each operation in the hidden-branch and type-coercion families, ask what happens with zero, missing, empty, malformed, overflow, timeout, NaN and the wrong type.
7. **Sibling comparison.** Compare the node with similar code: the other handler, the create and update pair, the same check in another file. A check that one has and the other lacks is a strong lead. Coverage tools cannot find this kind of gap.
8. **Error paths.** For each `catch` and early return, check what state the code leaves behind (half-done writes, held resources) and what the caller is told.

### Step 4: Check reachability

For each missing case:

1. **Write a trigger input**: a concrete value or state, not a description. For example, `size = 5`, `items = [{amount: "10"}]`, `name = "x'"`.
2. **Trace it back** to an entry point. Check every validation, type check, schema, middleware and caller on the way.
3. **Decide**:
   - **Reachable**: nothing on the path blocks it. Carry it to Step 5.
   - **Blocked upstream**: mark it *dismissed* and cite the blocking check as `file:line`. If that check is the only protection, say so in the note, because removing it would expose the node.
   - **Unknown**: the path runs through code you cannot see, such as another service or dynamic dispatch. Mark it *suspected* and say what would settle it.

### Step 5: Classify and rate

For each reachable case:

1. Pick the worst category it plausibly leads to (C1–C10).
2. Set the severity, with at most one level of adjustment and the reason.
3. Describe it in one plain sentence: the input, what happens, and why it matters. For example: "`sumValues()` at `calc.js:14` returns `"0102"` instead of `12` when amounts arrive as strings, so the stored total is wrong."

One root cause is one item, even if it shows up on several lines. List the other places in `also_at`.

### Step 6: Confirm

For every critical and high loophole, and for any other loophole where it is cheap to do:

1. Write the smallest reproduction you can: a unit test, a REPL snippet or a script, kept outside the reviewed repo (hard rules 1 and 2).
2. Run it, and record the command and the observed output.
3. If the outcome differs from what you expected, re-rate, re-classify or dismiss the item.

### Step 7: Report the loophole list

Default to the chat. Write a file only when asked. Use plain words, and lead with the answer.

1. **Answer**: two or three sentences giving the number of loopholes, the worst one, and the code reviewed.
2. **Loopholes**: one table, with critical items first, then high, medium and low.
3. **Suspected**: items you could not confirm, each with the check that would settle it.
4. **Dismissed**: missing cases blocked upstream, each with the blocking check. Readers use this list to spot false alarms and protection that rests on a single check.
5. **Limits**: what you reviewed and skipped, the nodes you could not trace, and the one observation that would change the list most.

When the list feeds another tool or agent, write it as JSON first, then check it and print the tables from it with `check_loopholes.py --markdown`. That keeps the tables and the JSON identical. Use one object per item:

| Field | Needed for | Value |
|---|---|---|
| `id` | all | unique, e.g. `L1`, `S1`, `D1` |
| `status` | all | `loophole`, `suspected` or `dismissed` |
| `location` | all | `file:line` or `file:start-end` |
| `node` | all | the logic node, e.g. `reduce with +` |
| `missing_case` | all | the case the node does not handle |
| `trigger` | all | a concrete input value |
| `category` | loophole, suspected | `C1`–`C10` |
| `severity` | loophole (optional for suspected) | `critical`, `high`, `medium`, `low` |
| `outcome` | loophole, suspected | what happens |
| `evidence` | loophole | `reproduced`, `strong`, `weak` (see "Evidence") |
| `reproduction` | loophole with `reproduced` evidence | the command you ran |
| `to_confirm` | suspected | the check that would settle it |
| `blocked_by` | dismissed | `file:line` of the blocking check |
| `also_at` | optional | list of other `file:line` places with the same root cause |
| `note` | optional | anything else, e.g. "this check is the only protection" |

```json
[
  {"id": "L1", "status": "loophole", "severity": "high", "category": "C3", "location": "calc.js:14",
   "node": "reduce with +", "missing_case": "amount is a string", "trigger": "[{\"amount\":\"10\"},{\"amount\":\"2\"}]",
   "outcome": "returns \"0102\" instead of 12", "evidence": "reproduced", "reproduction": "node -e \"...\""},
  {"id": "D1", "status": "dismissed", "location": "band.py:7", "node": "if/elif", "missing_case": "size is 0",
   "trigger": "size = 0", "blocked_by": "band.py:5", "note": "the guard raises first"}
]
```

---

## Scripts

Both scripts are optional. They live in this skill's `scripts/` folder. `SKILL_DIR` below means the folder that holds this `SKILL.md`. They need Python 3.8+ and the standard library only, and they are read-only: they write nothing except the file you pass to `--json`. `-I` runs Python in isolated mode, so files in the reviewed repo cannot change how a script behaves.

### `nodes.py`: rank candidates and list logic nodes

```bash
# Step 1: rank functions as review candidates (uses git history when there is one).
python3 -I SKILL_DIR/scripts/nodes.py rank <repo-or-folder> --top 20

# Step 2: list every logic node of a file or folder, or of one function.
python3 -I SKILL_DIR/scripts/nodes.py nodes <file-or-folder> --function <name>

# Only some families, with the full result saved as JSON.
python3 -I SKILL_DIR/scripts/nodes.py nodes <path> --family boundary,error-path --json /tmp/nodes.json

python3 -I SKILL_DIR/scripts/nodes.py --help
```

| Option | Use it when |
|---|---|
| `--top N` (rank) | You want more or fewer rows (default 25). |
| `--commits N` (rank) | You want more or less history (default 500 recent commits). |
| `--no-history` (rank) | Version history is missing, huge or not relevant. |
| `--function NAME` (nodes) | You want one function. `NAME` matches the full name (`Class.method`) or its last part. |
| `--family a,b` (nodes) | You want only some families: `decision`, `hidden`, `coercion`, `data-flow`, `boundary`, `resource`, `error-path`. |
| `--json OUT` | You want every result as JSON to search or count later. |
| `--exclude GLOB` | You need to skip generated code, fixtures or vendored copies. You can repeat it. |
| `--include-tests` | You also want test files (skipped by default). |

The rank score is `(v(G) - 1) + 3 × sinks + 2 × sources + 0.5 × min(commits, 10) + fix commits`. A fix commit is one whose subject mentions fix, bug, hotfix, patch or regression. The score only orders your reading list. It never sets severity.

The `nodes` output gives one header per function (`file:line name v(G)=… decisions=… exact|approx`) and then one row per node: line, family, kind and detail. The kinds are:

| Family | Kinds |
|---|---|
| `decision` | `if`, `for`, `while`, `case`, `catch`, `and`, `or`, `ternary`, `nullish`, `elvis`, `when-branch`, `comprehension`, `assert`, plus the gap hints `if-chain-no-else` and `switch-no-default` |
| `hidden` | `division`, `modulo`, `index-or-key`, `parse`, `network-call`, `network-no-timeout`, `loop-no-exit`, `recursion`, `may-return-undefined`, `not-null-assertion`, `type-assertion`, `next-no-default` |
| `coercion` | `loose-equality`, `parseInt-no-radix`, `optional-chaining`, `template-interpolation` |
| `data-flow` | `maybe-unassigned`, `mutable-default` |
| `boundary` | `source`, `sink:sql`, `sink:shell`, `sink:code`, `sink:html`, `sink:file`, `sink:deserialize`, `sink:object-merge`, `sink:regex`, `sink:outbound-request` |
| `resource` | `acquire-no-release` |
| `error-path` | `catch-swallows`, `catch-returns-default`, `bare-catch`, `error-ignored` |

The header's `decisions` count is `v(G) - 1`. One row can count more than once (`a and b and c` is one `and` row worth two decisions), and the gap hints count zero. Use the rows as a reading list: open each one and work through Steps 3–5. A row is weak evidence on its own.

**Known blind spots:**

- Python is parsed exactly. JavaScript/TypeScript, Java, Kotlin and Go are scanned with patterns, so their `v(G)` and rows are approximate. Unusual syntax, macros and generated code can be missed or misread.
- Code outside any function (module top level) is not listed.
- `maybe-unassigned` and `mutable-default` exist for Python only. Data flow in other languages needs reading.
- State-and-order nodes, `+` between strings and numbers, and most concurrency faults are not detected.
- A sink is flagged only when its argument looks built or variable. A constant argument passed through a variable looks variable.

### `check_loopholes.py`: check the list and print the tables

```bash
python3 -I SKILL_DIR/scripts/check_loopholes.py list.json              # check only
python3 -I SKILL_DIR/scripts/check_loopholes.py list.json --markdown   # check, then print the tables
```

The input is a JSON array of items, or an object with an `items` array. The script checks:

- that every field a status needs is present and not empty;
- that ids are unique and statuses known;
- that locations look like `file:line`;
- that each trigger is a concrete value;
- that categories, severities and evidence grades are valid;
- the evidence rules above;
- that loopholes run from critical to low;
- that no value looks like a private key, an access key, a signed token or a credential.

Each problem prints as a `FAIL` line. The script exits `0` and prints `OK` when the list passes, and exits `1` when it does not. Fix every `FAIL` and run it again. The tables print only when the list passes.

### Testing the scripts

If you change a script, run its tests first. They use the standard library only and run in about a second. The git-history test skips itself when git is not installed.

```bash
python3 -I -m unittest discover -s SKILL_DIR/scripts/tests -t SKILL_DIR/scripts/tests

# Same tests, plus line coverage per script. Exits 1 if a test fails, 2 if coverage is below --fail-under.
python3 -I SKILL_DIR/scripts/tests/coverage_report.py --fail-under 98
```

---

## Worked examples

**Python: a gap between two conditions (C1).**

```python
def band_score(size, boost):
    if size <= 0:
        raise ValueError("bad size")
    if size < 5:
        score = 5
    elif size > 5:
        score = 5 + (size - 5) * 2
    if boost:
        score *= 2
    return score
```

- *Gaps and overlaps*: `< 5` and `> 5` leave out `5`. *Data flow*: `score` is not assigned on that path. `nodes.py` reports both, as `if-chain-no-else` and `maybe-unassigned`.
- *Hidden branch*: `NaN <= 0` is false, so NaN gets past the guard and falls into the same gap.
- *Trigger*: `band_score(5, False)` raises `UnboundLocalError`, and so does `band_score(float("nan"), False)`.
- *Basis paths*: `v(G) = 5`. The fifth independent path needs `size > 5` to be false after `size < 5` was false, and only `5` or NaN can do that. So covering a full basis set exposes the bug.

**JavaScript: coercion gives a wrong result (C3).**

```js
function sumValues(items) { return items.reduce((sum, i) => sum + i.amount, 0); }
function label(record)    { return `Item ${record.name}`; }
```

- `sumValues([{amount: "10"}, {amount: "2"}])` returns `"0102"`, because `0 + "10"` turns the sum into a string.
- `sumValues([{}])` returns `NaN`.
- `label({})` returns `"Item undefined"`.

---

## Anti-patterns

- **Nodes without reachability.** A missing case behind a strict upstream check is not a loophole. Dismiss it and give the reason.
- **Pattern-match verdicts.** Rating something critical because it "looks like" a query built from strings, without reading where the string comes from. A script row is weak evidence.
- **Stopping at explicit branches.** Most loopholes hide inside operations (division, lookup, coercion, I/O), not in `if` statements.
- **Descriptions instead of triggers.** "Bad input might break it" is not a trigger. Write the value.
- **One item per line.** Group by root cause, and list the other places in `also_at`.
- **Dangerous reproductions.** Sending payloads to shared systems, or using payloads that change or leak data.
- **Fixing during review.** The output is a list. Fixes, triage and escalation happen elsewhere.
- **Silent drops.** Removing a missing case without marking it *dismissed* or *suspected*.
