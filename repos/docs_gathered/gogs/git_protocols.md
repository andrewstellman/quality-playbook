# Git Protocols (HTTP, SSH, LFS)

Gogs exposes three transports for Git repositories: smart HTTP/HTTPS, SSH (external `sshd` plus a `serv` shim, or the built-in Go SSH server), and Git LFS over HTTP. All three are mounted by the `web` process and converge on the same on-disk layout.

## Smart HTTP

Routes live in `internal/route/repo/http.go` under `/<username>/<reponame>.git/*`. They handle the smart-protocol endpoints (`info/refs?service=git-upload-pack`, `git-upload-pack`, `git-receive-pack`) plus dumb-protocol fall-backs (`HEAD`, `objects/...`).

`HTTPContexter()` middleware sets CORS headers when configured, resolves the owner and repository (trimming `.git` and `.wiki`), decides pull vs. push from the `service` query parameter, URL suffix, or HTTP method, and skips authentication for public pulls when `[auth] REQUIRE_SIGNIN_VIEW` is off. Otherwise it decodes `Authorization: Basic ...` and tries `db.Users.Authenticate`. On failure, the username is tried as a personal access token via `context.AuthenticateByToken`; failing that, the password is tried as a token. Users with two-factor enabled are rejected with a 401 instructing them to use a personal access token. `db.Perms.Authorize` is called with `Read` for pulls and `Write` for pushes; pushes to mirror repositories are refused.

After authentication, the handler delegates to `serviceRPC`, `getInfoRefs`, `getTextFile`, `getInfoPacks`, `getLooseObject`, `getPack`, or `getIdxFile`, which spawn `git` subprocesses or serve files from the bare repository directory.

## Built-in SSH server

`internal/ssh/ssh.go` implements an optional SSH server using `golang.org/x/crypto/ssh`. Enabled by `[server] START_SSH_SERVER = true`, bound to `[server] SSH_LISTEN_HOST:SSH_LISTEN_PORT`. `handleServerConn` accepts only `session` channels; `exec` requests are sanitized by `cleanCommand` (everything before the first `git` token is discarded) and re-invoked as `gogs serv key-<keyID>` with `SSH_ORIGINAL_COMMAND` set, piping stdio between the SSH channel and the child process. Algorithms come from `[server] SSH_SERVER_CIPHERS`, `SSH_SERVER_MACS`, `SSH_SERVER_ALGORITHMS`; per-algorithm minimum key sizes from `[ssh.minimum_key_sizes]`.

## External sshd integration

The alternative deployment uses the host's `sshd` plus a dedicated `git` user, with `~git/.ssh/authorized_keys` populated so each public key maps to a `command="gogs serv key-<id>"` line. `internal/cmd/serv.go` parses `SSH_ORIGINAL_COMMAND` to extract the Git verb (`git-upload-pack`, `git-receive-pack`, `git-upload-archive`) and repository path, looks up the key, resolves the user, checks `db.Perms.Authorize`, refuses push to mirror repositories, and exec's `git` inside the resolved repository. `[ssh] RewriteAuthorizedKeysAtStart` rebuilds `authorized_keys` from the `public_key` table at startup.

## Public key store

`internal/db/public_keys.go` defines `PublicKeysStore` and the `PublicKey` model. `ssh-keygen -lf` computes the fingerprint and validates the format on add; `[ssh] MinimumKeySizeCheck` enforces minimum sizes. Deploy keys live in a parallel table.

## Git LFS

LFS routes live in `internal/route/lfs/` under `/<username>/<reponame>.git/info/lfs/`. `serveBatch` handles the batch protocol; `basicHandler` handles basic transfers. The `authenticate` middleware requires HTTP Basic and follows the same triple-attempt sequence as smart HTTP. `authorize(mode)` enforces the requested access mode via `db.Perms.Authorize`.

LFS objects use a pluggable `Storager` (`internal/lfsutil/`); the default `LocalStorage` persists under `[lfs] ObjectsPath` keyed by OID. The `lfs_object` table (`LFSObject` model) pairs each `RepoID + OID` with size and creation timestamp. The protocol surfaces:

- `POST /objects/batch` — returns upload or download URLs.
- `GET /objects/basic/:oid` — download after read access and OID match.
- `PUT /objects/basic/:oid` — upload after write access and `Content-Type: application/octet-stream`.
- `POST /objects/basic/verify` — confirms upload size and OID.

## Working pool, hooks, mirroring

Mutating operations (push, edit, merge, archive, fork, mirror) acquire a per-repository lock via `internal/sync.ExclusivePool`. Server-side Git hooks are written into each repository under `hooks/` and re-exec `gogs hook ...`; `cmd hook` enforces branch protection and triggers webhook dispatch via `HookQueue`. `db.Mirror` records repositories configured to pull from an upstream; `cron.update_mirrors` invokes `db.MirrorUpdate` periodically.
