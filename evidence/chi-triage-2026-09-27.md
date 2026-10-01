# chi correctness-finding validation (2026-09-27)

Candidates from the QPB chi-1.6.0 run (`repos/chi-1.6.0/quality/BUGS.md`), checked against current go-chi/chi master. Nothing has been pushed, filed, or commented anywhere.

- **Pinned SHA:** `3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc` (commit 2026-09-18T13:51:53+02:00), fresh clone 2026-09-27.
- **Toolchain:** go1.25.1 linux/arm64 from the official go.dev tarball; sha256 `65a3e34fb2126f55b34e1edfc709121660e1be2dee6bdf405fc399a63a95a87d` matches go.dev's published value. Ubuntu 22.04's `golang-go` is 1.18, older than chi's `go 1.24`. `GOTOOLCHAIN=local`.
- **Baseline:** `go test ./...` and `go test -race ./...` both pass on unpatched master.
- **Disclosure searches:** GitHub search API via `web_fetch`. Exact queries are in each folder's README.
- **RFC quotes:** checked against the rfc-editor.org text of RFC 9110.

## Verdicts

| QPB ID | Finding | Verdict | Evidence |
|---|---|---|---|
| BUG-014 | `GetHead` inside a mounted router asks the root router about a sub-router-relative path. The sub-router's own HEAD handler is ignored, and a 405 is possible. | **CONFIRMED.** Red, then green; suite passes; no prior report found. | `evidence/chi-gethead-mount/` (with PR-DRAFT.md) |
| BUG-007 | `AllowContentEncoding` gives a 415 for `Content-Encoding: gzip, deflate` on one line | **ALREADY REPORTED**: issue #959 (open), PR #1182 (open, 2026-09-17), #1144 (closed by its author). Reproduced and fixed locally anyway. | `evidence/chi-allowcontentencoding-comma/` |
| BUG-008 | `Recoverer` matches only the exact string `Connection: Upgrade` | **ALREADY REPORTED**: open PRs **#1077 (by andrewstellman, 2026-04-04)**, #1170, #1172. Reproduced and fixed locally. The practical impact on current Go is a spurious "WriteHeader on hijacked connection" log line. | `evidence/chi-recoverer-upgrade-token/` |
| BUG-006 | `ContentCharset` rejects a quoted `charset="utf-8"` | **ALREADY REPORTED**: PR #1139, closed by its author ("too thin / low user impact"), not merged, no maintainer decision. The earlier triage reproduced it at this same SHA (`docs/research/triage-2026-09-27/nonlinux/evidence/chi-actual.log`). Not re-run here. | none (see earlier triage) |
| BUG-001 | `Mux.Find` leaves the mount `*` URLParam that live routing clears | **NEEDS-MAINTAINER-INPUT.** Reproduces. The `Find`/`Match` docs only warn that the context is mutated; they don't promise parity with live routing. A candidate fix and a green run exist. | `evidence/chi-find-mount-wildcard/` |
| BUG-002 | `PathRewrite`/`PageRoute` use `r.URL.Path`. Under Mount, `PathRewrite` does not affect routing and `PageRoute` needs the absolute path. | **NEEDS-MAINTAINER-INPUT.** Both reproduce. Mount-relative semantics are undocumented, and a fix would change behaviour that users may rely on. Test-only patch, no fix. | `evidence/chi-pathrewrite-pageroute-mount/` |
| BUG-009 | `RegisterMethod` races with serving | **NEEDS-MAINTAINER-INPUT, leaning working-as-designed.** The race reproduces under `-race`. The maintainer's PR #271 says to call it "in an init function", and the example does. No code fix proposed. | `evidence/chi-registermethod-race/` |

Already handled by the earlier triage and skipped here: Accept-Encoding/compression (#1069, #1177), SupressNotFound context mutation (#939, #940). BUG-013 (log injection) was skipped as instructed. None of the candidates checked here showed security impact.

## Decisions for Andrew
1. **BUG-014 / chi-gethead-mount** is the only candidate ready for a PR. The fix detects "inside a mounted router" with a heuristic (`len(rctx.RoutePatterns) > 0`). A maintainer might prefer the core API change requested in #623. The README lists this as an open question.
2. **BUG-008:** your own PR #1077 is open for this. Leave it or refresh it; don't open a duplicate.
3. **BUG-007:** PR #1182 already exists. Do nothing, or post a supportive review.
4. **BUG-001 / BUG-002:** whether to ask the maintainers in an issue. A PR is not recommended.
5. **BUG-009:** probably drop. At most, a doc-comment tweak.

## Repro commands (Mac, Go 1.26)
```zsh
git clone https://github.com/go-chi/chi /tmp/chi && cd /tmp/chi && git checkout 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
go test ./...                                   # baseline
git am "/Users/andrewstellman/Documents/QPB/evidence/chi-gethead-mount/0001-middleware-fix-GetHead-look-ahead-inside-a-mounted-r.patch"
go test -count=1 -v -run TestGetHead ./middleware/ && go test ./...
```
To see the red run, apply only the test hunk: `git apply --include='middleware/get_head_test.go' <patch>` on a clean checkout.
