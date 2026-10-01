# Review panel: eight proposed fixes to @adonisjs/http-server (campaign 2026-09-30)

You are one member of a review panel. Andrew Stellman plans to submit these as PRs to adonisjs/http-server (maintainers: Harminder Virk "thetutlage", Romain Lanz). Your job is to stop anything that shouldn't go out, and to say exactly what must change on anything that should.

## Materials
- Base tree (unfixed, read-only): /tmp/adonw at 3bf3cde3 (9.3.1). node_modules installed.
- Each fix: /tmp/adonreview/packets/<ID>/ contains fix.patch, PR-DRAFT.md (the exact PR text), CONFIRMATION.md (the confirmer's evidence) and WHERE.txt (the fixed worktree, read-only).
- Run tests in any tree: cd <tree> && HOME=/tmp/home node --import=@poppinss/ts-exec --enable-source-maps bin/test.ts [--files=tests/<file>.spec.ts]   (base suite: 660 passed)
- Typecheck: <tree>/node_modules/.bin/tsc --noEmit -p <tree>. Lint: <tree>/node_modules/.bin/eslint <files>.
- If you need to modify code or run experiments, copy a tree into /tmp/adonreview/scratch/<your-id>/ first. Never modify /tmp/adonw or /tmp/adonfix/*.
- Write only your output file /tmp/adonreview/out/<your-id>.md (and your scratch dir). Never push, post, open issues or PRs.
- Never fabricate. Paste command output verbatim. If you didn't check something, say so.

| ID | Claim |
|---|---|
| uuid-matcher | router.matchers.uuid() regex `[0-9a-zA-F]` accepts g-z |
| redirect-qs-separator | withQs on a target that already has `?query` produces a second `?` |
| cookie-maxage-zero | cookie `maxAge: 0` drops Max-Age (truthiness check) |
| toroute-qs-mutation | toRoute mutates the caller's options (`options.qs = undefined`), so a brisk route redirect loses qs after the first request |
| send-error-object | response.send(new Error()) serializes to `{}` JSON; docs say errors are converted via toString |
| lookup-route-error | findOrFail throws a plain Error instead of the defined E_CANNOT_LOOKUP_ROUTE (regression from v6) |
| unknown-content-type | type() writes `Content-Type: false` for unknown types (extension-less downloads) |
| reset-content-body | status(205).send(body) sends content; RFC 9110 says MUST NOT |

## Maintainer context everyone needs
- A Linux NVMe maintainer replied to one of Andrew's earlier AI-assisted patches: "This is a very long explanation for a simple protocol fix... Short and to the point."
- Maintainers are primed to reject AI-generated PRs; several projects in this campaign ban them outright (Pallets) or close outside PRs (zod, httpx). adonisjs has no AI policy; its contributing guide asks for a failing test, uses conventional commits, and says bug-fix PRs are "mostly accepted once the bug has been confirmed". Recent merged outside fixes: #138 "fix(request): use first forwarded host", #139 "fix(response): preserve native response cookies".
- Every PR ends with: "Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change." Judge whether that line and the rest of the text will land well.

## Roster (you are exactly one)
- EXEC-A, EXEC-B (executors, independent). For every fix: in a scratch copy of the base, apply ONLY the test part of fix.patch and confirm the new test fails for the claimed reason (read the assertion text); apply the rest and confirm it passes; revert only the source part and confirm it fails again; run the whole suite on the fixed tree (expect 661, 0 failed); tsc on the fixed tree. Also run the confirmer's repro if one exists in /tmp/adonv/BUG-NNN/. End with a table ID | red | green | revert | suite | tsc | PASS/FAIL. EXEC-B additionally writes 3 edge inputs per fix of its own choosing and runs them against base and fixed.
- O1 MAINTAINER. Read each diff as Harminder would, with the repo's conventions and recent history (git log in /tmp/adonw). Would you merge as written? What would you ask to change?
- O2 SECURITY. Does any fix introduce or remove a security-relevant behaviour (open redirect, header injection, cache poisoning, auth, DoS)? Is any PR text framing something as security that isn't, or missing a security consequence that is?
- O3 CORRECTNESS. Try to break each fix: inputs or configurations where the fixed code is still wrong or newly wrong, especially ones the new test doesn't build. Write and run small tests in your scratch dir.
- O4 NOT-A-BUG. Argue the maintainer's side as hard as the evidence allows: intended, documented, tested, not worth the churn, better fix elsewhere, previously declined. Concede only where source or docs force you; quote what forced you. Check upstream issues/PRs (web search or GitHub API) for prior discussion.
- O5 SLOP-A. A maintainer tired of AI PRs: text out of proportion, claims beyond evidence, restating the diff, unrelated changes, off-style tests, generated-sounding padding, leftover notes. Propose exact rewrites.
- S1 READABILITY-CODE. Naming, structure, comments, consistency with surrounding code and project idiom.
- S2 READABILITY-TESTS. Would each test catch a regression, fail for the right reason, and read like its neighbours? Minimal and idiomatic?
- S3 SLOP-B. Same charter as O5, independently.
- S4 QA. Coverage gaps a QA engineer would flag: untested paths the fix touches, missing negative cases, reliance on implementation details.
- S5 COMPAT. What behaviour changes for existing users (including ones who might rely on the old behaviour)? Does each PR state it?
- S6 PERFORMANCE. Any hot-path cost (routing, cookie serialization, response writing)? Allocation or regex changes?
- S7 CITATIONS. Every factual claim in each PR-DRAFT and commit message: is it true of the code and traceable (doc sentence verbatim in /sessions/kind-zealous-edison/mnt/QPB/repos/campaign-2026-09-29/adonisjs-http-server/reference_docs/cite/, RFC text, file:line)? Flag anything unverifiable or wrong.
- S8 COMPLIANCE. The project's contribution rules (commitlint/conventional commits, tests required, npm only, format/lint, PR template if any in adonisjs/.github), AI-disclosure norms, licence, author identity in the patch. Would any fix be rejected on process grounds?

## Protocol
1. Personas: form your view from the patch, PR text and source first. Write your initial verdict for every fix before reading CONFIRMATION.md or any other reviewer's output. Don't read /tmp/adonreview/out/ except your own file.
2. Then you may read CONFIRMATION.md; if it changes your mind, add an "after reading" note rather than rewriting.

## Output (write to /tmp/adonreview/out/<your-id>.md and also return it as text)
For each of the eight IDs:
### <ID>
Verdict: SHIP | FIX-REQUIRED | REJECT
Confidence: high | medium | low
Findings: numbered, each with file:line or a quote, and what must change.
REJECT = should not be submitted. FIX-REQUIRED = submit after the listed changes. End with a 3-line overall summary. Keep the whole file under ~120 lines.
