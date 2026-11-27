# Lessons

Mistakes made, or nearly made, on real runs of this skill. Read this before branching (step 5).

## Adding a lesson

Step 11 suggests where each new lesson belongs:

- **About one repo:** that repo's `AGENTS.md`, not here.
- **About the whole department:** the department docs, not here.
- **About this workflow, in any repo:** here, with the user's yes.

This file is public, so don't add internal content, people's names, ticket text or internal links. Write each lesson as one bullet: what went wrong, then what to do instead.

## Background and tooling

- **Department docs pages vary in age.** Some predate the move to GitHub, e.g. the branching guide still describes Bazaar. When a page disagrees with the repo's own files, follow the repo.
- **Don't infer tooling from untracked files.** `.dotrun.json` is local state that git ignores, so it doesn't mean the repo uses dotrun. Some repos have moved to Taskfile. Run things the way the repo's instructions say.
