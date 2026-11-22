# Pull request description

Write it with `crystal-clear`. The reviewer should understand what changed and why before reading any code. Save the draft as `<spec root>/<feature>/pr-description.md`.

If the project has a pull request template, the template wins: keep its headings and checkboxes, and put the content below into them.

## Template

```markdown
Closes #<issue>. <!-- or "Related: #<issue>", or drop the line -->

## What
One or two sentences: what the change does, from the user's point of view.
- Optional: up to 4 bullets of the visible changes.

## Why
The motivation: the problem, the request, or the design this change delivers.

## How
- **<principle, as a short sentence>.** What behavior it creates, and why it is safe.
- **<next principle>.** …

## Testing Done
- `<build command>`: N test files, M tests passed (includes lint, typecheck, ...).
- Unit tests cover:
  - <behavior>;
  - <behavior>.
- E2E (<tool>): <specs> passed.
- Coverage of new code: X% lines, Y% branches.
- Manual checks: <keyboard, screen reader, ...>.

## Screenshots
How they were captured: environment, sample data, flags, viewport. Anything odd in them and why.

### 1. <view name>
**Flow:** how to reach it.
**Look for:** what is different between before and after.

| | Light | Dark |
|-|-|-|
| Before | ![<view>, before, light](<url>) | ![<view>, before, dark](<url>) |
| After | ![<view>, after, light](<url>) | ![<view>, after, dark](<url>) |

## Walkthrough video
**Flow:** step → step → step.

<url>
```

### Rules for each section

- **Closes / Related** — `Closes #n` makes GitHub close the issue on merge. Use it only when the pull request fully delivers the issue; otherwise write `Related: #n`.
- **What** — very short. No implementation detail.
- **Why** — the purpose, not the steps.
- **How** — one bullet per principle or behavior, with a bold lead sentence. Explain what the change makes the system do, and why that is right. Leave out code-level detail (class names, function names, line changes) unless the reviewer needs a name to find something.
- **Testing Done** — real numbers from the auditors' reports, not estimates.
- **Screenshots / video** — only when the change has a visual effect. Drop the theme columns the product doesn't have. Drop the "Before" row for a view that is new.

## Sharing evidence

Reviewers can't reach your local servers or files. The evidence must be in the pull request. The `gh` CLI cannot upload images into a pull request body, so pick one of these at G5 and tell the commander which, with your recommendation:

| Option | How | Good for | Cost |
|---|---|---|---|
| **A. Drag and drop** (default) | Open the pull request with `<url>` placeholders. The commander drags each file onto the description in the browser; GitHub hosts it and inserts the link. | Every repository, images and video. | Manual step for the commander. Adds nothing to the repository. |
| **B. Evidence branch** | Commit the files to a separate orphan branch (for example, `dev-squad-evidence`, path `<feature>/<task_id>/`), push it, and link each file by commit SHA: `https://github.com/<owner>/<repo>/blob/<sha>/<path>?raw=true`. | Automation; images. | Adds a branch to the repository for good. On a private repository, only people with access see the images. Videos show as links, not players. |
| **C. Text only** | Put the test and coverage summaries in code blocks under "Testing Done". | Changes with no visual part. | None. |

Whatever the option: on a **public** repository, all evidence is public. Check every file for secrets and personal data first (rule 9).

To make the evidence branch (option B), use a separate worktree so the feature branch is not touched:

```sh
git worktree add --detach <tmp>/evidence
cd <tmp>/evidence
git switch --orphan dev-squad-evidence   # or: git switch dev-squad-evidence, if it already exists on the remote
# copy files to <feature>/<task_id>/, then:
git add <feature> && git commit -m "Evidence for <feature>"
git push -u origin dev-squad-evidence
```

## Posting order (after gate G5)

1. Push the feature branch: `git push -u origin <branch>` (or to the commander's fork).
2. Option B only: push the evidence branch, and put the SHA-pinned links into the draft.
3. Open the pull request:
   `gh pr create --base <base> --head <branch> --title "<title>" --body-file <spec root>/<feature>/pr-description.md`
   Add `--draft` if the commander chose a draft. Add `--reviewer`, `--label` or `--assignee` only with values the commander named.
4. Read it back: `gh pr view <n> --json url,title,body`. Confirm that every section and image link is present. Option A: send the commander the URL and the list of files to drag, with the place for each.
5. Watch the checks (SKILL.md, Phase 6 step 6).
6. Mark it ready (`gh pr ready <n>`) only if the commander asks.

## Updating the description later

`gh pr edit <n> --body-file <file>` **replaces** the whole body. First read the current body (`gh pr view <n> --json body`), keep anything a human added (images the commander dragged in, reviewer notes, checked boxes), then write the merged version. Read it back again.

On a new round of evidence, add the new files and replace only the images that changed.
