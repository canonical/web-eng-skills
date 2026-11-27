"""Jira credentials: where they're kept and how they're checked.

Shared by setup.py and preflight.py; not run directly. The token is kept in
the system keyring when there is one (secret-tool on Linux, the login keychain
on macOS), otherwise in a file only you can read. Nothing here prints it.
"""

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_SITE = "https://warthogs.atlassian.net"
TOKEN_PAGE = "https://id.atlassian.com/manage-profile/security/api-tokens"
SERVICE = "create-ticket-pr-jira"
STORAGES = ("secret-tool", "keychain", "file")
# Atlassian API tokens only use these. Anything else isn't passed to `security -i`.
TOKEN_CHARS = re.compile(r"^[A-Za-z0-9_=+/.-]+$")
SAFE_EMAIL = re.compile(r'^[^@\s"\\]+@[^@\s"\\]+\.[^@\s"\\]+$')


class NotSetUp(Exception):
    """No usable credentials. The message says what's missing."""


class JiraError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "create-ticket-pr"


def check_site(site):
    """Return the site's URL, refusing anything but https://<name>.atlassian.net."""
    parts = urllib.parse.urlsplit(site.strip())
    host = parts.hostname or ""
    if (
        parts.scheme != "https"
        or not host.endswith(".atlassian.net")
        or parts.username
        or parts.path.strip("/")
        or parts.query
    ):
        raise ValueError(f"{site!r} isn't an https://<name>.atlassian.net address")
    return f"https://{host}"


def keyring_available():
    """The keyring this machine has, or None."""
    if sys.platform == "darwin" and shutil.which("security"):
        return "keychain"
    if shutil.which("secret-tool"):
        return "secret-tool"
    return None


def describe(storage, folder):
    return {
        "secret-tool": "your keyring (secret-tool)",
        "keychain": "your login keychain",
        "file": f"a private file, {folder / 'jira-token'}",
    }[storage]


def _run(command, stdin=None):
    try:
        return subprocess.run(
            command, input=stdin, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _write_private(path, text):
    """Write a file only its owner can read, replacing any older copy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + ".tmp")
    handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w") as file:
        file.write(text)
    os.chmod(temporary, 0o600)  # in case it already existed with wider permissions
    os.replace(temporary, path)


def save_token(storage, email, token, folder):
    """Save the token and read it back. Raises OSError if that didn't work."""
    if storage == "secret-tool":
        done = _run(
            ["secret-tool", "store", "--label", "create-ticket-pr: Jira API token",
             "service", SERVICE, "account", email],
            stdin=token,
        )  # fmt: skip
        if not done or done.returncode:
            raise OSError(
                "secret-tool couldn't save it (is a keyring service running?)"
            )
    elif storage == "keychain":
        # `security -i` reads the command from stdin, so the token isn't in argv
        if not TOKEN_CHARS.match(token) or not SAFE_EMAIL.match(email):
            raise OSError("the token or email has characters the keychain can't take")
        command = f'add-generic-password -U -a "{email}" -s "{SERVICE}" -w "{token}"\n'
        done = _run(["security", "-i"], stdin=command)
        if not done or done.returncode:
            raise OSError("the keychain couldn't save it")
    elif storage == "file":
        _write_private(folder / "jira-token", token)
    else:
        raise ValueError(storage)
    if load_token(storage, email, folder) != token:
        raise OSError(f"{storage} didn't give the token back after saving it")


def load_token(storage, email, folder):
    """Return the saved token, or None."""
    if storage == "secret-tool":
        done = _run(["secret-tool", "lookup", "service", SERVICE, "account", email])
    elif storage == "keychain":
        done = _run(
            ["security", "find-generic-password", "-a", email, "-s", SERVICE, "-w"]
        )
    elif storage == "file":
        path = folder / "jira-token"
        if not path.exists():
            return None
        if os.name == "posix" and path.stat().st_mode & 0o077:
            raise NotSetUp(f"{path} can be read by other users: run `chmod 600 {path}`")
        return path.read_text().strip() or None
    else:
        return None
    if not done or done.returncode:
        return None
    return done.stdout.strip() or None


def delete_token(storage, email, folder):
    if storage == "secret-tool":
        _run(["secret-tool", "clear", "service", SERVICE, "account", email])
    elif storage == "keychain":
        _run(["security", "delete-generic-password", "-a", email, "-s", SERVICE])
    elif storage == "file":
        try:
            (folder / "jira-token").unlink()
        except FileNotFoundError:
            pass


def read_config(folder):
    path = folder / "config.json"
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        raise NotSetUp(f"{path} can't be read: run setup.py again") from None
    return data if isinstance(data, dict) else {}


def write_config(folder, site, email, storage):
    """The site, email and where the token is. Never the token itself."""
    settings = {"site": site, "email": email, "storage": storage}
    _write_private(folder / "config.json", json.dumps(settings, indent=2) + "\n")


def load_credentials(folder=None, environ=None):
    """Return (site, email, token, where it came from). Raises NotSetUp."""
    environ = os.environ if environ is None else environ
    folder = folder or config_dir()
    config = read_config(folder)
    try:
        site = check_site(environ.get("JIRA_URL") or config.get("site") or DEFAULT_SITE)
    except ValueError as error:
        raise NotSetUp(str(error)) from None
    if environ.get("JIRA_EMAIL") and environ.get("JIRA_API_TOKEN"):
        source = "the JIRA_EMAIL and JIRA_API_TOKEN environment variables"
        return site, environ["JIRA_EMAIL"], environ["JIRA_API_TOKEN"], source
    email, storage = config.get("email"), config.get("storage")
    if not email or storage not in STORAGES:
        raise NotSetUp("no Jira token saved yet")
    token = load_token(storage, email, folder)
    if not token:
        raise NotSetUp(f"the saved token is missing from {describe(storage, folder)}")
    return site, email, token, describe(storage, folder)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """urllib would otherwise send the Authorization header on to the new host."""

    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def jira_get(site, email, token, path, opener=None):
    """GET a Jira REST path as JSON. Errors never include the token."""
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    request = urllib.request.Request(
        site + path,
        headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
    )
    try:
        with (opener or _OPENER).open(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        reason = {
            401: "the email or API token was rejected",
            403: "your account isn't allowed to do this",
            404: "not found, or your account can't see it",
        }.get(error.code, f"Jira answered {error.code}")
        if 300 <= error.code < 400:
            reason = (
                "Jira redirected the request, and it isn't followed with your token"
            )
        raise JiraError(reason, error.code) from None
    except (urllib.error.URLError, OSError, ValueError) as error:
        reason = getattr(error, "reason", error)
        raise JiraError(f"couldn't reach {site}: {reason}") from None


def whoami(site, email, token, opener=None):
    """Return the account's display name. Raises JiraError."""
    data = jira_get(site, email, token, "/rest/api/2/myself", opener)
    return data.get("displayName") or email
