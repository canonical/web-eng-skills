"""Finding a repo's PR templates and their sections. Shared; not run directly."""

import re

# GitHub's default template: pull_request_template.md in the root, docs/ or .github/
DEFAULT = re.compile(r"^((\.github|docs)/)?pull_request_template\.md$", re.I)
# Templates for particular kinds of PR, picked with ?template= on GitHub
OTHERS = re.compile(r"^((\.github|docs)/)?pull_request_template/[^/]+\.md$", re.I)


def find(files):
    """Return (the default template or None, the other templates)."""
    default = next((name for name in files if DEFAULT.match(name)), None)
    return default, [name for name in files if OTHERS.match(name)]


def headings(text):
    """Markdown headings, leaving out code blocks and HTML comments."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    found, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        match = None if fenced else re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            found.append(" ".join(match[1].split()))
    return found


def missing(template_text, body_text):
    """Headings of the template that the body doesn't have, in template order."""
    have = {heading.lower() for heading in headings(body_text)}
    return [
        heading for heading in headings(template_text) if heading.lower() not in have
    ]
