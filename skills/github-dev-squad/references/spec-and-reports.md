# Spec files and HTML reports

All files live under the spec root the commander chose in Phase 0, outside the project's history (rule 6). The layout is a plain spec-driven one: requirements, then design, then tasks.

```
<spec root>/<feature>/
├── requirements.md
├── design.md
├── tasks.md
├── report-requirements.html
├── report-design.html
├── report-tasks.html
├── report-refactor-<group>.html
├── pr-description.md
└── evidence/<task_id>/...
```

## requirements.md

```markdown
# Requirements — <feature>

**Repository:** owner/name (public | private) — **Base:** main — **Branch:** <feature> — **Issue:** #123 or none

## Introduction
What the change is and why, in 2–4 sentences.

**Site type:** new house | old house — one-line reason.

## Requirements

### R1 — <short name>
**User story:** As a <role>, I want <capability>, so that <benefit>.

**Acceptance criteria**
1. R1.1 — WHEN <event> THE SYSTEM SHALL <response>.
2. R1.2 — IF <condition> THEN THE SYSTEM SHALL <response>.
3. R1.3 — WHILE <state> THE SYSTEM SHALL <response>.

## Out of scope
- …

## Open questions
- Question — recommended answer.
```

EARS patterns: `WHEN` (event), `IF … THEN` (unwanted case), `WHILE` (state), `WHERE` (optional feature), or a plain `THE SYSTEM SHALL` (always true). One response per criterion.

## design.md

```markdown
# Design — <feature>

## Overview
## Project facts
Build, lint, test, e2e commands; coverage threshold; e2e tool; CI checks on pull requests; pull request template; commit and branch conventions; expected scale and performance targets (or the assumption made); conventions that matter.
## Architecture
Components, data flow, diagram.
## Components and interfaces
## Error handling
## Testing strategy
Unit / integration / e2e; which requirement each layer proves.
## Risks
Each with its evidence grade.
## Evidence
| Claim | Grade | Source |
|---|---|---|
```

## tasks.md

```markdown
# Tasks — <feature>

## Group 1 — <milestone>
- [ ] 1.1 <task> — _R1.1, R1.2_ — files: a.ts, a.test.ts — after: —
- [ ] 1.2 <task> — _R2.1_ — files: b.ts — after: 1.1

## Parallel plan
| Wave | Tasks | Why they don't conflict |
|---|---|---|
| 1 | 1.1, 2.1 | different files, no dependency |

## Critical alerts
| # | Phase / task | Kind (performance / coupling / cohesion) | Where | Issue | Decision (approved / declined, and why) | Result |
|---|---|---|---|---|---|---|

## Review rounds
| Round | Comment (link) | Sort (change / question / disagree) | Action | Result |
|---|---|---|---|---|
```

## HTML reports

One report per phase. Each report is **one self-contained `.html` file**: inline CSS, diagrams as inline SVG, no external scripts, fonts or CDNs. It must open offline in any browser.

### Content

Write the text with `crystal-clear`. Each report has these parts, in order:

1. **Header** — feature, phase, date, status (`awaiting review`).
2. **The answer** — 2–4 sentences: what this phase decided or found.
3. **Decisions for the commander** — numbered, each with a recommendation. This is the part the commander must act on, so it comes before the detail.
4. **Body** — by phase:
   - *Requirements:* a requirement table (ID, criterion, priority), out of scope, open questions.
   - *Design:* the architecture diagram, components, an evidence table with colored grade badges, and risks.
   - *Tasks:* a task table (ID, task, requirements, files, depends on), the waves as columns, and a dependency diagram.
   - *Refactor:* a table of findings (🔴/🟡/🟢 with score, where, why it hurts, fix — as changed by the performance check, performance effect, performance verdict) and a checkbox column the commander can use when replying. Below it, a **Rejected suggestions** table (suggestion, the critical performance flaw it would cause, reason, evidence) with no checkbox, then the critical alerts raised in this phase and their decisions.
5. **Traceability** (design and tasks) — requirement → design section → task. Show a gap in red.

### Style

- Readable width (about 960px), system font stack, light background, good contrast.
- Color only to carry meaning: green = ok/measured/reproduced/strong/low, amber = weak/yellow/medium, red = gap/guess/red/high/critical. Always pair color with a text label.
- Diagrams: simple boxes and arrows in SVG. Keep labels short. If a diagram needs more than about 12 boxes, split it.

### Delivery

Give the commander the absolute path, and a chat summary that holds the answer and the decisions. A commander who doesn't open the file must still be able to decide from the summary alone.
