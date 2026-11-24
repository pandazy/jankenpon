---
name: race-condition-review
description: "Find race conditions in source code, pseudo code or a design (frontend, backend, distributed systems, databases, event loops, threads, message queues). Map who runs at the same time (actors), what they share (state), and where another actor can step in (race windows). Build the happens-before order the system actually enforces, find access pairs it leaves unordered, and keep only those that break a stated invariant. Classify each by race pattern (check-then-act, lost update, order violation, stale async result, partial state, duplicate message, fault timing, isolation anomaly, lifecycle, locks, stampede) and impact (security or limit bypass, data loss, wrong result, crash, deadlock, wasted resources, leak, cross-user exposure, divergence); rate severity from impact and who can trigger it; give a concrete interleaving for every item. Read-only; local reproduction only. Any language. Optional stdlib Python scripts list candidates and check the report."
version: 1.0.0
tags: [concurrency, race-condition, toctou, atomicity, distributed-systems, event-driven, idempotency, isolation, deadlock, security, code-review, design-review]
---

# Race Condition Review

A race condition is a bug whose result depends on timing. This skill finds those bugs in code, pseudo code or a design, says what each one breaks, and ranks them.

- An **actor** is anything that can run at the same time as something else: a thread, a request, a worker, a message consumer, a retry, a timer, a UI event, a browser tab, a second device, a replica, a failover node.
- **Shared state** is data that two actors can both touch: a database row, a cache entry, a file, a session, a counter in memory, a client-side store, a DOM node, a lease.
- A **race window** is the gap between two steps that the code assumes nothing can interrupt, but something can.
- A **race** is an unordered pair of accesses to the same shared state, at least one of them a write, inside a window.
- A **harmful race** is a race where some order of the steps breaks an **invariant**, a rule the system relies on, such as "a coupon credits once" or "the screen shows the latest search".

The output is a ranked list of harmful races. Each item has a concrete **interleaving**: the step-by-step schedule that breaks the invariant. Fixing the races is done by whoever reads the list, not by this skill.

`references/background.md` explains how and why the skill was built: the research it draws on, its trade-offs, and the reasoning behind the method. Read it before changing the skill. You don't need it to run one.

## Hard rules

1. **Read-only.** Do not edit the reviewed code or design. Write reproductions only in a temporary folder outside the reviewed repo.
2. **Local reproduction only.** Run reproductions only against local code: a unit test, a local build, a local database or a local container. **Never send parallel or repeated requests to a shared or deployed system.** A race test is a burst of traffic, and on a live system it can spend real money, corrupt real data or take the service down. Use harmless state, such as a test account in a local database.
3. **Interleaving or it isn't a race.** Every item names the shared state, the actors, and a concrete schedule of at least two steps by at least two actors. "This could race" is not a finding.
4. **Invariant before severity.** A race that breaks no invariant is benign. Mark it *dismissed* with the reason. Never drop it silently.
5. **Evidence or label.** Every item cites `file:line` (or `doc#section` for a design) and an evidence grade (see "Evidence"). A **critical** or **high** race must rest on a path you read end to end, or a run you observed, never on a pattern match alone.
6. **No secrets in the output.** Do not copy credentials, tokens or personal data from the code or its config. Cite the location instead.
7. **Context-agnostic.** Assume nothing about the language, framework, database, product or domain. Describe parts by their role ("the redeem handler", "the order consumer"), not by what the business does. Where the code relies on a lock, a transaction, a queue or a framework for safety, check that it really orders the steps rather than assuming it does.

---

## Race patterns

Give each item the one pattern closest to its root cause. Mention others in the outcome text.

| # | Pattern | Mechanism | Typical shapes |
|---|---|---|---|
| R1 | **Check-then-act** | A check and the action that relies on it are separate steps, and the state can change between them (TOCTOU, time-of-check to time-of-use). | `if not used: use()`; `if balance >= x: withdraw(x)`; `if not exists(path): create(path)`; a uniqueness check in code instead of a unique constraint; a rate limit read, then incremented. |
| R2 | **Lost update** | Read, change, write back. Two actors read the same value and the second write erases the first. | `x = get(); x.n += 1; save(x)`; `SELECT` then `UPDATE` with the computed value; a JSON blob or settings document overwritten whole; `counter++` on shared memory. |
| R3 | **Order violation** | Code assumes A happens before B, and nothing enforces it. | Use before initialization (a handler runs before the page, module or connection is ready); a reply handled before the request is recorded; a "created" event processed after "updated"; config read before it loads. |
| R4 | **Stale or out-of-order result** | An async result arrives after a newer one, or after its context is gone, and still wins. | Search-as-you-type showing the older query's results; a slow response overwriting a fast one; a reply applied to a different item after navigation; polling overwriting a user's edit. |
| R5 | **Exposed partial state** | A multi-step change is visible halfway, or an object passes through a hidden sub-state. | Two writes without a transaction, read in between; a session or token created before its permissions are set; a file read while it is being written; a status set to "done" before the result is stored. |
| R6 | **Duplicate or replayed operation** | The same operation runs twice: retries, double submits, at-least-once delivery, replays. | A payment or email sent twice after a timeout retry; a message consumer with no deduplication key; a double-clicked button; a webhook re-delivered; a client retry after the server already committed. |
| R7 | **Message timing against faults** | A message, timeout or lease expiry lands at an unexpected moment relative to a crash, restart, failover or another message. | A message arrives before or after a node restarts; a timeout fires while the reply is in flight; a paused old leader writes after a new leader takes over (split brain, missing fencing token); messages from two senders reordered. |
| R8 | **Isolation anomaly** | Each transaction is correct alone, but the database's isolation level lets them interleave badly. | Two transactions each check "at least one on call" then both remove themselves (write skew); a read of two related rows that sees half of another transaction (read skew); an `INSERT` passes a check because the row didn't exist yet (phantom); a lost update inside a transaction at the default level. |
| R9 | **Lifecycle race** | Work outlives its owner, or teardown runs while work is still in flight. | A component, connection or request closed while a callback is pending; a timer, listener, subscription or background task never removed; a pooled object reused while an old callback still holds it; a cancelled request that still writes. |
| R10 | **Lock and memory fault** | Shared memory without the right lock, or locks used in a way that blocks or deadlocks. | Unprotected shared field or map; two locks taken in a different order on two paths (deadlock); a lock held across network I/O, sleep or `await`; double-checked initialization without proper memory ordering; a non-thread-safe object shared across threads. |
| R11 | **Stampede** | Many actors react to one event by doing the same expensive work at once. | A popular cache entry expires and every request recomputes it; every client reconnects at the same moment after an outage; retries with no backoff or jitter (retry storm); every replica runs the same scheduled job. |

## Impact categories

Give each item the **worst plausible** impact. Mention others in the outcome text.

| # | Impact | What it looks like |
|---|---|---|
| I1 | **Security or limit bypass** | A once-only, limit, quota, balance, permission or authentication rule is broken: double spend, coupon or invite reuse, a rate limit exceeded, a role check on half-written state, a verification step skipped. |
| I2 | **Data corruption or loss** | Stored data ends up wrong, partial or gone: lost updates, duplicate records, orphaned rows, a counter that drifts, a file left half-written. |
| I3 | **Wrong or stale result** | The system shows or returns the wrong value, with no stored damage: an old search result, a flickering status, a wrong total on screen. |
| I4 | **Crash** | An unhandled error: use of a closed resource, a null from an uninitialized dependency, a concurrent modification error. |
| I5 | **Hang, deadlock or outage** | Threads, workers or a whole service stop: deadlock, livelock, a lock held across slow I/O that drains the pool, a retry storm that keeps a dependency down. |
| I6 | **Wasted resources** | CPU, memory, network, database or money spent on duplicate or useless work: a stampede of recomputation, duplicate jobs, duplicate paid API calls, work for results nobody reads. |
| I7 | **Resource leak** | Something acquired is never released: timers, listeners, tasks, goroutines, connections, memory held by forgotten callbacks. |
| I8 | **Cross-user data exposure** | One user sees another user's data: shared mutable state across requests, a cache key without the user, a response delivered to the wrong session. |
| I9 | **Silent divergence** | Copies of the same state disagree with no error: cache and database, replicas, client and server, two services. |

## Severity

Set the severity from the impact and from **who can trigger the race** (`trigger` field):

- **outside**: any outside caller can make the actors overlap on purpose, for example by sending parallel requests. Treat **every network endpoint** as outside-triggerable. Attackers can line up requests to within about a millisecond and can often widen a window, so a narrow window is **not** a defence.
- **normal**: it happens on its own under ordinary use: load, retries, slow networks, double clicks, several tabs, message redelivery.
- **rare**: it needs a fault or timing that no caller controls: a crash at a precise step, a failover, a long pause.

| Severity | Rule of thumb |
|---|---|
| **Critical** | I1 or I8 with an outside trigger; I2 on important data, outside or normal trigger, with no way to recover. |
| **High** | I1 or I2 with a normal trigger; I4 or I5 with an outside trigger (one burst takes down a worker or deadlocks a pool); I6 that multiplies load (stampede, retry storm) under normal use; I2 with a rare trigger and no way to recover; I8 with a rare trigger. |
| **Medium** | I3 on values users act on; I7 on a busy path; I9; I6 with a bounded cost; anything that needs an internal or administrator caller. |
| **Low** | Cosmetic I3 (a brief flicker); needs another bug or a misconfiguration first. |

Adjust by **one level at most**, and say why. **Raise** it when the race is on a path every request takes, or the damage spreads (money, other users, other services). **Lower** it when a later step reliably detects and repairs the damage, or when the trigger needs a trusted caller. A **rare** trigger is rated high at most.

---

## Evidence

Grade every item:

- **Reproduced**: you forced the interleaving locally and saw the invariant break.
- **Strong**: you read the full path of both actors, from their entry points through the window, and nothing on that path orders the steps. For a design, the design describes each step and names nothing that orders them.
- **Weak**: you read the window but not the full paths; or the item comes from a scanner row, a pattern match or another tool's claim; or the design is silent about the steps.
- **Guess**: no supporting observation. Say what would confirm it.

| Evidence | Allowed status |
|---|---|
| Reproduced, strong | race, at any severity |
| Weak | race at medium or low only; otherwise suspected |
| Guess | suspected only |

A design review can reach *strong* at best: nothing has run. Before you report, re-check every critical and high race. If one rests on weak evidence, read the paths or reproduce it. If you cannot, mark it *suspected* (rated medium at most) with the check that would settle it. If a later observation contradicts an item, change it or dismiss it. Never keep both versions.

(This follows the public [evidence-driven-reasoning](https://github.com/pandazy/jankenpon/blob/main/skills/evidence-driven-reasoning/SKILL.md) skill. The rules above are enough on their own if that skill is not available.)

---

## Procedure

The steps follow one idea from the research: **predict** where actors collide (Steps 1–4), **prove** the collision breaks something (Steps 5–8), then **report** (Step 9).

### Step 1: Pick the review scope

If the user names the code or design, use it. Otherwise rank candidates and review the top few. Record what you picked and why.

Rank higher when the code or design:

1. **enforces a once-only or limit rule**: redeem, claim, vote, invite, verify, reset, transfer, withdraw, checkout, reserve, quota, rate limit, sign-up with a unique name;
2. **changes state in several steps**: multi-write flows, state machines, sessions, sign-in, approval workflows;
3. **consumes messages, retries or webhooks**, which deliver at least once by default;
4. **caches** results, or keeps state on the client that a server also changes;
5. **starts concurrent work**: threads, pools, `Promise.all`, background tasks, timers, parallel jobs;
6. **coordinates nodes**: leaders, leases, locks across machines, replication, failover;
7. **sits near a past concurrency fix**, since a fix often misses its siblings.

`race_scan.py` lists candidates by file (see "Scripts"). Points 1, 2 and 6 need reading.

### Step 2: List the actors

For the scope, list every actor that can run at the same time as another, with where it starts. Do not stop at threads:

- **Requests**: each request is an actor, and **the same user can send many at once**.
- **Background work**: jobs, schedulers, timers, workers, pools, spawned tasks.
- **Messages**: consumers (several instances, redelivery), producers, webhooks, retries by clients, proxies and SDKs.
- **Client side**: user events, async replies, several tabs, several devices, service workers, polling.
- **Distributed**: replicas, a new and an old leader, a node before and after a restart, a timeout handler racing the real reply.
- **Faults as actors**: a crash, a restart, a network partition or a lease expiry can each "step in" at any point.

### Step 3: List the shared state and its protection

For each piece of state that two actors touch, record:

| Field | Example |
|---|---|
| State and its key | coupon row by `code`; cache entry by `user id`; in-memory `counter` |
| Where it lives | memory of one process; database; cache; file; client store; another service |
| Readers and writers | the redeem handler (read, write); the expiry job (write) |
| Protection that orders access | lock (which one, held where); transaction (which isolation level); conditional or atomic write; unique constraint; version or ETag check; idempotency key; single consumer per key; nothing |

A protection counts only if it covers **the whole window, for every actor**. A lock in one process does not protect a database row from another process. A transaction at the database's **default isolation level often allows lost updates and write skew**. Many common databases do not default to serializable. A check in application code is not a constraint.

### Step 4: Find the race windows and build the order

For each operation that touches shared state:

1. **Mark the yield points**, where another actor can step in: `await`, callbacks and promise `then`; any database, network or file call; message send and receive; lock release; transaction commit; each turn of an event loop; any point at all for shared memory without a lock; and, for a client, every round trip to the server.
2. **Mark the window**: from the first access (the read or check) to the last access that relies on it (the write or act), when a yield point lies between them. In a **single-threaded event loop** (browser JavaScript, server-side JavaScript, async Python), code with no yield point between two accesses cannot be interrupted by another event, so it is no window for in-memory state. It is still a window for state that **another process or machine** can change, such as a file, a database row or a cache entry.
3. **Write down what orders the steps (happens-before).** Only these count:
   - program order inside one actor's uninterrupted run;
   - a release, then an acquire, of the **same** lock;
   - one actor awaiting or joining another;
   - a message's send before its receive (but not between different senders);
   - an atomic or conditional operation, or a constraint, in the store itself;
   - a transaction at an isolation level that forbids this anomaly;
   - one consumer per key, when the routing is guaranteed.
4. **List the unordered pairs**: two accesses to the same state, by two actors, at least one a write, with nothing above ordering them. Each pair is a race candidate.
5. **Compare siblings.** The same state written by two code paths (create and update, the web handler and the batch job, two endpoints) where only one path is protected is a strong lead. Multi-endpoint races hide here.

Most real races need **only two actors and a few steps**. Look for pairs first. Large, many-actor scenarios rarely add findings.

### Step 5: Name the invariant and write the interleaving

For each candidate:

1. **State the invariant** it could break, in one plain sentence: "a coupon credits once", "stock never goes below zero", "the screen shows the latest query", "one leader writes at a time", "each message is applied once". Read the docs, tests, constraints and names to find the rule the code relies on.
2. **Write the interleaving**: the shortest schedule that breaks it, one step per line, each step labelled with its actor:
   `A: reads balance 100` → `B: reads balance 100` → `A: writes 100 − 80 = 20` → `B: writes 100 − 80 = 20`.
3. If no schedule breaks any invariant, the race is **benign**. Mark it *dismissed*, with "benign: no invariant breaks" and the reason.

### Step 6: Check the protection and reachability

For each harmful candidate:

1. **Can the actors really overlap?** For example, two requests from one user, two consumer instances, a retry while the first try is still running. If deployment or routing guarantees they can't, mark it *dismissed* and cite the guarantee. If that guarantee lives outside the code (a deployment setting, one worker per key), say so: it is the only protection.
2. **Does an existing protection close the window?** Read it. Check that it covers every actor and the whole window, and that its isolation level or memory ordering forbids this interleaving. If it does, mark it *dismissed* and cite it as `blocked_by`.
3. **Unknown**: the path runs through code or a service you cannot see. Mark it *suspected* and say what would settle it.

### Step 7: Classify and rate

For each harmful race:

1. Pick the pattern (R1–R11) and the worst plausible impact (I1–I9).
2. Pick the trigger (`outside`, `normal` or `rare`) and set the severity, with at most one level of adjustment and the reason.
3. Describe it in one plain sentence: the interleaving, what happens, and why it matters. For example: "Two parallel redeem requests both pass `is_redeemed()` at `redeem.py:12`, so one coupon credits twice."

One root cause is one item, even if it shows up in several places. List the other places in `also_at`.

### Step 8: Confirm locally

For every critical and high race, and for any other where it is cheap, force the interleaving **locally** (hard rule 2). Pick the lightest method that works:

| Method | How | Fits |
|---|---|---|
| **Forced schedule** | Put a latch, barrier or delay at the yield point inside the window (in a test double or a temporary copy), start both actors, and release them in the bad order. | R1, R2, R3, R5, R9: the most direct proof |
| **Parallel burst** | Fire N identical requests at a local instance at the same moment: open the connections first, then release all requests together. | R1, R2, R6, R8 behind an endpoint |
| **Event-order shuffling** | Delay or reorder async callbacks, replies and timers. | R3, R4, R9 in event-loop code (frontend, server-side JavaScript) |
| **Race detectors and schedulers** | Run the tests under the language's data-race detector or thread sanitizer; or a stress loop with random small delays or random scheduling. | R10, and shared memory in general |
| **History check** | Record every operation and result from a concurrent run, then check the invariant, or the isolation level the store promises, against the history. | R2, R8, R9 for databases and replicated stores |
| **Fault injection** | Kill, pause or restart a local node, or drop or delay a message, at the window. | R7 |
| **Design walk-through** | For a design with no code, write the interleaving as a sequence diagram, and check that the design allows every step. | Any pattern, design input. Evidence stays strong at most. |

Record the command and the observed output. If the run does not break the invariant, one try proves little: a race may need many runs. Repeat with the window widened, or drop the item to *suspected* and say what was tried.

### Step 9: Report the race list

Default to the chat. Write a file only when asked. Use plain words, and lead with the answer.

1. **Answer**: two or three sentences giving the number of harmful races, the worst one, and the scope reviewed.
2. **Races**: one table, with critical items first, then high, medium and low.
3. **Suspected**: items you could not confirm, each with the check that would settle it.
4. **Dismissed**: benign races and races blocked by a protection, each with the reason or the blocking check. Readers use this list to spot false alarms and protection that rests on a single setting.
5. **Actors and shared state**: the inventory from Steps 2–3, kept short. It shows the reader what was considered.
6. **Limits**: what you reviewed and skipped, the services and paths you could not see, and the one observation that would change the list most.

When the list feeds another tool or agent, write it as JSON first, then check it and print the tables from it with `check_races.py --markdown`. That keeps the tables and the JSON identical. Use one object per item:

| Field | Needed for | Value |
|---|---|---|
| `id` | all | unique, e.g. `R1`, `S1`, `D1` |
| `status` | all | `race`, `suspected` or `dismissed` |
| `location` | all | `file:line`, `file:start-end`, or `doc#section` for a design |
| `shared_state` | all | the state and its key, e.g. `coupon row (code)` |
| `window` | all | the first and last access, e.g. `is_redeemed() at 12 .. mark_redeemed() at 15` |
| `interleaving` | all | a list of at least 2 steps by at least 2 actors, each `"Actor: step"` |
| `invariant` | all | the rule it breaks (or would break) |
| `pattern` | race, suspected | `R1`–`R11` |
| `impact` | race, suspected | `I1`–`I9` |
| `trigger` | race | `outside`, `normal` or `rare` |
| `severity` | race (optional for suspected) | `critical`, `high`, `medium`, `low` |
| `outcome` | race, suspected | what happens |
| `evidence` | race | `reproduced`, `strong`, `weak` (see "Evidence") |
| `reproduction` | race with `reproduced` evidence | the command you ran |
| `to_confirm` | suspected | the check that would settle it |
| `blocked_by` | dismissed | `file:line` of the protection, or of the code that shows it is benign |
| `also_at` | optional | other places with the same root cause |
| `fix_hint` | optional | the kind of fix, e.g. "conditional update", "unique constraint", "idempotency key" (a direction, not a patch) |
| `note` | optional | anything else, e.g. "the only protection is a deployment setting" |

```json
[
  {"id": "R1", "status": "race", "severity": "critical", "pattern": "R1", "impact": "I1", "trigger": "outside",
   "location": "redeem.py:12", "shared_state": "coupon row (code)",
   "window": "is_redeemed() at 12 .. mark_redeemed() at 15",
   "interleaving": ["A: is_redeemed -> false", "B: is_redeemed -> false", "A: credit 10", "B: credit 10"],
   "invariant": "a coupon credits once", "outcome": "two parallel requests credit 20 instead of 10",
   "evidence": "reproduced", "reproduction": "python3 -I repro_redeem.py --parallel 2",
   "fix_hint": "conditional update: UPDATE ... SET used = true WHERE code = ? AND used = false"},
  {"id": "D1", "status": "dismissed", "location": "cart.py:20", "shared_state": "cart row (cart id)",
   "window": "load() at 20 .. save() at 25", "interleaving": ["A: loads v1", "B: loads v1"],
   "invariant": "no added item is lost", "blocked_by": "cart.py:25", "note": "save() checks the version and retries"}
]
```

---

## Scripts

Both scripts are optional. They live in this skill's `scripts/` folder. `SKILL_DIR` below means the folder that holds this `SKILL.md`. They need Python 3.8+ and the standard library only, and they are read-only: they write nothing except the file you pass to `--json`. `-I` runs Python in isolated mode, so files in the reviewed repo cannot change how a script behaves.

### `race_scan.py`: list race candidates

```bash
# Steps 1 and 4: list candidates in a repo, folder or file, with a per-file count.
python3 -I SKILL_DIR/scripts/race_scan.py <path>

# Only some kinds, a longer look-ahead, and every row saved as JSON.
python3 -I SKILL_DIR/scripts/race_scan.py <path> --kind check-then-act,read-modify-write --window 50 --json /tmp/races.json

python3 -I SKILL_DIR/scripts/race_scan.py --help
```

| Option | Use it when |
|---|---|
| `--window N` | Reads and their writes sit far apart (default 30 lines). The look-ahead stops at the next function start. |
| `--kind a,b` | You want only some kinds (see the table below). |
| `--json OUT` | You want every row as JSON to search or count later. |
| `--exclude GLOB` | You need to skip generated code, fixtures or vendored copies. You can repeat it. |
| `--include-tests` | You also want test files (skipped by default). |
| `--needs-wait` | The code runs on a single-threaded event loop and the state is in memory: drop windows with no wait inside (see Step 4.2). |

Each row is `file:line  kind  pattern  detail`. The kinds are:

| Kind | Pattern | What it flags |
|---|---|---|
| `check-then-act` | R1 | An `if` that checks state, then an action within the window |
| `read-modify-write` | R2 | A value read into a variable, changed, then written back |
| `select-then-update` | R2 | An SQL `SELECT` without `FOR UPDATE`, then a write |
| `stale-async-write` | R4 | State set from an async result with no cancel or latest-request check |
| `at-least-once` | R6 | A retry or message handler in a file with no deduplication key |
| `lifecycle` | R9 | A timer, listener, subscription, goroutine or task with no teardown in the file |
| `lock-across-wait` | R10 | A lock still held at an I/O call, sleep or `await` |
| `nested-locks` | R10 | A second lock taken while one is held |
| `shared-mutable` | R10 | Module-level or static mutable state (Python, JavaScript/TypeScript, Java-like, Go) |
| `cache-aside` | R11 | Cache read, then cache set, with no request coalescing |
| `spawn` | none | A place that starts concurrent work. Use it for the actor list in Step 2. |

A row that says `guard seen: X` found a protection keyword near the window. **It does not mean the code is safe.** Check in Step 6 that the guard covers the whole window for every actor. A row is weak evidence on its own: open each one and work through Steps 4–7.

**Known blind spots:**

- The scanner reads lines with patterns, for every language. It does not parse code, follow calls across functions or files, or know which state is really shared.
- It cannot see design-level races: R3, R5, R7 and R8 mostly need reading, as do races across services, and races where the read and the write are in different functions.
- A check on a plain field or variable (`if (!item.id)` before an `await` that sets it) is not flagged. Find those by reading: they are a common source of duplicate work (R6) in async code.
- Frameworks that add locks, transactions or retries implicitly are invisible to it, in both directions.
- `lifecycle` and `at-least-once` look at the whole file, so a teardown or key elsewhere in the file hides the row.

### `check_races.py`: check the list and print the tables

```bash
python3 -I SKILL_DIR/scripts/check_races.py list.json              # check only
python3 -I SKILL_DIR/scripts/check_races.py list.json --markdown   # check, then print the tables
```

The input is a JSON array of items, or an object with an `items` array. The script checks:

- that every field a status needs is present and not empty;
- that ids are unique and statuses known;
- that each interleaving has at least 2 steps by at least 2 different actors, each step written as `"Actor: step"`;
- that locations look like `file:line` or `doc#section`;
- that patterns, impacts, triggers, severities and evidence grades are valid;
- the evidence rules above, and that a rare trigger is rated high at most;
- that races run from critical to low;
- that no value looks like a private key, a long random-looking key, a signed token or a credential value.

Each problem prints as a `FAIL` line. The script exits `0` and prints `OK` when the list passes, and exits `1` when it does not. Fix every `FAIL` and run it again. The tables print only when the list passes.

### Testing the scripts

If you change a script, run its tests first. They use the standard library only and run in about a second. `-B` stops Python from writing `__pycache__` folders into the skill.

```bash
python3 -I -B -m unittest discover -s SKILL_DIR/scripts/tests -t SKILL_DIR/scripts/tests

# Same tests, plus line coverage per script. Exits 1 if a test fails, 2 if coverage is below --fail-under.
python3 -I -B SKILL_DIR/scripts/tests/coverage_report.py --fail-under 95
```

---

## Worked examples

**Backend: check-then-act on a once-only rule (R1, I1, critical).**

```python
def redeem(db, user, code):
    if db.is_redeemed(code):     # check
        return False
    db.credit(user, 10)          # act
    db.mark_redeemed(code)       # act
```

- *Actors*: two requests from the same user. *Shared state*: the coupon row. *Window*: from `is_redeemed` to `mark_redeemed`, with two database calls (yield points) in between.
- *Order*: nothing. No lock, no conditional update, no unique constraint on "redeemed".
- *Interleaving*: `A: is_redeemed → false`, `B: is_redeemed → false`, `A: credit 10`, `B: credit 10`. *Invariant broken*: a coupon credits once.
- *Trigger*: outside. Anyone can send two requests at once. Severity critical.
- *Fix direction*: make the check and the act one atomic step, such as `UPDATE coupons SET redeemed = true WHERE code = ? AND redeemed = false`, and credit only when it changed one row.

**Frontend: stale async result (R4, I3, medium).**

```js
async function onInput(q) {
  const res = await fetch(`/search?q=${encodeURIComponent(q)}`);
  setResults(await res.json());
}
```

- *Actors*: two input events and their two replies. *Shared state*: the results list.
- *Interleaving*: `User: types "ab"`, `User: types "abc"`, `Net: "abc" reply → setResults`, `Net: "ab" reply → setResults`. *Invariant broken*: the screen shows results for the latest query.
- *Trigger*: normal (any slow network). Impact I3. Raise it to high if users act on the results, for example by buying the item shown.
- *Fix direction*: cancel the older request, or ignore replies that don't match the latest query id.

**Design: lease without a fencing token (R7, I2, suspected).**

> "The leader holds a 10-second lease and writes to storage. If the lease expires, another node becomes leader."

- *Interleaving*: `Old leader: pauses 15 s (garbage collection)`, `New leader: takes the lease`, `New leader: writes v2`, `Old leader: resumes and writes v1`. *Invariant broken*: one writer at a time.
- The design does not say whether storage rejects writes from an old lease (a fencing token). Mark it *suspected*, to confirm: "Does storage check a lease or epoch number on each write?"

---

## Anti-patterns

- **Races without invariants.** Many unordered accesses are harmless. Report only those where some order breaks a stated rule, and dismiss the rest with the reason.
- **"The window is too small to matter."** For anything an outside caller can trigger, timing is the attacker's choice. Rate by impact and trigger, not by window size.
- **Trusting the word "transaction" or "lock".** Check the isolation level, which actors share the lock, and whether it covers the whole window.
- **Single-run proof of absence.** One clean run of a race test proves little. Widen the window and repeat, or report it as suspected.
- **Descriptions instead of interleavings.** "Concurrent requests may conflict" is not a finding. Write the schedule.
- **Stopping at threads.** Requests, retries, tabs, consumers, timers, replicas and faults are all actors.
- **Testing on live systems.** Parallel bursts against shared or deployed systems can spend money, corrupt data or cause an outage. Reproduce locally.
- **Fixing during review.** The output is a list. A `fix_hint` names a direction; patches happen elsewhere.
- **Silent drops.** Removing a candidate without marking it *dismissed* or *suspected*.

## Related skills

- [logic-gap-review](https://github.com/pandazy/jankenpon/blob/main/skills/logic-gap-review/SKILL.md) finds missing cases in single-actor logic. Its category C7 (concurrency fault) is where this skill goes deeper.
- [performance-review](https://github.com/pandazy/jankenpon/blob/main/skills/performance-review/SKILL.md) covers contention and redundant work in depth. This skill reports only the wasted work that timing causes (I6, R11).
