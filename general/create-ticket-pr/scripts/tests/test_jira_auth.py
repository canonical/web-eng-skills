import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import jira_auth

TOKEN = "ATATT3xFfGF0-example_token=="
SITE = "https://example.atlassian.net"


class FakeKeyring:
    """Stands in for secret-tool and `security`, remembering what was stored."""

    def __init__(self):
        self.secrets = {}
        self.calls = []

    def __call__(self, command, stdin=None):
        self.calls.append((command, stdin))
        out = ""
        if command[:2] == ["secret-tool", "store"]:
            self.secrets[tuple(command[-4:])] = stdin
        elif command[:2] == ["secret-tool", "lookup"]:
            out = self.secrets.get(tuple(command[2:]), "")
        elif command == ["security", "-i"]:
            self.secrets["keychain"] = stdin.split('-w "')[1].split('"')[0]
        elif command[:2] == ["security", "find-generic-password"]:
            out = self.secrets.get("keychain", "") + "\n"
        return subprocess.CompletedProcess(command, 0, out, "")


class SiteTests(unittest.TestCase):
    def test_atlassian_cloud_over_https_only(self):
        self.assertEqual(jira_auth.check_site(SITE + "/"), SITE)
        for bad in (
            "http://example.atlassian.net",
            "https://example.com",
            "https://example.atlassian.net.evil.example",
            "https://me@example.atlassian.net",
            "https://example.atlassian.net/browse/ABC-1",
            "https://example.atlassian.net/?next=x",
            "",
        ):
            with self.assertRaises(ValueError, msg=bad):
                jira_auth.check_site(bad)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp()) / "create-ticket-pr"

    def test_file_is_private_and_config_has_no_token(self):
        jira_auth.save_token("file", "me@example.com", TOKEN, self.folder)
        jira_auth.write_config(self.folder, SITE, "me@example.com", "file")
        token_file = self.folder / "jira-token"
        self.assertEqual(stat.S_IMODE(token_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.folder.stat().st_mode), 0o700)
        self.assertNotIn(TOKEN, (self.folder / "config.json").read_text())
        self.assertEqual(
            jira_auth.load_credentials(self.folder, environ={}),
            (SITE, "me@example.com", TOKEN, mock.ANY),
        )

    def test_file_others_can_read_is_refused(self):
        jira_auth.save_token("file", "me@example.com", TOKEN, self.folder)
        os.chmod(self.folder / "jira-token", 0o644)
        with self.assertRaisesRegex(jira_auth.NotSetUp, "chmod 600"):
            jira_auth.load_token("file", "me@example.com", self.folder)

    def test_secret_tool_gets_the_token_on_stdin_not_argv(self):
        keyring = FakeKeyring()
        with mock.patch.object(jira_auth, "_run", keyring):
            jira_auth.save_token("secret-tool", "me@example.com", TOKEN, self.folder)
            jira_auth.write_config(self.folder, SITE, "me@example.com", "secret-tool")
            site, email, token, source = jira_auth.load_credentials(
                self.folder, environ={}
            )
        self.assertEqual(token, TOKEN)
        self.assertIn("keyring", source)
        for command, _ in keyring.calls:
            self.assertNotIn(TOKEN, " ".join(command))

    def test_keychain_gets_the_token_on_stdin_not_argv(self):
        keyring = FakeKeyring()
        with mock.patch.object(jira_auth, "_run", keyring):
            jira_auth.save_token("keychain", "me@example.com", TOKEN, self.folder)
            self.assertEqual(
                jira_auth.load_token("keychain", "me@example.com", self.folder), TOKEN
            )
            with self.assertRaises(OSError):
                jira_auth.save_token(
                    "keychain", "me@example.com", 'a" -x "b', self.folder
                )
        for command, _ in keyring.calls:
            self.assertNotIn(TOKEN, " ".join(command))

    def test_failed_save_is_reported(self):
        failed = subprocess.CompletedProcess([], 1, "", "no keyring daemon")
        with mock.patch.object(jira_auth, "_run", return_value=failed):
            with self.assertRaises(OSError):
                jira_auth.save_token(
                    "secret-tool", "me@example.com", TOKEN, self.folder
                )

    def test_environment_wins_and_bad_sites_are_refused(self):
        environ = {"JIRA_EMAIL": "env@example.com", "JIRA_API_TOKEN": "env-token"}
        self.assertEqual(
            jira_auth.load_credentials(self.folder, environ)[1:3],
            ("env@example.com", "env-token"),
        )
        with self.assertRaisesRegex(jira_auth.NotSetUp, "atlassian.net"):
            jira_auth.load_credentials(
                self.folder, {**environ, "JIRA_URL": "https://evil.example"}
            )

    def test_nothing_saved(self):
        with self.assertRaisesRegex(jira_auth.NotSetUp, "no Jira token"):
            jira_auth.load_credentials(self.folder, environ={})


class JiraCallTests(unittest.TestCase):
    def opener(self, response=None, error=None):
        fake = mock.Mock()
        if error:
            fake.open.side_effect = error
        else:
            fake.open.return_value = io.BytesIO(json.dumps(response).encode())
        return fake

    def test_whoami_sends_basic_auth(self):
        opener = self.opener({"displayName": "A Person", "accountId": "1"})
        self.assertEqual(
            jira_auth.whoami(SITE, "me@example.com", TOKEN, opener), "A Person"
        )
        request = opener.open.call_args[0][0]
        self.assertEqual(request.full_url, SITE + "/rest/api/2/myself")
        self.assertTrue(request.get_header("Authorization").startswith("Basic "))

    def test_errors_explain_and_never_contain_the_token(self):
        for code, words in ((401, "rejected"), (302, "redirected"), (500, "500")):
            error = urllib.error.HTTPError(SITE, code, "x", {}, io.BytesIO(b""))
            with self.assertRaises(jira_auth.JiraError) as caught:
                jira_auth.whoami(
                    SITE, "me@example.com", TOKEN, self.opener(error=error)
                )
            self.assertIn(words, str(caught.exception))
            self.assertNotIn(TOKEN, str(caught.exception))
            self.assertEqual(caught.exception.status, code)
        offline = urllib.error.URLError("no route")
        with self.assertRaisesRegex(jira_auth.JiraError, "couldn't reach"):
            jira_auth.whoami(SITE, "me@example.com", TOKEN, self.opener(error=offline))

    def test_redirects_are_not_followed(self):
        handler = jira_auth._NoRedirect()
        request = urllib.request.Request(SITE)
        self.assertIsNone(
            handler.redirect_request(request, None, 302, "", {}, "https://evil.example")
        )


if __name__ == "__main__":
    unittest.main()
