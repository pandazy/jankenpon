---
name: performance-review
description: "Evaluate the performance of specified code, then find and rank its performance flaws. For each flaw, state the symptom (what a user, operator or monitor observes, such as slow responses, high CPU, growing memory or timeouts) and the culprit (the exact code, the mechanism and the input or load that triggers it). Classify flaws by type (algorithmic complexity, redundant work, I/O round trips, blocking and contention, memory, data structures, payload size, startup, caching, abstraction overhead), rank them by severity (from impact × frequency × growth) and then by share of the total cost, and grade the evidence. Every fix is checked against coupling and cohesion, so a speed-up does not quietly break module boundaries, and a refactor for modularity does not quietly cost speed. Any language, framework or domain. Read-only: it reports, it does not optimize. Use when asked why code is slow, to review performance, find bottlenecks, hot paths, N+1 queries, memory growth, scalability limits, or 'will this scale?'."
version: 1.0.0
tags: [performance, profiling, bottlenecks, complexity, scalability, latency, memory, code-review, coupling, cohesion, refactoring, trade-offs]
---

# Performance Review

Find where code spends more time, memory or I/O than it needs to. For each flaw, say what someone observes (the **symptom**) and which code causes it and why (the **culprit**). Rank the flaws, and give fixes that keep the code's module boundaries healthy.

- A **symptom** is an observable effect: a slow page or request, high CPU, memory that keeps growing, a timeout, a long queue, a slow start.
- A **culprit** is the cause in code: a `file:line`, the mechanism (for example "one database query per list item") and the trigger (for example "lists over 1,000 items").
- A **hot path** is code that runs often, sits on the critical path of a request, job or frame, or takes a large share of the total cost. Most flaws matter only on hot paths.

Performance and modularity pull in different directions at times. Clean boundaries can add calls, copies and indirection; speed-ups can merge units or share state. This skill treats both as standard engineering goals and makes every trade-off explicit (see "Design tension").

## Hard rules

1. **Read-only.** Do not edit the reviewed code. Write benchmarks and reproductions only in a temporary folder outside the reviewed repo.
2. **Local measurement only.** Profile and benchmark only local code or a local build. Never send load, benchmarks or stress tests to a shared or deployed system. Read existing metrics, traces or logs from such systems only if the user gives them or you already have read access, and do not change anything there.
3. **Culprits are code, never people.** Name the unit, line and mechanism. Do not name or guess authors, teams or groups, and do not use version history to assign blame. History may show *when* code changed, not *who* is at fault.
4. **Context-agnostic.** Assume nothing about the language, runtime, framework, hosting, product or domain. Describe units by their role ("the list loader", "the cache", "the export job"), not by what the business does. Learn conventions, budgets and expected scale from the repo and the user. If the repo states performance targets, judge against them and cite them.
5. **Own words, no copied material.** The flaw types below are standard, public engineering vocabulary. Describe them in your own words. Quote the reviewed code only as far as needed to prove a finding. Do not put secrets, credentials, personal data or large code blocks into the report.
6. **Evidence or label.** Every finding cites `file:line`, a symptom, a culprit with its trigger, and an evidence grade (see "Evidence"). A **critical** or **high** finding must rest on a measurement or on code you read end to end with a known or stated input size, never on a pattern match alone.
7. **Hot path first.** Spend reading and measuring time on hot paths. Off the hot path, severity is capped at low (see "Severity").

---

## Flaw types

Give each finding one type: the one closest to the root cause. Mention others in the culprit text.

| # | Type | Mechanism | Typical culprits | Typical symptoms |
|---|---|---|---|---|
| P1 | **Algorithmic complexity** | Work grows faster than the input. | Nested loops over the same data; a linear search inside a loop; repeated sorting; string building by repeated concatenation in a loop (in languages where strings are immutable); recursion without memoization. | Fine on small data, slow or stuck on large data. Time grows much faster than input. |
| P2 | **Redundant work** | The same result is computed more than once. | A value recomputed in every loop pass; the same parse, regex compile or lookup repeated; derived data rebuilt on every call or render; work done for results nobody uses. | High CPU with no matching increase in useful output; UI that re-renders or lags. |
| P3 | **I/O round trips** | Many small calls where one or a few would do, or calls made one after another that could overlap. | One query or request per item (the "N+1" pattern); chatty calls across a boundary; independent calls awaited in series; no batching. | Latency that grows with item count; many tiny calls in traces; high load on a database or remote service. |
| P4 | **Blocking and contention** | Work waits on something it should not wait on. | Blocking I/O or heavy CPU on an event loop or UI thread; a lock held during I/O; one global lock for unrelated data; a connection or thread pool that is too small or never released. | Throughput that stops growing as load grows; freezes; long tail latency; idle CPU while requests queue. |
| P5 | **Memory and allocation** | More memory, or more allocations, than the work needs. | Loading a whole dataset to use part of it; copying large values between layers; short-lived objects created in a tight loop; collections, listeners or caches that only grow. | Memory that rises over time; frequent or long garbage-collection pauses; out-of-memory crashes. |
| P6 | **Data structure and access** | The structure does not fit how the data is used. | A list used for membership tests; a missing database index for a frequent filter; scattered memory access in a tight loop; a full scan where a key lookup would do. | Slow lookups that grow with size; slow queries on growing tables. |
| P7 | **Payload size** | More data moves than the consumer uses. | Fetching all columns or fields; no pagination or limit; large serialized messages; uncompressed transfers; large client bundles. | Slow transfers; high bandwidth; slow first load; high serialization CPU. |
| P8 | **Startup and loading** | Work done up front that could be done later or never. | Eager initialization of everything at start; large imports for rarely used features; warm-up done on every start instead of once. | Slow start, cold start or first request; slow tests. |
| P9 | **Caching faults** | A cache is missing, ineffective or harmful. | No cache for expensive, stable, repeated results; a key that rarely repeats; invalidation that clears too much; no size limit; many callers rebuilding the same expired entry at once (stampede). | Repeated expensive work; low hit rate; memory growth; load spikes when entries expire. |
| P10 | **Abstraction overhead** | The cost of a boundary or layer itself. | A mapping chain that copies data between near-identical types per call; dynamic dispatch, reflection or proxies in a tight loop; a fine-grained interface that forces many calls per task; serialization between parts that run in one process. | CPU spent in glue code; deep, repeated stacks in profiles; costs that appear in every layer. |

### Severity

Severity follows from **impact × frequency × growth**:

- **Impact** — the cost of one occurrence: time, memory, calls or bytes.
- **Frequency** — how often it runs: per process, per request, per item, per frame.
- **Growth** — how the cost scales with input or load: constant, linear, or worse. Growth counts only when the input can really be large. If code caps the input small (for example a list capped at 10 items), treat the growth as constant and cite the cap.

| Severity | Rule of thumb |
|---|---|
| **Critical** | On a hot path, it already breaks a stated target or causes failures (timeouts, out-of-memory, outages), or its growth is worse than linear on input that can be large. |
| **High** | On a hot path, it costs a clear share of the total (as a rule of thumb, 20% or more of the time or memory), or it grows linearly in round trips or memory with an input that can be large. |
| **Medium** | On a hot path with a small share; or a flaw that will become high at an expected, stated scale. |
| **Low** | Off the hot path, or a small constant cost. |

You may adjust by **one level at most**; say why when you do. **Raise** it when it also loads a shared resource (a database, a remote service), so one caller slows others. **Lower** it when only rare input or an unusual configuration triggers it. Never raise an off-hot-path flaw above low.

Within one severity, rank by share of the total. Speeding up a part that takes a fraction `f` of the time by a factor `s` saves at most `f × (1 − 1/s)` of the total. A 10× speed-up on 5% of the time saves at most 4.5%.

---

## Evidence

Grade every finding:

- **Measured** — you profiled or benchmarked it locally, or read existing metrics, traces or profiles, and saw the cost.
- **Strong** — you read the code from the entry point to the culprit, worked out its cost (for example "one query per item, no batching"), and know the input size or frequency from code, config, data or the user.
- **Weak** — you read the culprit but not the path, or the input size is unknown; or the item comes from a pattern match or another tool's claim.
- **Guess** — no supporting observation. Say what would confirm it.

| Evidence | Allowed status |
|---|---|
| Measured, strong | flaw, at any severity |
| Weak | flaw at medium or low only; otherwise suspected |
| Guess | suspected only |

Before you report, re-check every critical and high flaw. If it rests on weak evidence, read the path, find the input size or measure it. If you cannot, mark it *suspected* (medium at most) with the check that would settle it. If a later observation contradicts a finding, change or drop it. Never keep both versions.

---

## Design tension

For every finding, record its **boundary relation**:

| Relation | Meaning | Fix direction |
|---|---|---|
| **Independent** | The flaw sits inside one unit and has nothing to do with its boundaries. | Fix it inside the unit. Coupling and cohesion do not change. |
| **Boundary-caused** | The flaw comes from how units are split or connected (P3 and P10 often are). | Change the **shape** of the boundary, not its existence (see the list below). |
| **Fix crosses a boundary** | The obvious fix would merge units, share mutable state, or reach into another unit's internals. | Prefer a fix that keeps the boundary. If none is good enough, state the trade-off and let the reader choose. |

Fixes that keep boundaries, in order of preference:

1. **Fix inside the owner.** Change the algorithm, structure or query inside the unit that owns the work. Callers do not change.
2. **Widen the contract, keep the owner.** Add a batch or bulk method (`getMany(ids)` beside `get(id)`), a field selection, or pagination to the existing interface. This keeps data coupling and cuts round trips.
3. **Cache behind the owner.** Put a cache inside the unit that owns the data, with one owner for writes and invalidation. That is encapsulated module state, not shared global state.
4. **Move the work to the data.** Move a filter, join or aggregate into the unit (or the database) that already holds the data, instead of moving the data to the work.
5. **Remove a layer that does no work.** A pass-through layer or mapping chain that adds cost and no value is also over-engineering. Removing it helps both goals.

Fixes that cost modularity: inlining another unit's logic, sharing a mutable structure between units, bypassing an owner to read its storage directly, or merging units. Recommend one only when the finding is critical or high, **measured**, and no fix above is enough. Then state the coupling or cohesion type it creates (for example "this adds common coupling: two units would write the same state", using the coupling-cohesion-review skill's terms when that skill is available) and what it would cost to maintain.

The reverse also holds. When the reviewed code is a refactor done for modularity, check whether it added a flaw on a hot path: new round trips across a new boundary, new copies between layers, or indirection in a tight loop. Rate such costs with the Severity table like any other flaw. Off the hot path they are low at most, so say so and keep the refactor.

---

## Procedure

### Step 1 — Scope, goal and scale

1. Get the **scope** from the request: a file, a function, a diff, a feature or a whole repo.
2. Get the **goal**: the symptom the user reports ("the export is slow") or a general review. A reported symptom comes first: trace it to its culprits before anything else.
3. Find the **scale and targets**: expected input sizes, request rates, data growth, and any stated budget (latency, memory, start time). Look in docs, config, tests, fixtures, limits in code and existing monitoring. If none is stated, ask the user, or state your assumption in "Limits".
4. Read the repo's docs for performance notes, known limits, and deliberate trade-offs.

### Step 2 — Find the hot paths

1. List the **entry points** in scope: request handlers, jobs, consumers, CLI commands, render functions, loops that run per frame or per message.
2. For each, estimate **frequency** (per request, per item, once at start) and **input size**.
3. If a profile, trace or metrics already exist, use them first. They are the strongest guide to where time goes.
4. If the code can run locally with safe sample input, profile it with the platform's standard profiler (Step 5). Otherwise rank by reading.

Rank the code to read in this order: code inside loops over large or growing input; code that does I/O; code on every request or frame; code that recently changed in the area of a reported symptom.

### Step 3 — Inspect for flaws

For each hot path, walk the code and check every type, P1–P10. Ask at each loop, call and allocation:

1. **How many times does this run** for one entry-point call, as a function of input size? (P1, P2, P3)
2. **Does it wait**, and on what? Could the wait overlap with other work, or move off a critical thread? (P3, P4)
3. **What does it allocate or copy**, and is it released? (P5)
4. **Does the structure fit the access pattern?** Lookups, scans, indexes. (P6)
5. **How much data crosses each boundary**, and how much of it is used? (P7, P10)
6. **What runs before the first useful result?** (P8)
7. **Is the same expensive result computed again**, and is any cache bounded and correctly invalidated? (P2, P9)

Look through layers. An innocent-looking call (`getUser()`, a property access, an ORM relation, a framework hook) can hide a query, a lock or a copy. Open the callee before deciding.

### Step 4 — Write the symptom and the culprit

For each flaw:

1. **Symptom** — what an observer sees, at what scale: "The list page takes about 3 s with 500 items and gets slower as items grow."
2. **Culprit** — `file:line`, the mechanism, and the trigger: "`loader.js:42` calls `fetchDetail()` once per item inside the loop, so 500 items make 501 queries."
3. **Chain** — when the symptom and the culprit are far apart, list the steps between them: entry point → caller → culprit.

One root cause is one finding, even if it appears on several lines. List the other places in `also_at`. If several culprits produce one symptom, list each as its own finding and link them through `related`, ranked by share.

### Step 5 — Measure and confirm

For every critical and high flaw, and for others when it is cheap, measure when the code can run locally with safe sample input (Step 2). When it cannot, keep the grade the reading supports, and name the missing measurement in "Limits".

1. Build the smallest local reproduction: a micro-benchmark, a profile of one entry point, or a query count. Keep it outside the reviewed repo (hard rules 1 and 2).
2. Measure fairly:
   - Use realistic input sizes, and at least two sizes to see growth (for example 100 and 10,000 items).
   - Warm up first in runtimes that compile or cache at run time.
   - Repeat, and report the median and the spread (or p95/p99 for latency), not a single run.
   - Change one thing at a time. Compare against the current code, not against an ideal.
   - Count operations (queries, calls, allocations) as well as time. Counts are stable across machines; times are not.
3. Record the command and the observed numbers.
4. If the result differs from your expectation, re-rate, re-type or drop the finding.

### Step 6 — Rank and plan fixes

1. Sort findings by severity, then by share of the total cost.
2. For each critical, high and medium flaw, give the **cheapest fix that removes most of the cost**, with its cost (small / medium / large), its risk, and the expected gain. Use measured numbers when you have them; otherwise say "estimated". A low flaw gets a one-line hint, or none.
3. Fill in the boundary relation, and choose the fix by the rules in "Design tension".

### Step 7 — Over-optimization check

Speed is a means, not a goal. Check your fixes, and any existing optimizations in the code, for these signs:

- **Off the hot path** — an optimization of code that runs rarely or takes a small share.
- **Complexity for little gain** — a hand-rolled structure, manual pooling or a hand-tuned loop that saves little and is hard to read or test.
- **Unbounded or unowned cache** — a cache added for speed with no size limit, no clear owner or no invalidation rule. It trades a P2 flaw for a P5 or P9 flaw.
- **Concurrency without need** — parallel or asynchronous code added where the work is small, which adds ordering bugs for no gain.
- **Modularity spent for speed** — an existing shortcut (shared state, inlined logic, a bypassed owner) that no measurement justifies.

Revise your own fixes that show these signs. Mark only existing code **⚠ over-optimized**, and recommend the simpler shape. When simplicity and a small speed-up conflict, simplicity wins.

---

## Report

Default to the chat. Write a file (Markdown or HTML) only when asked. Write in plain words: answer first, short active sentences, one term per idea, each technical term defined the first time it appears. Do not add headings or phrases about how the report is written.

Structure:

1. **Answer** — two or three sentences: overall health, the worst flaw (symptom and culprit), and the one change that helps most.
2. **Terms used** — one line each for symptom, culprit, hot path, the severities, the evidence grades and the boundary relations.
3. **Hot paths** — the entry points reviewed, with frequency and input size.
4. **Findings** — one table, critical first, then high, medium and low.
5. **Suspected** — items you could not confirm, each with the check that would settle it.
6. **Design tension** — the findings whose fix touches a boundary, and any modularity refactor that added cost on a hot path, with the trade-off in one line each.
7. **⚠ Over-optimized** — from Step 7.
8. **Limits** — what you reviewed and skipped, the scale you assumed, what you could not measure, and the one measurement that would change the ranking most.

Finding table columns:

| # | Severity | Type | Symptom | Culprit (`file:line`, mechanism, trigger) | Evidence | Boundary relation | Fix (cost, risk, expected gain) |
|---|---|---|---|---|---|---|---|
| F1 | High | P3 I/O round trips | The list page takes about 3 s at 500 items and grows with item count. | `loader.js:42` fetches details once per item in a loop: 500 items make 501 queries. | Measured — query count 501 at 500 items, 11 at 10. Not raised: the effect on other database users is not known (see "Limits") | Boundary-caused | Add `fetchDetails(ids)` to the detail service and call it once (small; low risk; about 500 fewer queries) |

Put the chain, the `also_at` places and any `related` findings in the culprit cell when they exist.

When the list feeds another tool or agent, also give it as JSON, one object per item:

| Field | Needed for | Value |
|---|---|---|
| `id` | all | unique, e.g. `F1`, `S1`, `O1`; the same id as the table's `#` column (suspected and over-optimized items use their id in their own report section) |
| `status` | all | `flaw`, `suspected` or `over-optimized` |
| `location` | all | `file:line` or `file:start-end` |
| `type` | flaw, suspected | `P1`–`P10` |
| `severity` | flaw (optional for suspected) | `critical`, `high`, `medium`, `low` |
| `symptom` | flaw, suspected | what an observer sees, at what scale |
| `mechanism`, `trigger` | flaw, suspected | the culprit's mechanism and the input or load that triggers it |
| `chain` | optional | entry point → caller → culprit |
| `evidence` | all | `measured`, `strong`, `weak`, `guess` (see "Evidence") |
| `measurement` | evidence `measured` | the command or source, and the numbers |
| `boundary_relation` | flaw, over-optimized | `independent`, `boundary-caused`, `fix-crosses-boundary` |
| `fix` | flaw (critical to medium), over-optimized | `change`, `cost`, `risk`, `gain` (mark the gain "estimated" when not measured) |
| `to_confirm` | suspected | the check that would settle it |
| `also_at`, `related`, `note` | optional | other places with the same cause; ids of findings that share a symptom; anything else |
