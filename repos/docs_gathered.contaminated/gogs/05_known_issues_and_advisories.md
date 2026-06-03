# Gogs Known Issues and Advisories

## Sources

- https://github.com/gogs/gogs/security/advisories (the canonical maintainer-published list, 40 advisories at time of writing)
- https://github.com/advisories?query=gogs (the GitHub-wide advisory DB for the package `gogs.io/gogs`)
- https://github.com/gogs/gogs/blob/main/SECURITY.md (the policy file; brief, points reports to private advisory creation)
- https://github.com/gogs/gogs/blob/main/CHANGELOG.md (release notes; each security fix is listed under the version that closed it)
- https://gogs.io/docs (user documentation; no security-bulletin RSS, so advisories are the canonical source)

## Context

Gogs follows GitHub's private security advisory workflow. Reports go through `https://github.com/gogs/gogs/security/advisories/new`; the maintainer (`@unknwon`) publishes them after a fix ships. The dominant advisory burst in this codebase is **February-March 2026**, where about 10 advisories were published in a six-week window — these are the most QPB-relevant ones because they characterize the *current* shape of the codebase's weaknesses, and they include the broken-access-control CVEs.

All advisories below are paginated from the canonical sources listed above. CVE IDs use the format the GitHub advisory page assigns; CVE-2026-NNNNN reflects entries assigned in 2026.

## The CASE-010 candidate set ([REDACTED])

This is the subset QPB needs to consider for blind detection of CASE-010. They are all real, all recent, all in the same `internal/route/repo/` area, and all share the "load by ID without scoping to URL repo" shape. Each one is patched in 0.13.4 or 0.14.0.

### [REDACTED] — [REDACTED] allows [REDACTED] modification *(primary CASE-010 candidate)*

- **GHSA**: [REDACTED]
- **CWE**: [REDACTED] (Improper Access Control)
- **Severity**: Moderate
- **Affected**: `<= 0.13.4`; patched in `0.14.0`
- **Reporter**: @spingARbor
- **File**: `internal/route/repo/issue.go`, function `UpdateLabel`, lines 1040-1054
- **Endpoint**: `POST /:username/:reponame/labels/edit`
- **Root cause** (verbatim from the advisory): `UpdateLabel` calls `database.[REDACTED](f.ID)` (unscoped) instead of `database.[REDACTED](c.Repo.Repository.ID, f.ID)`. The advisory notes that the unscoped call "internally passes `repoID=0` to the ORM layer," and that according to code comments in `internal/database/issue_label.go:147-166`, `repoID=0` "causes the ORM to ignore repository restrictions." There is no `if l.RepoID != c.Repo.Repository.ID` check. The route middleware `reqRepoWriter` only validates write access to the URL-path repo, not the label's actual repo.
- **Impact**: An authenticated user with write access to *any* repo can rewrite any label on any other repo (cross-repo IDOR by integer label ID). The PoC: alice has write on `alice/repo-a`; she POSTs `id=1&title=HACKED&color=#000000` to `/alice/repo-a/labels/edit`; bob's `bob/repo-b` label with ID 1 is now renamed.
- **Internal inconsistency**: The advisory explicitly notes that the *API* version of edit-label (`EditLabel`) uses the correctly-scoped query, and the Web UI's `NewLabel` and `DeleteLabel` are also correctly scoped. **Only `UpdateLabel` in the Web UI was vulnerable.** That's the "parity gap" pattern.
- **Fix**: swap `[REDACTED](f.ID)` → `[REDACTED](c.Repo.Repository.ID, f.ID)`. One-line.

**Why this is the strongest CASE-010 match**: localized, well-documented, one-line fix, clear before/after, reproducible PoC, no exotic exploitation conditions (any authenticated user with write on any repo), and the surrounding code (`NewLabel`, `DeleteLabel`, API `EditLabel`) shows the correct pattern within the same file — so the bypass is unmistakable when seen.

### [REDACTED] — Cross-repository comment deletion

- **GHSA**: [REDACTED]
- **CWE**: [REDACTED] ([REDACTED] Through User-Controlled Key)
- **Severity**: Moderate (CVSS 6.5)
- **Affected**: `<= 0.13.4`; patched in `0.14.0`
- **Reporter**: @tenbbughunters
- **File**: `internal/route/repo/issue.go`, function `DeleteComment`, lines 955-968
- **Endpoint**: `POST /:owner/:repo/issues/comments/:id/delete`
- **Root cause**: handler fetches `comment, _ := database.GetCommentByID(c.ParamsInt64(":id"))` (unscoped). The next check, `if c.UserID() != comment.PosterID && !c.Repo.IsAdmin()`, gates on the *URL-path* repo's admin status. There is no comparison of the comment's actual repo against `c.Repo.Repository.ID`. The secondary database function `DeleteCommentByID` also performs no authorization.
- **Impact**: A user who is admin of any repo (e.g., their own) can delete any comment from any other repo by knowing/guessing the comment ID. PoC: `POST /alice/attacker-repo/issues/comments/42/delete` with alice's session cookie, where comment 42 is in `bob/victim-repo`.
- **Fix**: add the binding step that `UpdateCommentContent` already had — load the issue from `comment.IssueID`, verify `issue.RepoID == c.Repo.Repository.ID`, then proceed.

### [REDACTED] — Protected branch deletion bypass

- **GHSA**: [REDACTED]
- **CWE**: [REDACTED] (Incorrect Authorization)
- **Severity**: Critical
- **Affected**: `<= 0.13.4`; patched in `0.14.0`
- **Reporter**: @spingARbor
- **File**: `internal/route/repo/branch.go`, function `DeleteBranchPost`, lines 110-155
- **Route declaration**: `internal/cmd/web.go:589` — `m.Post("/delete/*", reqSignIn, reqRepoWriter, repo.DeleteBranchPost)`
- **Root cause**: a tier-mismatch + missing handler check. Route is mounted under `reqRepoWriter` (writer-tier). Handler verifies branch existence and (optionally) commit ID match, but performs no protected-branch check and no default-branch check. The UI layer correctly hides the delete button for protected branches; the backend handler runs anyway when the POST is sent directly. The Git-hook layer (`internal/cmd/hook.go:122-125`) does prevent SSH-push deletion of protected branches, so the bypass is web-UI-only.
- **Impact**: Any writer can delete any protected branch (including default), bypassing PR review requirements. Privilege escalation from Writer → Admin-equivalent on branch lifecycle.
- **Fix**: add `database.GetProtectBranchOfRepoByName(c.Repo.Repository.ID, branchName)` lookup and refuse if protected; also refuse if `branchName == c.Repo.Repository.DefaultBranch`.

### [REDACTED] — Read-only PAT can update repository contents via API

- **GHSA**: [REDACTED]
- **CWE**: [REDACTED] (Missing Authorization) + [REDACTED] (Incorrect Authorization)
- **Severity**: Moderate (CVSS 6.5)
- **Affected**: `<= 0.13.3`; patched in `0.13.4` and `0.14.0+dev`
- **Reporter**: @odgrso
- **Endpoint**: `PUT /repos/:owner/:repo/contents/*`
- **Root cause**: the route gate is `repoAssignment()` (read-level access sufficient). The handler `PutContents()` calls `UpdateRepoFile()` which creates a commit and performs a `git push`. There is no inline write check at the top of the handler. A read-only PAT, or any user with read access to a public repo, can write file contents.
- **Impact**: source-code tampering, backdoor injection, release-artifact compromise — all from a PAT marketed as read-only.
- **Fix**: gate on writer permission, either through `reqRepoWriter`-equivalent middleware or an inline `if !c.Repo.IsWriter() { c.Status(403); return }`.

### [REDACTED] — [REDACTED] in repository deletion API

- **GHSA**: [REDACTED]
- **Severity**: Moderate
- **Affected**: per the advisory listing
- **Endpoint**: API repo-deletion handler
- **Root cause**: handler did not properly verify owner-tier access on the target repo before deletion. (Advisory page returned empty body on fetch; the listing in `https://github.com/advisories?query=gogs` confirms the title "Gogs has [REDACTED] in repository deletion API" and credits @Yannis175.)
- **Impact**: cross-tenant repo deletion.

### [REDACTED] — Cross-repository LFS object overwrite

- **GHSA**: [REDACTED]
- **Severity**: Critical
- **Affected**: per the advisory listing
- **Reporter**: @zjuchenyuan
- **Root cause**: missing content-hash verification on LFS object PUT; an object's OID can be supplied to an endpoint scoped to repo A but the content stored against the same OID is then visible to repo B. Cross-tenant tampering through the LFS data plane.

### [REDACTED] — Unauthenticated file upload

- **GHSA**: [REDACTED]
- **Severity**: Moderate
- **Root cause**: per the advisory title, a file-upload endpoint reachable without sign-in. Belongs to the same category as the BAC group because the missing middleware is the authorization defect; included here for completeness.

## Non-BAC advisories with relevance to the audit

These aren't CASE-010 themselves but they shape the attack surface and inform the invariants.

### Path-traversal cluster

- **[REDACTED]** ([REDACTED], High): arbitrary file deletion via path traversal in wiki page update.
- **[REDACTED]** ([REDACTED], Moderate): arbitrary file read/write via path traversal in Git hook editing — gate was site-admin-only but the path constraint broke, turning admin-only into full-host read/write.
- **[REDACTED]** ([REDACTED], Critical): deletion of internal files leading to RCE.

### Command/argument injection

- **[REDACTED]** ([REDACTED], Critical): argument injection in the built-in SSH server.
- **[REDACTED]** ([REDACTED], Critical): `.git/config` update path → remote command execution.
- **[REDACTED]** ([REDACTED], High): release tag option injection in release deletion.

### Authentication weaknesses

- **[REDACTED]** ([REDACTED], High): 2FA bypass via recovery code (replay).
- **[REDACTED]** ([REDACTED], Moderate): access tokens exposed through URL params in API requests.
- **[REDACTED]** ([REDACTED], High): bypass of [REDACTED]'s fix (regressions on previous patches).

### XSS cluster (multiple separately reported)

- [REDACTED] (DOM XSS via milestone selection), [REDACTED] (stored XSS in branch/wiki views via author/committer names), [REDACTED] (stored XSS via data URI in issue comments), [REDACTED] (stored XSS via Mermaid), [REDACTED] (stored call in PDF renderer).

### DoS

- **[REDACTED]** ([REDACTED], Moderate): denial of service.

## The advisory cadence as a signal

Reading the published-dates column: the maintainer landed roughly a dozen advisories in February-March 2026, almost all credited to a small group of external reporters (spingARbor, odgrso, rezmoss, tenbbughunters, zjuchenyuan). This is the diagnostic profile of an active codebase that has accumulated repeat-pattern bugs over time and is now triaging a coordinated wave of external research. **The implication for the audit: bugs in the same patterns probably still exist in handlers that haven't been touched in this wave.** The "load by ID without scoping to URL repo" pattern is documented as still-present in multiple places by the advisories themselves; QPB should expect to find further instances.

## Gogs's security policy in brief

`SECURITY.md` in the repo is short — it directs reports to the private GitHub advisory workflow rather than to a security mailing list, mentions no formal disclosure window, and lists no security contact email. The `/admin/notices` UI in a running Gogs instance also lists nothing public. **The advisory list above is therefore the canonical sources-of-truth for this audit.**

## Fix-pattern summary (for blind detection)

The patches across the BAC cluster fall into three repeating shapes:

1. **Swap the unscoped query for the scoped variant.** `[REDACTED](id)` → `[REDACTED](repoID, id)`. [REDACTED].
2. **Add an explicit `if obj.RepoID != c.Repo.Repository.ID { c.NotFound(); return }` after a global-ID load.** [REDACTED].
3. **Add a missing pre-action check that mirrors a check the other transport already has.** Either tier-up the middleware (`reqRepoWriter` → `[REDACTED]` is the cleanest), or add an inline check (`if !c.Repo.IsWriter()`, `if protectBranch.Protected`). [REDACTED] (protected branch), [REDACTED] (read-only PAT writes).

For CASE-010 blind detection, **shape #1 is the easiest to spot** because the unsafe call (`GetXByID` / `GetIssueByID`) and the safe alternative (`GetXOfRepoByID`) typically live in the same file (or in the same package), making the absence diagnostic.
