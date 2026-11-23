---
name: bau-review
description: Review a BAU (business-as-usual) website content-update pull request end to end. Reads the PR description and existing comments, opens the demo at the right URL, compares it against the linked Figma design and copydoc (Google Doc), and checks the PR's changes for HTML validation, markup and accessibility issues. Use when given a GitHub PR link to review against its design and copydoc, or asked to review a content, copy or BAU update PR.
compatibility: Needs a shell with git, the GitHub CLI (gh, signed in), curl, Python 3 and Node.js 18+. Optional - a browser tool, a Google Drive tool or connector, a Figma tool or FIGMA_TOKEN, and a model that can view images.
metadata:
  author: Canonical web team
  version: "2.0"
---

# BAU content-update review

The user gives a GitHub pull request URL. If they didn't, ask for it and stop.

Work through the steps in order. Collect findings as you go and report them all at the end (step 7).

**Don't post anything to GitHub** (comments, approvals, change requests) unless the user asks after seeing the report.

## Setup

- `SKILL_DIR` is the directory containing this `SKILL.md`. The helper scripts are in `SKILL_DIR/scripts/` and the team's conventions are in `SKILL_DIR/references/conventions.md`.
- Make a working directory for downloads and outputs, e.g. `WORK=$(mktemp -d)`. Keep downloaded files there, not in the repo.
- Read `SKILL_DIR/references/conventions.md` before step 5. It records what past reviews got wrong.
- The instructions below name capabilities ("a browser tool", "a Google Drive tool"), not specific tool names, because harnesses name them differently. Use whatever your harness provides. If a capability is missing, use the shell fallback given, and list anything you couldn't check under "Not checked" in the report.

## 1. Read the PR and its discussion

```bash
gh pr view <url> --json number,title,body,author,headRefName,headRefOid,state,files,updatedAt
gh pr diff <url>
gh api repos/<owner>/<repo>/pulls/<n>/commits --jq '.[] | "\(.sha[0:9]) \(.commit.author.date) \(.commit.message|split("\n")[0])"'
```

From the description, extract:

- **Demo URL:** usually `https://<repo-name>-<pr-number>.demos.haus/<path>`. The page to review is the demo host plus the path being changed.
- **Figma link(s):** including the `node-id` parameter.
- **Copydoc link:** usually a `docs.google.com/document/...` link.
- **Issue or Jira link**, and the **QA steps**.

Then:

- **Missing page path:** if the description doesn't give one, work it out from the changed templates (e.g. `templates/data/mysql/index.html` → `/data/mysql`).
- **Missing links:** if the demo, Figma or copydoc link is missing, record it as a finding and carry on with what you have.
- **Full-page rewrites:** the diff is hard to read, so fetch the changed files whole at the head commit. Use the SHA, because PR branches from forks don't exist in the base repo:
  ```bash
  gh api -H "Accept: application/vnd.github.raw" "repos/<owner>/<repo>/contents/<path>?ref=<headRefOid>" > $WORK/<file>
  ```
- **Copydoc block:** check that the template's `meta_copydoc` block points at the same copydoc as the description.
- **Review scope:** if the user asks you to review only the latest commit, or the PR has been reviewed before, also fetch that commit's diff (`gh api repos/<owner>/<repo>/commits/<sha>`) and focus on it.

**Read the existing discussion before reviewing:**

```bash
gh api repos/<owner>/<repo>/issues/<n>/comments --paginate --jq '.[] | "### \(.user.login) \(.created_at)\n\(.body)\n"'
gh api repos/<owner>/<repo>/pulls/<n>/reviews --jq '.[] | "### \(.user.login) \(.state) \(.submitted_at)\n\(.body)\n"'
gh api repos/<owner>/<repo>/pulls/<n>/comments --paginate --jq '.[] | "### \(.user.login) \(.path):\(.line) [\(.commit_id[0:9])]\n\(.body)\n"'
```

Treat earlier reviews (from people, bots, or a Figma and copydoc comparison) as input:
- Don't repeat findings that are already raised or resolved.
- Cite the earlier review for anything you reuse.
- Compare comment dates with commit dates to see which requested fixes were made.
- Don't re-raise anything the author has already explained with a reason, unless you have new evidence.

**Check access up front:** confirm whether you can read the Figma design (step 3) and the copydoc (step 4). If either fails, tell the user straight away what's needed, and carry on with the other checks meanwhile.

## 2. Open the demo and capture it

Fetch the page and confirm it loads. A 404, a "demo building" page or a login wall means the demo isn't ready. Say so and skip the visual checks.

```bash
curl -sL -o $WORK/page.html -w "%{http_code}\n" <demo-url>
python3 SKILL_DIR/scripts/extract_text.py $WORK/page.html > $WORK/page-text.txt
```

`page-text.txt` holds the title, meta description and main content. It lists headings with their levels, paragraphs, links with hrefs, and image alt text. Use it for the copy comparison instead of reading the raw HTML, which is often 250KB or more.

**Screenshots and accessibility scan:**

```bash
cd SKILL_DIR/scripts && [ -d node_modules ] || npm install --silent
node SKILL_DIR/scripts/capture.mjs $WORK <demo-url>
```

- **Output:** `desktop.png` (1440px), `tablet.png` (768px), `mobile.png` (375px), `rendered.html` and `axe.json`.
- **Clean captures:** the script accepts the cookie notice, hides overlays and sticky headers, and waits for lazy-loaded images.
- **No browser:** if it can't launch one, run `npx playwright install chromium` and try again.

**Viewing the screenshots:**
- If you can view images, look at all three. Crop tall images into sections (e.g. with Python PIL) so the detail is legible.
- If you can't view images, or the harness has no way to show them to you, skip the visual comparison and say so in the report. Don't guess what the page looks like.
- If your harness has a browser tool, you can use it instead to open the demo at each width.

## 3. Compare against the Figma design

Get the frame referenced by the Figma link's `node-id`, using the first of these that works:

1. **A Figma tool** your harness provides.
2. **The Figma REST API**, if `FIGMA_TOKEN` is set. URLs write node IDs as `123-456`, but the API expects `123:456`.
   - `GET https://api.figma.com/v1/files/<file_key>/nodes?ids=<node_id>` (header `X-Figma-Token: $FIGMA_TOKEN`) returns the node tree and text.
   - `GET https://api.figma.com/v1/images/<file_key>?ids=<node_id>&format=png&scale=1` returns a render URL. Download it into `$WORK`.
3. **An earlier comparison** posted on the PR (step 1), if one exists. Say that you relied on it.
4. **Ask the user** for an export of the frame.

Compare design and demo section by section, at each breakpoint the design provides:
- section order, layout and grid
- heading levels and text styles
- images, icons and logos (asset, crop, size and position)
- CTAs (style, label and placement)
- components and their variants
- backgrounds and dividers
- anything present in one but not the other

Ignore tiny pixel differences. Flag what a designer would notice.

Default macro behaviour isn't a finding (see `conventions.md`). Without the Figma frame for a breakpoint, don't list default responsive behaviour as something to check.

## 4. Compare against the copydoc

Read the Google Doc using the first of these that works:

1. **A Google Drive or Docs tool** your harness provides. Include comments if it supports them. "Not found" usually means the doc isn't shared with the connected account.
2. **A public export:** `curl -sL "https://docs.google.com/document/d/<id>/export?format=txt"`. A 401 or an HTML login page means the doc is private.
3. **A browser tool** that's signed in to Google.
4. **Ask the user** to share the doc or paste its text. Carry on with the rest of the review meanwhile.

Use the final, accepted text. Note any unresolved suggestions or comments that affect the content.

Compare the copydoc with `page-text.txt` word for word:
- Missing, extra or reordered sections and paragraphs.
- Wording, typos, punctuation and capitalisation (headings are usually sentence case).
- Curly vs straight quotes, en and em dashes.
- Link text **and** link targets. Flag `#`, empty, staging or localhost links.
- CTA labels and destinations.
- Image alt text, meta title and meta description, where the copydoc gives them.
- Lists, tables and footnotes.

Present differences as a table with three columns: location on page, copydoc says, page says.

## 5. Code review of the changes

Focus on lines the PR adds or changes. Mention pre-existing problems briefly and label them as such. Apply `references/conventions.md` throughout. In particular, read the source of any macro before suggesting a change to the markup it generates.

**HTML validation:**

```bash
npx --yes html-validate@8 --formatter text $WORK/page.html > $WORK/hv.txt 2>&1
grep -n 'id="main-content"\|<footer' $WORK/page.html | head -3      # line range of the main content
```

- Keep only errors inside the main-content line range.
- Drop style-only rules: `void-style`, `no-trailing-whitespace`, `attribute-boolean-style` and `no-inline-style`.
- Count the rest by rule (`grep -oE '\[[a-z-]+\]' | sort | uniq -c`) and look at each one.
- Work out where each error comes from: this PR, a shared macro, or the live site. To check the live site, validate the live page the same way.

Also read the changed templates for unclosed or mismatched tags, duplicate `id`s, invalid nesting and stray Jinja syntax.

**Markup:**
- **Headings:** one `<h1>`, no skipped levels, and no headings used only for styling.
- **Vanilla classes** (`p-*`, `u-*`, `row`/`col-*`): misspelt classes, column totals that don't add up, deprecated patterns, and inline styles where a utility exists.
- **Images:** `alt`, `width` and `height` are set, and below-the-fold images are lazy-loaded.
- **Links:** no `href="#"`, no tracking parameters, and relative links within the same site.
- **Leftovers:** placeholders ("Lorem ipsum", "TBC", "TODO"), commented-out blocks and debug code.
- **New pages:** have a title and description, and appear in the navigation, sitemap and redirects where needed.
- **Formatting:** consistent with the surrounding templates.

**JavaScript and CSS changes** (for PRs that aren't pure content):
- Test the behaviour on the demo with a short Playwright script (the dependency is already in `scripts/`). Check:
  - the feature works
  - there are no new console errors
  - it still works without the newest browser APIs, through feature detection or a fallback
  - keyboard and screen-reader behaviour
- Check that removed markup isn't still referenced elsewhere, for example by JS handlers or ids. Use `gh search code` or the repo's code search.

**Accessibility:**
- **Automated:** use `axe.json` from step 2, keep the violations in changed sections, and say when one comes from a shared macro.
- **Manual:**
  - meaningful alt text (`alt=""` only for decorative images)
  - descriptive link text
  - colour contrast
  - focus order and visible focus for new interactive elements
  - valid ARIA
  - table headers
  - video captions
  - `lang` attributes on foreign-language text
  - usable at 200% zoom and on mobile

If a tool can't be installed or run, do the check by reading the markup, and say which automated check was skipped.

**Before reporting a visual problem** (blank images, overlays, broken layout), check it isn't something the capture caused: re-capture or inspect the DOM. If something you reported earlier turns out to be wrong, say so clearly and withdraw it.

## 6. Run the PR's QA steps

Follow the QA steps from the description on the demo and note whether each passes. When a step needs real data you don't have, such as a real lead id or a signed-in account, say it wasn't verified rather than calling it a failure.

## 7. Report

Lead with what the author can act on: wrong links, invalid markup, accessibility failures. Leave out speculative items that are really default behaviour or deliberate choices. Every suggested fix must be possible with the macro or template as it stands.

```
## BAU review: <PR title> (#<number>)
Demo: <url reviewed>   Figma: <link>   Copydoc: <link>

**Verdict:** Ready to merge / Needs changes / Blocked (reason)

### Design vs demo
- [severity] location: issue (design shows X, demo shows Y)

### Copy vs page
| Location | Copydoc | Page |

### Code
- [severity] file:line: issue. Suggested fix.

### Accessibility
- [severity] location: issue. Suggested fix.

### QA steps
- step: pass / fail / not verified

### Not checked
- anything skipped and why
```

Severities:
- **blocker:** wrong or missing content, a broken layout, or invalid HTML or an accessibility failure this PR introduced.
- **should fix**
- **nit**

Say plainly when a section has no issues.

Offer to post the report as a PR comment. If the user says yes, write it to a file and run `gh pr comment <url> --body-file <file>`. Don't add `@` mentions unless the user asks.

## 8. Learn from replies

When the user asks you to learn from the replies to a review, read the comments posted after it (same commands as step 1). For each point the author rejected or explained, decide whether it's a general lesson (a macro default, design-system behaviour, a team convention) or specific to that PR.

Add general lessons to `references/conventions.md` in the repo this skill comes from, and propose the change as a pull request so the whole team gets it. Don't edit an installed copy only. Don't record one-off details.
