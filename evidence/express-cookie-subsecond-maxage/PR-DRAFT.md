# PR draft (not submitted)

**Base:** `master` (5.x bug fix, per CONTRIBUTING "Use the `master` branch for bug fixes")
**Title:** `fix(res.cookie): don't send Max-Age=0 for a sub-second maxAge`

## Body

`res.cookie(name, value, { maxAge: 500 })` currently sends:

```
name=value; Max-Age=0; Path=/; Expires=<now + 0.5s>
```

`Math.floor(maxAge / 1000)` turns any positive `maxAge` below 1000 into `Max-Age=0`. RFC 6265 gives `Max-Age` precedence over `Expires` (§4.1.2.2) and treats `Max-Age=0` as "expire now" (§5.2.2). So a cookie the app asked to keep for half a second is deleted on arrival, just like `res.clearCookie`.

This change keeps the floor but sends `Max-Age=1` when a positive `maxAge` would otherwise floor to 0. `maxAge: 0` and negative values still produce `Max-Age=0`, and values of 1000 ms or more are unchanged.

Tests: one for the sub-second case (fails on master), and one pinning `maxAge: 0` -> `Max-Age=0`. `npm test` passes (1263) and `npm run lint` is clean.

Refs #<issue number, if one is opened first per CONTRIBUTING>

The bug was found by a Quality Playbook (https://github.com/andrewstellman/quality-playbook) code-review run. Reproduction, the test, and the fix were done by Claude (Anthropic) and reviewed by me before submitting.

## Template

The expressjs PR template (org-level `.github/PULL_REQUEST_TEMPLATE.md`) has no checklist. It asks for a description and includes the Developer's Certificate of Origin 1.1 as an HTML comment. Keep that comment in the body when opening the PR.

Contributing guide items (https://github.com/expressjs/.github/blob/HEAD/CONTRIBUTING.md):
- [ ] Issue created first and referenced (CONTRIBUTING step 1, "Create an issue for the bug you want to fix")
- [x] Tests pass (`npm test`: 1263 passing)
- [x] Lint (`npm run lint` exits 0 on the patched branch)
- [x] Bug fix includes a test
- [ ] Read the OpenJS AI Coding Assistants Policy (linked from the expressjs.com footer) and adjust the disclosure line if it requires specific wording
