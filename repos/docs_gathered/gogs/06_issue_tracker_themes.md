# Gogs Issue Tracker Themes

## Sources

- https://github.com/gogs/gogs/issues (929 open issues at time of writing)
- https://github.com/gogs/gogs/discussions (the project's primary user-support venue, large; questions about permissions and admin workflows recur here)
- https://github.com/gogs/gogs/issues?q=is%3Aissue+permission
- https://github.com/gogs/gogs/issues?q=is%3Aissue+access
- https://github.com/gogs/gogs/issues?q=is%3Aissue+admin
- https://github.com/gogs/gogs/issues?q=is%3Aissue+protected
- https://github.com/gogs/gogs/issues?q=is%3Aissue+security
- https://github.com/gogs/gogs/security/advisories (some patterns flagged here recur in non-CVE issues)
- The advisory texts cited in `05_known_issues_and_advisories.md`

## Context

Gogs's issue tracker is large and long-running (the project is over a decade old). Issues fall into recurring clusters; this file summarizes the ones most relevant to an access-control audit. The point is not to enumerate individual tickets but to map the *thematic concentration* of user-reported problems onto the access-control surface, so QPB can read findings in context.

These themes are derived by browsing the issue tracker's title list with the queries above and grouping by recurring concern. Specific issue numbers are cited where they exemplify the theme.

## Theme 1: "Why can/can't this user do X on this repo?" — permission model is hard to reason about

Recurring user-facing pain. Common shapes:

- A user is on multiple teams in an org; their effective permission on a repo isn't what they expected.
- A site admin is interacting with a private repo they're not a collaborator on; the UI shows admin actions because of the implicit `AccessModeOwner` promotion in `RepoAssignment()`.
- A collaborator on a fork doesn't understand why they got a different effective level on the base repo than expected (the fork-fallback path in `RepoAssignment()` caps indirect access at `AccessModeWrite`).
- A deploy key was added with read-only but the user expects it to push; deploy-key access mode is not the same as user access mode.

**Audit relevance**: the user-reported confusion is downstream of *real* complexity in `database.Handle.Permissions().AccessMode(...)`. Bugs in the max-merge logic across team membership, direct collaboration, and the fork-fallback path would be very hard to spot from user reports because users blame their own mental model first. A focused review of the `AccessMode` resolution is high-leverage.

## Theme 2: Protected branches don't always feel protected

Pre-CVE-2026-25232 (and recurringly in older issues): users report that protected branches are still being modified or deleted in ways they didn't expect. Several issues asked why a PR could merge despite branch protection, or why a force-push got through.

The settled answer in the codebase is that branch protection is enforced in two places:

1. The Git pre-receive hook (`internal/cmd/hook.go`) — for SSH and smart-HTTP push paths.
2. The web-UI branch-delete handler (post-CVE-2026-25232 fix only).

There's no third enforcement at the database layer. **Anywhere else a "delete branch" or "force update ref" operation could be invoked** is a candidate for the same class of bypass that CVE-2026-25232 closed. The audit invariant: every code path that ends in `git update-ref -d` or `git push --force` for a branch must run through one of those two gates.

## Theme 3: Webhooks fire for actions users don't expect (or don't fire when they should)

Recurring class of issues. Two shapes:

- **Over-firing**: a webhook event triggers for an action that shouldn't have been allowed in the first place (the BAC bypass succeeded; the webhook then made the unauthorized action externally observable).
- **Under-firing**: an action was performed via a code path that didn't call into `PrepareWebhooks(...)`, so external integrations never saw it.

**Audit relevance**: when fixing a BAC bug, check whether the unauthorized path also fired webhooks. If it did, downstream integrations may have acted on the false signal. If it didn't, the audit trail is silent and detection-after-the-fact is impossible.

## Theme 4: API behavior diverges from web-UI behavior

Recurring user reports of "I can do X in the UI but the API returns 403" or vice versa. Most of these are not security bugs (they're missing API parity for features), but a subset is. CVE-2026-25229 is exactly this theme in security clothing: the API's `EditLabel` had the correct repo-scoping; the Web UI's `UpdateLabel` did not.

**Audit invariant** (re-stated from `04_invariants.md`): the authorization predicates for the API handler and the Web UI handler implementing the same operation must be equivalent. The shape of the bug is **always**: one side reaches a less-guarded code path than the other. The audit's job is to enumerate every (web-handler, api-handler) operation pair and verify equivalence.

## Theme 5: Org-team boundaries and edge cases

Issues report edge cases like:

- A team is deleted while members are mid-session; their effective access doesn't refresh until they re-authenticate.
- A user's org membership is revoked but they retain access through a collaboration row they were also granted independently.
- A repo is transferred between orgs and the old org's teams retain references in the access table.

**Audit relevance**: these are concurrency / stale-state bugs at the access-mode resolution boundary. Most are not exploitable BAC, but they expand the gap between "what the admin thinks the permission is" and "what `AccessMode(...)` returns." A handler that performs a fresh `AccessMode` lookup at the moment of action is robust; a handler that trusts a value cached earlier in the request (which is fine in Gogs because requests are short) is also fine; a handler that trusts a value cached *across requests* would be the bug. There's no such handler in the current code, but the pattern to watch.

## Theme 6: Anonymous users see more than expected on partially-public repos

A "partially public" repo is private but with `CanGuestViewIssues()` or `CanGuestViewWiki()` enabled. The handling in `RepoAssignment()` redirects anonymous users between issue and wiki tabs based on which is permitted, and 404s elsewhere — but this is a relatively recent feature and the redirect logic is intricate.

Issues report variants of: "I made my repo private but a guest can still see X." Most are configuration confusion; a small number have been real bugs (the issue surface that resolves to the CanGuestViewIssues / CanGuestViewWiki branches).

**Audit relevance**: any handler that runs on a repo and is reachable anonymously needs to consult `c.Repo.HasAccess()` before exposing data that's not in the partially-public set. The bug shape: a handler that runs after `RepoAssignment()` (which let the anonymous user past the gate because of partial-public) but then reads data that's outside the partially-public window (e.g., reading file contents while only issues are guest-visible). This is the class CVE-2026-25242 was an instance of, even though the specific bug was a file-upload route.

## Pattern: maintainer's response style

`@unknwon`'s response style on issues and discussions is: triage quickly, accept patches, close with a fix-version label when the fix lands. There is no security mailing list and no formal disclosure timeline; high-severity issues are tracked through GitHub's private advisory workflow and published when the fix is in a release. **For QPB**, this means:

- The maintainer publishes once a fix is in a release. Affected versions are accurate and the patched version is the cutoff.
- There is no "known but unfixed" advisory list separate from the public list.
- The maintainer's own commits to a security fix are typically tagged in the changelog with the GHSA ID; cross-referencing the changelog entry to the commit gives the patch diff.

## What's *not* in the issue tracker that you might expect

A counterpoint: there are very few user reports specifically titled "broken access control" or "IDOR" in the issue tracker. The pattern in this codebase is that BAC bugs are reported by external security researchers directly through the private-advisory workflow, *not* discovered by users hitting them in production and filing public tickets. **This means QPB cannot use issue-tracker volume as a signal of where BAC bugs cluster.** The signal lives in the advisory list (`05_known_issues_and_advisories.md`) and in the static code patterns (`03_access_control_patterns.md`). The issue tracker themes above are useful for context, not for hunting.
