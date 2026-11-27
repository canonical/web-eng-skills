import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import state

# Ignore the machine's git config (signing, hooks, default branch)
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


class StateTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, GIT_ENV)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.repo = Path(tempfile.mkdtemp())
        self.git("init", "-q")
        (self.repo / "page.html").write_text("old\n")
        self.git("add", ".")
        self.git("commit", "-qm", "init")
        (self.repo / "page.html").write_text("new\n")
        self.git("add", "page.html")
        self.files = Path(tempfile.mkdtemp())
        (self.files / "body.md").write_text("## Done\n\n- Fix the page\n")
        (self.files / "message.txt").write_text(
            "fix: serve the new page\n\nCloses #1\n"
        )

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def run_state(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = state.main([*args, "--path", str(self.repo)])
        return code, output.getvalue()

    def approval_args(self, command, *extra, title="fix: serve the new page"):
        return (
            command, "WD-1", *extra, "--title", title,
            "--body-file", str(self.files / "body.md"),
            "--message-file", str(self.files / "message.txt"),
            "--push", "origin/WD-1-new-page", "--into", "canonical/x:main",
        )  # fmt: skip

    def test_notes_live_inside_git_and_are_never_committed(self):
        code, out = self.run_state("path", "wd-1")
        self.assertEqual(code, 0)
        folder = self.repo.resolve() / ".git/create-ticket-pr"
        self.assertEqual(
            out.splitlines(),
            [
                f"Notes: {folder / 'WD-1.md'}",
                f"PR body: {folder / 'WD-1.pr.md'}",
                f"Commit message: {folder / 'WD-1.commit.txt'}",
            ],
        )
        subdir = self.repo / "sub"
        subdir.mkdir()
        self.assertEqual(
            str(state.state_dir(subdir)),
            str(self.repo.resolve() / ".git/create-ticket-pr"),
        )

    def test_the_approved_change_can_be_committed_and_opened(self):
        self.assertEqual(self.run_state(*self.approval_args("approve"))[0], 0)
        code, out = self.run_state(*self.approval_args("verify", "--stage", "commit"))
        self.assertEqual(code, 0, out)
        self.git("commit", "-q", "-F", str(self.files / "message.txt"))
        code, out = self.run_state(*self.approval_args("verify", "--stage", "pr"))
        self.assertEqual(code, 0, out)

    def test_any_change_after_the_yes_means_asking_again(self):
        self.run_state(*self.approval_args("approve"))
        code, out = self.run_state(
            *self.approval_args("verify", "--stage", "commit", title="fix: other")
        )
        self.assertEqual(code, 1)
        self.assertIn("title or body", out)

        (self.repo / "extra.txt").write_text("not shown to the user\n")
        self.git("add", "extra.txt")
        code, out = self.run_state(*self.approval_args("verify", "--stage", "commit"))
        self.assertEqual(code, 1)
        self.assertIn("staged changes", out)

    def test_commit_message_and_extra_commits_are_checked(self):
        self.run_state(*self.approval_args("approve"))
        self.git("commit", "-qm", "a different message")
        code, out = self.run_state(*self.approval_args("verify", "--stage", "pr"))
        self.assertEqual(code, 1)
        self.assertIn("commit message", out)

        self.git("commit", "-q", "--allow-empty", "-m", "another")
        code, out = self.run_state(*self.approval_args("verify", "--stage", "pr"))
        self.assertIn("one commit", out)

    def test_no_approval_and_nothing_staged(self):
        code, out = self.run_state(*self.approval_args("verify", "--stage", "commit"))
        self.assertEqual(code, 1)
        self.assertIn("NO APPROVAL", out)
        self.git("reset", "-q")
        code, out = self.run_state(*self.approval_args("approve"))
        self.assertEqual(code, 2)
        self.assertIn("nothing is staged", out)

    def test_default_files_are_the_ones_path_prints(self):
        folder = state.state_dir(self.repo)
        (folder / "WD-1.pr.md").write_text("## Done\n\n- Fix the page\n")
        (folder / "WD-1.commit.txt").write_text("fix: serve the new page\n")
        targets = ("--push", "origin/WD-1-x", "--into", "canonical/x:main")
        self.assertEqual(
            self.run_state("approve", "WD-1", "--title", "t", *targets)[0], 0
        )
        verify = ("verify", "WD-1", "--stage", "commit", "--title", "t", *targets)
        self.assertEqual(self.run_state(*verify)[0], 0)
        (folder / "WD-1.pr.md").write_text("## Done\n\n- Something else\n")
        self.assertEqual(self.run_state(*verify)[0], 1)

    def text_files(self):
        body, message = self.files / "body.md", self.files / "message.txt"
        return ("--body-file", str(body), "--message-file", str(message))

    def add_template(self, text="## Done\n\n## QA\n\n## Screenshots\n"):
        (self.repo / ".github").mkdir(exist_ok=True)
        (self.repo / ".github/pull_request_template.md").write_text(text)
        self.git("add", ".github")
        self.git("commit", "-qm", "template", "--", ".github")

    def test_check_finds_missing_template_sections(self):
        self.add_template()
        options = self.text_files()
        code, out = self.run_state("check", "WD-1", *options)
        self.assertEqual(code, 1)
        self.assertIn("missing these sections", out)
        self.assertIn("QA; Screenshots", out)
        (self.files / "body.md").write_text(
            "## Done\n\n- x\n\n## QA\n\n- y\n\n## Screenshots\n\nNone\n"
        )
        code, out = self.run_state("check", "WD-1", *options)
        self.assertEqual(code, 0, out)

    def test_approve_refuses_missing_sections_unless_the_user_agreed(self):
        self.add_template()
        code, out = self.run_state(*self.approval_args("approve"))
        self.assertEqual(code, 1)
        self.assertIn("NOT RECORDED", out)
        code, out = self.run_state(
            *self.approval_args("approve", "--allow-missing-sections")
        )
        self.assertEqual(code, 0, out)

    def test_another_template_can_be_named(self):
        self.add_template()
        takeover = self.repo / ".github/PULL_REQUEST_TEMPLATE"
        takeover.mkdir()
        (takeover / "TAKEOVER_PR.md").write_text("## Done\n")
        self.git("add", ".github")
        options = self.text_files()
        template = ("--template", ".github/PULL_REQUEST_TEMPLATE/TAKEOVER_PR.md")
        self.assertEqual(self.run_state("check", "WD-1", *options, *template)[0], 0)

    def test_an_empty_commit_message_is_never_allowed(self):
        (self.files / "message.txt").write_text("\n\n")
        code, out = self.run_state(
            *self.approval_args("approve", "--allow-missing-sections")
        )
        self.assertEqual(code, 1)
        self.assertIn("commit message is empty", out)

    def test_bad_input(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                state.main(["path", "not-a-key"])
            with self.assertRaises(SystemExit):
                state.main(["approve", "WD-1", "--title", "x"])


if __name__ == "__main__":
    unittest.main()
