---
name: create-ticket-pr
description: >
  Help Canonical Web Engineering contributors take a Jira ticket or an
  already-edited change through investigation, approval, testing, commit,
  push, and a GitHub PR. Use the team's conventions while adapting to the
  target repository's instructions and available tooling.
metadata:
  version: "1.2"
---

Turn one Jira ticket or already-edited change into one PR in one repo. A
ticket is optional for already-edited changes. Never skip straight to
committing — always get explicit approval on the diff first, and never
invent a PR number, ticket, or demo link.

Follow any applicable `AGENTS.md`, contribution guide, PR template, and
repository-specific instructions before applying team defaults below. Do
not assume every repo has the same tooling, labels, or demo environment.

**Writing style for anything a human reads** (commit messages, PR bodies,
code comments): optimize for a reviewer skimming on a phone, not a
reader who wants the full investigation writeup. Prefer short bullets
over prose paragraphs. Every line should earn its place — cut mechanism
detail a reviewer doesn't need to approve the change (e.g. "registered as
`image` in the Jinja context", exact Cloudinary flag names) unless they
asked, or it's genuinely surprising. State the fix and its user-visible
effect in as few words as possible; put anything longer (root-cause deep
dive, alternatives considered) in a PR comment or linked doc, not the
main description.

## Progress checklist

- [ ] Entry point identified (ticket-first vs. code-already-edited) and repo
      confirmed
- [ ] On the right branch, cut from an up-to-date `main` (or already on a
      working branch — see Entry points)
- [ ] Investigated the actual code before writing a fix
- [ ] Fix implemented
- [ ] Asked the user whether tests are needed for this change; written/updated
      them if yes
- [ ] Diff summarized and **explicit user approval** obtained before commit
- [ ] Committed with the `Fix/Feat/Bug/Test/...: <message>` format
- [ ] Pushed with `-u origin <branch>`
- [ ] PR opened with the repository's PR template, or the team template below
- [ ] Applicable review labels added, if required by the repository
- [ ] Applicable demo links added to the PR's QA section
- [ ] Reported the real PR URL back to the user (never fabricate one)

## Entry points

Figure out which of these applies before doing anything else — ask the
user only if it's genuinely ambiguous (e.g. they mention a ticket but
`git status` also shows edits).

### A. Ticket-first (no code written yet)

1. Fetch the ticket using the available Jira tool. Read its title,
   description, and component/labels to identify **which repo** it belongs
   to. If that is unclear, ask the user which repo before touching
   anything — don't guess at a checkout path.
2. In that repo: `git status --short` (must be clean — see Gotchas if
   not), then sync `main` (see "Syncing main" below).
3. Branch: `git checkout -b <TICKET-ID>-<kebab-case-summary>`, derived
   from the ticket title.
4. Continue at **Investigate → Fix → Test? → Approve → Commit → PR**
   below.

### B. Code-already-edited

The user has already made changes (`git status --short` is non-empty)
before asking for a PR.

- **B1 — currently on `main`:** if a Jira ticket is linked, use its key
  for the branch name and PR's Issue/Card section. If no ticket is linked,
  use a short descriptive branch name and state that no issue is linked
  in the PR's Issue/Card section. Then:
  1. Stash the edits if `git pull` would conflict with them:
     `git stash push -u -m "wip before <short-description>"`.
  2. Sync `main` (see "Syncing main" below).
  3. Branch: `git checkout -b <TICKET-ID>-<kebab-case-summary>` when a
     ticket exists, otherwise use `<kebab-case-summary>`.
  4. Restore the edits: `git stash pop` (resolve conflicts if any arise).
  5. Continue at **Investigate → Fix → Test? → Approve → Commit → PR**.
- **B2 — already on a non-main branch:** assume this branch is the
  working branch. Use the linked ticket key if available; otherwise
  proceed without a ticket reference. Skip straight to
  **Investigate → Fix → Test? → Approve → Commit → PR** — do not re-sync
  main or re-branch on top of work already in progress.

### Syncing main

```
git fetch origin --quiet
git checkout main
git pull --ff-only origin main
git log -1 --oneline main
git log -1 --oneline origin/main   # must match before branching
```

## Investigate → Fix → Test? → Approve → Commit → PR

1. **Investigate before writing code.** Read the actual file(s) involved —
   don't assume the fix from the ticket description alone; confirm the
   root cause in the code first.
2. **Implement the fix.**
3. **Always ask whether tests are needed** — don't assume either way.
   Some fixes (copy tweaks, template markup, one-off scripts) genuinely
   don't warrant new tests; others do. Ask explicitly, e.g. "Should I add
   tests for this?", optionally noting what you'd cover if the answer is
   yes. Only write/update tests (following the repo's existing
   conventions/location — check [AGENTS.md](AGENTS.md) or equivalent for
   the test command) if the user confirms.
4. **Ask for approval before committing.** Summarize the diff (files
   changed + what changed, and whether tests were included or
   deliberately skipped per the user's answer above) and explicitly ask
   the user to confirm before running `git commit`. Never commit without
   an explicit go-ahead.
5. **Commit**, once approved — see Commit message format below.
6. **Push:** `git push -u origin <branch-name>`.
7. **Open the PR** — see PR description template and labels below.
8. **Add demo links when applicable** — see Demo links below.
9. **Report back** the real PR URL, branch name, and labels applied when
   applicable. Never fabricate a PR number or demo link.

## Commit message format

`<Type>: <crisp but sufficient message>` — one line, no period, capitalized
type, describes the user-visible change not the mechanics:

```
Fix: prevent pixelated blog card thumbnails by routing images through image_template
Feat: add Ubuntu Pro chip to hero on Livepatch page
Bug: correct off-by-one in pagination on tag pages
Test: cover blog-card image_template output with a VCR cassette
```

Valid types: `Fix`, `Feat`, `Bug`, `Test`, `Chore`, `Docs`, `Refactor`,
`Style`, `Perf` — pick the one that matches the change; don't default to
`Fix` for everything.

## PR description template

Use the repository's PR template when one exists. Otherwise use this team
template, omitting sections that do not apply (for example, Screenshot for
non-visual changes). Keep the Issue / Card section but state that no issue
is linked when the change has no ticket.

```markdown
## Done

<2-5 short bullets, not a paragraph. Each bullet is one fact in one line:
what changed, then its user-visible effect. Skip implementation mechanics
a reviewer doesn't need (exact helper/registration names, internal flag
values) unless they're surprising or the reviewer would ask. Only add a
table instead of/alongside bullets when several pages/items each need
their own per-row attributes that bullets can't carry.>

| Page | <relevant column> | <relevant column> |
| --- | --- | --- |
| ... | ... | ... |
```

Good (precise, skimmable):
```markdown
## Done

- Route blog card + featured article thumbnails through `image_template`
  instead of a raw `source_url` dict, so Cloudinary optimises
  format/quality and adds a responsive `srcset`
- Fixes pixelation on small cards and high-DPI screens
- Mirrors the fix in canonical/ubuntu.com#16738, adapted for this repo's
  image-fallback logic
```

Bad (long paragraph, buries the actual fix in mechanism):
```markdown
## Done

Blog card and featured article thumbnails use vf_card's image param, but
were being fed a raw dict built directly from article.image.source_url —
bypassing Cloudinary's image_template helper entirely. That meant no auto
format/quality optimisation, and images rendered at native/incorrect
resolution, causing visible pixelation on smaller card sizes and high-DPI
screens. This mirrors the same bug fixed in canonical/ubuntu.com#16738...
```

### QA

<Testing instructions. Reference the repo's standard QA doc/checklist if
one exists. For deployed pages/routes, add available demo and live links;
omit these when no demo environment applies.>

### Screenshot

<Only include this section for visual/UI changes. A before/after image or
GIF, or a single after-screenshot if there's no meaningful before. Omit
the whole section entirely for non-visual changes (backend logic, config,
docs, tests) rather than leaving it empty.>

### Notes

- **<item>** — <description, e.g. breaks somthing, need to be careful, why something was not does, out of scope,
  blocked by another ticket>

### Issue / Card

<Fixes [<TICKET-ID>](<ticket-url>) when applicable; otherwise write "No linked issue".>
Related: [<OTHER-TICKET-ID>](<ticket-url>) (<why related>)   <!-- only if applicable -->

Include the ticket suffix in the title only when there is a linked
ticket. Add the `--label` options only when repository/team guidance
requires those labels:
```
gh pr create --base main --head <branch-name> \
  --title "<Title>" \
  --body "<rendered template above>" \
  --label "Review: code needed" --label "Review: QA needed"
```
Add only labels required by repository/team guidance. If a required label
is missing, follow that repo's policy or ask before creating it.

## Demo links

Only add demo links when the change affects a page or route with a
configured demo environment. Check the target repository's guidance and
deploy setup first. In repositories that use the standard demos.haus
pattern, construct the URL directly:

```
https://<repo-name-with-dots-as-dashes>-<PR-number>.demos.haus/<path>
```

e.g. repo `cn.ubuntu.com`, PR 884, path `/blog` →
`https://cn-ubuntu-com-884.demos.haus/blog`.

The PR number isn't known until `gh pr create` returns, so, when that
pattern applies:

1. Create the PR with the QA section's demo links left as a
   `<!-- demo links added below once PR number is known -->` placeholder.
2. Take the PR number/URL from `gh pr create`'s own output (it prints the
   PR URL, which ends in `/pull/<number>`).
3. Derive the repo name from `git remote get-url origin` (strip the
   `.git` suffix and org/user prefix) and replace every `.` with `-`.
4. Immediately run `gh pr edit <PR> --body-file -` to replace the
   placeholder with one
   `- Name — [demo](<demo-url>/<path>) · [live](<production-url>/<path>)`
   bullet per affected page/route. Do this as part of the same PR-creation
   step, not a separate follow-up the user has to ask for.

## Gotchas

- **Never commit without explicit approval** — showing the diff and
  waiting for a yes is not optional, even for small fixes.
- **A "Done" section that reads like a bug report is too long.** If it
  takes more than ~5 lines or one paragraph, cut it down to bullets before
  posting — reviewers skim, they don't read investigation narratives. This
  applies equally to commit messages and code comments: precise and short
  beats complete and long.
- **Dirty working tree in the ticket-first flow (A):** if `git status
  --short` shows unrelated pre-existing changes that aren't part of this
  ticket, stop and ask the user rather than stashing/discarding silently.
- **`git checkout -b` fails if the branch already exists** — check with
  `git branch --list <name>` first rather than assuming a fresh name.
- **Don't assume tests are (or aren't) needed** — always ask. Defaulting
  to "skip tests" under time pressure is exactly the failure this skill
  guards against, but forcing tests onto pure copy/markup changes is
  equally wrong; the user's answer is the source of truth, not a guess.
- **Don't fabricate the PR number or repo-name slug.** Only build a
  demo URL when that repo uses the pattern, and only from values you
  actually read (git remote, `gh pr create`'s returned URL) — never guess
  a PR number ahead of creation.
- **Never `git push --force`** on a shared branch without the user
  explicitly asking for it.
- **Check labels in the target repo.** Use the exact names its guidance
  requires; don't create missing labels without authorization.
