import unittest

import repo


class RemoteTests(unittest.TestCase):
    def test_remote_urls(self):
        for url, expected in (
            ("git@github.com:canonical/canonical.com.git", "canonical/canonical.com"),
            ("git@github.com:canonical/products-api", "canonical/products-api"),
            ("https://github.com/me/lxd-ui.git", "me/lxd-ui"),
            ("ssh://git@github.com/canonical/maas.io", "canonical/maas.io"),
            ("ssh://git@github.com:22/canonical/maas.io", "canonical/maas.io"),
            ("git@github-work:canonical/ubuntu.com.git", "canonical/ubuntu.com"),
        ):
            self.assertEqual("/".join(repo.parse_remote(url)), expected)
        self.assertIsNone(repo.parse_remote("git+ssh://git.launchpad.net/x"))


class ParsingTests(unittest.TestCase):
    def test_title_styles(self):
        for title, start in (
            ("WD-1: thing", "ticket key first"),
            ("[LIB-1] thing", "ticket key first"),
            ("fix(WD-1): thing", "conventional"),
            ("Fix: thing", "capitalised"),
            ("Update thing", "free text"),
        ):
            self.assertTrue(repo.title_style(title).startswith(start), title)

    def test_pull_request_triggers(self):
        yes = (
            "on: pull_request\n",
            "on:\n  pull_request:\n",
            "on: [push, pull_request]\n",
            "'on':\n  pull_request_target:\n",
            "on:\n  push:\n\n  pull_request:\n    branches: [main]\n",
            "on:\n  pull_request:\n    types: [opened, synchronize]\n",
        )
        no = (
            "on: push\njobs:\n  a:\n    if: pull_request\n",
            "on:\n  pull_request:\n    types: [closed]\njobs:\n",
            "name: x\n",
        )
        for text in yes:
            self.assertTrue(repo.pr_triggered(text), text)
        for text in no:
            self.assertFalse(repo.pr_triggered(text), text)

    def test_front_matter(self):
        text = (
            "---\napplyTo: '**/*.py'\ndescription: >\n  Long text\n  over lines\n"
            "name: x\n---\n# Body\n"
        )
        self.assertEqual(
            repo.frontmatter(text),
            {"applyTo": "**/*.py", "description": "Long text over lines", "name": "x"},
        )
        self.assertEqual(repo.frontmatter("# No front matter"), {})

    def test_mentions_whole_keys_only(self):
        for text in (
            "feat(WD-12): x",
            "wd-12-fix",
            "copilot/wd-12-x",
            "[WD-12]",
            "x WD-12",
        ):
            self.assertTrue(repo.mentions("WD-12", text), text)
        for text in ("WD-123", "AWD-12", "WD-1", None):
            self.assertFalse(repo.mentions("WD-12", text), text)

    def test_file_patterns(self):
        for path in (
            "AGENTS.md",
            "apps/web/AGENTS.md",
            ".github/AGENTS.md",
            "README.md",
        ):
            self.assertTrue(repo.INSTRUCTIONS.match(path), path)
        self.assertFalse(repo.INSTRUCTIONS.match("docs/README.md"))
        self.assertTrue(
            repo.PATH_INSTRUCTIONS.match(".github/instructions/py.instructions.md")
        )
        self.assertTrue(repo.SKILL.match(".github/skills/vanilla-patterns/SKILL.md"))


class ConventionTests(unittest.TestCase):
    def test_key_placement(self):
        for title, expected in (
            ("WD-1: thing", "key first"),
            ("[WD-1] thing", "key first"),
            ("fix(WD-1): thing", "key as the scope"),
            ("fix: thing WD-1", "key at the end"),
            ("fix: thing (WD-1)", "key at the end"),
            ("Update WD-1 thing", "key elsewhere"),
            ("fix: thing", "no key"),
        ):
            self.assertEqual(repo.key_placement(title), expected, title)

    def test_ticket_pattern_from_a_workflow(self):
        workflow = 'if [[ "$branch_name" =~ ([Ww][Dd]-[0-9]+) ]]; then\n'
        self.assertEqual(repo.ticket_pattern(workflow), "([Ww][Dd]-[0-9]+)")
        self.assertIsNone(repo.ticket_pattern("run: echo hi\n"))
        self.assertIsNone(repo.ticket_pattern('[[ "$x" =~ ([unclosed ]]'))

    def test_release_labels(self):
        config = (
            "categories:\n"
            "  - title: 'Features'\n"
            "    label: 'Feature 🎁'\n"
            "  - title: 'Bug Fixes'\n"
            "    labels:\n"
            "      - 'Bug 🐛'\n"
            "      - fix\n"
            "  - title: Docs\n"
            '    labels: [docs, "Documentation 📝"]\n'
            "change-template: '- $TITLE'\n"
            "template: |\n"
            "  label: not-a-category\n"
        )
        self.assertEqual(
            repo.release_labels(config),
            ["Feature 🎁", "Bug 🐛", "fix", "docs", "Documentation 📝"],
        )
        self.assertEqual(repo.release_labels("template: x\n"), [])


class PushAdviceTests(unittest.TestCase):
    def prs(self, same, fork):
        return [{"isCrossRepository": False}] * same + [
            {"isCrossRepository": True}
        ] * fork

    def test_push_advice(self):
        advice = repo.push_advice
        self.assertIn(
            "same-repo", advice("c/x", "origin", True, [], "me", self.prs(20, 6))
        )
        self.assertIn(
            "same-repo", advice("c/x", "origin", True, ["mine"], "me", self.prs(20, 6))
        )
        self.assertIn("same-repo", advice("c/x", "origin", True, [], "me", []))
        self.assertIn(
            "--head me:", advice("c/x", "origin", True, ["mine"], "me", self.prs(0, 27))
        )
        self.assertIn(
            "ASK: 27 of 27", advice("c/x", "origin", True, [], "me", self.prs(0, 27))
        )
        self.assertIn("--head me:", advice("c/x", None, False, ["mine"], "me", []))
        self.assertIn(
            "ASK: you can't push", advice("c/x", "origin", False, [], "me", [])
        )


if __name__ == "__main__":
    unittest.main()
