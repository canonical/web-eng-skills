import contextlib
import io
import unittest
from unittest import mock

import github_access
import jira_auth
import preflight
import setup

SIGNED_IN = {"ok": True, "login": "someone", "scopes": {"repo", "read:org"}}
CREDENTIALS = (
    "https://example.atlassian.net",
    "me@example.com",
    "secret",
    "your keyring",
)


def run(main, *args):
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        code = main(list(args))
    return code, output.getvalue()


class SetupTests(unittest.TestCase):
    def test_refuses_without_a_terminal(self):
        with mock.patch("sys.stdin.isatty", return_value=False):
            code, out = run(setup.main)
        self.assertEqual(code, 2)
        self.assertIn("your own terminal", out)


class PreflightTests(unittest.TestCase):
    def patch(
        self, credentials=CREDENTIALS, whoami="A Person", status=SIGNED_IN, scope=None
    ):
        patches = [
            mock.patch.object(
                jira_auth,
                "load_credentials",
                side_effect=credentials if isinstance(credentials, Exception) else None,
                return_value=credentials,
            ),
            mock.patch.object(
                jira_auth,
                "whoami",
                side_effect=whoami if isinstance(whoami, Exception) else None,
                return_value=whoami,
            ),
            mock.patch.object(github_access, "github_status", return_value=status),
            mock.patch.object(github_access, "repo_scope", return_value=scope),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_ready(self):
        self.patch(scope=("OK", "canonical/ubuntu.com is a web repo"))
        code, out = run(preflight.main, "--repo", "canonical/ubuntu.com")
        self.assertEqual(code, 0, out)
        self.assertIn("Jira: OK, signed in to example.atlassian.net as A Person", out)
        self.assertTrue(out.rstrip().endswith("Ready: yes"))
        self.assertNotIn("secret", out)

    def test_not_set_up_points_the_user_to_setup(self):
        self.patch(credentials=jira_auth.NotSetUp("no Jira token saved yet"))
        code, out = run(preflight.main)
        self.assertEqual(code, 1)
        self.assertIn("Jira: NOT SET UP", out)
        self.assertIn("their own terminal", out)
        self.assertIn(str(preflight.SETUP), out)

    def test_rejected_token(self):
        self.patch(
            whoami=jira_auth.JiraError("the email or API token was rejected", 401)
        )
        code, out = run(preflight.main)
        self.assertEqual(code, 1)
        self.assertIn("Jira: REJECTED", out)
        self.assertIn(str(preflight.SETUP), out)

    def test_unreachable_jira(self):
        self.patch(whoami=jira_auth.JiraError("couldn't reach example.atlassian.net"))
        code, out = run(preflight.main)
        self.assertEqual(code, 1)
        self.assertIn("Jira: COULDN'T CHECK", out)

    def test_github_not_signed_in_skips_the_repo(self):
        status = {
            "ok": False,
            "problem": "gh isn't signed in",
            "fix": github_access.LOGIN_COMMAND,
        }
        self.patch(status=status)
        code, out = run(preflight.main, "--repo", "canonical/ubuntu.com")
        self.assertEqual(code, 1)
        self.assertIn(github_access.LOGIN_COMMAND, out)
        self.assertIn("Repo: NOT CHECKED", out)

    def test_out_of_scope_repo(self):
        self.patch(scope=("STOP", "canonical/snapd isn't a web repo"))
        code, out = run(preflight.main, "--repo", "canonical/snapd")
        self.assertEqual(code, 1)
        self.assertIn("Repo: STOP", out)


if __name__ == "__main__":
    unittest.main()
