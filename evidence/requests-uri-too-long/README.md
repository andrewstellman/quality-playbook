# psf/requests — `codes.uri_too_long` resolves to 414, not 122

**Verdict: NEEDS-MAINTAINER-INPUT, leaning WORKING-AS-INTENDED (do not file a PR as originally framed).**

No patch, no regression test, no PR-DRAFT was produced. This does not meet this task's bar for
"real, fixable bug" — see reasoning below. This directory contains only investigation evidence.

## Candidate as scouted

Source: `QPB/docs/research/triage-2026-09-27/scout-candidates.md`, rank 6, and the historical
finding `QPB/repos/secbench2_widenet/wn-py-10-requests/quality/BUGS.md` BUG-001 (2026-06-22,
Quality Playbook v1.5.8, code-only Phase 3 review). The historical report claims
`requests.codes.uri_too_long == 414` (should be `122`) and frames it as a MEDIUM-severity
"status-code alias registry collision" caused by dict last-writer-wins in `_init()`.

## 1. Fresh clone

```
$ git clone https://github.com/psf/requests.git
$ git log -1 --format='%H %cI'
611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60 2026-09-21T13:22:33-07:00
```

HEAD SHA: `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`, committed 2026-09-21 (6 days before this
session, same SHA the historical scout report already cited — repo hasn't moved since).

No `CONTRIBUTING.md` at repo root; the actual contributing guide lives at
`docs/dev/contributing.rst`. No dedicated `.github/PULL_REQUEST_TEMPLATE.md` was found either.

## 2. Current source (verbatim, `src/requests/status_codes.py`)

```python
_codes = {
    ...
    122: ("uri_too_long", "request_uri_too_long"),
    ...
    413: ("request_entity_too_large", "content_too_large"),
    414: ("request_uri_too_large", "uri_too_long"),
    ...
}

codes: LookupDict[int] = LookupDict(name="status_codes")

def _init():
    for code, titles in _codes.items():
        for title in titles:
            setattr(codes, title, code)
            if not title.startswith(("\\", "/")):
                setattr(codes, title.upper(), code)
    ...

_init()
```

`_init()` iterates `_codes` in dict-insertion order (100 -> 511) and does last-writer-wins
`setattr`. Since 414 is inserted after 122, `codes.uri_too_long` ends up bound to 414. This part of
the historical report's mechanism is accurate and still reproduces (see `execution_log.txt`):

```
$ python3 -c "import sys; sys.path.insert(0,'src'); import requests; print('uri_too_long =', requests.codes.uri_too_long)"
uri_too_long = 414
```

## 3. git blame / history — is this deliberate?

```
2a6f290bc requests/status_codes.py (Nate Prewitt 2022-04-29)     122: ("uri_too_long", "request_uri_too_long"),
e45b42896 (Michiel W. Beijen 2024-04-08)     413: ("request_entity_too_large", "content_too_large"),
e45b42896 (Michiel W. Beijen 2024-04-08)     414: ("request_uri_too_large", "uri_too_long"),
```

Full commit + diff in `introducing_commit.txt`. Commit `e45b4289` ("Add rfc9110 HTTP status code
names", merged as PR #6680 on 2024-04-11, authored by a third-party contributor and merged after
maintainer review) explicitly says:

> RFC 9110 *HTTP Semantics* obsoletes some earlier RFCs which defined HTTP 1.1. It adds some status
> codes that were previously only used for WebDAV to HTTP proper after making the names somewhat
> more generic... This commit adds the http status code names from that RFC.

RFC 9110 Appendix B ("Changes from RFC 7231") renames HTTP 414 from "URI Too Long" using exactly
that name — `uri_too_long` is the standards-track RFC 9110 name for 414, not a mistake. The 122
entry predates this by two years (added 2022-04-29 by maintainer Nate Prewitt) and encodes the
older, non-standard, WebDAV/IE-era "Request-URI too long" nickname.

**So this is not a copy-paste slip.** It's a deliberate 2024 addition of the modern RFC-canonical
name for 414, which happens to collide with a pre-existing informal alias for the obscure,
non-standard 122. The PR description invokes the project's compliance policy
(`docs/user/advanced.rst` "Compliance" section: "Requests is intended to be compliant with all
relevant specifications and RFCs") as rationale — i.e., the *414* binding is the one grounded in an
actual normative spec, and the *122* binding is not.

## 4. Same-commit sibling collision, and how maintainers reacted to it a month ago

The same commit (`e45b4289`) also introduced a second, structurally identical collision:
`102: ("processing", "early-hints")` — RFC 9110 defines 103 as Early Hints, not 102, so
`early-hints`/`early_hints` is misattached to 102 there too.

This sibling bug was reported as GitHub issue **psf/requests#7611** on 2026-08-26 (one month
before this session) and closed the same day with `state_reason: "not_planned"`. Maintainer
**Nate Prewitt** — the same person who authored the 122 entry in 2022 — responded on that issue:

> "@Shaivarth, this still contains nonsense content. In the future, this will be treated as spam and
> may result in removing your accounts access to PSF repositories. Please do not post content you
> have not validated yourself."

and, after the reporter trimmed the issue to just the 102/103 point:

> "@Shaivarth 508 is a WebDAV status code, not a standard HTTP Status code. Your LLM has created
> references to RFC sections that do not exist. Please validate what you're submitting before
> opening issues. We'll take a look at the 102 mapping."

Despite that closing remark, the 102/103 mapping is **still unfixed** on current HEAD (verified in
the source dump above: `102: ("processing", "early-hints")`, `103: ("checkpoint",)` unchanged) and
the issue is closed as not-planned, not open/tracked.

This is directly relevant to how a `uri_too_long`/122/414 report would land right now:
- Same file, same root commit, same maintainer, same shape of defect (an RFC9110-addition alias
  colliding with a pre-existing legacy alias).
- That maintainer has, within the last month, publicly flagged a report on this exact pattern as
  probable LLM-generated noise and did not act on it even after saying he would look.
- A `uri_too_long` PR from this exercise — self-disclosed as Quality-Playbook/Claude-sourced, per
  this task's own PR-DRAFT convention — would land in the same suspicious-of-LLM-slop context.

## 5. Backward compatibility

`codes.uri_too_long == 414` has been the shipped behavior since requests 2.32.0 (April 2024), over
2.5 years and multiple releases as of this scan. Any fix has to pick a side, and either choice is a
breaking behavior change for someone who adopted the current mapping:
- Restoring `uri_too_long == 122` breaks any caller who (knowingly or not) has relied on
  `codes.uri_too_long == 414` since 2024.
- Removing `uri_too_long` from 414's tuple and keeping it only on 122 is the "restore original
  intent" fix, but still changes observable behavior for existing installs — no deprecation path,
  no major-version gate.
- There's no fix that recovers "correctness" without an observable break in a widely-installed
  library where `requests.codes.<name>` is public, documented API surface.

## 6. Existing issue/PR search (all via GitHub API, api.github.com/search/issues)

| Query | Result |
|---|---|
| `uri_too_long repo:psf/requests` | 1 hit — unrelated 2013 PR #1456 (`im_used`/226), not this bug |
| `122 status_codes repo:psf/requests` | 1 hit — unrelated issue #122 ("Fixing myself :)", 2011) |
| `"content_too_large" repo:psf/requests` | 0 hits |
| `status_codes duplicate repo:psf/requests` | 0 hits |
| `status_codes.py collision repo:psf/requests` | 0 hits |
| `rfc9110 repo:psf/requests` | 5 hits: **#7611** (102/103 collision from the same commit, closed not_planned 2026-08-26, see section 4), the original #6680 PR that introduced both collisions, and 3 unrelated RFC9110-adjacent issues/PRs (StringIO Content-Length, NUL-byte headers, Authorization-header overwrite) |
| `122 414 repo:psf/requests` | 3 hits, all unrelated (numeric coincidences: issue #414 "Redirect to unicode URL fails", issue #122, PR #1456) |

**No existing report specifically names the `uri_too_long`/122/414 collision.** The closest and most
relevant prior art is #7611 (section 4), the same commit's sibling collision — not this one, but
highly predictive of how a report on this file would be received right now.

## Verdict reasoning (three sentences, also in the top-level response)

`requests.codes.uri_too_long == 414` is a real, reproducible alias collision (confirmed by
execution against fresh HEAD `611c6162`), but it was produced by a 2024 maintainer-merged commit
that deliberately added the RFC 9110-canonical name for 414, not by an unnoticed typo, and either
"fix" direction is a backward-incompatible behavior change to public API that's shipped for 2.5+
years. A structurally identical sibling collision from the same commit was reported to the project
one month ago (#7611) and was closed not-planned with the maintainer explicitly calling out
suspected LLM-generated content in the report and not following through on his own "we'll take a
look" — so a `uri_too_long` PR right now would land in an actively hostile-to-this-pattern
maintainer context. Given the ambiguous intent, the compatibility cost, and the live negative
precedent on the exact same file/commit/maintainer, this does not clear the bar for a regression
test + fix + PR under this task's "only if real and fixable" instruction; it's flagged
NEEDS-MAINTAINER-INPUT rather than CONFIRMED.

## Decisions for Andrew

1. **File nothing right now.** Recommend treating this as closed-out research, not a PR candidate,
   given #7611's precedent — a `uri_too_long` issue from an AI-assisted-quality-run would very
   plausibly get the same "validate what you submit" response, especially self-disclosed as
   Claude/Quality-Playbook-sourced per this project's own PR-DRAFT convention.
2. If Andrew disagrees and wants to file anyway: the honest framing is "propose deprecating the
   ambiguous 122 alias in favor of the RFC9110 name on 414" (i.e., argue for keeping 414's binding
   and dropping/renaming 122's), not "fix a bug" — because 414's binding is the RFC-grounded one.
   That's a design proposal, not a defect report, and belongs in a GitHub Discussion or a low-key
   issue, not a code-only PR with a silent behavior change.
3. This candidate should be marked in the scout-candidates ranking as investigated-and-declined
   (not "reserve pool," not "confirmed") so a future pass doesn't re-spend time on it.

## Files in this directory

- `README.md` — this file
- `head_sha.txt` — pinned clone HEAD SHA + commit date
- `execution_log.txt` — verbatim `python3` execution against fresh HEAD confirming `uri_too_long == 414`
- `blame.txt` — `git blame` on the two relevant lines
- `introducing_commit.txt` — full `git show` of commit `e45b42896` (the PR #6680 diff that created the collision)
