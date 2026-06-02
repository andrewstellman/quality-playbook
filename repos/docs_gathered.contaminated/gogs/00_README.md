# Gogs: Project Overview

## Sources

- https://github.com/gogs/gogs
- https://gogs.io
- https://gogs.io/docs
- https://github.com/gogs/gogs/blob/main/README.md
- https://github.com/gogs/gogs/blob/main/SECURITY.md
- https://github.com/gogs/gogs/security/advisories
- https://gogs.io/api-reference
- https://github.com/gogs/gogs/blob/main/internal/context/repo.go
- https://github.com/gogs/gogs/blob/main/internal/context/auth.go
- https://github.com/gogs/gogs/blob/main/internal/route/repo/issue.go

## Context

**Gogs (`/gɑgz/`) is a self-hosted Git service** written in Go, in the same product category as GitHub Enterprise, GitLab self-hosted, Bitbucket Server, and Gitea (which is a hard fork of Gogs). It packages a Git server (SSH + HTTP/HTTPS + built-in Git LFS), a web UI, a JSON REST API, an issue tracker, pull requests, wikis, webhooks, and admin tooling into a single static binary that can run anywhere Go runs (Linux/macOS/Windows/ARM).

- **Repository**: https://github.com/gogs/gogs (47.6K stars, 5.1K forks at time of writing)
- **Primary maintainer**: [@unknwon](https://github.com/unknwon)
- **License**: MIT
- **Latest release**: 0.14.2 (Feb 19, 2026); the security-relevant boundary for almost every active advisory is `<= 0.13.4` vs `0.14.0`.
- **Language mix**: Go 73.8%, Go templates 19.6%, Less 3.0%, JavaScript 2.3% (per the GitHub language bar on the repo).
- **Web framework**: [Macaron](https://gopkg.in/macaron.v1) — the same Go web framework that Gitea was forked off and migrated away from. Macaron's middleware-handler chain is load-bearing for every access-control decision Gogs makes.
- **Persistence**: PostgreSQL, MySQL, SQLite3 (or any DB that speaks one of those wire protocols). ORM: XORM.
- **Auth sources**: local (PBKDF2), SMTP, LDAP, reverse proxy, GitHub.com / GitHub Enterprise OAuth, 2FA (TOTP + recovery codes).

The product surface QPB needs to reason about is unusually large for one binary: it is simultaneously a **Git server** (smart-HTTP and SSH endpoints that need to authenticate every push and pull), a **multi-tenant SaaS-like web app** (users, organizations, teams, repositories with collaborator roles), and a **REST API** that accepts personal access tokens. The access-control logic lives in three different places:

1. A **route-level middleware chain** declared in `internal/cmd/web.go` and `internal/route/api/v1/api.go`. Each route picks its own set of guards (`reqSignIn`, `reqRepoWriter`, `[REDACTED]`, `reqAdmin`, `reqToken`, ...).
2. A **per-request repository context** built in `internal/context/repo.go` by the `RepoAssignment()` macaron handler. This computes `c.Repo.AccessMode` once per request and exposes the helpers `IsOwner()`, `IsAdmin()`, `IsWriter()`, `HasAccess()` against it.
3. **Ad-hoc inline checks** inside handler bodies — `c.UserID() != comment.PosterID && !c.Repo.IsAdmin()`, `if !c.Repo.IsWriter()`, etc. These are where the broken-access-control bugs cluster: handlers that load an object by ID without verifying the object's repository matches the URL repository, or routes that mount under `reqRepoWriter` when they should be under `[REDACTED]`.

## Key Terminology

| Term | Meaning |
| --- | --- |
| **User** | A natural account with a username, primary email, and optional 2FA. Owns repositories. Has a global `IsAdmin bool` (site admin) and per-source `LoginSourceID`. |
| **Site admin** | A user with `User.IsAdmin = true`. Bypasses every per-repository permission check — in `RepoAssignment()`, an admin's `AccessMode` is forced to `AccessModeOwner`. Site admins are the *only* role with cross-tenant authority. |
| **Organization** | A user record with `Type = UserTypeOrganization`. Owns repositories and teams. Cannot log in directly; acted on through its owner team. |
| **Team** | A named group inside an organization with a fixed `Authorize` access level (`Read` / `Write` / `Admin` / `Owner`). Members of a team inherit that level on the repositories the team has access to. The implicit "Owners" team has `AccessModeOwner` and full admin rights on the organization. |
| **Repository** | A Git repository on disk plus database rows for issues, PRs, labels, releases, hooks. Has an `OwnerID` (user or org), `IsPrivate`, `IsBare`, `EnableIssues`, `EnableWiki`, `EnablePulls`, and zero or more **collaborators** and **protected branches**. |
| **Collaborator** | A non-owner user granted explicit access to a single repository at an `AccessMode` (Read/Write/Admin). Stored in the `collaboration` table. |
| **Access mode** | The integer permission level on a repository: `AccessModeNone` (0) < `AccessModeRead` (1) < `AccessModeWrite` (2) < `AccessModeAdmin` (3) < `AccessModeOwner` (4). Computed by `database.Handle.Permissions().AccessMode(...)`. |
| **Deploy key** | An SSH public key bound to a single repository with read-only or read/write access. Authenticates over SSH for CI/automation; *cannot* authenticate the web UI or the JSON API. |
| **Access token** (PAT) | A SHA-1-keyed personal access token used to authenticate REST API requests. Has the same authority as its owning user — there are no per-token scopes in Gogs. |
| **OAuth app** | A registered third-party app that can OAuth-sign-in users. |
| **Protected branch** | A row in the `protected_branch` table marking a branch name on a repository as undeletable, with optional whitelist of users who may push, optional required PR. Enforced in the Git pre-receive hook and (when working correctly) in the web UI's branch-delete handler. Has been the locus of multiple bypasses; see [REDACTED]. |
| **Webhook** | A URL fired on repository events. Has its own secret; configurable per-repo and per-org. |
| **Git hook** (server-side) | A shell-runnable hook on the repository's bare path (pre-receive/post-receive/update). Editable from the web UI by site admins only — when the gate works, see [REDACTED] for when it didn't. |
| **Mirror** | A repository configured to periodically pull from a remote. |
| **LFS** | Git Large File Storage; objects stored under `data/lfs/`. The pre-2026-25921 cross-tenant LFS overwrite vulnerability lived here. |
| **Pull request** (PR) | An issue with `IsPull = true` and a `pull_request` row recording head/base repo + branch. |
| **Issue / Comment / Label / Milestone** | Standard issue-tracker primitives, each owned by a repository. Multiple 2026 CVEs ([REDACTED], [REDACTED]) exploit handlers that load these by ID without checking the URL-path repository matches. |

## High-level architecture

A single Go binary serves three logical surfaces:

1. **Web UI** — Macaron-routed handlers under `internal/route/`. Templates live in `templates/`. Renders Markdown via `internal/markup/`. Cookies signed and stored via macaron sessions; session cookie name is `i_like_gogs`.
2. **REST API v1** — Macaron-routed handlers under `internal/route/api/v1/`. Modeled on the GitHub v3 API. Authenticated via PAT (`Authorization: token <SHA1>`), HTTP Basic, or session cookie. No per-token scopes.
3. **Git transport** —
   - **SSH**: either OpenSSH (with `gogs serv` shim) or the built-in Go SSH server (`internal/ssh/`); the built-in server has had a critical argument-injection bug — [REDACTED].
   - **HTTP smart Git**: `internal/route/lfs/` and the `*-info/refs` / `*git-upload-pack` / `*git-receive-pack` handlers.

All three converge on the same `database` package (`internal/database/`) — the same `Repository`, `User`, `Access`, `Collaboration`, `ProtectBranch`, `Comment`, `Issue`, `Label`, `Milestone` tables and the same permission helpers. **Every published broken-access-control CVE in Gogs's recent history is a missing or wrong call against one of those permission helpers in one of the route handlers.**

## Why Gogs has a high broken-access-control surface

Gogs has all four ingredients that make broken-access-control bugs common:

1. **Multi-tenant identity hierarchy**: site admin → org owner → team admin → repo admin → repo writer → repo reader → authenticated user → anonymous. Eight distinct roles, with cross-tenant interactions (a user can be admin on repo A and reader on repo B at the same time).
2. **Many object types referenced by integer primary key**: issue, comment, label, milestone, release, webhook, deploy-key, protected-branch, LFS object, OAuth-app. Every one of these is a potential IDOR vector if a handler fetches by ID without re-checking the URL's repository.
3. **Duplicated authorization across UI and API**: the web UI route tree, the REST API route tree, and the Git transport each enforce permissions independently. The same logical operation (edit a label, delete a comment, push to a branch) can be reached through three different handler paths. [REDACTED] illustrates this: the API's `EditLabel` correctly used the scoped query `database.[REDACTED]`; the web UI's `UpdateLabel` used the unscoped `database.[REDACTED]` and was vulnerable.
4. **Middleware-handler split**: the route declaration says `reqRepoWriter`, which guarantees the *URL-path repository* is writeable — but the handler then loads an object by ID from a *different* repository and acts on it. The middleware did its job; the handler didn't. This is the canonical Gogs broken-access-control shape.

The rest of these docs catalogue the exact endpoints, helpers, and patterns that QPB needs in order to detect a missed scope check.
