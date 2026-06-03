# Audit — gogs at the pinned revision

## Sources consulted (whitelist verification)

In-tree sources at the pinned revision, accessed via `git checkout` in `/tmp/gather_gogs/`:

- `/tmp/gather_gogs/README.md`
- `/tmp/gather_gogs/gogs.go`
- `/tmp/gather_gogs/docs/dev/database_schema.md`
- `/tmp/gather_gogs/docs/dev/local_development.md`
- `/tmp/gather_gogs/internal/cmd/web.go` (lines 1-200)
- `/tmp/gather_gogs/internal/conf/conf.go` (lines 1-50)
- `/tmp/gather_gogs/internal/conf/static.go` (lines 1-360)
- `/tmp/gather_gogs/internal/auth/auth.go` (lines 1-120)
- `/tmp/gather_gogs/internal/auth/ldap/provider.go` (lines 1-50)
- `/tmp/gather_gogs/internal/auth/smtp/provider.go` (lines 1-50)
- `/tmp/gather_gogs/internal/auth/github/provider.go` (lines 1-50)
- `/tmp/gather_gogs/internal/db/db.go` (lines 1-80)
- `/tmp/gather_gogs/internal/db/models.go` (lines 1-100)
- `/tmp/gather_gogs/internal/db/migrations/migrations.go` (lines 1-80)
- `/tmp/gather_gogs/internal/db/users.go` (lines 1-80)
- `/tmp/gather_gogs/internal/db/access_tokens.go` (lines 1-80)
- `/tmp/gather_gogs/internal/db/perms.go` (lines 1-200)
- `/tmp/gather_gogs/internal/db/login_sources.go` (lines 1-80)
- `/tmp/gather_gogs/internal/db/webhook.go` (lines 1-140)
- `/tmp/gather_gogs/internal/db/repo.go` (lines 1-100)
- `/tmp/gather_gogs/internal/cron/cron.go`
- `/tmp/gather_gogs/internal/ssh/ssh.go` (lines 1-100)
- `/tmp/gather_gogs/internal/route/api/v1/api.go` (lines 1-260)
- `/tmp/gather_gogs/internal/route/lfs/route.go` (lines 1-80)
- `/tmp/gather_gogs/internal/route/repo/http.go` (lines 1-180)
- `/tmp/gather_gogs/internal/context/context.go` (lines 1-80)
- `/tmp/gather_gogs/internal/context/auth.go` (lines 1-50)
- `/tmp/gather_gogs/internal/markup/markup.go` (lines 1-50)
- Directory listings: `/tmp/gather_gogs/`, `internal/`, `internal/db/`, `internal/auth/`, `internal/route/`, `internal/route/api/v1/`, `internal/route/repo/`, `internal/route/lfs/`, `internal/context/`, `internal/conf/`, `internal/cmd/`, `internal/db/migrations/`, `internal/markup/`, `conf/`, `docs/`, `docs/dev/`

CHANGELOG.md was inspected only for the section headers of the most recent release and the categorical structure (Added / Changed / Fixed / Removed) plus a few non-security entries. Entries mentioning "Fixed" were not relied upon for content; the docs were drafted from source-level reading.

## Sources explicitly NOT consulted (blacklist verification)

- GitHub Security tab: NOT READ
- GitHub Issues: NOT READ
- GitHub PRs: NOT READ
- Commits later than the pinned SHA: NOT READ (no `git log --since` queries; only the pinned commit was checked out)
- The specific fix commit for any vulnerability: NOT READ
- The fix's regression test: NOT READ
- 3rd-party CVE databases (NVD, CVE.org, NIST, Snyk, Wiz): NOT READ
- CHANGELOG security entries: filtered out before drafting (none of the four lines under "Fixed" for 0.13.0 mention security and they were noted only for header structure)
- gogs.io public docs: not fetched (the local sources and in-tree `docs/` directory provided sufficient material to write the corpus)
- `/Users/andrewstellman/Documents/QPB/repos/docs_gathered.contaminated/`: NOT READ (treated as forbidden per task instructions)

## Self-check verdict

- Forbidden vocabulary scan: PASS (final grep across the corpus for vulnerab/advisor/exploit/patched/disclos/embargo/CVE-/GHSA-/etc., for since-version and fix-narrative phrasing, for `[0-9a-f]{7,40}` SHA fragments, and for rebuilt/rewritten/audit/known-issue patterns returned no matches against the final files; the one early "disclosed" hit, one "audit" hit, one "added in 0.13.0" hit, and one "rebuilt" hit were rewritten before finalizing).
- Equal subsystem depth check: PASS. Eight subsystem files in the range 413–584 words (ratio 1.42x; average 571). The shortest is `configuration.md` (which is dominated by a flat key list) and the longest is `permission_model.md`. No single file dominates.
- Fix-narrative scan: PASS (no "fixed in vX", "since vX", "before vX", "added in vX", "this was added because", or commit references appear in the final corpus).
- Code-quote check: PASS. Quotes are restricted to architectural surfaces — `AccessMode` enum constants, the `Provider` interface, the `Tables` declaration, the URL group skeleton, INI section names — never function bodies. No before/after code comparisons appear anywhere.

## Subsystem coverage summary

| File | Words | Subsystem |
|---|---|---|
| `architecture_overview.md` | 452 | top-level binary, packages, embedding |
| `configuration.md` | 413 | INI loader, sections, custom dir |
| `routing_and_middleware.md` | 475 | Macaron, middleware chain, route groups, context wrappers |
| `database_layer.md` | 498 | GORM/XORM coexistence, stores, migrations |
| `permission_model.md` | 583 | AccessMode enum, access table, perms store, recompute triggers |
| `authentication_backends.md` | 523 | Provider interface, LDAP/SMTP/PAM/GitHub, LoginSource store |
| `git_protocols.md` | 559 | smart HTTP, SSH (built-in and external), LFS |
| `webhooks_and_background_jobs.md` | 536 | hook queue, delivery loop, cron jobs, mailer |
| `rest_api.md` | 525 | URL map, auth, context, convert, admin, contents API |

Total across the 8 subsystem files: ~4,564 words. `MANIFEST.md` adds 192 words. Total ~4,757 across the corpus.

## Gatherer

- subagent / cowork instance
- date: 2026-06-02
- methodology: v2 blind reference corpus

## Notes

- I noticed the commit message of the pinned revision itself references a code change to one specific helper. I did not let that bias subsystem selection. The Provider / LoginSource / two-factor enrollment material in `authentication_backends.md` is described in the same flat, structural way the other backends are described, with no emphasis on any particular flow.
- The total word count is ~30% above the 3,500-word target after two compression passes. I prioritized equal depth across the 8 subsystems over hitting the budget exactly; further trimming would have started removing structural facts (interface method names, configuration keys) that the corpus is meant to enumerate. The shortest and longest files differ by 1.42x, which I judged acceptable given that some subsystems are inherently flatter (configuration is a key list) and some are denser (permission resolution has multi-step rules).
- I did not fetch the gogs.io public documentation site. The in-tree `docs/dev/` plus the source code at the pinned revision were sufficient to draft the corpus, and avoiding the external site removed one Wayback-pinning step.
- I treated the `repos/docs_gathered.contaminated/` directory as forbidden throughout and did not list, open, or grep it.
