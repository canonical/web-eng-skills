import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import docs
import run

PYTHON = sys.executable


class RunTests(unittest.TestCase):
    def setUp(self):
        self.logs = Path(tempfile.mkdtemp())
        patcher = mock.patch.object(run, "log_dir", return_value=self.logs)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_check(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = run.main(list(args))
        return code, output.getvalue()

    def test_pass_shows_a_short_tail_and_the_log(self):
        script = "for i in range(100): print('line', i)"
        code, out = self.run_check("--", PYTHON, "-c", script)
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("PASSED in "))
        self.assertIn("line 99", out)
        self.assertNotIn("line 94\n", out)
        log = out.strip().split("Full log: ")[1]
        self.assertIn("line 0\n", Path(log).read_text())

    def test_failure_keeps_the_exit_code_and_more_lines(self):
        script = "import sys\nfor i in range(100): print('line', i)\nsys.exit(3)"
        code, out = self.run_check("--tail", "20", "--", PYTHON, "-c", script)
        self.assertEqual(code, 3)
        self.assertIn("FAILED (exit 3)", out)
        self.assertIn("line 80", out)
        self.assertNotIn("line 79\n", out)

    def test_colour_codes_and_progress_rewrites_are_dropped(self):
        script = "print('\\x1b[31mred\\x1b[0m'); print('10%\\r50%\\r100%')"
        out = self.run_check("--", PYTHON, "-c", script)[1]
        shown = out.split("Last 2 lines:\n")[1].split("Full log:")[0]
        self.assertEqual(shown, "  red\n  100%\n")

    def test_timeouts_and_missing_commands(self):
        code, out = self.run_check(
            "--timeout", "1", "--", PYTHON, "-c", "import time; time.sleep(30)"
        )
        self.assertEqual(code, 124)
        self.assertIn("TIMED OUT", out)
        code, out = self.run_check("--", "no-such-command-here")
        self.assertEqual(code, 127)
        self.assertIn("COULDN'T RUN", out)


PAGE = """---
title: "Commit guidelines"
author: "someone"
---
(commit-guidelines)=
# Commit guidelines

Intro.



## Conventional commits

Use a type.

### Detail

More.

## Breaking up large tickets

Split them.
"""


class DocsTests(unittest.TestCase):
    def test_clean_drops_front_matter_and_labels(self):
        text = docs.clean(PAGE)
        self.assertTrue(text.startswith("# Commit guidelines"))
        self.assertNotIn("author", text)
        self.assertNotIn("(commit-guidelines)=", text)
        self.assertNotIn("\n\n\n", text)

    def test_section_runs_to_the_next_heading_at_its_level(self):
        part = docs.section(docs.clean(PAGE), "conventional")
        self.assertTrue(part.startswith("## Conventional commits"))
        self.assertIn("### Detail", part)
        self.assertNotIn("Breaking up", part)
        self.assertIsNone(docs.section(PAGE, "nothing like this"))

    def test_every_topic_points_at_a_docs_page(self):
        for name, (path, about) in docs.TOPICS.items():
            self.assertTrue(path.endswith(".md") and not path.startswith("/"), name)
            self.assertTrue(about, name)

    def test_no_access_is_said_plainly(self):
        output = io.StringIO()
        with mock.patch.object(
            docs.github_access, "gh", return_value=(1, "")
        ), contextlib.redirect_stdout(output):
            self.assertEqual(docs.main(["commits"]), 1)
        self.assertIn("Go on with the repo's own files", output.getvalue())

    def test_moved_page_offers_candidates(self):
        def gh(*args):
            if args[1] == f"repos/{docs.DOCS_REPO}":
                return 0, docs.DOCS_REPO
            if "git/trees" in args[1]:
                return 0, "docs/reference/qa-steps-new.md\ndocs/how-to/other.md\n"
            return 1, ""

        output = io.StringIO()
        with mock.patch.object(
            docs.github_access, "gh", gh
        ), contextlib.redirect_stdout(output):
            self.assertEqual(docs.main(["qa"]), 1)
        self.assertIn("reference/qa-steps-new.md", output.getvalue())


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    unittest.main()
