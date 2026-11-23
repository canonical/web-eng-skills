# Canonical web team review conventions

Lessons from past reviews and from authors' replies to them. Read this before the code review (step 5). Each entry is something a reviewer got wrong or missed before.

## Vanilla Framework macros

Many pages on canonical.com, ubuntu.com and similar sites are built from `templates/_macros/vf_*.jinja` (Vanilla Framework patterns). Before writing a finding about markup a macro generates, read that macro at the PR's head commit. Then check:

- **Defaults.** Don't flag a class or attribute as missing when the macro adds it by default. Example: the `vf_hero` primary CTA already gets `p-button--positive`.
- **What the macro accepts.** Only suggest a fix the author can make through the macro's parameters. Example: `vf_data_spotlight` links take only `url` and `text`, so `js-invoke-modal` can't be added there. If the fix needs a macro change, say so and route it to the macro.
- **Upstream fixes.** For a bug in a shared macro or Vanilla pattern, compare the repo's `vanilla-framework` version in `package.json` with the latest release (`npm view vanilla-framework version`). Check the Vanilla changelog or the macro on `canonical/vanilla-framework` `main` to see whether it's already fixed. If it is, recommend bumping the version rather than patching it locally. Example: `vf_divided_section` used to put `<hr>` directly inside `<ul>`, and a version bump fixed it.
- **Default responsive behaviour isn't a finding.** Macro layouts at each breakpoint come from the design system, and Design has already approved them. Examples: a 25/75 hero image scaling to full width at tablet, or a 3-item data spotlight wrapping 1+2 at tablet. Only raise a layout difference when the Figma frame for that breakpoint shows something different.

## Content and metadata

- **Title vs H1.** The meta `title` often differs from the `<h1>` because it comes from the copydoc's SEO section. That's intentional. Only check the title against the SEO section.
- **Contact CTAs.** There are two working patterns:
  - **`href="/contact-us"` with `js-invoke-modal` + `aria-controls`:** opens the page's contact pop-up and still works without JavaScript. Use this wherever the link can take attributes, e.g. the `vf_hero` CTA or raw HTML.
  - **`href="<page>#get-in-touch"`:** `static/js/modals.js` opens the contact pop-up whenever the URL hash is `#get-in-touch`, so this works even where the macro can't add `js-invoke-modal`, e.g. `vf_data_spotlight` links. Without JS it does nothing, because no element has that id. It's an acceptable trade-off for macro links, but suggest `/contact-us` + `js-invoke-modal` wherever attributes are allowed.

  Copydocs and Figma usually write `#get-in-touch`, so either implementation is fine. Check every Contact CTA opens the pop-up by clicking it in a browser test.
- **Copy-pasted URLs.** Flag tracking or session parameters pasted in from a browser (`?_gl=`, `_gcl_aw`, `_gcl_au`, `utm_*`, `usp=sharing`) and give the clean URL.
- **Brands named in copy.** Check that every brand or product named in the copy (e.g. in a logo list) appears on the page, and the other way round.

## Markup

- **Ids copied from examples.** An id like `id="2-blocks"` was copied from a macro example. It's meaningless, may collide with other ids, and fails `valid-id` because it starts with a digit.
- **`role="list"` on a `<ul>`** with list styling removed is deliberate: Safari drops list semantics without it. html-validate reports it as `no-redundant-role`. Don't flag it.
- **Page-level `<style nonce="{{ csp_nonce }}">` blocks** inside `{% block content %}` are an established pattern on canonical.com data pages (e.g. kafka, lakehouse, services). html-validate reports `<style>` inside `<div>`, but it isn't a finding for content PRs.
- **Spacing utilities.** `u-no-margin--bottom` and similar often differ on purpose between blocks, e.g. a heading followed by a button vs one followed by a text link. Only flag spacing when Figma shows a difference.
- **Lazy loading.** Judge "below the fold" at desktop size (1440×900). A section visible in the first desktop viewport, such as a logo row right under the hero, can keep `loading="auto"`.
- **Informative logos.** A logo with text in it (e.g. "Includes MySQL") is informative and needs alt text such as `alt="MySQL"`, not `alt=""`.

## Where errors come from

Before blaming a PR for an HTML validation or accessibility error, classify it:

- **This PR:** markup or arguments written in the changed template.
- **Shared macro or include:** `_macros/vf_*.jinja`, `load_form`, base templates. Report these as macro bugs and check upstream (above).
- **Already on the live site:** compare with the live page. Report these as pre-existing, briefly.

The contact form included by `load_form` currently produces several validation errors on every page (duplicate `id="company"`, `<h3>` inside `<label>`, `aria-label` misuse). These are pre-existing and aren't a finding for content PRs.

## Screenshot pitfalls

- The nav search overlay (`.p-navigation__search-overlay`) is a fixed full-viewport layer that paints a grey band over element screenshots. `scripts/capture.mjs` hides it.
- Lazy-loaded images can come out blank if the capture scrolls too fast. Re-capture before reporting missing images.

## Tooling notes

- A 404 for a `/docs/...` path on the demo is expected, because docs are served in production only. Check the same path on the live site instead.
- The live site can return 5xx at times. If it does, work out where an error comes from by checking other pages built from the same macro.
