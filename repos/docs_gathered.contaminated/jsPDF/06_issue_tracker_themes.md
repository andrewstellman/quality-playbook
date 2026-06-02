# jsPDF — GitHub Issue Tracker Themes

## Sources

- https://github.com/parallax/jsPDF/issues (open issues, state at June 2026)
- https://github.com/parallax/jsPDF/issues/2170 ("Plans for the future")
- https://github.com/parallax/jsPDF/issues/2677 ("Issues with characters not displayed correctly?")
- https://github.com/parallax/jsPDF/issues/3067 ("Suggestions for next major release breaking changes")
- https://github.com/parallax/jsPDF/issues/3963 ("DOMPurify contains a Cross-site Scripting vulnerability")
- https://github.com/parallax/jsPDF/issues/3936 ("Warning: Synchronous XMLHttpRequest on the main thread")
- https://github.com/parallax/jsPDF/issues/3927 ("security issue - developer information disclosure")
- https://github.com/parallax/jsPDF/issues/3929 ("Upgrade html2canvas to html2canvas-pro")
- https://github.com/parallax/jsPDF/issues/3964 ("Update to canvg@4 for ESM support")

## Context

QPB's blind [REDACTED] hunt is the primary objective, but issue-tracker themes
inform invariant detection — they show where adopters report friction
that overlaps with the file-access pipeline, and where the maintainers'
attention is currently focused. The themes below are derived from the
open-issues list and the three pinned planning issues.

## Theme 1: Dependency Security Posture (HIGH RELEVANCE)

The most relevant theme for the [REDACTED] hunt. Multiple open issues report
that jsPDF's *optional* dependencies have their own security advisories,
and adopters expect jsPDF to upgrade transitively:

- **#3963 (Mar 2026, open):** "DOMPurify contains a Cross-site Scripting
  vulnerability" — DOMPurify is the sanitiser used by `html()` when a
  string HTML document is supplied. The reporter wants jsPDF to bump
  the DOMPurify dependency.
- **#3929 (Dec 2025, open):** "Upgrade html2canvas to html2canvas-pro"
  — html2canvas is unmaintained; html2canvas-pro is a community fork.
  `html2canvas` is the engine behind `html()` resource resolution,
  which is one of the four affected methods in [REDACTED].
- **#3964 (Mar 2026, open):** "Update to canvg@4 for ESM support" —
  canvg is the optional SVG-rendering dependency.

**Relevance to [REDACTED]:** All three implicate the `html()` code path,
which is one of the four advisory-listed affected methods. A future
upgrade to html2canvas-pro or DOMPurify might change how `html()`
resolves resource paths and could either tighten or loosen the
[REDACTED] surface. Any change to `html()` resource resolution must continue
to route through `nodeReadFile` (INV-CONTRACT-1 / INV-9).

## Theme 2: Synchronous Network I/O (MEDIUM RELEVANCE)

- **#3936 (Jan 2026, open):** "Warning: Synchronous XMLHttpRequest on
  the main thread" — adopters running in the browser get console
  deprecation warnings because `browserRequest` defaults to
  synchronous XHR (matching `loadFile`'s default `sync=true`).

**Relevance to [REDACTED]:** This is browser-side noise, but it's a hint that
the `loadFile(url, sync=true, callback)` API contract — sync by
default — propagates into both builds. The Node build's
`fs.readFileSync` choice mirrors the same default. Both choices are
defensible (PDFs are assembled serially) but mean an audit looking
for async-only filesystem patterns will miss the dominant path.

## Theme 3: Generic "Developer Information Disclosure" (LOW DIRECT RELEVANCE)

- **#3927 (Dec 2025, open, labelled `no-issue-activity`):** "security
  issue - developer information disclosure" — title only; the issue
  text is not the [REDACTED] CVE (different report timing, different
  reporter). The label `no-issue-activity` suggests the maintainers
  have not engaged.

**Relevance to [REDACTED]:** Likely a low-severity report unrelated to
[REDACTED]. Listed here so QPB doesn't confuse it for the in-scope
advisory if the issue title surfaces in search results.

## Theme 4: Unicode / Font Handling (MEDIUM RELEVANCE)

- **#2677 (Feb 2020, open, 26 comments):** "Issues with characters not
  displayed correctly?" — long-running thread on Unicode font support.
- **#3957 (Feb 2026, open):** "Support for emojis and non-latin scripts"
  — directly related to font/glyph capability.
- **#3958 (Feb 2026, open):** "Font Converter Web Page Not Available"
  — the recommended workflow for adding fonts (via the
  `fontconverter.html` tool) is broken.

**Relevance to [REDACTED]:** Adopters with non-Latin requirements are
strongly incentivised to load custom TTFs. The two paths to load a TTF
are (a) addFileToVFS + addFont with binary string (safe, no
filesystem) and (b) addFont with a path string that triggers
`loadFile` (the [REDACTED] surface). When the documented tool (`#3958`) is
broken, adopters are nudged toward the second path more often. This
is not a CVE but is a usability pressure on the [REDACTED] surface.

## Theme 5: Roadmap and Breaking-Change Planning (CONTEXT)

- **#2170 (Dec 2018, open, 21 comments):** "Plans for the future" —
  long-running roadmap discussion.
- **#3067 (Jan 2021, open):** "Suggestions for next major release
  breaking changes" — major-version planning. [REDACTED] was
  shipped in the v4.0.0 major bump and the README notes the only
  breaking change in that semver-major was the filesystem-access
  restriction itself: "This semver-major update does not introduce
  other breaking changes." This suggests the [REDACTED] fix was the trigger
  for the v4.0.0 release, not a coincidental bundled change.

## Theme 6: Build-Output / Distribution Stability (LOW RELEVANCE)

- **#3947 (Jan 2026, open):** "Link to CDN in README is 404" — minor.
- **#3933 (Dec 2025, open):** "request: Support compression for RGBA
  images" — feature request.
- **#3938 (Jan 2026, open):** "documentProperties" — API question.

These don't intersect the [REDACTED] surface; included for completeness so
the theme list is representative rather than cherry-picked.

## Invariants

- **INV-ISSUES-1 (html2canvas migration watch):** Any future migration
  from `html2canvas` to `html2canvas-pro` or any DOMPurify upgrade
  must preserve the `loadFile`-funneled resource resolution. A
  migration that introduces a new code path resolving HTML-embedded
  URLs without going through `nodeReadFile` re-opens the [REDACTED]
  surface for `html()`.
- **INV-ISSUES-2 (fontconverter as workflow nudge):** The recommended
  font-adding workflow (`fontconverter.html` → VFS) is broken at the
  tooling level (#3958). Adopters under deadline pressure may take
  the path-string shortcut through `addFont`. The library cannot
  prevent this, but the [REDACTED] gates in `nodeReadFile` must hold for
  this exact case.
- **INV-ISSUES-3 (sync-default matches `fs.readFileSync`):** The
  library's API defaults to synchronous loads in both builds. Any
  static-analysis rule looking only for async-callback paths into
  `fs` misses the dominant call shape. Patterns that match
  `fs.readFileSync` are required for completeness; patterns
  restricted to `fs.readFile` alone miss the primary attack surface.
- **INV-ISSUES-4 (separate from #3927):** The open issue #3927
  ("developer information disclosure") is NOT the [REDACTED] CVE. Detection
  patterns must not cross-trigger. The [REDACTED] is uniquely identified by
  [REDACTED] / [REDACTED] and the fix locus
  `src/modules/fileloading.js`.
