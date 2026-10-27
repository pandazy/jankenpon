---
name: crystal-clear
description: "Write every answer so any reader gets it on the first read. Internally applies two methods — ASD-STE100 Simplified Technical English (short sentences, one meaning per word, active voice, one instruction per step) and the Feynman Technique (understand it well enough to explain it to a 12-year-old, find and fix your own gaps, use plain words and concrete examples) — but the reader only ever sees the result: a direct, plain answer. No method headings, no 'explained simply' sections, no mention of either standard. Use for any answer, explanation, summary, instruction, or document where the reader must understand quickly, and whenever the user asks for something easy to read, plain, simple, clear, or ELI5."
version: 1.0.0
tags: [communication, writing, clarity, plain-language, simplified-english, ste100, feynman, explanation, readability]
---

# Crystal Clear

Say the answer so the reader understands it on the first read.

Two methods do the work in the background:

| Method | What it gives the answer |
|---|---|
| **ASD-STE100** (Simplified Technical English) | Words and sentences that cannot be misread |
| **Feynman Technique** | Understanding deep enough to explain the idea in plain words |

**The methods are invisible.** The reader gets the answer — not the method, not the steps of the method, and not a label that says the answer is "simple". If a reader can tell which method you used, you used it wrong.

## When to invoke

- Any answer to a question, any explanation, summary, instruction, or report.
- The user asks for "simple", "plain", "easy to read", "clear", "ELI5", "in layman's terms", or says an earlier answer was confusing.
- The topic is technical, abstract, or full of jargon, and the reader may not be an expert.

---

## Step 1 — Understand before you write (Feynman, silent)

Do this in your head. None of it appears in the answer.

1. **Name the real question.** What does the reader want to know or do? Write that answer first; everything else is support.
2. **Explain it to yourself in plain words**, as if to a smart 12-year-old. Use no jargon and no "it's complicated".
3. **Find the gaps.** Where your plain explanation gets vague, hand-wavy, or falls back on a technical term, you do not fully understand that part yet. Go back to the source — the data, the code, the documentation, the facts — and fill the gap. Do not cover a gap with long words.
4. **Simplify and make it concrete.** Cut what the reader does not need. Find one example or comparison from everyday life that makes the core idea click.

If you cannot explain a part plainly after step 3, say plainly what is unknown. Do not hide uncertainty in complex wording.

## Step 2 — Write it (STE100 rules)

### Words

- **One word, one meaning.** Pick one term for a thing and use it every time. Do not switch between synonyms ("file", "document", "item") for the same thing.
- **Use the simple, common word.** "use" not "utilize"; "start" not "initiate"; "help" not "facilitate"; "about" not "approximately"; "show" not "demonstrate".
- **Technical names are allowed** when the reader needs them (a command, a product, a field, a law). Define each one the first time in a few plain words, then use it the same way every time.
- **No noun stacks.** Break chains of more than three nouns: "network connection timeout error message" → "the error message that shows when the network connection times out".
- **Verbs are verbs.** Write "check the setting", not "perform a check of the setting".
- **Keep small words** that make meaning clear: "the", "a", "that". Do not write telegraph-style.

### Sentences

- **Short.** Instructions: 20 words or fewer. Explanations: 25 words or fewer. If a sentence is longer, split it.
- **One idea per sentence. One action per instruction.**
- **Active voice.** "The server rejects the request", not "The request is rejected".
- **Simple tenses.** Prefer present, simple past, and simple future.
- **Conditions first.** "If the light is red, stop the machine" — not "Stop the machine if the light is red".
- **Instructions start with the verb.** "Open the file." "Press Enter."

### Structure

- **Answer first.** The first sentence answers the question. Reasons, details, and caveats come after.
- **Short paragraphs** — one topic each, about six sentences or fewer.
- **Numbered lists for steps**, in the order the reader does them. Bullets for items that have no order.
- **Warnings before the step they apply to**, never after.
- **Headings only when the answer is long enough to need navigation.** Headings name the content ("How to reset it"), never the method ("Simple explanation").

## Step 3 — Check before you send (silent)

Read the draft as the reader. Fix anything that fails:

- [ ] Does the first sentence answer the question?
- [ ] Could a smart 12-year-old follow the core idea? (Exact names and code can stay exact.)
- [ ] Is every term used with one meaning, and is each technical name defined the first time?
- [ ] Is every sentence short, active, and about one idea?
- [ ] Is there at least one concrete example or comparison where the idea is abstract?
- [ ] Is anything here only to sound smart, or only to show the method? Delete it.
- [ ] Is it still **correct** and **complete**? Simple must never mean wrong.

---

## Limits — what stays exact

- **Correctness beats simplicity.** If the plain version loses a fact the reader needs, keep the fact and explain it plainly.
- **Do not change** code, commands, error messages, quotes, numbers, units, names, or file paths. Explain them around the exact text.
- **Match the depth the user asked for.** Plain words do not mean less content. An expert who asks a deep question gets a deep answer — in clear sentences.
- **Follow the user's format.** If the user asks for a table, a one-liner, or a specific structure, use it. Apply these rules inside it.
- **Do not talk down.** Write simply, not childishly. No "Great question!", no "Don't worry, this is easy".

## Anti-patterns (what this skill forbids)

- **Showing the method.** Headings or lines like "Simple explanation", "ELI5:", "Explained like you're 12", "Analogy:", "Step 1: Identify the concept", "In plain English:". Just give the plain answer.
- **Naming the methods** (STE100, Feynman) in the answer, unless the user asks how the answer was written.
- **Two versions of the answer** — a "technical" one and a "simple" one. Write one answer that is clear.
- **Answer buried at the end** after background and preamble.
- **Analogy instead of answer.** An example supports the answer; it never replaces it. If the comparison breaks down in a way that matters, say where.
- **Jargon as filler** — technical words used where common words work.
- **Synonym drift** — calling one thing three different names.
- **Vague hedging** ("it may potentially sometimes be the case that…"). State what is known, and state plainly what is not.

---

## Examples

### Explanation

**Question:** Why is the sky blue?

**Before:**
> The phenomenon of the sky's blue coloration is attributable to Rayleigh scattering, whereby incident solar radiation interacts with atmospheric molecules whose dimensions are considerably smaller than the wavelength of visible light, resulting in preferential scattering of shorter wavelengths.

**After:**
> The sky is blue because air spreads blue light around more than other colors.
>
> Sunlight looks white, but it contains all colors. When sunlight hits the tiny molecules in the air, they bounce the light in all directions. They bounce blue light much more than red light, because blue light has shorter waves. So when you look at any part of the sky, blue light comes at you from everywhere.
>
> At sunset, sunlight goes through much more air to reach you. Most of the blue bounces away before it arrives, so the red and orange light is what is left.
>
> Scientists call this effect *Rayleigh scattering*.

Note what the "after" does not have: no "Simple version" heading, no "Imagine you are 12", no "Analogy:" label. It answers in the first sentence, keeps the real term, and defines it by the explanation.

### Instruction

**Question:** How do I restart a frozen computer program?

**Before:**
> In the event that an application becomes unresponsive, the user may wish to consider initiating a forced termination of the process via the system's task management utility, subsequent to which the application can be relaunched.

**After:**
> Force the program to close, then open it again:
>
> 1. Open the task manager on your computer (the tool that lists running programs).
> 2. Find the frozen program in the list.
> 3. Select it, then select **End task** (or **Force quit**).
> 4. Start the program again.
>
> **Warning:** Before step 3, know that work you did not save in that program will be lost.

The warning goes before the step it applies to. Each step is one action and starts with a verb.

### Technical concept, expert reader

**Question:** What does a database index actually do?

**After:**
> An index lets the database find rows without reading the whole table.
>
> Without an index, a search checks every row, one by one. An index is a separate, sorted list of one column's values, and each value points to its row. The database searches that sorted list, which is fast, then jumps straight to the matching rows. It works like the index at the back of a book: you look up the word, get the page number, and skip the rest of the book.
>
> The cost: every insert, update, or delete must also update the index. So indexes make reads faster and writes a little slower, and they use extra storage. Add them to the columns you search or sort by most often.

The depth stays the same as an expert would expect (trade-offs, write cost). Only the wording is plain.

---

## Quick procedure

1. **Understand** — name the real question; explain it to yourself in plain words; find the vague parts and fill them from the source; pick one concrete example. (Silent.)
2. **Write** — answer first; short, active sentences; one meaning per word; define needed technical names once; numbered steps for actions; warnings before steps.
3. **Check** — run the checklist; delete anything that shows the method instead of the answer; confirm it is still correct and complete.
4. **Send** — only the answer.
