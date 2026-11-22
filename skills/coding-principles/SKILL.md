---
name: coding-principles
description: "Basic principles for writing or changing any code: Occam's Razor (fewest assumptions and moving parts), KISS (the simplest thing that works), and non-intrusiveness (in an existing project, learn its patterns and style, follow them consistently, and ASK before changing anything that breaks the first two principles). Use whenever you write, edit, refactor, or review code — especially in a codebase you did not write."
version: 1.0.0
tags: [coding, principles, simplicity, kiss, occams-razor, consistency, style, refactoring]
---

# Coding Principles

Three rules. They apply to every change, large or small.

## 1. Occam's Razor — fewest assumptions

Pick the solution that needs the fewest new parts and the fewest guesses.

- Explain a bug with the simplest cause that fits **all** the evidence before you reach for an exotic one.
- Do not add a layer, abstraction, config option, dependency, or file unless the task needs it now.
- Do not design for requirements nobody stated. "We might need it later" is not a need.
- If two solutions both work, choose the one with less to explain.

## 2. KISS — keep it simple

Write the plainest code that solves the problem correctly.

- Straight-line code beats clever code. A reader should understand it on the first read.
- Prefer the language's and framework's built-in tools over hand-rolled ones.
- Small functions, clear names, obvious data flow. No indirection without a reason.
- Delete code you no longer need. Do not leave dead paths "just in case".
- Simple never means wrong: keep the error handling, edge cases, and tests the task needs.

## 3. Don't be intrusive — fit into the existing project

When you work in code that already exists, you are a guest. Change only what the task needs.

### a. Understand the project's patterns first

Before you write code, read nearby and similar code. Learn:

- Naming (files, functions, variables, tests).
- Structure (where things live, how modules split, how they import each other).
- Idioms (error handling, logging, async style, state management, test style, helpers already available).
- Formatting and lint rules (the config files decide, not your taste).

Search for an existing helper before you write a new one.

### b. Follow them — be consistent

- New code looks like the code around it. A reader must not be able to tell which lines you wrote.
- Use the project's existing helpers, libraries, and conventions — even if you would choose differently in a new project.
- Keep the diff minimal: no drive-by reformatting, renames, reordering, or "cleanups" outside the task.
- Match the scope you were given. Fix the bug; do not redesign the module.

### c. Ask before you deviate

If an existing pattern breaks rule 1 or rule 2 (needlessly complex, over-abstracted, clearly fragile):

1. **Do not change it on your own.** Follow the existing pattern for the task, or stop if following it would cause a real problem.
2. **Tell the user**: what the pattern is, where it is (`file:line`), why it breaks Occam's Razor or KISS, and the simpler alternative.
3. **Wait for a clear yes** before you refactor it. Approval for one change does not cover others.

Consistency wins by default. Only the user can decide that a simpler, inconsistent change is worth it.

## Quick check before you finish

- [ ] Is every new part needed for this task? (Occam)
- [ ] Is this the simplest code that works correctly? (KISS)
- [ ] Does it look like the code around it, using the project's own helpers and style? (Consistency)
- [ ] Does the diff touch only what the task needs? (Non-intrusive)
- [ ] Did I ask before changing any existing pattern? (Ask first)
