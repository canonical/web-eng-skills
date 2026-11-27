import json
import unittest
from unittest import mock

import github_access

USER_RESPONSE = (
    "HTTP/2.0 200 OK\r\n"
    "X-Accepted-Oauth-Scopes: something\r\n"
    "X-Oauth-Scopes: gist, read:org, repo\r\n"
    "\r\n"
    '{"login": "someone"}'
)


def fake_gh(responses):
    """gh answering from {args: (code, stdout)}; anything else fails like a 404."""

    def gh(*args):
        return responses.get(args, (1, ""))

    return gh


def repo_view(name, archived=False, visibility="PUBLIC"):
    args = ("repo", "view", name, "--json", "nameWithOwner,isArchived,visibility")
    data = {"nameWithOwner": name, "isArchived": archived, "visibility": visibility}
    return args, (0, json.dumps(data))


def team_has(slug, name):
    return ("api", f"orgs/canonical/teams/{slug}/repos/{name}"), (0, "")


class SignInTests(unittest.TestCase):
    def test_scopes_come_from_the_exact_header(self):
        login, scopes = github_access.parse_user_response(USER_RESPONSE)
        self.assertEqual(login, "someone")
        self.assertEqual(scopes, {"gist", "read:org", "repo"})
        no_header = 'HTTP/2.0 200 OK\nX-Accepted-Oauth-Scopes: repo\n\n{"login": "x"}'
        self.assertEqual(github_access.parse_user_response(no_header), ("x", None))

    def test_missing_scopes(self):
        self.assertEqual(github_access.missing_scopes({"repo", "admin:org"}), [])
        self.assertEqual(github_access.missing_scopes({"repo"}), ["read:org"])
        self.assertEqual(
            github_access.missing_scopes({"public_repo"}), ["repo", "read:org"]
        )
        self.assertEqual(github_access.missing_scopes(None), [])

    def test_status(self):
        cases = (
            ({("api", "-i", "user"): (0, USER_RESPONSE)}, True, None),
            ({}, False, github_access.LOGIN_COMMAND),
            ({("auth", "status"): (0, "")}, False, None),
            (
                {("api", "-i", "user"): (0, USER_RESPONSE.replace("read:org, ", ""))},
                False,
                github_access.REFRESH_COMMAND,
            ),
        )
        for responses, ok, fix in cases:
            with mock.patch.object(github_access, "gh", fake_gh(responses)):
                status = github_access.github_status()
            self.assertEqual(status["ok"], ok, responses)
            self.assertEqual(status.get("fix"), fix, responses)

    def test_gh_not_installed(self):
        with mock.patch.object(github_access, "gh", return_value=(None, "")):
            self.assertIn("install", github_access.github_status()["fix"])


class ScopeTests(unittest.TestCase):
    teams = ["web-and-design", "portal", "portal-admins"]

    def scope(self, name, responses):
        with mock.patch.object(github_access, "gh", fake_gh(dict(responses))):
            return github_access.repo_scope(name, self.teams)

    def test_web_repos_via_the_team_or_a_team_under_it(self):
        verdict, reason = self.scope(
            "canonical/ubuntu.com",
            [
                repo_view("canonical/ubuntu.com"),
                team_has("web-and-design", "canonical/ubuntu.com"),
            ],
        )
        self.assertEqual(verdict, "OK")
        self.assertIn("public", reason)
        verdict, reason = self.scope(
            "canonical/athena",
            [
                repo_view("canonical/athena", visibility="PRIVATE"),
                team_has("portal-admins", "canonical/athena"),
            ],
        )
        self.assertEqual(verdict, "OK")
        self.assertIn("portal-admins, under web-and-design", reason)
        self.assertIn("private", reason)

    def test_stops(self):
        for name, responses, words in (
            ("someone/ubuntu.com", [], "organisation"),
            ("canonical/canonical.com-ghsa-ab12-cd34-ef56", [], "advisory"),
            ("canonical/old", [repo_view("canonical/old", archived=True)], "archived"),
            ("canonical/snapd", [repo_view("canonical/snapd")], "isn't a web repo"),
        ):
            verdict, reason = self.scope(name, responses)
            self.assertEqual(verdict, "STOP", name)
            self.assertIn(words, reason)

    def test_asks_when_it_cant_tell(self):
        self.assertEqual(self.scope("canonical/missing", [])[0], "ASK")
        self.assertEqual(self.scope("not a repo", [])[0], "ASK")
        with mock.patch.object(
            github_access, "gh", fake_gh(dict([repo_view("canonical/x")]))
        ):
            self.assertEqual(github_access.repo_scope("canonical/x")[0], "ASK")

    def test_team_tree_is_walked_to_the_bottom(self):
        def children(slug):
            path = f"orgs/canonical/teams/{slug}/teams"
            return ("api", "--paginate", path, "--jq", ".[].slug")

        responses = {
            ("api", "orgs/canonical/teams/web-and-design"): (0, "{}"),
            children("web-and-design"): (0, "portal\nlibrary\n"),
            children("portal"): (0, "portal-admins\n"),
            children("library"): (0, ""),
            children("portal-admins"): (0, ""),
        }
        with mock.patch.object(github_access, "gh", fake_gh(responses)):
            self.assertEqual(
                github_access.web_teams(),
                ["web-and-design", "portal", "library", "portal-admins"],
            )
        with mock.patch.object(github_access, "gh", fake_gh({})):
            self.assertIsNone(github_access.web_teams())


if __name__ == "__main__":
    unittest.main()
