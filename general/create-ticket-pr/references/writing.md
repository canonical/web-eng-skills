# Writing the commit and the PR

Write for a reviewer skimming on a phone. Everything here is public, so `safety.md` decides what can be said. The repo's own habits, which `repo.py` reports under "Conventions", win over the defaults below.

## Commit message and PR title

- **Match the repo's title style.** `repo.py` counts the styles of recent PRs written by people and gives examples. Follow the most common style.
- **Put the ticket key where the repo puts it.** `repo.py` also says where recent titles put the key: none, first, as the scope, or at the end. If most leave it out, leave it out. The branch name and the PR body already link the ticket.
- **Only when there's no clear pattern** for style or key, use the department's default from `docs.py commits`: a conventional type and scope, then what changed, with the key at the end. For example: `fix(nav): keep the search overlay below the header WD-12345`.
- **One line, no full stop.** Describe the visible change, not how it was done.
- **The PR title** is usually the commit's first line. Many web repos merge PRs as merge commits, so the commit message ends up on the default branch too.
- **If the commit needs a body**, use a few short bullets.

## PR body

### With a template

`gh pr create --body-file` doesn't apply the template for you. Start from the template file that `repo.py` lists.

- **Which template:** use the one `repo.py` marks as the default. Other templates (such as those in `PULL_REQUEST_TEMPLATE/`) are only for the kind of PR their file name says, e.g. a takeover. If you use one, pass it to `state.py check --template`.
- **Keep every heading, in order.** Replace the prompts in square brackets with real content. Under a section that doesn't apply, write "None" instead of deleting it.
- **Keep template text that isn't a prompt**, such as help links and checklists.
- **Placeholders:** leave any that `repo.py` says a workflow fills in, such as `__DEMO_URL__` or `Fixes #`. The workflows skip fork PRs, and the ticket-link workflow only finds keys that match the pattern `repo.py` shows. In either case, write the ticket link yourself.
- **Check before showing the user:** `state.py check <KEY>` lists any template sections the body is missing.

### Without a template

Use this, and drop any section that doesn't apply:

```markdown
## Done

- <2 to 5 bullets: what changed, then what that fixes for people>

## QA

- <steps to check it, with demo and live links where they exist>

## Issue / Card

Fixes [<KEY>](<ticket URL>)

## Screenshots

<visual changes only>

## Notes

- **<topic>**: <a risk, something left out on purpose, or a blocker>
```

### Either way

- **GitHub issues:** write `Closes #123`. A workflow may rewrite `Fixes #`.
- **QA steps:** for website changes, see `docs.py qa` for what reviewers expect to check.
- **"Done" over five lines is too long:** cut it. Put root causes and the alternatives you rejected in a PR comment, and only if the user wants one.

Good:

```markdown
- Load card thumbnails through `image_template` instead of the raw URL
- Small cards and high-DPI screens no longer show pixelated images
```

Too long, because the fix is buried in mechanism:

```markdown
The card macro was passed a dictionary built from the article's original
image URL, which bypassed the image helper, so no responsive sources were
generated and the browser downloaded...
```

## Labels

- **Release-note labels:** when `repo.py` says release notes sort PRs by label (release-drafter), ask the user which one applies, and add it with `gh pr create --label`. Packages and Vanilla are versioned from these.
- **Other labels:** add only what the repo's guidance requires, by its exact names. Never create a label.
- **Review labels** such as `Review: Code +1` are added by reviewers. Never add them.
