"""Print what's needed to open a PR from a checkout. Read-only.

Usage: repo.py [--path DIR] [--key KEY]

Prints, in this order: whether the repo is in scope, where to branch from and
push to, the files to read before changing anything, how the repo is run and
checked, its PR conventions (title style, where the ticket key goes, labels)
and, with --key, existing work for the ticket.
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import github_access
import pr_template

ORG = github_access.ORG
WRITABLE = ("WRITE", "MAINTAIN", "ADMIN")
REMOTE = re.compile(
    r"github[\w.-]*[:/]+(?:\d+/)?(?P<owner>[\w.-]+)/(?P<name>[\w.-]+?)(?:\.git)?/?$"
)
INSTRUCTIONS = re.compile(
    r"^(.*/)?(AGENTS|CLAUDE)\.md$|^(README|CONTRIBUTING|HACKING)(\.\w+)?$"
    r"|^\.github/(copilot-instructions|CONTRIBUTING)\.md$",
    re.I,
)
PATH_INSTRUCTIONS = re.compile(r"^\.github/instructions/.+\.instructions\.md$")
SKILL = re.compile(r"^\.(github|claude|agents|opencode)/skills/[^/]+/SKILL\.md$")
WORKFLOW = re.compile(r"^\.github/workflows/[^/]+\.ya?ml$")
# Tracked files only: e.g. .dotrun.json is local state, and ignored by git
TOOLING = {
    "mise.toml": "mise: see mise.toml for tasks",
    ".mise.toml": "mise: see .mise.toml for tasks",
    "taskfile.yml": "task: run `task --list`",
    "taskfile.yaml": "task: run `task --list`",
    "makefile": "make: see the Makefile",
    "justfile": "just: run `just --list`",
    "tox.ini": "tox: see tox.ini",
    "run": "./run: the older run script",
}
SCRIPT_NAMES = re.compile(r"^(lint|test|check|format|build|serve|start)", re.I)
CONVENTIONAL = r"(feat|fix|chore|docs|ci|test|refactor|style|perf|build|revert)"
STYLES = (
    ("ticket key first (WD-123: ...)", re.compile(r"^\[?[A-Z][A-Z0-9]+-\d+\b")),
    ("conventional (fix: ...)", re.compile(rf"^{CONVENTIONAL}(\([^)]*\))?!?: ")),
    ("capitalised (Fix: ...)", re.compile(rf"^{CONVENTIONAL}(\([^)]*\))?!?: ", re.I)),
)
TITLE_KEY = r"[A-Z][A-Z0-9]+-\d+"
RELEASE_DRAFTER = re.compile(r"^\.github/release-drafter\.ya?ml$")


def run(*command, cwd=None):
    """Return stdout, or None if the command failed."""
    try:
        done = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def gh_json(*args):
    code, output = github_access.gh(*args)
    try:
        return json.loads(output) if code == 0 and output.strip() else None
    except ValueError:
        return None


def parse_remote(url):
    match = REMOTE.search(url.strip())
    return (match["owner"], match["name"]) if match else None


def read_remotes(path):
    remotes = {}
    for line in (run("git", "remote", "-v", cwd=path) or "").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "(fetch)" and parse_remote(parts[1]):
            remotes[parts[0]] = parse_remote(parts[1])
    return remotes


def find_repo(remotes):
    """Return (owner/name in canonical, its remote or None if only a fork is set up)."""
    ordered = sorted(remotes.items(), key=lambda item: item[0] != "origin")
    for remote, (owner, name) in ordered:
        if owner.lower() == ORG:
            return f"{owner}/{name}", remote
    for remote, (owner, name) in ordered:
        parent = gh_json("repo", "view", f"{owner}/{name}", "--json", "parent") or {}
        parent = parent.get("parent")
        if parent and parent["owner"]["login"].lower() == ORG:
            return f"{ORG}/{parent['name']}", None
    return None, None


def frontmatter(text):
    """Simple `key: value` pairs from a YAML front matter block."""
    if not text.startswith("---"):
        return {}
    block = text.split("\n---", 1)[0].split("\n")[1:]
    values, key = {}, None
    for line in block:
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if match:
            key, value = match.groups()
            values[key] = "" if value in (">", "|", ">-", "|-") else value.strip("'\"")
        elif key and line.startswith((" ", "\t")):
            values[key] = f"{values[key]} {line.strip()}".strip()
    return values


def pr_triggered(text):
    """True if the workflow runs on pull requests (other than only when closed)."""
    trigger = re.search(r"^['\"]?(on|true)['\"]?:.*?(?=^[^\s#]|\Z)", text, re.M | re.S)
    if not trigger:
        return False
    for found in re.finditer(r"\bpull_request(_target)?\b", trigger[0]):
        after = trigger[0][found.end() :]
        if not re.match(r":\s+types:\s*\[\s*closed\s*\]", after):
            return True
    return False


def title_style(title):
    for name, pattern in STYLES:
        if pattern.search(title):
            return name
    return "free text"


def key_placement(title):
    """Where a PR title puts its ticket key."""
    if not re.search(TITLE_KEY, title):
        return "no key"
    if re.match(rf"^\[?{TITLE_KEY}\b", title):
        return "key first"
    if re.match(rf"^\w+\({TITLE_KEY}\)", title):
        return "key as the scope"
    if re.search(rf"{TITLE_KEY}\W*$", title):
        return "key at the end"
    return "key elsewhere"


def ticket_pattern(workflow):
    """The regex a workflow uses to find the ticket key in the branch name."""
    match = re.search(r"=~\s*(\S+)\s*\]\]", workflow)
    if not match:
        return None
    try:
        return re.compile(match[1]).pattern
    except re.error:
        return None


def unquote(value):
    return value.strip().strip("'\"")


def release_labels(text):
    """The labels release-drafter sorts PRs into release notes by."""
    block = re.search(r"^categories:\s*\n(.*?)(?=^\S|\Z)", text, re.M | re.S)
    labels, listing = [], False
    for line in (block[1] if block else "").splitlines():
        pair = re.match(r"^\s*(?:-\s+)?([\w-]+):\s*(.*?)\s*$", line)
        if pair:
            name, value = pair.groups()
            listing = name == "labels" and not value
            if name == "label":
                labels.append(unquote(value))
            elif name == "labels" and value.startswith("["):
                labels += [unquote(item) for item in value.strip("[]").split(",")]
        elif listing:
            item = re.match(r"^\s*-\s+(.+?)\s*$", line)
            if item:
                labels.append(unquote(item[1]))
    return list(dict.fromkeys(label for label in labels if label))


def mentions(key, text):
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?!\d)", text or "", re.I))


def push_advice(full, remote, can_push, forks, login, people):
    """Where to push. `forks` are remotes pointing at the user's own fork."""
    from_forks = sum(pr["isCrossRepository"] for pr in people)
    mostly_forks = len(people) >= 5 and from_forks > len(people) / 2
    if forks and (mostly_forks or not (can_push and remote)):
        return f"{forks[0]} (fork PR: --repo {full} --head {login}:<branch>)"
    if can_push and remote:
        if mostly_forks:
            return (
                f"ASK: {from_forks} of {len(people)} recent PRs come from forks, and "
                "there's no remote for your fork. Ask whether to use one"
            )
        return f"{remote} (same-repo PR)"
    return "ASK: you can't push to this repo and there's no remote for your fork"


def print_list(label, items, limit=15):
    items = list(items)
    print(f"{label}: {'none' if not items else ''}".rstrip())
    for item in items[:limit]:
        print(f"  - {item}")
    if len(items) > limit:
        print(f"  - ... and {len(items) - limit} more")


def print_inline(label, items):
    items = list(items)
    print(f"{label}: {', '.join(items) if items else 'none'}")


def print_found(label, items):
    """A failed search must never look like an empty result."""
    if items is None:
        print(f"{label}: COULDN'T CHECK, so ask the user to check by hand")
    else:
        print_list(label, items)


def required_checks(full, branch):
    names = set()
    rules = gh_json("api", f"repos/{full}/rules/branches/{branch}") or []
    for rule in rules:
        if rule.get("type") == "required_status_checks":
            for check in rule["parameters"]["required_status_checks"]:
                names.add(check["context"])
    protection = gh_json(
        "api", f"repos/{full}/branches/{branch}/protection/required_status_checks"
    )
    names |= set((protection or {}).get("contexts", []))
    return sorted(names)


def recent_merged(full):
    return gh_json(
        "pr", "list", "-R", full, "--state", "merged", "--limit", "30",
        "--json", "title,author,isCrossRepository,labels",
    )  # fmt: skip


def find_prs(key, full):
    found = {}
    for query in (f'"{key}"', f"head:{key}", f"head:{key.lower()}"):
        prs = gh_json(
            "pr", "list", "-R", full, "--state", "all", "--search", query,
            "--json", "number,title,state,url,headRefName,body",
        )  # fmt: skip
        if prs is None:
            return None
        for pr in prs:
            if mentions(key, f"{pr['title']} {pr['headRefName']} {pr['body']}"):
                found[pr["number"]] = f"{pr['state']} {pr['url']} {pr['title']}"
    return list(found.values())


def find_prs_elsewhere(key, full):
    prs = gh_json(
        "search", "prs", f'"{key}"', "--owner", ORG, "--limit", "20",
        "--json", "repository,state,url,title,body",
    )  # fmt: skip
    if prs is None:
        return None
    return [
        f"{pr['state']} {pr['url']} {pr['title']}"
        for pr in prs
        if pr["repository"]["nameWithOwner"].lower() != full.lower()
        and mentions(key, f"{pr['title']} {pr['body']}")
    ]


def find_issues(key, full):
    issues = gh_json(
        "issue", "list", "-R", full, "--state", "all", "--search", f'"{key}"',
        "--json", "state,url,title,body",
    )  # fmt: skip
    if issues is None:
        return None
    return [
        f"{issue['state']} {issue['url']} {issue['title']}"
        for issue in issues
        if mentions(key, f"{issue['title']} {issue['body']}")
    ]


def find_branches(key, remotes, path):
    found = []
    for remote in remotes:
        heads = run("git", "ls-remote", "--heads", remote, cwd=path)
        if heads is None:
            return None
        names = [line.split("refs/heads/", 1)[-1] for line in heads.splitlines()]
        found += [f"{remote}/{name}" for name in names if mentions(key, name)]
    local = run("git", "branch", "--format=%(refname:short)", cwd=path) or ""
    return found + [f"local {name}" for name in local.split() if mentions(key, name)]


def print_files(path, ref, key=""):
    """Print what to read and how it's checked. Return the release-note labels."""
    files = (run("git", "ls-tree", "-r", "--name-only", ref, cwd=path) or "").split(
        "\n"
    )
    names = {name.lower(): name for name in files if "/" not in name}

    def show(name):
        return run("git", "show", f"{ref}:{name}", cwd=path) or ""

    print(f"\nRead before changing anything (files at {ref})")
    print_list("Instructions", filter(INSTRUCTIONS.match, files))
    path_specific = [
        f"{name} (applies to: {frontmatter(show(name)).get('applyTo', 'not stated')})"
        for name in filter(PATH_INSTRUCTIONS.match, files)
    ]
    print_list("Path-specific instructions", path_specific)
    skills = []
    for name in filter(SKILL.match, files):
        description = frontmatter(show(name)).get("description", "")
        skills.append(
            f"{name}: {description[:150]}{'...' if len(description) > 150 else ''}"
        )
    print_list("Skills in this repo", skills)
    default, others = pr_template.find(files)
    if default:
        sections = "; ".join(pr_template.headings(show(default))) or "no headings"
        print(f"PR template: {default} (the default; sections: {sections})")
    else:
        print("PR template: no default")
    if others:
        print_inline(
            "Other PR templates, only for the kind of PR each is named for", others
        )

    print("\nHow it's run and checked (the instructions above say which to use)")
    print_list("Tooling", [TOOLING[n] for n in TOOLING if n in names])
    if "package.json" in names:
        try:
            scripts = json.loads(show(names["package.json"])).get("scripts", {})
        except ValueError:
            scripts = {}
        print_inline("package.json scripts", filter(SCRIPT_NAMES.match, scripts))
    workflows = {name: show(name) for name in filter(WORKFLOW.match, files)}
    on_prs = [name for name, text in workflows.items() if pr_triggered(text)]
    print_inline(
        "Workflows that run on PRs", (name.rsplit("/", 1)[-1] for name in on_prs)
    )
    for name in on_prs:
        text = workflows[name]
        forks = (
            ", except on fork PRs"
            if "head.repo.full_name == github.repository" in text
            else ""
        )
        if "__DEMO_URL__" in text:
            print(f"Demo link: {name} replaces __DEMO_URL__{forks}. Leave it as it is")
        if "Fixes #" in text:
            pattern = ticket_pattern(text)
            found = f", matching {pattern}" if pattern else ""
            print(
                f"Ticket link: {name} rewrites 'Fixes #' with the key in the branch "
                f"name{found}{forks}. Leave it as it is. Write 'Closes #' for issues"
            )
            if key and pattern and not re.search(pattern, f"{key}-x"):
                print(
                    f"  {key} doesn't match that, so the link won't be filled in: "
                    "write the ticket link in the PR body yourself"
                )
    drafter = next(filter(RELEASE_DRAFTER.match, files), None)
    return (drafter, release_labels(show(drafter))) if drafter else (None, [])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--path", default=".")
    parser.add_argument("--key")
    options = parser.parse_args(argv)
    key = (options.key or "").upper()
    if key and not re.fullmatch(r"[A-Z][A-Z0-9_]+-\d+", key):
        parser.error("--key must look like ABC-123")

    top = run("git", "rev-parse", "--show-toplevel", cwd=options.path)
    if not top:
        print(f"{options.path} isn't a git checkout", file=sys.stderr)
        return 2
    path = top.strip()
    remotes = read_remotes(path)
    full, remote = find_repo(remotes)
    if not full:
        print(
            "No canonical GitHub repo found in this checkout's remotes", file=sys.stderr
        )
        return 2

    verdict, reason = github_access.repo_scope(full)
    print(f"Scope: {verdict}, {reason}")
    if verdict == "STOP":
        print("Don't work in this repo. Tell the user why.")
        return 1
    repo = gh_json(
        "repo", "view", full, "--json",
        "nameWithOwner,defaultBranchRef,visibility,viewerPermission",
    )  # fmt: skip
    if not repo:
        print(f"Couldn't read {full} with gh", file=sys.stderr)
        return 1
    full, default = repo["nameWithOwner"], repo["defaultBranchRef"]["name"]
    # The GitHub lookups are slow, so they run at the same time
    with ThreadPoolExecutor(8) as pool:
        jobs = {
            "login": pool.submit(
                lambda: (gh_json("api", "user") or {}).get("login", "")
            ),
            "merged": pool.submit(recent_merged, full),
            "checks": pool.submit(required_checks, full, default),
        }
        if key:
            jobs["prs"] = pool.submit(find_prs, key, full)
            jobs["elsewhere"] = pool.submit(find_prs_elsewhere, key, full)
            jobs["issues"] = pool.submit(find_issues, key, full)
            jobs["branches"] = pool.submit(find_branches, key, remotes, path)
        found = {name: job.result() for name, job in jobs.items()}
    login = found["login"]
    forks = [
        name for name, (owner, _) in remotes.items() if owner.lower() == login.lower()
    ]
    people = [pr for pr in found["merged"] or [] if not pr["author"].get("is_bot")]
    can_push = repo["viewerPermission"] in WRITABLE

    print(f"Repository: {full} ({repo['visibility'].lower()})")
    print(f"Default branch: {default}")
    print(f"Your permission: {repo['viewerPermission'].lower()}")
    if remote:
        print(
            f"Branch from: {remote}/{default} "
            f"(run `git fetch {remote} {default}` first)"
        )
    else:
        print(
            f"Branch from: no remote for {full}. Run "
            f"`git fetch https://github.com/{full}.git {default}` and use FETCH_HEAD"
        )
    print(f"Push to: {push_advice(full, remote, can_push, forks, login, people)}")
    branch = (run("git", "branch", "--show-current", cwd=path) or "").strip()
    dirty = (run("git", "status", "--porcelain", cwd=path) or "").splitlines()
    print(f"Current branch: {branch or '(detached)'}")
    print_list("Uncommitted changes", (line.strip() for line in dirty), 10)

    ref = "HEAD"
    if remote and run(
        "git", "rev-parse", "--verify", "-q", f"{remote}/{default}", cwd=path
    ):
        ref = f"{remote}/{default}"
    drafter, note_labels = print_files(path, ref, key)

    print("\nConventions")
    if found["checks"]:
        print_inline("Required checks", found["checks"])
    else:
        print("Required checks: none visible. Go by the workflows that run on PRs")
    if people:
        styles = Counter(title_style(pr["title"]) for pr in people)
        summary = ", ".join(f"{count} {style}" for style, count in styles.most_common())
        print(f"Recent PR titles ({len(people)} by people): {summary}")
        keys = Counter(key_placement(pr["title"]) for pr in people)
        summary = ", ".join(f"{count} {where}" for where, count in keys.most_common())
        print(f"Ticket key in those titles: {summary}")
        print_list("  Examples", [pr["title"] for pr in people[:5]])
        labels = Counter(
            label["name"]
            for pr in people
            for label in pr.get("labels") or []
            if not label["name"].lower().startswith("review")
        )
        print_inline(
            "Labels on those PRs, leaving out review labels",
            (f"{name} ({count})" for name, count in labels.most_common(8)),
        )
    else:
        print("Recent PR titles: none found. Use `docs.py commits`")
    if note_labels:
        print_inline(
            f"Release notes sort PRs by these labels ({drafter}). "
            "Ask the user which applies",
            note_labels,
        )

    if key:
        print(f"\nExisting work for {key}")
        print_found("PRs here", found["prs"])
        print_found("PRs in other canonical repos", found["elsewhere"])
        print_found("Issues here", found["issues"])
        print_found("Branches", found["branches"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
