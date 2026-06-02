# Gogs Authorization Invariants

## Sources

- https://github.com/gogs/gogs/blob/main/internal/context/repo.go
- https://github.com/gogs/gogs/blob/main/internal/context/auth.go
- https://github.com/gogs/gogs/blob/main/internal/route/repo/issue.go
- https://github.com/gogs/gogs/blob/main/internal/database/issue_label.go (per advisory citation)
- https://github.com/gogs/gogs/blob/main/internal/database/comment.go (per advisory citation)
- https://github.com/gogs/gogs/security/advisories (the full advisory list — every published BAC advisory anchors at least one invariant below)
- https://gogs.io/docs
- Earlier docs in this folder: `00_README.md`, `01_security_model.md`, `02_api_and_endpoint_contract.md`, `03_access_control_patterns.md`

## Context

This file collects the "X must always" / "X must never" statements that follow from the security model and the published advisory history. Each invariant is a contract Gogs claims to honor; a violation is, by definition, a security bug. Many of them *have been* bugs at some point — each one tags the CVE/GHSA that proved it real, so the audit can use the historical fix as an oracle.

The invariants are grouped by concern. Each is phrased crisply enough that QPB can mechanically search for code that contradicts it.

---

## Authentication invariants

- **Every state-changing endpoint must require authentication.** Web routes: must be inside an `m.Group(..., reqSignIn, ...)` or have `reqSignIn` in their middleware chain. API routes: must reject requests with no PAT, no session, no basic auth, and no trusted-proxy header. *Tag:* CVE-2026-25242 (unauthenticated file upload).
- **The reverse-proxy authentication header must only be honored when the source IP is in `conf.Auth.TrustedProxyCIDRs`.** Anything else is header-forgery. `isRequestFromTrustedProxy()` is the gate. *Tag:* defense-in-depth, no known CVE post-CIDR-check.
- **`EnableReverseProxyAutoRegistration` must not be honored without the trusted-proxy CIDR check.** A trust-on-first-use account creation reached from an untrusted source is account-creation-as-a-service. *Tag:* same.
- **A PAT must never appear in URL params, log lines, or webhook payloads.** *Tag:* CVE-2026-26196 (GHSA-x9p5-w45c-7ffc, access tokens exposed through URL params).
- **2FA recovery codes must be single-use and invalidated after consumption.** Replaying a recovery code must fail. *Tag:* CVE-2025-64175 (2FA bypass via recovery code).
- **A session cookie must be invalidated on password change, on 2FA toggle, and on sign-out across devices.** *Tag:* general.

## Authorization (broken-access-control) invariants — the CASE-010 core

These are the highest-priority invariants for QPB's hunt.

- **Every handler that loads an object by integer primary key must verify the object belongs to the URL-path repository before acting on it.** Either via a `*OfRepoByID(repoID, id)` query, or via an explicit `if obj.RepoID != c.Repo.Repository.ID { c.NotFound(); return }` after a global-ID load. *Tag:* CVE-2026-25229 (label, GHSA-cv22-72px-f4gh), CVE-2026-25120 (comment, GHSA-jj5m-h57j-5gv7). The two highest-yield CVEs in this category.
- **Specifically for issue labels: `UpdateLabel` must use `database.GetLabelOfRepoByID(c.Repo.Repository.ID, id)`, never `database.GetLabelByID(id)`.** The advisory text quotes the patched diff verbatim; the unsafe shape passes `repoID=0` to the ORM, which the comments in `internal/database/issue_label.go:147-166` flag as "no repository restriction." *Tag:* CVE-2026-25229.
- **Specifically for issue comments: `DeleteComment` must verify `issue.RepoID == c.Repo.Repository.ID` after loading the issue from `comment.IssueID`.** `UpdateCommentContent` does this; `DeleteComment` did not. *Tag:* CVE-2026-25120.
- **An endpoint that performs a state-changing operation must be mounted under a middleware whose access tier is at least the tier the operation requires.** Specifically: write operations → `reqRepoWriter` minimum; admin operations (protected-branch deletion, webhook edit, settings change, deploy-key management) → `reqRepoAdmin`. *Tag:* CVE-2026-25232 (protected branch deletion routed under writer-tier middleware).
- **Protected-branch enforcement must apply on every transport that can delete or force-push a branch: SSH (pre-receive hook), HTTP smart Git (pre-receive hook), and the web-UI branch-delete handler.** *Tag:* CVE-2026-25232.
- **`PUT /repos/:owner/:repo/contents/*` must require write permission on the repository, not merely read.** Read-only PATs must not be able to call this endpoint successfully. *Tag:* CVE-2026-23632 (GHSA-5qhx-gwfj-6jqr).
- **`DELETE /repos/:owner/:repo` must require owner-level access on the target repository.** A user with admin or lower must not be able to delete it; no IDOR via path tampering should reach the deletion code path. *Tag:* CVE-2025-65852 (GHSA-rjv5-9px2-fqw6, authz bypass in repository deletion API).
- **For each (web-UI handler, API handler) pair implementing the same logical operation, the authorization predicates must be equivalent.** No "API requires writer, web does not" or vice versa. *Tag:* the parity-gap pattern documented in `02_api_and_endpoint_contract.md`; CVE-2026-25229 is the worked example (web `UpdateLabel` unsafe, API `EditLabel` safe).
- **Site admin authority must be the sole cross-tenant authority in the system.** No non-admin role may take an action on a resource it does not own through a repo-mode predicate computed against a different repo. *Tag:* general, enforced by `RepoAssignment()`'s admin override.
- **A handler's role check (`c.Repo.IsWriter()`, `c.Repo.IsAdmin()`) must be interpreted as "...on the URL-path repository," and is meaningful only after the loaded object has been bound to that repository.** A role check against the URL repo on an object that lives in a different repo is the CASE-010 shape. *Tag:* CVE-2026-25229, CVE-2026-25120.
- **An anonymous request must never reach `c.User.ID` without an `!c.IsLogged` guard.** Calling `c.User.ID` when `c.User == nil` panics; relying on `c.UserID()` (which returns 0) and comparing against `obj.PosterID == 0` is a vacuous true. *Tag:* general.

## Cross-repository / cross-tenant isolation invariants

- **An LFS object must not be overwritable through a request whose URL points at a different repository.** Object identity is content-hash; the handler must verify the OID belongs to *this* repo's set and reject content whose hash does not match. *Tag:* CVE-2026-25921 (cross-repository LFS object overwrite via missing content-hash verification, GHSA-cj4v-437j-jq4c, **critical**).
- **An organization owner of org A must have no implicit access to repos of org B.** *Tag:* general; this is the team→repo edge constraint.
- **A user who is a writer on `alice/repo-a` must not be able to mutate state on `bob/repo-b` through a handler reached at `/alice/repo-a/...`.** This is the literal "CASE-010 in one sentence" for Gogs. *Tag:* CVE-2026-25229, CVE-2026-25120 — both proved this exact violation possible.

## Site-admin-only operation invariants

- **Editing per-repo git hooks (`pre-receive`, `post-receive`, `update`) must be restricted to site admins.** Gate: `GitHookService()` middleware (which checks `User.CanEditGitHook()`). The path the hook content is written to must be normalized and confined to the repo's bare path. *Tag:* CVE-2026-23633 (path traversal in git-hook editing, GHSA-mrph-w4hh-gx3g) — site-admin gate held, but the inner path-confinement broke.
- **Admin-panel routes (`/admin/**`, `/api/v1/admin/**`) must require `User.IsAdmin == true`.** *Tag:* general.
- **The internal config endpoint must not be reachable, even to authenticated users, except where explicitly designed.** *Tag:* general.

## Repository setting and protection invariants

- **A protected branch must not be deletable except by force-pushing a `delete` ref through a path that runs the pre-receive hook (which will deny it) — i.e., effectively never via normal operations.** The Web UI delete-branch handler must reject the request before the underlying Git delete is invoked. *Tag:* CVE-2026-25232.
- **The default branch of a repository must not be deletable, even by an owner, except through transfer/rename flows.** *Tag:* CVE-2026-25232 explicitly mentions default-branch deletion as part of the impact.
- **A repository must not become un-private through anything except a deliberate owner-initiated change.** *Tag:* general.
- **A repository setting that exposes secrets (webhook URL with secret, deploy key, OAuth client secret) must require admin tier and must not be readable except in the form for editing.** *Tag:* general.

## Object-creation and reference invariants

- **Issues, comments, labels, milestones, releases, webhooks, deploy keys, and protected-branch rows must always be persisted with a `RepoID` equal to `c.Repo.Repository.ID`, never with one provided in user input.** *Tag:* general; the `NewLabel` handler correctly sets `RepoID = c.Repo.Repository.ID`, per the GHSA-cv22-72px-f4gh advisory.
- **A foreign-key reference from a child object (e.g., a comment) to a parent (e.g., an issue) must be loaded with a server-side query, not trusted from user input.** *Tag:* general.

## Path-handling and traversal invariants (relevant because traversal often turns into a BAC primitive)

- **A user-controlled path component used to address a server-side file (wiki page name, hook script name, repo content path) must be canonicalized and constrained to its intended subtree before any I/O.** *Tag:* CVE-2026-24135 (arbitrary file deletion via path traversal in wiki page update, GHSA-jp7c-wj6q-3qf2), CVE-2026-23633 (path traversal in git-hook editing, GHSA-mrph-w4hh-gx3g), CVE-2024-56731 (arbitrary file deletion → RCE).
- **A release "tag option" must be treated as data, not parsed as a `git tag -d` argument.** *Tag:* CVE-2026-26194 (release tag option injection in release deletion, GHSA-v9vm-r24h-6rqm).
- **An OS-level subprocess argument must never be assembled by string-concatenating user input.** *Tag:* CVE-2024-39930 (argument injection in built-in SSH server, GHSA-vm62-9jw3-c8w3, **critical**) — the canonical historical example.

## Webhook and integration invariants

- **A webhook secret must not be readable through any API endpoint after creation, except possibly for the repo admin in an edit form.** *Tag:* general.
- **A webhook event must not be triggered on a state change the actor was not authorized to make.** (If the change was authorized incorrectly, the webhook firing makes it auditable but does not legitimize it.) *Tag:* general — when fixing a BAC bug, audit whether the bypass also fired webhooks.

## Non-invariants (documented absences)

These are *not* guarantees Gogs provides. Code that relies on them is making a bad assumption:

- **There is no per-PAT scope.** A "read-only token" only exists if the routes it can reach are read-only. The route declarations are the entire scope model.
- **There is no row-level filtering at the database layer for most types.** Repo-scoping is the handler's responsibility.
- **There is no detection of bypassed authorization at the data layer.** A handler that mutates a row in repo B from a request handling repo A produces a successful 200 and a legitimate-looking audit trail.
- **There is no CSRF protection on the JSON API.** Cookie-authenticated browser POSTs to `/api/v1/...` may succeed; this is by design (the API expects PATs). It also means that an XSS that exfiltrates the session cookie has full API access.

## How to use this list

For CASE-010 (broken access control), the most likely match against Gogs is one of:

1. A handler in `internal/route/repo/` or `internal/route/api/v1/repo/` that loads an issue/comment/label/release/webhook/branch/release-tag by ID without binding it to `c.Repo.Repository.ID` — that's the CVE-2026-25229 / CVE-2026-25120 / CVE-2025-65852 shape.
2. A route in `internal/cmd/web.go` or `internal/route/api/v1/api.go` whose middleware chain is one tier weaker than the operation requires — that's the CVE-2026-25232 / CVE-2026-23632 shape.

The blind-detection signal: in either shape, the *fix* always adds a single short check (either swap to a `*OfRepoByID` query, or add an `if obj.RepoID != c.Repo.Repository.ID` line, or upgrade `reqRepoWriter` → `reqRepoAdmin`). The pre-fix code reads "approximately correct" because the role check is present and against the right helper — it's the *scoping of the helper* that's wrong.
