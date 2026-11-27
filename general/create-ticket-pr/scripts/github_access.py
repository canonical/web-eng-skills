"""GitHub sign-in checks and the web-repo scope check.

Shared by setup.py and preflight.py; not run directly. A repo is a web repo
when the canonical/web-and-design team, or any team under it, has access.
"""

import json
import re
import subprocess

ORG = "canonical"
ROOT_TEAM = "web-and-design"
NEEDED_SCOPES = ("repo", "read:org")
# A scope also counts when a broader one includes it
INCLUDED_IN = {"repo": {"repo"}, "read:org": {"read:org", "write:org", "admin:org"}}
LOGIN_COMMAND = "gh auth login --hostname github.com --scopes read:org"
REFRESH_COMMAND = "gh auth refresh --hostname github.com --scopes repo,read:org"
INSTALL_HINT = "install the GitHub CLI (https://cli.github.com)"
REPO_NAME = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")
ADVISORY_FORK = re.compile(r"-ghsa(-[0-9a-z]{4}){3}$", re.I)


def gh(*args):
    """Return (exit code, stdout). The exit code is None if gh couldn't run."""
    try:
        done = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return done.returncode, done.stdout


def parse_user_response(text):
    """Return (login, scopes) from `gh api -i user`. Scopes are None if not reported."""
    head, _, body = text.replace("\r\n", "\n").partition("\n\n")
    scopes = None
    for line in head.splitlines():
        name, _, value = line.partition(":")
        if name.strip().lower() == "x-oauth-scopes":
            scopes = {scope.strip() for scope in value.split(",") if scope.strip()}
    try:
        login = json.loads(body).get("login")
    except (ValueError, AttributeError):
        login = None
    return login, scopes


def missing_scopes(scopes):
    """Needed scopes the token lacks. Fine-grained tokens don't report scopes,
    so nothing is reported missing and the checks that use them find out."""
    if scopes is None:
        return []
    return [scope for scope in NEEDED_SCOPES if not INCLUDED_IN[scope] & scopes]


def github_status():
    """Return a dict: ok, login, scopes, and when not ok, problem and fix."""
    code, output = gh("api", "-i", "user")
    if code is None:
        return {"ok": False, "problem": "gh isn't installed", "fix": INSTALL_HINT}
    if code != 0:
        if gh("auth", "status")[0] == 0:
            return {"ok": False, "problem": "couldn't reach GitHub", "fix": None}
        return {"ok": False, "problem": "gh isn't signed in", "fix": LOGIN_COMMAND}
    login, scopes = parse_user_response(output)
    missing = missing_scopes(scopes)
    if missing:
        return {
            "ok": False,
            "login": login,
            "scopes": scopes,
            "problem": f"gh's sign-in lacks the {' and '.join(missing)} scope",
            "fix": REFRESH_COMMAND,
        }
    return {"ok": True, "login": login, "scopes": scopes}


def web_teams():
    """web-and-design and every team under it, or None if they can't be read."""
    if gh("api", f"orgs/{ORG}/teams/{ROOT_TEAM}")[0] != 0:
        return None
    found, queue = [ROOT_TEAM], [ROOT_TEAM]
    while queue:
        code, output = gh(
            "api", "--paginate", f"orgs/{ORG}/teams/{queue.pop(0)}/teams",
            "--jq", ".[].slug",
        )  # fmt: skip
        if code != 0:
            return None
        for child in output.split():
            if child not in found:
                found.append(child)
                queue.append(child)
    return found


def repo_scope(full_name, teams=None):
    """Return (verdict, reason): OK, STOP (don't work in it) or ASK (couldn't tell)."""
    match = REPO_NAME.match(full_name.strip())
    if not match:
        return "ASK", f"{full_name!r} isn't written as owner/name"
    owner, name = match.groups()
    if owner.lower() != ORG:
        return "STOP", f"{full_name} isn't in the {ORG} organisation"
    if ADVISORY_FORK.search(name):
        return "STOP", (
            f"{full_name} is a security advisory fork; "
            "its content can't go into a public PR"
        )
    code, output = gh(
        "repo",
        "view",
        f"{owner}/{name}",
        "--json",
        "nameWithOwner,isArchived,visibility",
    )
    try:
        repo = json.loads(output) if code == 0 else None
    except ValueError:
        repo = None
    if not repo:
        return (
            "ASK",
            f"couldn't read {full_name}: it doesn't exist, or you can't see it",
        )
    full_name, visibility = repo["nameWithOwner"], repo["visibility"].lower()
    if repo["isArchived"]:
        return "STOP", f"{full_name} is archived"
    teams = web_teams() if teams is None else teams
    if teams is None:
        return "ASK", (
            f"couldn't read the {ORG}/{ROOT_TEAM} team, "
            f"so couldn't check {full_name} is a web repo"
        )
    for slug in teams:
        if gh("api", f"orgs/{ORG}/teams/{slug}/repos/{full_name}")[0] == 0:
            via = slug if slug == ROOT_TEAM else f"{slug}, under {ROOT_TEAM}"
            return "OK", f"{full_name} is a web repo (team {via}), {visibility}"
    return "STOP", (
        f"{full_name} isn't a web repo: neither {ROOT_TEAM} "
        "nor any team under it has access"
    )
