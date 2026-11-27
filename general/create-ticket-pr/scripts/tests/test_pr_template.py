import unittest

import pr_template

TEMPLATE = """## Done

- [List of work items]

<!--
## Not a section, just a hint
-->

## QA

```bash
# not a heading either
task start
```

### Check if PR is ready for release

## Issue / Card

Fixes #

## Screenshots
"""


class TemplateTests(unittest.TestCase):
    def test_default_and_other_templates(self):
        files = [
            "README.md",
            ".github/PULL_REQUEST_TEMPLATE/TAKEOVER_PR.md",
            ".github/pull_request_template.md",
            "src/pull_request_template.md",
        ]
        self.assertEqual(
            pr_template.find(files),
            (
                ".github/pull_request_template.md",
                [".github/PULL_REQUEST_TEMPLATE/TAKEOVER_PR.md"],
            ),
        )
        self.assertEqual(
            pr_template.find([".github/PULL_REQUEST_TEMPLATE.md"])[0],
            ".github/PULL_REQUEST_TEMPLATE.md",
        )
        self.assertEqual(pr_template.find(["README.md"]), (None, []))

    def test_headings_leave_out_code_and_comments(self):
        self.assertEqual(
            pr_template.headings(TEMPLATE),
            [
                "Done",
                "QA",
                "Check if PR is ready for release",
                "Issue / Card",
                "Screenshots",
            ],
        )

    def test_missing_sections(self):
        body = (
            "## Done\n\n- Fixed it\n\n## qa\n\n- Open the demo\n\n## Issue  /  Card\n"
        )
        self.assertEqual(
            pr_template.missing(TEMPLATE, body),
            ["Check if PR is ready for release", "Screenshots"],
        )
        self.assertEqual(pr_template.missing(TEMPLATE, TEMPLATE), [])


if __name__ == "__main__":
    unittest.main()
