"""Set up create-ticket-pr on this machine: your Jira API token and the GitHub CLI.

Usage: python3 setup.py [--site URL] [--storage auto|keyring|file] [--forget]

Run it yourself in your own terminal, not through an agent. It asks for your
Jira API token without showing it, checks it with Jira, then saves it in your
system keyring, or in a file only you can read if there's no keyring. Then it
checks that gh is signed in with the scopes the skill needs.
"""

import argparse
import getpass
import os
import subprocess
import sys

import github_access
import jira_auth


def ask_yes(question):
    return input(f"{question} [Y/n] ").strip().lower() in ("", "y", "yes")


def ask_email(default):
    while True:
        prompt = "Atlassian account email" + (f" [{default}]" if default else "")
        email = input(f"{prompt}: ").strip() or default
        if jira_auth.SAFE_EMAIL.match(email):
            return email
        print("That doesn't look like an email address.")


def ask_token(site, email):
    """Return (token, display name), or (None, None) after three failed tries."""
    print(f"No API token yet? Create one at {jira_auth.TOKEN_PAGE}")
    for _ in range(3):
        token = getpass.getpass("Jira API token (hidden): ").strip()
        if not token:
            print("Nothing entered.")
            continue
        try:
            return token, jira_auth.whoami(site, email, token)
        except jira_auth.JiraError as error:
            print(f"Jira didn't accept it: {error}.")
            if error.status not in (401, 403):
                return None, None
    return None, None


def storage_order(choice):
    keyring = jira_auth.keyring_available()
    if choice == "file":
        return ["file"]
    if choice == "keyring":
        return [keyring] if keyring else []
    return [keyring, "file"] if keyring else ["file"]


def setup_jira(site, choice, folder):
    config = jira_auth.read_config(folder)
    if os.environ.get("JIRA_EMAIL") and os.environ.get("JIRA_API_TOKEN"):
        print(
            "Note: JIRA_EMAIL and JIRA_API_TOKEN are set in your environment. "
            "They're used instead of anything saved here until you unset them."
        )
    print(f"Jira site: {site}")
    email = ask_email(config.get("email", ""))
    token, name = ask_token(site, email)
    if not token:
        print("Jira: not set up. Nothing was saved.")
        return False
    order = storage_order(choice)
    if not order:
        print("No keyring found. On Ubuntu: sudo apt install libsecret-tools")
    for storage in order:
        try:
            jira_auth.save_token(storage, email, token, folder)
        except OSError as error:
            print(f"Couldn't save it with {storage}: {error}")
            continue
        old = (config.get("storage"), config.get("email"))
        if old[0] in jira_auth.STORAGES and old != (storage, email):
            jira_auth.delete_token(old[0], old[1], folder)
        jira_auth.write_config(folder, site, email, storage)
        print(f"Jira: OK. Signed in as {name}.")
        print(f"The token is saved in {jira_auth.describe(storage, folder)}.")
        if storage == "file" and sys.platform.startswith("linux"):
            print(
                "To keep it in your keyring instead: "
                "sudo apt install libsecret-tools, then run this again."
            )
        return True
    print("Jira: the token works, but it couldn't be saved anywhere.")
    return False


def setup_github():
    status = github_access.github_status()
    if not status["ok"]:
        print(f"GitHub: {status['problem']}.")
        fix = status.get("fix") or ""
        if fix.startswith("gh ") and ask_yes(f"Run `{fix}` now?"):
            subprocess.run(fix.split())
            status = github_access.github_status()
        if not status["ok"]:
            print(f"GitHub: not set up. Fix: {fix or 'try again later'}")
            return False
    print(f"GitHub: OK. gh is signed in as {status['login']}.")
    teams = github_access.web_teams()
    if teams is None:
        print(
            f"Couldn't read the {github_access.ORG}/{github_access.ROOT_TEAM} "
            "team, so the skill can't tell web repos apart. You need to be a "
            "member of the canonical organisation on GitHub."
        )
        return False
    print(
        f"Can see {github_access.ROOT_TEAM} and the {len(teams) - 1} teams under "
        "it, so web repos can be recognised."
    )
    return True


def forget(folder):
    config = jira_auth.read_config(folder)
    if config.get("storage") in jira_auth.STORAGES:
        jira_auth.delete_token(config["storage"], config.get("email", ""), folder)
    try:
        (folder / "config.json").unlink()
    except FileNotFoundError:
        pass
    print("Deleted the saved Jira token and settings. gh is unchanged.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Set up the Jira token and GitHub CLI for create-ticket-pr."
    )
    parser.add_argument(
        "--site",
        help=f"Jira site (default: the saved one, or {jira_auth.DEFAULT_SITE})",
    )
    parser.add_argument(
        "--storage", choices=("auto", "keyring", "file"), default="auto",
        help="where to save the token (default: the keyring if there is one)",
    )  # fmt: skip
    parser.add_argument(
        "--forget", action="store_true", help="delete the saved token and settings"
    )
    options = parser.parse_args(argv)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(
            "Run this yourself in your own terminal. It asks for your Jira token, "
            "which shouldn't go through an agent or a pipe.",
            file=sys.stderr,
        )
        return 2
    folder = jira_auth.config_dir()
    try:
        if options.forget:
            forget(folder)
            return 0
        saved = jira_auth.read_config(folder).get("site")
        site = jira_auth.check_site(options.site or saved or jira_auth.DEFAULT_SITE)
        jira_ok = setup_jira(site, options.storage, folder)
        print()
        github_ok = setup_github()
    except (jira_auth.NotSetUp, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\nStopped.")
        return 130
    print()
    if jira_ok and github_ok:
        print(
            "All set. Your agent can check with preflight.py, or just give it a ticket."
        )
        return 0
    print("Not finished: fix the items above, then run this again.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
