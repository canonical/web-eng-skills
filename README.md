# Sites team agent skills

This repository contains agent skills for Canonical's web engineering Sites team. It is for sharing reusable, team-relevant instructions with agents; it is not a home for applications, general-purpose tooling, or unrelated documentation.

## Contribute a skill

Team members are welcome to contribute skills. Add each skill in its own directory under `skills/`:

```text
skills/
└── skill-name/
    └── SKILL.md
```

Use a short, lowercase, hyphen-separated directory name. Each `SKILL.md` must begin with YAML front matter containing a matching `name` and a concise `description` of when the skill should be used:

```markdown
---
name: skill-name
description: Use this skill when ...
---

# Skill title

Give the agent clear, actionable instructions for the task.
```

Keep the skill focused on a specific task and include only the supporting files it needs. Do not add application code, dependencies, or material unrelated to agent skills.

When contributing, check that the skill is understandable on its own, does not duplicate an existing skill, and contains no sensitive information. Open a pull request with a brief explanation of what the skill helps with and who should use it; the Sites team can review it before it is added.
