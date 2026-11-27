"""Check this machine is ready for create-ticket-pr. Read-only; never prints secrets.

Usage: preflight.py [--repo OWNER/NAME]

Checks that the saved Jira token works and that gh is signed in with the scopes
needed. With --repo, also checks the repo is a Canonical web repo. Exits 0 only
when everything is ready.
"""

import argparse
import sys
from pathlib import Path

import github_access
import jira_auth

SETUP = Path(__file__).resolve().with_name("setup.py")
IN_THEIR_TERMINAL = "Ask the user to run this in their own terminal, not through you"


def check_jira():
    """Return (ready, line)."""
    try:
        site, email, token, source = jira_auth.load_credentials()
    except jira_auth.NotSetUp as problem:
        return (
            False,
            f"Jira: NOT SET UP ({problem}). {IN_THEIR_TERMINAL}: python3 {SETUP}",
        )
    try:
        name = jira_auth.whoami(site, email, token)
    except jira_auth.JiraError as error:
        if error.status in (401, 403):
            return (
                False,
                f"Jira: REJECTED ({error}). {IN_THEIR_TERMINAL}: python3 {SETUP}",
            )
        return False, f"Jira: COULDN'T CHECK ({error}). Try again shortly."
    host = site.split("://", 1)[1]
    return True, f"Jira: OK, signed in to {host} as {name}, token from {source}"


def check_github():
    """Return (ready, line)."""
    status = github_access.github_status()
    if status["ok"]:
        scopes = (
            "scopes not reported, so they're tested when used"
            if status["scopes"] is None
            else "has the repo and read:org scopes"
        )
        return True, f"GitHub: OK, signed in as {status['login']} ({scopes})"
    if not status.get("fix"):
        return (
            False,
            f"GitHub: COULDN'T CHECK ({status['problem']}). Try again shortly.",
        )
    if status["fix"].startswith("gh "):
        return False, (
            f"GitHub: NOT READY ({status['problem']}). "
            f"{IN_THEIR_TERMINAL}: {status['fix']}"
        )
    return (
        False,
        f"GitHub: NOT READY ({status['problem']}). Ask the user to {status['fix']}",
    )


def check_repo(full_name):
    """Return (ready, line)."""
    verdict, reason = github_access.repo_scope(full_name)
    return verdict == "OK", f"Repo: {verdict}, {reason}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo", help="the repo to check, as owner/name")
    options = parser.parse_args(argv)

    results = [check_jira(), check_github()]
    if options.repo:
        if results[1][0]:
            results.append(check_repo(options.repo))
        else:
            results.append((False, "Repo: NOT CHECKED, because gh isn't ready"))
    for _, line in results:
        print(line)
    ready = all(ok for ok, _ in results)
    print(
        "Ready: yes"
        if ready
        else "Ready: no. Don't go on until every line above says OK."
    )
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
