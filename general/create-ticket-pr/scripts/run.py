"""Run a check and print only what matters. The full output goes to a log file.

Usage: run.py [--tail N] [--timeout SECONDS] -- COMMAND [ARGS...]

Prints PASSED or FAILED with the exit code and time taken, the last lines of
output (more when it fails) and where the full log is. Runs COMMAND as given,
without a shell; wrap it in `bash -c '...'` if it needs one. Exits with the
command's own exit code.
"""

import argparse
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
PASS_TAIL = 5


def log_dir():
    """Inside .git when in a checkout, so logs are never committed."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--git-path", "create-ticket-pr/logs"],
            capture_output=True,
            text=True,
        )
        out = done.stdout.strip() if done.returncode == 0 else ""
    except OSError:
        out = ""
    folder = (
        Path(out).resolve()
        if out
        else Path(tempfile.gettempdir()) / "create-ticket-pr-logs"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def log_name(command):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", " ".join(command))[:50].strip("-")
    return f"{datetime.now():%Y%m%d-%H%M%S}-{slug or 'command'}.log"


def tail(path, count):
    """The last `count` lines, without colour codes or progress-bar rewrites."""
    with open(path, "rb") as file:
        file.seek(0, 2)
        size = file.tell()
        file.seek(max(0, size - 200_000))
        text = file.read().decode(errors="replace")
    lines = [ANSI.sub("", line.split("\r")[-1]).rstrip() for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return lines[-count:] if count else []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tail", type=int, default=40, help="lines to show on failure")
    parser.add_argument(
        "--timeout", type=int, default=1800, help="seconds (default 30 min)"
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    options = parser.parse_args(argv)
    command = options.command[1:] if options.command[:1] == ["--"] else options.command
    if not command:
        parser.error("give the command after --")

    log = log_dir() / log_name(command)
    shown = " ".join(command)
    started = time.monotonic()
    try:
        with open(log, "w") as output:
            process = subprocess.Popen(
                command,
                stdout=output,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
            try:
                code = process.wait(timeout=options.timeout)
                result = "PASSED" if code == 0 else f"FAILED (exit {code})"
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                code, result = 124, f"TIMED OUT after {options.timeout}s"
    except FileNotFoundError:
        print(f"COULDN'T RUN: {command[0]} isn't installed or isn't on PATH")
        return 127
    seconds = time.monotonic() - started
    print(f"{result} in {seconds:.0f}s: {shown}")
    lines = tail(log, PASS_TAIL if code == 0 else options.tail)
    if lines:
        print(f"Last {len(lines)} lines:")
        print("\n".join(f"  {line}" for line in lines))
    print(f"Full log: {log}")
    return code


if __name__ == "__main__":
    sys.exit(main())
