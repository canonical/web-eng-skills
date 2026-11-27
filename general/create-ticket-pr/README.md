# create-ticket-pr

An agent skill that turns one Jira ticket into a draft pull request on a Canonical web repository. It uses the open [Agent Skills](https://agentskills.io) format.

- **What it takes:** bugs and maintenance tickets, one repo at a time.
- **Which repos:** web repos only, meaning any repo that the `canonical/web-and-design` GitHub team, or a team under it, has access to. It checks this live.
- **When it asks:** before it commits, pushes or opens anything.
- **When it stops, and says why:** on copy and page work, design tasks, epics, blocked tickets, other people's tickets and vulnerability reports.

## Requirements

- `git`, Python 3.9+ and the [GitHub CLI](https://cli.github.com) (`gh`)
- A Jira API token for your Atlassian account. [Create one here](https://id.atlassian.com/manage-profile/security/api-tokens)
- Membership of the `canonical` organisation on GitHub

## One-time setup

Run this yourself, in your own terminal:

```bash
python3 <path to this folder>/scripts/setup.py
```

It asks for your Atlassian email and API token without showing what you type, and checks them with Jira before saving anything. The token is saved in your system keyring: `secret-tool` on Linux (`sudo apt install libsecret-tools`) or the login keychain on macOS. Without a keyring, it goes in a file only you can read, `~/.config/create-ticket-pr/jira-token`. Then setup checks that `gh` is signed in with the `repo` and `read:org` scopes, and offers to fix that if not.

- **Agents can't run it:** setup refuses to run without a real terminal, so an agent can't run it for you.
- **The agent never sees the token:** it only runs `preflight.py`, which reports whether things work.
- **Remove the token:** `setup.py --forget`.
- **Another Jira site:** pass `--site https://<name>.atlassian.net`.
- **Environment variables:** if `JIRA_EMAIL` and `JIRA_API_TOKEN` are set, they're used instead of the saved token.

## Install

Link this folder into your harness's personal skills folder, so there's one copy and your edits apply straight away. For Claude Code:

```bash
ln -s "$PWD/general/create-ticket-pr" ~/.claude/skills/create-ticket-pr   # from this repo's root
```

Other harnesses that support Agent Skills have their own personal skills folder; link it there. Install it personally rather than in a repo, and keep it out of unattended agents such as the Copilot cloud agent, because the skill needs someone to approve each change.

To uninstall, run `rm ~/.claude/skills/create-ticket-pr`. That removes only the link.

## Use

From a checkout of the repo, ask your agent "create a PR for WD-12345", or run `/create-ticket-pr WD-12345` in harnesses that turn skills into slash commands.

## Try it safely

1. **Check the setup.** `python3 scripts/preflight.py --repo canonical/ubuntu.com` should say OK on every line.
2. **Check it loads.** Start a new agent session in a checkout of a web repo and type `/create-ticket-pr`. If it autocompletes, it's loaded.
3. **Make pushing impossible.** In that checkout, run `git remote set-url --push origin DISABLED`. To undo it afterwards, run `git config --unset remote.origin.pushurl`.
4. **Do a run.** Give it a real ticket that's ready to work on, and answer no at the approval step. Nothing leaves your machine. The run's notes and logs are in `.git/create-ticket-pr/`, and you can delete them.

## Scripts

Only `state.py` writes anything, and only inside `.git/`. The others are read-only.

| Script | What it does |
|---|---|
| `setup.py` | One-time setup of the Jira token and `gh` (run by you) |
| `preflight.py [--repo OWNER/NAME]` | Checks Jira, `gh` and that the repo is in scope |
| `jira.py KEY [--full]` | Prints the ticket, keeping people's text between markers |
| `repo.py --path DIR --key KEY` | Shows the scope, where to push, what to read and how the repo runs its checks. Also its PR conventions (title style, where the ticket key goes, the template's sections, labels) and any existing work |
| `docs.py TOPIC` | Reads a page of the department docs live (`--list` for the topics) |
| `run.py -- COMMAND` | Runs a check and prints a short result; the full log goes to `.git/` |
| `state.py path, check, approve, verify` | Keeps per-ticket notes, checks the PR body has the template's sections, and ties the approval to the exact change |

To run the tests, from this folder:

```bash
python3 -m unittest discover -s scripts/tests -t scripts
```

## Improving it

- **One repo's conventions** belong in that repo's `AGENTS.md`.
- **Department conventions** belong in the department docs.
- **Mistakes in this workflow** go in `references/lessons.md`. The skill suggests these at the end of a run.

This repository is public. Don't add internal content, people's names, ticket text or internal links. Naming the internal docs repo and its page paths is fine.
