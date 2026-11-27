# Finding the repo

Choose the first of these that applies, and tell the user which you chose and why:

1. The repo the user named.
2. The checkout you're in, if the ticket is about it.
3. The URLs and site names in the ticket, worked out as below.

If the ticket and the checkout disagree, ask. Don't guess where a checkout is on disk, and don't clone without asking. `repo.py` then checks the repo is a web repo: a `Scope: STOP` ends the run.

## From a site name to a repo

1. **Expand short names.** In tickets, a trailing `c.com` means `canonical.com` and `u.com` means `ubuntu.com`. So `cs.c.com` is `cs.canonical.com`, and `jp.u.com` is `jp.ubuntu.com`.
2. **Use the whole hostname**, leaving out `www.` and `staging.`. The repo is usually `canonical/<hostname>`, and a subdomain is a different repo from the main site.
3. **Check it exists** with `gh repo view canonical/<hostname>`. If it doesn't, ask. Never pick a repo just because its name is similar.

| In the ticket | Repo |
|---|---|
| A path on canonical.com, including product pages such as `/multipass` | `canonical/canonical.com` |
| A path on ubuntu.com | `canonical/ubuntu.com` |
| A `canonicalwebteam.*` Python package | `canonical/canonicalwebteam.<name>` |
| Vanilla, or a `vf_*` macro | `canonical/vanilla-framework` |

## Watch out for

- **Shared code.** A bug that shows on one site can come from a package, a Vanilla macro or the global navigation. Follow the code to its source before choosing. Check which version the site pins (`requirements.txt`, `package.json`): a newer release may already fix it, and then the fix is a version bump.
- **Pages served from elsewhere.** Some paths, such as docs, are proxied or come from Discourse. If no template or route in the repo matches the path, say so.
- **Private repos and security advisory copies.** Only work in a private repo the user named. `repo.py` stops on advisory forks.
