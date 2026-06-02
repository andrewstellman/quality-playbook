# Gogs API and Web-UI Endpoint Contract

## Sources

- https://github.com/gogs/gogs/blob/main/internal/cmd/web.go (route table — the canonical map of which middleware sits in front of which handler)
- https://github.com/gogs/gogs/tree/main/internal/route/api/v1 (REST API v1 route tree)
- https://github.com/gogs/gogs/tree/main/internal/route/repo (per-repo web handlers; this is where most BAC bugs live)
- https://github.com/gogs/gogs/blob/main/internal/context/auth.go (`Toggle`, `reqSignIn`/`reqAdmin` shape)
- https://github.com/gogs/gogs/blob/main/internal/context/repo.go (`RepoAssignment`, `RequireRepoAdmin`, `RequireRepoWriter`)
- https://gogs.io/api-reference (publicly hosted API docs)
- https://github.com/gogs/gogs/security/advisories/GHSA-2c6v-8r3v-gh6p (cites `internal/cmd/web.go:589` route line)
- https://github.com/gogs/gogs/security/advisories/GHSA-cv22-72px-f4gh (cites `internal/route/repo/issue.go:1040-1054`)

## Context

Gogs is a Macaron app. Routes are declared as a tree of `m.Group(...)` and `m.Get/Post/Put/Delete(...)` calls in `internal/cmd/web.go` for the web UI and Git transport, and in `internal/route/api/v1/api.go` for the REST API. Each route is a sequence:

```go
m.<METHOD>("<path>", mw1, mw2, ..., mwN, handler)
```

where `mw1..mwN` are macaron handlers (middleware) and `handler` is the final handler. Authorization in Gogs is enforced by which middleware are listed before the handler — there is no implicit framework gate.

This is the central operational fact for a broken-access-control audit:

> **The route declaration is the entire authorization contract. If `reqRepoWriter` is missing from a line that writes to a repo, the handler runs for anonymous users.**

## The middleware vocabulary

These are the functions that act as gates. Reading them with their exact return-on-fail behavior is the most efficient way to understand the authorization surface.

| Middleware | Defined in | Returns to client when gate fails | Purpose |
| --- | --- | --- | --- |
| `Toggle{SignInRequired: true}` (alias: `reqSignIn`) | `internal/context/auth.go` | 403 JSON on API paths; redirect to `/user/sign-in` on web paths | Require any authenticated user. |
| `Toggle{SignOutRequired: true}` | `internal/context/auth.go` | Redirect to `/` | Reject already-signed-in users (used on the sign-in form). |
| `Toggle{AdminRequired: true}` (alias: `reqAdmin`) | `internal/context/auth.go` | 403 | Require `User.IsAdmin == true`. Used on `/admin/**`. |
| `RepoAssignment()` | `internal/context/repo.go` | 404 (`c.NotFound()`) or redirect to issues/wiki tab if partially public | Loads `c.Repo.Owner`, `c.Repo.Repository`, computes `c.Repo.AccessMode`. If user has no access and repo is fully private, returns 404. Site-admin override: forces `AccessModeOwner`. |
| `RequireRepoAdmin()` (alias: `reqRepoAdmin`) | `internal/context/repo.go` | 404 | Require `c.Repo.IsAdmin() || c.User.IsAdmin`. |
| `RequireRepoWriter()` (alias: `reqRepoWriter`) | `internal/context/repo.go` | 404 | Require `c.Repo.IsWriter() || c.User.IsAdmin`. |
| `GitHookService()` | `internal/context/repo.go` | 404 | Require `c.User.CanEditGitHook()` (site-admin only). |
| `RepoRef()` | `internal/context/repo.go` | Various | Resolves a branch/tag/commit ref from URL parts. Does not gate access; assumes `RepoAssignment` already ran. |
| `MustEnableIssues` / `MustAllowPulls` / `MustEnableWiki` | `internal/route/repo/*.go` | 404 or redirect to external tracker | Enforce that this repo has the feature toggled on. Per-feature, not per-permission. |
| `ReqToken()` / API auth chain | `internal/route/api/v1/` | 403 | Require PAT or session-authenticated user on the API. |

### The "should be admin but is writer" hazard

`reqRepoWriter` is the gate on every "edit issue / push / merge / manage labels" route. `reqRepoAdmin` is the gate on every "manage collaborators / edit webhook / change settings / delete branch under protection" route. A route that *should* be admin-only mounted under `reqRepoWriter` is a silent privilege escalation: a writer can hit it.

**This is CVE-2026-25232.** The protected-branch deletion route was declared at `internal/cmd/web.go:589` as:

```go
m.Post("/delete/*", reqSignIn, reqRepoWriter, repo.DeleteBranchPost)
```

The handler had write-level guard but performed no protected-branch check. A writer who hit `POST /:owner/:repo/branches/delete/main` deleted the default branch. The fix added a protected-branch lookup inside the handler — and crucially, the route's middleware chain alone could never have stopped this, because the bug is "any-writer-can-do-an-admin-thing" not "any-anonymous-can-do-a-writer-thing."

## The pattern: middleware authorizes the URL repo, handler must authorize the target object

Every handler in `internal/route/repo/` is reached through `RepoAssignment()` against the URL path `/:username/:reponame`. By the time the handler runs:

- `c.Repo.Owner` is the URL-path repo's owner
- `c.Repo.Repository` is the URL-path repo
- `c.Repo.AccessMode` is the caller's level *on the URL-path repo*
- `c.Repo.IsWriter() / IsAdmin() / IsOwner()` answer about *the URL-path repo*

If the handler then loads any object by integer ID — comment ID, label ID, issue ID, release ID — that object can belong to *a different repository*. The middleware will not catch it. The handler must.

The two safe shapes:

**(a) Load the object with a repo-scoped query.** Use the variant that takes both the repo ID and the object ID and returns "not found" if they don't match. Examples:

```go
label, err := database.GetLabelOfRepoByID(c.Repo.Repository.ID, id)
issue, err := database.GetIssueByIndex(c.Repo.Repository.ID, index)
release, err := database.GetReleaseByID(c.Repo.Repository.ID, id)   // if such a scoped variant exists
```

**(b) Load by ID, then re-check the repo.** Useful when only the unscoped query exists.

```go
comment, err := database.GetCommentByID(id)
if comment.IssueID != 0 {
    issue, _ := database.GetIssueByID(comment.IssueID)
    if issue.RepoID != c.Repo.Repository.ID {
        c.NotFound()
        return
    }
}
```

The unsafe shape — and the canonical broken-access-control pattern in Gogs — is `(c)`:

**(c) Load by ID, do nothing further, act on the loaded object.** This is the shape that produced GHSA-cv22-72px-f4gh (`UpdateLabel` loaded a label by ID with no repo check), GHSA-jj5m-h57j-5gv7 (`DeleteComment` loaded a comment, checked the *URL* repo's admin level but never verified the comment belonged to that repo).

## Route registration — the slices QPB will need to read

The audit's job is to walk the route table and, for every state-changing handler, verify:

1. The route has a `reqSignIn` (or stricter) gate.
2. The route's permission level matches the operation:
   - State change at a repo → at least `reqRepoWriter`
   - Settings change → `reqRepoAdmin`
   - Repo deletion → owner check inside the handler
   - Anything under `/admin/**` or `/api/v1/admin/**` → `reqAdmin`
3. The handler does *one* of (a) or (b) above for every object loaded by ID, every time, before acting on it.

### Web UI route file
- `internal/cmd/web.go` — the entire web UI routing table. The protected-branch CVE cited line 589 of this file.

### API v1 route file
- `internal/route/api/v1/api.go` — the entire REST API routing table. The read-only-content-update CVE (CVE-2026-23632) was a route declared with `repoAssignment()` only (read sufficient) when it needed `reqRepoWriter` semantics; the underlying call performed a write.

### Handler files (most-cited in advisories)
- `internal/route/repo/issue.go` — issues, comments, labels, milestones. **`UpdateLabel` (lines 1040-1054), `DeleteComment` (lines 955-968), `UpdateCommentContent`. The single highest-bug-density file in the repo.**
- `internal/route/repo/branch.go` — branch deletion (CVE-2026-25232 lives here in `DeleteBranchPost`, lines 110-155).
- `internal/route/repo/release.go` — release creation/edit/delete (CVE-2026-26194: option-injection in tag handling for release deletion).
- `internal/route/repo/wiki.go` — wiki page CRUD (CVE-2026-24135: path traversal in wiki update).
- `internal/route/repo/editor.go` — web editor / content updates.
- `internal/route/repo/setting.go` — repo settings, webhooks, git-hooks. Hosts the `GitHookService()`-gated paths.
- `internal/route/api/v1/repo/contents.go` — `PutContents` (CVE-2026-23632: missing write check).
- `internal/route/api/v1/repo/repo.go` — repo deletion (CVE-2025-65852: authz bypass in deletion API).
- `internal/route/lfs/` — LFS object handling (CVE-2026-25921: cross-repo overwrite).

## REST API authentication

The REST API auth path is in `internal/context/auth.go`, function `authenticatedUserID`:

1. **PAT** — Header `Authorization: token <SHA1>`. Looked up via `GetAccessTokenBySHA1`. **A token grants the full authority of its owning user; there are no scopes.** Tokens have been mishandled before: GHSA-x9p5-w45c-7ffc (CVE-2026-26196, moderate) was tokens leaking into URL params.
2. **Session cookie** — `i_like_gogs=<sessid>` set on web sign-in; also accepted on API calls.
3. **Basic auth** — `Authorization: Basic <base64(user:pass)>`. Goes through `AuthenticateUser`.
4. **Reverse-proxy header** — header named by `conf.Auth.ReverseProxyAuthenticationHeader`, only honored if the source IP is in `conf.Auth.TrustedProxyCIDRs`. Auto-registration optionally enabled. `isRequestFromTrustedProxy()` in `internal/context/auth.go` gates this; pre-CIDR-check, the header was forgeable from any reachable source — making this a load-bearing check.

API endpoints generally chain through:

```
[Toggle{SignInRequired: true via API path}] -> [ReqToken (where required)]
     -> [repoAssignment() (loads c.Repo.Repository, computes AccessMode)]
     -> [handler]
```

Note that on the API side, the file is conventionally named `repoAssignment` (lowercase) and lives in `internal/route/api/v1/context/repo.go`. The behavior is parallel to the web UI's `RepoAssignment()`.

### The trap that produced CVE-2026-23632

```
m.Put("/contents/*", repoAssignment(), repo.PutContents)
```

`repoAssignment()` requires read access to view the repo but does *not* gate writes. `PutContents` invokes `UpdateRepoFile` which performs `git commit && git push`. A user with a read-only PAT and read access (or simply any user, on a public repo) could mutate file contents through this endpoint. The patched version added a write check inside the handler; the route's middleware never required it.

The QPB-detectable invariant is: **any `m.Put / m.Post / m.Delete / m.Patch` on `/repos/...` whose middleware chain stops at `repoAssignment()` (read-only) is suspect.** Every state-changing API verb needs either `reqRepoWriter` or `reqRepoAdmin` (or an inline equivalent check at the top of the handler).

## Web UI vs API parity gap

A subtle but recurring pattern: a logical operation is implemented in both the web UI and the API. One side has the correct repo-scoping pattern; the other doesn't.

- **Labels**: API's `EditLabel` uses `database.GetLabelOfRepoByID(repoID, id)` — safe. Web UI's `UpdateLabel` used `database.GetLabelByID(id)` — unsafe (CVE-2026-25229).
- **Comments**: API's `EditIssueComment` / `DeleteIssueComment` scope by repo. Web UI's `DeleteComment` did not check `issue.RepoID == c.Repo.Repository.ID` (CVE-2026-25120).
- **Branch deletion**: Git-hook path (over SSH) refuses to delete a protected branch. Web UI's `DeleteBranchPost` did not check protection (CVE-2026-25232).
- **Repo content write**: Web UI editor requires writer permission; API `PutContents` did not (CVE-2026-23632).

**An audit invariant:** for any pair of (web UI handler, API handler) that performs the same operation, the authorization predicates must be equivalent. If one is missing a check the other has, the missing one is the bug.

## Anonymous / partially-public paths

The handler files have a few intentional anonymous-reachable code paths. They are:

- Sign-in, sign-up, password reset, account activation.
- `/api/v1/repos/search`, `/api/v1/users/search`, `/api/v1/markdown`, `/api/v1/version`, `/api/v1/topics/search` — listed in `internal/route/api/v1/api.go` as "no auth required."
- Smart Git HTTP `info/refs?service=git-upload-pack` on a public repo.
- Repo views (HTML and a small read-only API surface) for public repos.

CVE-2026-25242 (unauthenticated file upload) was a route that ended up in this set by accident: it was reachable without sign-in when it should not have been. Any handler in this set that does anything beyond reading public data is a candidate for the same class of bug.
