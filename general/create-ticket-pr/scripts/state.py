"""Per-ticket notes and approvals, kept inside .git so they're never committed.

Usage:
  state.py path KEY
      Print the files for KEY: the notes (read them first if they exist, and
      update them after every step), the PR body and the commit message.
  state.py check KEY [--template FILE]
      Check the PR body has every section of the repo's PR template, and that
      the commit message isn't empty. Run it before showing the user.
  state.py approve KEY --title T --push REMOTE/BRANCH --into OWNER/REPO:BASE
      Record the user's yes for exactly what's staged now, with this PR title,
      push target and PR target, and the PR body and commit message files.
      Refuses if `check` fails, unless --allow-missing-sections is given
      because the user agreed to leave those sections out.
  state.py verify KEY --stage commit|pr  (plus the same options)
      Check nothing changed since the yes: before committing (--stage commit),
      then before pushing and opening the PR (--stage pr).

Every command takes --path DIR, the checkout (default: the current directory).
--body-file and --message-file default to the files `path` prints, and
--template to the repo's default PR template.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pr_template

KEY = re.compile(r"^[A-Z][A-Z0-9_]+-\d+$")
ASK_AGAIN = "Show the user the current version and ask for a yes again."


class StateError(Exception):
    pass


def git(path, *args, stdin=None):
    done = subprocess.run(
        ["git", *args], cwd=path, input=stdin, capture_output=True, text=True
    )
    if done.returncode:
        raise StateError(f"`git {' '.join(args)}` failed: {done.stderr.strip()}")
    return done.stdout


def state_dir(path):
    out = git(path, "rev-parse", "--git-path", "create-ticket-pr").strip()
    folder = Path(out) if os.path.isabs(out) else Path(path).resolve() / out
    folder.mkdir(parents=True, exist_ok=True)
    return folder.resolve()


def normalise_message(path, text):
    """The message as `git commit -F` stores it."""
    return git(path, "stripspace", stdin=text).strip()


def text_hash(path, options):
    try:
        body = Path(options.body_file).read_text()
        message = Path(options.message_file).read_text()
    except OSError as error:
        raise StateError(f"couldn't read {error.filename}") from None
    parts = [
        options.title.strip(),
        body.rstrip(),
        normalise_message(path, message),
        options.push.strip(),
        options.into.strip(),
    ]
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def problems_with_text(path, options):
    """What's wrong with the PR body and commit message, as a list of lines."""
    problems = []
    try:
        body = Path(options.body_file).read_text()
        message = Path(options.message_file).read_text()
    except OSError as error:
        return [f"{error.filename} doesn't exist yet"]
    if not normalise_message(path, message):
        problems.append("the commit message is empty")
    top = git(path, "rev-parse", "--show-toplevel").strip()
    template = options.template
    if not template:
        template = pr_template.find(git(path, "ls-files").splitlines())[0]
    if template:
        try:
            text = (Path(top) / template).read_text()
        except OSError:
            return problems + [f"couldn't read the template {template}"]
        gone = pr_template.missing(text, body)
        if gone:
            problems.append(
                f"the PR body is missing these sections of {template}: "
                f"{'; '.join(gone)}. Keep every heading, writing 'None' under any "
                "that don't apply"
            )
    return problems


def check(path, key, options):
    problems = problems_with_text(path, options)
    if problems:
        print(f"NOT READY TO SHOW for {key}:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"The PR body and commit message for {key} are ready to show the user.")
    return 0


def approve(path, key, options):
    problems = problems_with_text(path, options)
    if problems and not (
        options.allow_missing_sections
        and all(problem.startswith("the PR body is missing") for problem in problems)
    ):
        print(f"NOT RECORDED for {key}:")
        for problem in problems:
            print(f"  - {problem}")
        print("Fix these and show the user again, or ask whether to leave them out.")
        return 1
    folder = state_dir(path)
    tree = git(path, "write-tree").strip()
    head = git(path, "rev-parse", "HEAD").strip()
    if tree == git(path, "rev-parse", "HEAD^{tree}").strip():
        raise StateError("nothing is staged: stage exactly the files the user saw")
    staged = git(path, "diff", "--cached", "--name-only").split("\n")
    record = {
        "key": key,
        "tree": tree,
        "parent": head,
        "text": text_hash(path, options),
        "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (folder / f"{key}.approval.json").write_text(json.dumps(record, indent=2) + "\n")
    count = len([name for name in staged if name])
    print(
        f"Recorded the user's yes for {key}: {count} staged "
        f"file{'' if count == 1 else 's'}. "
        "Run `verify --stage commit` before committing and "
        "`verify --stage pr` before pushing."
    )
    return 0


def verify(path, key, options):
    record_file = state_dir(path) / f"{key}.approval.json"
    try:
        record = json.loads(record_file.read_text())
    except (OSError, ValueError):
        print(f"NO APPROVAL RECORDED for {key}. {ASK_AGAIN}")
        return 1
    problems = []
    if text_hash(path, options) != record["text"]:
        problems.append("the PR title or body, commit message or targets changed")
    if options.stage == "commit":
        if git(path, "write-tree").strip() != record["tree"]:
            problems.append("the staged changes aren't the ones the user approved")
        if git(path, "rev-parse", "HEAD").strip() != record["parent"]:
            problems.append("the branch moved since the approval")
    else:
        if git(path, "rev-parse", "HEAD^{tree}").strip() != record["tree"]:
            problems.append("the committed changes aren't the ones the user approved")
        try:
            parent = git(path, "rev-parse", "HEAD^").strip()
        except StateError:
            parent = None
        if parent != record["parent"]:
            problems.append(
                "the branch isn't exactly one commit on top of the approval"
            )
        message = Path(options.message_file).read_text()
        if git(path, "log", "-1", "--format=%B").strip() != normalise_message(
            path, message
        ):
            problems.append("the commit message isn't the approved one")
    if problems:
        print(f"APPROVAL DOESN'T MATCH for {key}:")
        for problem in problems:
            print(f"  - {problem}")
        print(ASK_AGAIN)
        return 1
    print(f"Approval matches for {key}: go ahead.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=("path", "check", "approve", "verify"))
    parser.add_argument("key")
    parser.add_argument("--path", default=".")
    parser.add_argument("--stage", choices=("commit", "pr"))
    for name in (
        "--title", "--body-file", "--message-file", "--push", "--into", "--template"
    ):  # fmt: skip
        parser.add_argument(name)
    parser.add_argument("--allow-missing-sections", action="store_true")
    options = parser.parse_args(argv)
    key = options.key.upper()
    if not KEY.match(key):
        parser.error("KEY must look like ABC-123")
    if options.command in ("approve", "verify"):
        missing = [
            name for name in ("title", "push", "into") if not getattr(options, name)
        ]
        if options.command == "verify" and not options.stage:
            missing.append("stage")
        if missing:
            flags = ", ".join("--" + name for name in missing)
            parser.error(f"{options.command} needs {flags}")
    try:
        folder = state_dir(options.path)
        options.body_file = options.body_file or folder / f"{key}.pr.md"
        options.message_file = options.message_file or folder / f"{key}.commit.txt"
        if options.command == "path":
            print(f"Notes: {folder / f'{key}.md'}")
            print(f"PR body: {options.body_file}")
            print(f"Commit message: {options.message_file}")
            return 0
        if options.command == "check":
            return check(options.path, key, options)
        if options.command == "approve":
            return approve(options.path, key, options)
        return verify(options.path, key, options)
    except StateError as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
