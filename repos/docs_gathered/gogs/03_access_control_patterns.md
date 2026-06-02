# Gogs Access-Control Patterns and Footguns

## Sources

- https://github.com/gogs/gogs/blob/main/internal/context/repo.go (`RequireRepoAdmin`, `RequireRepoWriter`, `Repository` permission helpers)
- https://github.com/gogs/gogs/blob/main/internal/context/auth.go (`Toggle`)
- https://github.com/gogs/gogs/blob/main/internal/route/repo/issue.go (canonical safe and unsafe handler shapes)
- https://github.com/gogs/gogs/blob/main/internal/database/issue_label.go (the scoped-vs-unscoped DB helpers — referenced in CVE-2026-25229 advisory as "code comments at lines 147-166")
- https://github.com/gogs/gogs/security/advisories/GHSA-cv22-72px-f4gh (CVE-2026-25229 — label authz bypass, gives the canonical safe/unsafe diff)
- https://github.com/gogs/gogs/security/advisories/GHSA-jj5m-h57j-5gv7 (CVE-2026-25120 — comment IDOR, shows two-step "issue.RepoID == c.Repo.Repository.ID" pattern)
- https://github.com/gogs/gogs/security/advisories/GHSA-2c6v-8r3v-gh6p (CVE-2026-25232 — protected branch bypass, shows the route-level vs handler-level gap)
- https://github.com/gogs/gogs/security/advisories/GHSA-5qhx-gwfj-6jqr (CVE-2026-23632 — read-only PAT writes via API)

## Context

This file documents the **patterns** (canonical good shapes) and **footguns** (canonical bad shapes) that the Gogs codebase has accumulated over a decade of evolution. Each pattern is exact enough that an audit tool can match against it. The named CVE on each footgun is real and recent — for any pattern that produced a CVE, the diff between the unsafe shape and the patched shape is the QPB detection target.

## Pattern 1: Route declaration is the first authorization layer

The shape:

```go
m.Group("/:username/:reponame", func() {
    m.Group("", func() {
        m.Get("/issues", repo.Issues)
        m.Get("/issues/:index", repo.ViewIssue)
    }, context.RepoRef())

    m.Group("", func() {
        m.Post("/issues/new", bindIgnErr(form.NewIssue{}), repo.NewIssuePost)
        m.Post("/issues/:index/label", repo.UpdateIssueLabel)
        m.Post("/issues/comments/:id/delete", repo.DeleteComment)
    }, reqSignIn, context.RepoRef())

    m.Group("", func() {
        m.Post("/labels/new", bindIgnErr(form.CreateLabel{}), repo.NewLabel)
        m.Post("/labels/edit", bindIgnErr(form.CreateLabel{}), repo.UpdateLabel)
        m.Post("/labels/delete", repo.DeleteLabel)
        m.Post("/branches/delete/*", repo.DeleteBranchPost)
    }, reqRepoWriter, context.RepoRef())

    m.Group("/settings", func() {
        m.Combo("").Get(repo.Settings).Post(repo.SettingsPost)
        m.Combo("/collaboration").Get(repo.Collaboration).Post(repo.CollaborationPost)
        m.Combo("/hooks").Get(repo.Webhooks).Post(repo.WebhooksPost)
    }, reqRepoAdmin)
}, context.RepoAssignment())
```

The contract: a state-changing handler is only ever reached for users who already cleared the outer `RepoAssignment()` (existence + read on the URL repo) **plus** the inner `reqRepoWriter` / `reqRepoAdmin` gate.

**The full set of in-tree middleware aliases used as gates:**

| Alias | Calls | Notes |
| --- | --- | --- |
| `reqSignIn` | `Toggle{SignInRequired: true}` | required for any state change |
| `reqSignOut` | `Toggle{SignOutRequired: true}` | for sign-in form etc. |
| `reqAdmin` | `Toggle{AdminRequired: true}` | site admin only |
| `reqRepoWriter` | `RequireRepoWriter()` | writer or site admin |
| `reqRepoAdmin` | `RequireRepoAdmin()` | repo admin or site admin |
| `repoAssignment()` / `RepoAssignment()` | loads `c.Repo.Repository` and `c.Repo.AccessMode`; 404 if no access | required for any per-repo handler |
| `gitHookService()` | requires `User.CanEditGitHook()` | site admin only, additional knob |

**Footgun 1A: Route declared with no gate at all.** Any `m.Post / m.Put / m.Delete` declared outside a sign-in group is anonymous-reachable. The web routes use `m.Group(..., reqSignIn, ...)` wrappers to enforce this; an `m.Post` accidentally hoisted outside a group is the bug. CVE-2026-25242 (unauthenticated file upload) was an instance.

**Footgun 1B: Route declared at the wrong permission tier.** Mounting an admin-level operation under `reqRepoWriter` means writers can hit it. CVE-2026-25232 (protected branch deletion) is this pattern: the route required only writer access, the operation required admin.

**Footgun 1C: API route declared with `repoAssignment()` only when the handler mutates state.** `repoAssignment()` ensures the caller can *read* the repo. CVE-2026-23632: `m.Put("/contents/*", repoAssignment(), repo.PutContents)` reached a write operation through a read gate.

## Pattern 2: Per-handler object-to-repo binding

The single most important pattern in the codebase. Every handler that reaches an object by integer ID must prove that object belongs to the URL-path repository before acting on it.

### Pattern 2A: Use the scoped database helper

```go
// SAFE
label, err := database.GetLabelOfRepoByID(c.Repo.Repository.ID, c.QueryInt64("id"))
if err != nil {
    c.NotFoundOrError(err, "get label by ID")
    return
}
// label is guaranteed to belong to c.Repo.Repository
```

Known scoped helpers (the safe variants):

- `database.GetLabelOfRepoByID(repoID, id)` — used in `UpdateIssueLabel` (line 776 of issue.go, current main) and the API's `EditLabel`. The corresponding *unsafe* helper is `database.GetLabelByID(id)`, which the advisory's comments at `internal/database/issue_label.go:147-166` say "passes `repoID=0` to the ORM layer," with the ORM treating `repoID=0` as "no restriction."
- `database.GetIssueByIndex(repoID, index)` — note: the API uses *issue index* (the per-repo sequential number visible in URLs like `/issues/42`), which is implicitly repo-scoped. The unsafe sibling is `database.GetIssueByID(id)` which takes the global integer primary key.
- `database.DeleteLabel(repoID, id)` — used in `DeleteLabel`. Will only delete if the row's repo matches.
- `database.GetWebhookOfRepoByID(repoID, id)` — for webhook handlers.
- `database.GetMilestoneByRepoID(repoID, id)`.

### Pattern 2B: Re-check after loading by global ID

When only the unscoped query exists, the handler must compare:

```go
// SAFE (the post-fix pattern in UpdateCommentContent, lines ~927+)
comment, err := database.GetCommentByID(c.ParamsInt64(":id"))
if err != nil {
    c.NotFoundOrError(err, "get comment by ID")
    return
}
issue, err := database.GetIssueByID(comment.IssueID)
if err != nil {
    c.NotFoundOrError(err, "get issue by ID")
    return
}
if issue.RepoID != c.Repo.Repository.ID {     // ← the load-bearing check
    c.NotFound()
    return
}
if c.UserID() != comment.PosterID && !c.Repo.IsAdmin() {
    c.NotFound()
    return
}
```

The `if issue.RepoID != c.Repo.Repository.ID` line is the binding step. `UpdateCommentContent` has it (per the current source); `DeleteComment` did not have it pre-fix (CVE-2026-25120, GHSA-jj5m-h57j-5gv7). The advisory's own diff is the canonical example QPB can train on.

### Pattern 2C: Inline ownership-or-admin check for resources owned by a user

```go
// SAFE pattern from UpdateIssueTitle (issue.go ~744)
if !c.IsLogged || (!issue.IsPoster(c.User.ID) && !c.Repo.IsWriter()) {
    c.Status(http.StatusForbidden)
    return
}
```

The condition is **"poster OR has at least write on the URL-path repo."** Three things must be right:

1. Authentication is required (`c.IsLogged`).
2. The ownership predicate is on the loaded object (`issue.IsPoster(c.User.ID)`) — not on the URL.
3. The fallback role check uses the URL-path repo (`c.Repo.IsWriter()`) — but the loaded object must already have been bound to that repo.

**Footgun 2D: Object loaded by ID, role check uses URL-path repo, no binding.** This is the canonical CVE shape in this codebase. Pseudocode:

```go
// UNSAFE — the shape that produced GHSA-cv22-72px-f4gh and GHSA-jj5m-h57j-5gv7
obj, err := database.GetObjectByID(c.QueryInt64("id"))   // global lookup
if c.UserID() != obj.OwnerID && !c.Repo.IsAdmin() {       // URL-repo admin — wrong scope!
    c.NotFound()
    return
}
mutate(obj)
```

The check approves anyone who is admin on the URL-path repo (their own repo) to mutate any object whose integer ID they can guess — even if that object lives in someone else's repo.

## Pattern 3: Defense-in-depth — middleware + handler check

For high-value operations, the route gate is the *necessary* condition and the handler check is the *sufficient* condition. The protected-branch case (CVE-2026-25232) is the clearest illustration of "necessary but not sufficient":

- Route: `m.Post("/delete/*", reqSignIn, reqRepoWriter, repo.DeleteBranchPost)`
- Necessary: caller must be signed in and have write on the repo.
- Sufficient: handler must additionally check that the branch is not protected.

The pre-fix handler did the route's job but not the handler's. The post-fix handler adds:

```go
protectBranch, err := database.GetProtectBranchOfRepoByName(c.Repo.Repository.ID, branchName)
if err != nil && !database.IsErrBranchNotExist(err) {
    c.Error(err, "get protect branch")
    return
}
if protectBranch != nil && protectBranch.Protected {
    c.Flash.Error(c.Tr("repo.settings.branch_protected"))
    return
}
```

The Git-hook pre-receive path (`internal/cmd/hook.go`) already had this check for SSH push, so SSH push could not delete a protected branch. The web-UI delete was a parallel path missing the gate. **Whenever a security-relevant operation exists in two transports (web vs SSH vs API), all transports need the gate.**

## Pattern 4: Site admin override

Many helpers internally allow site admin to pass any check:

```go
// in RequireRepoAdmin()
if !c.IsLogged || (!c.Repo.IsAdmin() && !c.User.IsAdmin) {
    c.NotFound()
    return
}
```

`c.User.IsAdmin` short-circuits the per-repo admin check. This is intentional, but it also means a compromised admin account is total. The `RepoAssignment()` middleware further promotes the access mode for site admins:

```go
if c.IsLogged && c.User.IsAdmin {
    c.Repo.AccessMode = database.AccessModeOwner
}
```

A subtle consequence: `c.Repo.IsWriter()` returns true for site admins on every repo, including private ones owned by other users. This is the documented contract, but it means any "is the actor a writer?" question is implicitly "...or are they site admin?"

## Pattern 5: Anonymous-aware handlers

Handlers that may be reached anonymously (because the route doesn't have `reqSignIn`) must check `c.IsLogged` explicitly before performing a per-user action:

```go
// from UpdateIssueTitle
if !c.IsLogged || (!issue.IsPoster(c.User.ID) && !c.Repo.IsWriter()) {
    c.Status(http.StatusForbidden)
    return
}
```

**Footgun 5A: Per-user action without `!c.IsLogged` check on an anonymous-reachable route.** Calling `c.User.ID` when `c.User` is nil panics; calling `c.UserID()` (which returns 0 for anonymous) and comparing to `obj.PosterID == 0` is a vacuous true that could grant write access.

## Pattern 6: Reverse-proxy authentication

The reverse-proxy auth path (`internal/context/auth.go`, `authenticatedUser`) honors a header named by `conf.Auth.ReverseProxyAuthenticationHeader` (typical: `X-WEBAUTH-USER`) and identifies the user as whoever the header names — *only if* the source IP is inside `conf.Auth.TrustedProxyCIDRs`.

**Footgun 6A: A reverse-proxy header that can be forged.** If `TrustedProxyCIDRs` is misconfigured (or the deployment runs without the front-proxy), the header is attacker-controlled. Auto-registration (`EnableReverseProxyAutoRegistration`) makes this catastrophic — an attacker creates a new user account by setting the header. The `isRequestFromTrustedProxy()` function is the only mitigation, and Gogs ships with no default CIDRs configured.

## Pattern 7: PAT scope (the absence of scopes)

PATs in Gogs have no scopes. A PAT is the user. An audit's job around PATs:

- Every operation reachable with a PAT must be reachable through the same authorization predicates as the same operation reached via session. (No PAT-only privilege paths.)
- A read-only PAT must not be able to perform writes. The pre-CVE-2026-23632 API let this happen because the route gate was read-level.
- A PAT must not be logged in URL params. CVE-2026-26196 (GHSA-x9p5-w45c-7ffc): tokens were exposed through URL params in API requests — moderate, but a PAT-in-logs leak is a complete-impersonation primitive.

## Summary: the four broken-access-control shapes to grep for

QPB's job for CASE-010 reduces to recognizing one of these four shapes in a Gogs handler:

1. **Route declared with no `reqSignIn`** for an operation that mutates per-user or per-repo state.
2. **Route declared with the wrong permission tier** (`reqRepoWriter` on an operation that should be `reqRepoAdmin`).
3. **Handler loads an object via the unscoped database helper** (`GetLabelByID`, `GetCommentByID`, `GetIssueByID`, `GetReleaseByID`, ...) **and then acts on it** without (a) re-querying via the `*OfRepoByID` variant, or (b) comparing `obj.RepoID == c.Repo.Repository.ID` / `obj.OwnerID == c.User.ID`.
4. **Two transports of the same operation diverge** in their authorization checks (web UI lenient, API strict — or vice versa). One of them is the bug.

Detection signal #3 is the highest-yield. Every recent broken-access-control CVE in the gogs/gogs history is a literal instance of it.
