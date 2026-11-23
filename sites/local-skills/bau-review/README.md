# bau-review

An agent skill that reviews a website content-update pull request. It checks the demo against the Figma design and the copydoc, and looks for HTML validation, markup and accessibility problems. It follows the open [Agent Skills](https://agentskills.io) format, with a `SKILL.md` file plus `scripts/` and `references/` folders, so any harness that supports skills can use it.

## Install

Copy or symlink this folder (`sites/local-skills/bau-review` in [canonical/web-eng-skills](https://github.com/canonical/web-eng-skills)) into your harness's skills directory:

| Harness | Project | Personal |
|---|---|---|
| Claude Code | `.claude/skills/bau-review/` | `~/.claude/skills/bau-review/` |
| opencode | `.opencode/skills/bau-review/` (opencode also reads `.claude/skills/`) | `~/.config/opencode/skills/bau-review/` |
| Others (Codex, Cursor, Copilot…) | `.agents/skills/bau-review/` or the harness's documented path | see the harness docs |

Or use the `skills` CLI, which installs into the right place for each agent:

```bash
npx skills add canonical/web-eng-skills --skill bau-review
```

Then install the script dependencies once:

```bash
cd <skills-dir>/bau-review/scripts && npm install
npx playwright install chromium   # only if you have no Chrome/Chromium installed
```

## Requirements

- `gh` signed in with access to the repos you review
- `curl`, Python 3, Node.js 18+

Optional, but each one unlocks a check:

| Capability | Unlocks |
|---|---|
| Google Drive tool or connector, with access to the copydocs | Copy comparison |
| Figma tool, or `FIGMA_TOKEN` | Design comparison |
| A model that can view images (most Claude, GPT and Gemini models do; many open models on OpenRouter don't) | Visual comparison of the screenshots |

The skill says in its report which checks it couldn't run and why.

## Use

Ask your agent to review a PR, e.g. "bau-review https://github.com/canonical/canonical.com/pull/3109". In harnesses that turn skills into slash commands, you can also run `/bau-review <url>`.

## Improving it

When an author's reply shows that a review got something wrong, add the general lesson to `references/conventions.md` in a pull request. Asking the agent to "learn from the replies on <PR>" drafts that change for you.
