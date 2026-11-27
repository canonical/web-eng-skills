"""Read a page of the Web Engineering docs, live. Read-only.

Usage:
  docs.py --list                 the topics, and what each covers
  docs.py TOPIC [--section HEADING] [--full]
  docs.py --page PATH            any page, by its path under docs/

The docs are in canonical/web-engineering-docs, an internal repo that
canonical organisation members can read. Never copy what they say into a
public repo. Some pages are old: the repo's own files win over them.
"""

import argparse
import re
import sys

import github_access

DOCS_REPO = "canonical/web-engineering-docs"
LIMIT = 150
TOPICS = {
    "commits": ("reference/best-practices/git-commit-guidelines.md", "commit messages"),
    "pull-requests": (
        "how-to/working-on-github.md",
        "PRs on GitHub: process, templates",
    ),
    "qa": ("reference/best-practices/qa-steps.md", "QA steps for website changes"),
    "labels": ("reference/issue-label-descriptions.md", "what the labels mean"),
    "website-changes": (
        "how-to/make-changes-on-websites.md",
        "how changes reach the websites, and the Jira automation",
    ),
    "run-locally": (
        "how-to/run-websites-in-5-steps-with-mise-dev.md",
        "running a website locally",
    ),
    "run-script": ("how-to/using-run-script.md", "the older ./run script"),
    "project-interface": (
        "reference/project-interface.md",
        "the standard package.json scripts",
    ),
    "project-structure": ("reference/basic-structure-web-projects.md", "repo layout"),
    "demos": ("how-to/demo-service.md", "demos of PRs"),
    "security-patches": (
        "how-to/how-to-apply-security-patches-without-the-risk-of-exposing-"
        "vulnerabilities.md",
        "fixing vulnerabilities without disclosing them",
    ),
    "images": ("how-to/working-with-image-template.md", "image_template"),
    "code-review": ("explanation/code-review-etiquette.md", "code review etiquette"),
    "python": ("reference/best-practices/python-coding-guidelines.md", "Python"),
    "html": ("reference/best-practices/html-code-standards.md", "HTML"),
    "css": ("reference/best-practices/stylesheet-coding-standards.md", "SCSS and CSS"),
    "js": ("reference/best-practices/js-coding-guidelines.md", "JavaScript, React"),
    "copy-updates": (
        "how-to/actioning-copy-update-issues.md",
        "copy-update tickets (handled elsewhere, not by this skill)",
    ),
    "new-pages": (
        "how-to/new-web-pages-and-page-refreshes.md",
        "new pages and refreshes (handled elsewhere, not by this skill)",
    ),
}
NO_ACCESS = (
    f"Couldn't read {DOCS_REPO}. Reading it needs membership of the canonical "
    "GitHub organisation. Go on with the repo's own files."
)


def fetch(path):
    """Return the page's text, or None if it isn't there."""
    code, text = github_access.gh(
        "api", f"repos/{DOCS_REPO}/contents/docs/{path}",
        "-H", "Accept: application/vnd.github.raw",
    )  # fmt: skip
    return text if code == 0 else None


def last_changed(path):
    code, date = github_access.gh(
        "api", f"repos/{DOCS_REPO}/commits?path=docs/{path}&per_page=1",
        "--jq", ".[0].commit.committer.date[:10]",
    )  # fmt: skip
    return date.strip() if code == 0 and date.strip() else "unknown"


def search(words):
    """Pages whose path contains every word, for when a page has moved."""
    code, output = github_access.gh(
        "api", f"repos/{DOCS_REPO}/git/trees/HEAD?recursive=1", "--jq", ".tree[].path"
    )
    if code != 0:
        return None
    pages = [
        p[5:] for p in output.split() if p.startswith("docs/") and p.endswith(".md")
    ]
    return [page for page in pages if all(word in page.lower() for word in words)]


def clean(text):
    """Drop front matter, MyST labels and runs of blank lines."""
    if text.startswith("---"):
        text = text.split("\n---", 1)[-1].split("\n", 1)[-1]
    text = re.sub(r"^\([\w-]+\)=\s*$", "", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def heading_lines(lines):
    """(line number, level, title) for each Markdown heading outside code blocks."""
    found, fenced = [], False
    for number, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        match = None if fenced else re.match(r"^(#+)\s+(.*)", line)
        if match:
            found.append((number, len(match[1]), match[2].strip()))
    return found


def headings(text):
    return [title for _, _, title in heading_lines(text.splitlines())]


def section(text, wanted):
    """The first section whose heading has `wanted`, up to the next at its level."""
    lines = text.splitlines()
    found = heading_lines(lines)
    for position, (start, level, title) in enumerate(found):
        if wanted.lower() in title.lower():
            later = [n for n, depth, _ in found[position + 1 :] if depth <= level]
            return "\n".join(lines[start : later[0] if later else len(lines)])
    return None


def show(path, wanted=None, full=False):
    text = fetch(path)
    if text is None:
        return None
    text = clean(text)
    print(
        f"From {DOCS_REPO}, docs/{path} (last changed {last_changed(path)}). "
        "Internal: don't copy it into a public repo. The repo's own files win."
    )
    if wanted:
        part = section(text, wanted)
        if part is None:
            print(
                f"No section matching {wanted!r}. Sections: {'; '.join(headings(text))}"
            )
            return 1
        text = part
    lines = text.splitlines()
    if not full and len(lines) > LIMIT:
        print("\n".join(lines[:LIMIT]))
        print(
            f"\n[... {len(lines) - LIMIT} more lines. Use --full, or --section with "
            f"one of: {'; '.join(headings(text))}]"
        )
    else:
        print(text)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("topic", nargs="?")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--page", help="a page's path under docs/")
    parser.add_argument("--section", help="only the section whose heading has this")
    parser.add_argument("--full", action="store_true", help="don't shorten long pages")
    options = parser.parse_args(argv)

    if options.list or not (options.topic or options.page):
        for name, (_, about) in TOPICS.items():
            print(f"{name:18} {about}")
        return 0
    if github_access.gh("api", f"repos/{DOCS_REPO}", "--jq", ".full_name")[0] != 0:
        print(NO_ACCESS)
        return 1
    if options.page:
        path = re.sub(r"^docs/", "", options.page)
    elif options.topic in TOPICS:
        path = TOPICS[options.topic][0]
    else:
        print(f"No topic {options.topic!r}. Run `docs.py --list`.")
        return 2
    result = show(path, options.section, options.full)
    if result is not None:
        return result
    words = re.findall(r"[a-z]+", path.rsplit("/", 1)[-1].lower().replace(".md", ""))
    candidates = (search(words[:3]) or [])[:10]
    print(f"docs/{path} isn't there any more (the page may have moved).")
    if candidates:
        print("Pages that might be it (read one with --page PATH):")
        for page in candidates:
            print(f"  - {page}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
