# Permission Model

Gogs has three permission concepts that compose: repository access modes, organization team membership, and site-admin status. The combined effect is computed each time a handler resolves a repository or organization context.

## Access modes

`internal/db/perms.go` defines `AccessMode`:

```
AccessModeNone   = 0
AccessModeRead   = 1
AccessModeWrite  = 2
AccessModeAdmin  = 3
AccessModeOwner  = 4
```

`String()` and `ParseAccessMode("write")` translate to and from human-readable forms. The ordering is meaningful; higher modes include lower ones, and comparisons use `desired <= actual`.

## Access table

The `access` table (`Access` model) is the persistent map from `(user_id, repo_id)` to `mode`, with a unique constraint named `access_user_repo_unique`. Repository owners are not stored here — ownership is implicit in `repository.owner_id`. Members of organization owner teams are folded in by bookkeeping when team membership changes.

## PermsStore interface

- `AccessMode(ctx, userID, repoID int64, opts AccessModeOptions) AccessMode` — resolve the effective access mode. Takes `OwnerID` and `Private` flags so the caller does not need a second round-trip.
- `Authorize(ctx, userID, repoID int64, desired AccessMode, opts AccessModeOptions) bool` — wraps `AccessMode` and compares.
- `SetRepoPerms(ctx, repoID int64, accessMap map[int64]AccessMode) error` — atomic replacement of every row for a repository, in a transaction that deletes existing rows and inserts the new map.

Resolution rules in `AccessMode`:

1. If `repoID <= 0`, return `AccessModeNone`.
2. If the repository is public, the floor is `AccessModeRead` for everyone.
3. If the caller is anonymous (`userID <= 0`), return the floor.
4. If the caller is the owner, return `AccessModeOwner`.
5. Otherwise read the matching `access` row; if none exists, return the floor.

## Recomputation triggers

The `access` table is a denormalized projection of (a) explicit collaborators, (b) team membership for organization-owned repositories, and (c) the public/private flag. Whenever one of these changes, the projection is refreshed via `SetRepoPerms` or higher-level helpers (`RecalculateAccesses`, `Repository.RecalculateAccesses`). Triggers include adding/removing a collaborator, toggling `IsPrivate`, transferring ownership, and editing team membership.

## Token-scoped access

REST requests authenticated by token set `c.IsTokenAuth = true` and inherit the underlying user's effective access mode. Site-admin token holders are mapped to `AccessModeOwner` for the targeted repository.

## API context helper

`repoAssignment()` in `internal/route/api/v1/api.go` is the shared middleware that REST repository routes apply:

1. Look up the owner from `:username`.
2. Look up the repository from `:reponame`.
3. Resolve the access mode via `db.Perms.AccessMode(...)`.
4. If the mode is `AccessModeNone`, return 404 so the response does not differentiate between a missing repository and a private one the caller cannot see.
5. Store `Repository` and `AccessMode` on `c.Repo` for downstream handlers.

The web context (`internal/context/repo.go`) follows the same pattern for browser requests.

## Per-handler enforcement

Handlers compare `c.Repo.AccessMode` against a `desired` mode: read endpoints (commits, files, branches, tags) require `AccessModeRead`; edit endpoints (issues, pulls, branches, releases) require `AccessModeWrite`; settings endpoints (collaborators, webhooks, transfer) require `AccessModeAdmin`; deletion and ownership changes require `AccessModeOwner`. `reqRepoWriter`, `reqRepoAdmin`, and `reqRepoOwner` Macaron handlers centralize the comparison.

## Organization teams and site administrators

Organization access goes through teams (`Team` model). A team has an `Authorize` access mode and a set of repositories; the implicit "Owners" team gets `AccessModeOwner` for every repository in the organization. `RecalculateTeamAccesses` projects team membership into `access`. `User.IsAdmin` is the global escalation. Handlers wired with `context.Toggle({AdminRequired: true})` bail out unless `IsLogged && User.IsAdmin`; API endpoints under `/api/v1/admin/...` apply the same check.

## Visibility flags

`[repository] ForcePrivate = true` forces every repository to private regardless of its stored flag. `Repository.IsUnlisted` is orthogonal to access mode: it hides the repository from browse listings but does not change resolution for direct URL access.
