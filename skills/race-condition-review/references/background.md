# Background: how and why race-condition-review was built

This note records where the skill came from, which research shaped it, and the choices made along the way. You don't need it to run the skill. Read it before you change the skill, so a change doesn't undo a decision that was made on purpose.

Built on 2026-11-23 in one working session, then tried on a synthetic sample and on one real code base.

---

## 1. How it started

The session began with a research question: "Are there doctoral theses or research papers on how to address race condition bugs in a communication system, frontend or backend?" The answer was a short literature survey, done with the [evidence-driven-reasoning](https://github.com/pandazy/jankenpon/blob/main/skills/evidence-driven-reasoning/SKILL.md) skill. It found three bodies of work (frontend event races, backend and distributed races, and races as security loopholes in web apps) and turned them into a seven-step strategy.

The requester then asked for a skill that:

- reviews **source code, pseudo code or a design** and finds race conditions that cause bugs, wasted resources (memory, CPU and the like), security holes or other severe problems, and **ranks them by severity**;
- follows the shape of the companion [logic-gap-review](https://github.com/pandazy/jankenpon/blob/main/skills/logic-gap-review/SKILL.md) skill;
- is generic and safe to publish as open source: no business, personal, credential or company-internal information, except credit to public research;
- uses the research from the survey as much as possible;
- keeps this background note.

---

## 2. Sources and what each one contributed

Evidence grades follow the skill's own scale. **Verified** means the bibliographic record (title, authors, venue, year) was checked during the session, in a public index or on the author's or publisher's page. The content was **not** re-read: what each work "gave" the skill comes from the survey and from memory of the paper. **Recalled** means cited from memory only. Treat recalled titles, authors and years as leads to check before you cite them.

### Verified

| Source | What it gave the skill |
|---|---|
| Lu, Park, Seo, Zhou, *Learning from Mistakes: A Comprehensive Study on Real World Concurrency Bug Characteristics*, ASPLOS 2008 | The two core patterns, **atomicity violation** (R1, R2) and **order violation** (R3). Its finding that most real concurrency bugs involve only two threads and a few accesses gave Step 4's "look for pairs first". (Recalled detail: the reported share of non-deadlock bugs that are atomicity or order violations is about 97%. Not re-checked.) |
| Petrov, Vechev, Sridharan, Dolby, *Race Detection for Web Applications* (WebRacer), PLDI 2012 | A **happens-before model for the browser**: parsing, events, timers and network replies as actors. This became Step 4.3, the list of what really orders steps. |
| Raychev, Vechev, Sridharan, *Effective Race Detection for Event-Driven Programs* (EventRacer), OOPSLA 2013 | **Harmful vs. benign races.** Event-driven code has huge numbers of unordered accesses, and most are harmless. This became hard rule 4 and Step 5.3: every race needs a broken invariant, and benign ones are dismissed with a reason. |
| Adamsen, Møller, Tip, *Practical Initialization Race Detection for JavaScript Web Applications*, OOPSLA 2017 | **Initialization races** (use before the page or module is ready): R3's first example. |
| Adamsen, Møller, Alimadadi, Tip, *Practical AJAX Race Detection for JavaScript Web Applications*, FSE 2018 | **Out-of-order async replies**: pattern R4, and the "event-order shuffling" row of Step 8. |
| Davis, Thekumparampil, Lee, *Node.fz: Fuzzing the Server-Side Event-Driven Architecture*, EuroSys 2017 | **Server-side event-loop races**, and confirmation by **shuffling the event order**. Step 8's event-order row. |
| Endo, Møller, *Event Race Detection for Node.js Using Delay Injections*, ECOOP 2025 | Confirmation by **injecting delays** at chosen points. Step 8's "forced schedule" row (delay variant). |
| Leesatapornwongsa, Lukman, Lu, Gunawi, *TaxDC: A Taxonomy of Non-Deterministic Concurrency Bugs in Datacenter Distributed Systems*, ASPLOS 2016 | **Distributed races as message timing against faults**: a message, crash, reboot or timeout arriving at an unexpected moment. This became pattern R7, and "faults as actors" in Step 2. |
| Liu, Li, Lukman, Li, Lu, Gunawi, Tian, *DCatch: Automatically Detecting Distributed Concurrency Bugs in Cloud Systems*, ASPLOS 2017 | A **happens-before model across nodes** (message send before receive, and its limits). Step 4.3's message rule. |
| Warszawski, Bailis, *ACIDRain: Concurrency-Related Attacks on Database-Backed Web Applications*, SIGMOD 2017 | **Races as attacks**, and the finding that real applications were exploitable **at their databases' default isolation levels**, often because the invariant is checked in application code. This became pattern R8, the "a transaction is not automatically a protection" rule in Step 3, and the anti-pattern "Trusting the word transaction". |
| Kingsbury, Alvaro, *Elle: Inferring Isolation Anomalies from Experimental Histories*, VLDB 2020 | Confirmation by **recording a history and checking it** against an invariant or isolation level: Step 8's "history check" row. |
| Kettle, *Smashing the State Machine: The True Potential of Web Race Conditions*, Black Hat USA 2023 (PortSwigger research article, read in summary) | Three things. (1) The **predict, probe, prove** method, which became the shape of the procedure. (2) The **single-packet attack**: 20–30 HTTP/2 requests in one TCP packet, median spread about 1 ms in the author's benchmark. This is why the skill says a narrow window is **not** a defence, and why every network endpoint counts as `outside`-triggerable. (3) **Hidden sub-states** and **multi-endpoint** collisions: pattern R5 and the sibling comparison in Step 4.5. |
| Two doctoral theses from Aarhus University: C. Q. Adamsen, *Automated Testing Techniques for Event-Driven and Dynamically Typed Software Applications* (2018); C. S. Jensen, *Automated Testing of Event-Driven Applications* (2015) | The thesis-level treatment of event-race testing that the two OOPSLA/FSE papers above come from. Titles and years verified on the supervisor's student page; not read. |
| G.-V. Saioc, *Detecting and Preventing Goroutine Leaks via Program Analysis*, Aarhus doctoral thesis (2025) | Work that outlives its owner, as a concurrency fault: supports pattern R9 and impact I7. Title verified only. |

### Recalled (not checked this session)

| Source | What it gave the skill |
|---|---|
| Lamport, *Time, Clocks, and the Ordering of Events in a Distributed System*, 1978 | The **happens-before** relation itself, which every detector above builds on. |
| Savage et al., *Eraser* (lock-set race detection), 1997; Flanagan & Freund, *FastTrack*, PLDI 2009; Serebryany & Iskhodzhanov, *ThreadSanitizer*, 2009 | Data races on shared memory (R10), and "race detectors" in Step 8. |
| Musuvathi et al., *CHESS* (systematic schedule exploration), OSDI 2008; Burckhardt et al., *PCT* (randomized scheduling with probabilistic guarantees), ASPLOS 2010 | Bugs have a small **depth** (few ordering constraints), so bounded or random exploration finds most of them. This supports "look for pairs first" and the scheduler row of Step 8. |
| Leesatapornwongsa et al., *SAMC* (semantic-aware model checking of distributed systems), OSDI 2014 | Fault injection at message boundaries: Step 8's fault-injection row. |
| Paleari, Marrone, Bruschi, Monga, *On Race Vulnerabilities in Web Applications*, DIMVA 2008 | Early work on races as web vulnerabilities. Supports pattern R1 and impact I1. |
| Maiya, Kanade, Majumdar, *Race Detection for Android Applications* (DroidRacer), PLDI 2014; Hsiao et al., *CAFA*, PLDI 2014 | Event races on mobile clients, beyond the browser. Supports "client side" in Step 2. |
| Wang et al., *A Comprehensive Study on Real World Concurrency Bugs in Node.js*, ASE 2017 | Server-side event-loop bugs are mostly atomicity and order violations across callbacks. Supports Step 4.2's event-loop rule. |
| Doctoral work from the authors of TaxDC and DCatch (University of Chicago), and Shan Lu's doctoral work (UIUC, 2008) | Probably the thesis-level versions of the papers above. Titles **not** confirmed: the session's searches were blocked. Check before you cite them. |

### Practitioner knowledge (no source)

Pattern **R11 (stampede)**: cache stampedes, thundering-herd reconnects and retry storms. The fixes (request coalescing, jitter, backoff) and impact **I6 (wasted resources)** came from common engineering practice. The requester asked for wasted resources explicitly. No paper was used, and the skill doesn't claim one. The same holds for the lease-and-fencing-token example, a widely discussed distributed-systems pattern.

---

## 3. How the research maps to the skill

| Research idea | Where it lives in the skill |
|---|---|
| Happens-before: a race is two unordered accesses, at least one a write (Lamport; WebRacer; EventRacer; DCatch; FastTrack) | Definitions at the top; Step 4.3–4.4 |
| Harmful vs. benign races (EventRacer) | Hard rule 4; Step 5; the Dismissed list |
| Atomicity and order violations; small bug depth (Lu et al.; PCT) | R1–R3; "look for pairs first" |
| Event races in browsers and servers (WebRacer, EventRacer, AjaxRacer, initialization races, Node.fz, delay injection) | R3, R4, R9; Step 2 client side; Step 4.2 event-loop rule; Step 8 shuffling and forced schedule |
| Distributed timing against faults (TaxDC, DCatch, SAMC) | R7; "faults as actors"; Step 8 fault injection |
| Races as attacks; default isolation is weak (ACIDRain; Kettle; Paleari et al.) | R1, R5, R8; impact I1; the `outside` trigger; "narrow window is not a defence"; Step 3's protection rule |
| Predict, probe, prove (Kettle) | The procedure's structure: Steps 1–4 predict, 5–8 prove |
| History checking (Elle) | Step 8 history check |
| Leaks from work that outlives its owner (goroutine-leak thesis) | R9; impact I7 |

---

## 4. Trade-off decisions

| Decision | Chosen | Given up | Why |
|---|---|---|---|
| Two axes: pattern (R1–R11) and impact (I1–I9) | Mechanism and consequence classified separately | One combined list, as logic-gap-review has | The research classifies races by **mechanism** (atomicity, order, message timing). The requester asked for ranking by **consequence** (bugs, waste, security). One axis can't do both. |
| Trigger axis: `outside`, `normal`, `rare` | Severity = impact × who can trigger it | Rating by window size or probability | Kettle showed that attackers control timing, so window size is a poor guide for anything reachable from outside. `rare` (fault timing) is capped at high, because no caller can choose it. |
| Interleaving required on every item | The checker rejects items without at least 2 steps by 2 actors | Faster writing | The research is consistent that a race is about **order**. A concrete schedule is what makes a finding reproducible and arguable. It plays the role of logic-gap-review's concrete trigger input. |
| Invariant required | Every item names the rule it breaks | Reporting every unordered pair | EventRacer's harmful-race filter. Without it the list is noise. |
| Design input | Allowed, with `doc#section` locations and evidence strong at most | Code-only review | The requester asked for designs and pseudo code. Nothing has run, so a design review can't be *reproduced*. |
| Reproduction | Local only. No parallel requests to shared or deployed systems | Testing against real systems | Safety. A race test is a burst of traffic, and on a live system it can spend money, corrupt data or cause an outage. Kettle's technique is cited for what attackers can do, not as a test to run on shared systems. |
| Fixes | An optional `fix_hint` (a direction, not a patch) | No fix information at all, as logic-gap-review does | Race fixes come from a small, well-known set (atomic or conditional write, constraint, idempotency key, version check, cancellation, coalescing). Naming the direction costs one line and helps triage. Patches stay out of scope. |
| Scanner approach | Line patterns, for all languages, with a per-file count | A parser per language, or reuse of logic-gap-review's node scanner | Standard library only, runs anywhere. Race candidates depend on reads, writes and waits **between** lines, which a node list doesn't capture. Rows are weak evidence by design. |
| Guards in scanner rows | Reported ("guard seen: X"), never used to hide a row (except `FOR UPDATE`, a cancel check, a dedup key or coalescing) | Hiding rows that show a lock or transaction | ACIDRain: a transaction at the default level often does not protect the window. The reader must check the guard. |
| Location format | `file:line` or `doc#section` | `file:line` only | Designs have sections, not lines. |
| Wording | No product, business, vendor, credential-format, company, institution or person names in `SKILL.md` or the scripts | Credit inside the skill | Safe to publish. Credit lives in this note, and only for public research. |
| Description length | Under 1,024 characters | A fuller description | The skill packaging format limits it. |

---

## 5. The reasoning behind the method

1. **A race needs three things:** two actors, shared state, and a window with no enforced order. Steps 2–4 list each one on purpose, because missing any one of them gives a false alarm or a miss.
2. **Order is the whole question.** Happens-before says which orders are guaranteed. Everything else can happen. The skill lists only the guarantees that count (Step 4.3), so "it usually runs first" is never mistaken for an order.
3. **Most unordered pairs are harmless.** A race matters only when some schedule breaks an invariant. Naming the invariant is the oracle, the same role logic-gap-review's consequence categories play.
4. **Timing belongs to the attacker.** Anything an outside caller can reach is rated as if the caller picks the worst interleaving, because they can.
5. **Proof is a forced schedule.** One clean stress run proves little. Forcing the interleaving with a latch or a delay turns a timing bug into a deterministic test.
6. **Limits are stated, not hidden.** Services you cannot see, deployment settings, and framework behaviour are named in Suspected and Limits rather than guessed.

---

## 6. What the trials taught

- **Synthetic sample (two small files, Python and TypeScript, with 12 planted race shapes).** The first run flagged 11. It missed the check-then-act, because the action verb (`credit`) was not in its list, and the verb could only match at the start of a name (`mark_redeemed` failed too). The verb list was widened and now matches anywhere in a name, and all 12 are flagged. The worked example (a coupon redeemed by two parallel requests) was then **reproduced locally** with the forced-schedule method: two threads, an in-memory SQLite database, and a barrier placed between the check and the act. The race credited 20 instead of 10, and the conditional-update fix credited 10.
  - The first attempt at the reproduction crashed, because both threads shared one database cursor. That was itself a race of pattern R10 (a non-thread-safe object shared across threads), inside the test harness. The lesson is now implicit in Step 8: keep the harness itself free of shared mutable objects, or the reproduction proves the wrong race.
- **A small, real, event-driven TypeScript service (about 30 files).** The first scan gave 55 candidate rows (not counting `spawn` rows). Spot checks found three sources of noise, and each was fixed or made filterable:
  - **Optional chaining was read as a ternary** (`a?.b(x, { k: v })`). Fixed in the scanner, with a test.
  - **Windows ran across `switch` cases**, joining a check in one case to an action in another. Fixed: windows now stop at `case` and `default`.
  - **Windows with no wait inside**, on in-memory state in a single-threaded runtime, can't interleave. They became the event-loop rule in Step 4.2 and the `--needs-wait` option.
  - Reading also found a lead the scanner can't see: a field checked before an `await` that sets it, which could post the same message twice if two calls overlap. Whether the calls can overlap was **not** checked, so it stays a lead and is listed as a blind spot. No confirmed harmful race was found in the spot checks. That is consistent with the scanner's rows being weak evidence that only orders the reading.

Things to consider next, none of them decided:

- a check-on-field rule (`if (!x.y)` followed by an `await` that sets `x.y`), if it can be made quiet enough;
- a small helper that generates a forced-schedule test skeleton (barrier between two named steps) for Python and JavaScript;
- adding this review to the development-squad auditor's checklist when a change touches shared state.
