# Is this ticket ready?

Go through the rules in order: the first match decides. If a fact is missing, ask rather than assume. To check what a label means, run `docs.py labels`.

## Stop

Tell the user which rule applied and what would unblock it.

| The ticket is... | Why it stops |
|---|---|
| A vulnerability report, or it explains how to exploit something | A public branch or PR would disclose it. Point the user to `docs.py security-patches` |
| At a restricted security level | Its content can't go into a public repo. "Vendor Access Controlled", the usual level on WD tickets, isn't restricted |
| An epic, or its subtasks hold the work | There's no single change to make. List the children |
| A design, UX or copywriting task, e.g. a summary starting "Visual Design -" or "UX -" | It isn't engineering work |
| Copy or page work (see below) | It has its own process |
| Done, in review, or blocked | Already handled, or waiting on something. Say what |
| Assigned to someone else | They may have started. The user can confirm it's theirs to take. Never reassign it |
| An investigation or discussion | The result is a finding, not a PR |
| Infrastructure, DNS, credentials, or a change in a third-party service | There's no code change in a web repo, or it needs access you shouldn't use |
| Already fixed on the default branch | Show the evidence |

### Copy and page work

Any one of these means copy or page work:

- a label such as `copy-update`, `New-Page`, `Page-Update`, `case-study` or `sites_BAU`
- a "Copy Doc URL" field, or a Google Docs or Figma link that holds the requirement
- a summary like "Dev - Create", "Dev - Refresh" or "Dev - Update" followed by a URL

`docs.py copy-updates` and `docs.py new-pages` describe how that work is done. A maintenance ticket that states the exact new values itself (e.g. version numbers to change in a file) isn't copy work.

## Ask, then go on if the user agrees

- **Untriaged:** nobody has agreed the work yet.
- **Several repos:** ask which one to do now, and list the rest in the final report.
- **No clear end state:** ask what "fixed" looks like. Ask at most three questions, all at once.
- **The description and the comments disagree:** show both and ask which is current.
- **Images you can't view hold the detail:** ask the user to describe them.
- **A large change** (several areas, a migration, a new dependency): propose a first slice.
- **Blocked by another ticket that's still open.**

## Go on

Only when all of these are true:

- It's a bug or a maintenance task. It's either not started, or in progress by the user.
- It's assigned to the user or to nobody.
- You can say what's wrong, what will change and how to check it.
- It's one repo, and you know which.

Labels differ between tribes. The ones above come from Sites. In other projects, judge by what the ticket asks for, and ask if you're unsure.
