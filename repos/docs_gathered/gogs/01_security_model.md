# Gogs Security Model: Roles, Trust Boundaries, and Access Modes

## Sources

- https://github.com/gogs/gogs/blob/main/internal/context/repo.go (`RepoAssignment`, `RequireRepoAdmin`, `RequireRepoWriter`, `Repository.IsOwner/IsAdmin/IsWriter/HasAccess`)
- https://github.com/gogs/gogs/blob/main/internal/context/auth.go (`Toggle`, `authenticatedUser`, reverse-proxy and basic-auth paths)
- https://github.com/gogs/gogs/blob/main/internal/database/ (`access_mode.go`, `permissions.go`, `collaboration.go`, `team.go`, `protect_branch.go`)
- https://github.com/gogs/gogs/blob/main/SECURITY.md
- https://github.com/gogs/gogs/security/advisories
- https://gogs.io/docs/features/repository_permissions (linked from docs nav)

## Context

This file is the canonical role-and-trust-boundary reference for the rest of the docs. Every invariant in `04_invariants.md` is written against the access-mode ladder and the middleware vocabulary defined here.

The reader can take everything in this file as a contract that QPB checks the source against, not as a description of what the source happens to do. Departures from this model in `internal/route/**` are the broken-access-control bugs.

## The access-mode ladder

The integer access mode is defined in `internal/database/access_mode.go` and used as the comparison key throughout:

```
AccessModeNone   = 0   // No access at all
AccessModeRead   = 1   // Can clone, view UI, comment on issues (if enabled)
AccessModeWrite  = 2   // Can push, edit issues/PRs, attach labels, merge PRs
AccessModeAdmin  = 3   // Can change repo settings, manage collaborators, edit webhooks
AccessModeOwner  = 4   // The owner; can delete the repo; for orgs, only via Owners team
```

Site admins (`User.IsAdmin = true`) are hardcoded to `AccessModeOwner` for every repository they touch — see `RepoAssignment()`:

```go
if c.IsLogged && c.User.IsAdmin {
    c.Repo.AccessMode = database.AccessModeOwner
} else {
    c.Repo.AccessMode = database.Handle.Permissions().AccessMode(c.Req.Context(), c.UserID(), repo.ID, ...)
}
```

The per-request helpers on `*context.Repository`:

| Helper | Returns true when | Used by |
| --- | --- | --- |
| `HasAccess()` | `AccessMode >= AccessModeRead` | route guards on repo views; `IsGuest = !HasAccess()` |
| `IsWriter()` | `AccessMode >= AccessModeWrite` | `RequireRepoWriter()`; label add/remove; issue edit; merge PR |
| `IsAdmin()`  | `AccessMode >= AccessModeAdmin` | `RequireRepoAdmin()`; repo settings; webhook edits; protected-branch settings |
| `IsOwner()`  | `AccessMode >= AccessModeOwner` | repository deletion; transfer ownership |

**Key property: these helpers are total — they answer about the repository in `c.Repo`, which is the URL-path repository. They say nothing about whether an arbitrary object the handler loaded by integer ID belongs to that repository.** Every broken-access-control CVE in this repo is a handler that called `IsWriter()` or `IsAdmin()` on the URL-path repo and then acted on an object owned by a different repo.

## Role hierarchy (most-trusted → least)

1. **Site admin** (`User.IsAdmin = true`)
   - Global. Crosses tenant boundaries (any user, any org, any repo).
   - Can edit Git server-side hooks (CVE-2026-23633 was a path-traversal bypass against this gate).
   - Can run the `/admin` panel: edit any user, lock accounts, view auth sources, manage applications.
   - Trust boundary: a site admin compromise is equivalent to a full Gogs root compromise.

2. **Repository owner** (`AccessMode == AccessModeOwner`)
   - For user-owned repos: the user whose `User.ID == Repository.OwnerID`.
   - For org-owned repos: members of the org's Owners team.
   - Can delete or transfer the repository, change visibility, configure all settings.

3. **Organization Owners-team member**
   - Equivalent to repository owner for every repo in the org.
   - Can add/remove org members and teams.
   - Promotes regular members to owners via the Owners team.

4. **Repository admin** (`AccessMode == AccessModeAdmin`)
   - Manage collaborators on this repo, edit webhooks, configure protected branches, edit deploy keys.
   - Cannot delete the repository (that's owner-only).

5. **Repository writer** (`AccessMode == AccessModeWrite`)
   - Push to non-protected branches.
   - Open/close/edit any issue or PR on this repo.
   - Merge PRs.
   - Add/remove labels on issues.
   - **Must not** be able to delete protected branches (CVE-2026-25232 was a bypass), change repo settings, manage collaborators, or edit git hooks.

6. **Repository reader** (`AccessMode == AccessModeRead`)
   - Clone over HTTP/SSH.
   - Comment on issues/PRs (if the issue tracker is enabled and configured to allow it).
   - View files, branches, tags, releases.
   - **Must not** be able to push, edit other users' comments, modify labels, or change any persistent repo state. CVE-2026-23632 was a Read-only PAT able to modify repo content through `PUT /repos/:owner/:repo/contents/*`.

7. **Authenticated non-collaborator** (`AccessMode == AccessModeNone`, `IsLogged = true`)
   - Can view public repositories.
   - Can fork.
   - Can open issues on repositories whose owner enabled `CanGuestViewIssues()`.
   - Can edit *their own* issue/comment content.
   - **Must not** be able to touch anyone else's resources.

8. **Anonymous** (`IsLogged = false`)
   - Can clone public repos over HTTPS (unless disabled in config).
   - Can view public repos' UI.
   - Can read public issues if `CanGuestViewIssues()`.
   - **Must not** reach any state-changing endpoint, `/api/v1/admin/*`, `/admin/*`, or `/user/settings/*`. CVE-2026-25242 was an unauthenticated file-upload bug on a route that should have required sign-in.

## Public vs private repositories

`Repository.IsPrivate` controls whether anonymous + non-collaborator users see the repo at all:

- **Public repo**: anyone (including anonymous) can clone, view files, view issues/PRs. Their `AccessMode` is `AccessModeNone` so they cannot write anything. Anonymous Git pull over HTTPS does not require auth; SSH pull always does (because SSH requires a key).
- **Private repo**: visible only to users with `AccessMode >= AccessModeRead`. Clone over HTTPS requires HTTP Basic auth (username + password/PAT). Clone over SSH requires a key that resolves to a user with read access — *or* a deploy key bound to this repo.
- **Partially-public repo**: a private repo whose owner explicitly enabled `CanGuestViewIssues()` or `CanGuestViewWiki()`. Anonymous users land on those tabs only. `RepoAssignment()` redirects them between issue/wiki tabs based on which is permitted; everywhere else they 404. This is a relatively recent feature and a fertile area for "should be private but isn't" bugs.

## Organization-level model

Organizations are users with `Type = UserTypeOrganization`. Their access is structured by **teams**:

- Every org has an implicit **Owners team** with `Authorize = AccessModeOwner`. Members of this team are org owners; they get owner access to every repo in the org and can manage teams and members.
- Other teams are user-defined. Each has a fixed `Authorize` level (`Read`, `Write`, `Admin`, or `Owner`) and a list of repositories the team has access to. Members of the team inherit `Authorize` on those repositories.
- A user can be on multiple teams. The effective access on a repo is the maximum across the teams the user belongs to *and* any direct collaboration row.
- `database.Handle.Permissions().AccessMode(...)` is the single function that does this max-merge. Every handler that consults `c.Repo.AccessMode` (including the four helper methods above) is implicitly trusting it.

Anti-patterns at the org boundary:

- Code that checks "is this user the repo owner?" by comparing `User.ID == Repository.OwnerID` is **wrong for org-owned repos** because the org's owners are not the org user. The correct check goes through the access-mode helpers.
- A team-admin on org A acting on repo of org B must not get any access via that team membership. The team→repo edge is always within one org.

## Trust boundaries (summary)

| Boundary | Crossed by | Crossing controlled by |
| --- | --- | --- |
| Anonymous → authenticated | sign-in cookie, HTTP Basic, PAT, reverse-proxy header (if trusted CIDR) | `Toggle{SignInRequired: true}` middleware → `reqSignIn` |
| Authenticated → site admin | `User.IsAdmin == true` (set out-of-band or by another admin) | `Toggle{AdminRequired: true}` middleware → `reqAdmin` |
| Outside repo → inside repo | URL path `/:username/:reponame`, resolved by `RepoAssignment()` | computed `c.Repo.AccessMode`; helpers `HasAccess/IsWriter/IsAdmin/IsOwner` |
| Read → write on a repo | `IsWriter()` returns true | `RequireRepoWriter()` middleware → `reqRepoWriter` |
| Write → admin on a repo | `IsAdmin()` returns true | `RequireRepoAdmin()` middleware → `reqRepoAdmin` |
| Per-tenant isolation (label/comment/issue/release) | the object's `RepoID` matching `c.Repo.Repository.ID` | **inline, in each handler** — and this is where the bugs are |
| User session → other user's data | the object's `PosterID` / `OwnerID` matching `c.UserID()` | **inline, in each handler** |
| Trusted-proxy reverse-auth | source IP inside `conf.Auth.TrustedProxyCIDRs` + presence of `ReverseProxyAuthenticationHeader` | `isRequestFromTrustedProxy()` in `internal/context/auth.go` |
| Built-in SSH server → shell | only via `gogs serv` / hook scripts | input must be parsed, not shelled out; CVE-2024-39930 was a missed gate here |
| Web UI git-hook editor → fs | only site admins, only inside the repo's bare path | `GitHookService()` middleware + path normalization; CVE-2026-23633 was a path-traversal break |
| LFS object access | belongs to the repository being requested | object OID + repo-scoped lookup; CVE-2026-25921 was a cross-tenant overwrite |

## Things the security model does *not* provide

These are documented absences. Code that depends on them existing is making a bad assumption:

- **No per-PAT scopes**. A PAT is the user. If the user is a site admin, the PAT is a site admin. Defense-in-depth around PATs (`Authorization: token …`) is single-layer.
- **No CSRF protection on the JSON API**, by design — clients are expected to use a PAT not a cookie. CSRF middleware is applied to the *web* routes.
- **No row-level filtering at the database layer** for most object types. `GetCommentByID(id)`, `GetLabelByID(id)`, `GetIssueByID(id)`, `GetReleaseByID(id)` all return any row matching the integer key. The repo-scoping is the *handler's* responsibility. The safer-named alternatives exist — `GetLabelOfRepoByID(repoID, id)`, `database.DeleteLabel(repoID, id)` — and the asymmetric availability of these is what makes the unsafe versions a footgun.
- **No structured logging of denied access**. A bypassed authorization check produces a successful 200 with the wrong row mutated; nothing distinguishes it from a legitimate action in logs.
