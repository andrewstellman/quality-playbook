# jsPDF — Known Issues and Security Advisories

## Sources

- https://github.com/parallax/jsPDF/security (advisory index, page 1)
- https://github.com/parallax/jsPDF/security?page=2 (page 2)
- https://github.com/parallax/jsPDF/security/advisories/[REDACTED] (the CVE in scope)
- https://github.com/parallax/jsPDF[REDACTED] (fix PR for the CVE in scope)
- https://github.com/parallax/jsPDF/blob/master/SECURITY.md
- https://github.com/parallax/jsPDF/blob/master/README.md

## Context

jsPDF has an unusually large published-advisory list for a PDF library —
12 advisories in the GitHub Security page as of June 2026, with a
sustained reporting cadence from researcher HackbrettXXX through 2025
and 2026. This concentration is signal: the library is large, old (10+
years, 2009-origin), and has many input paths that can carry attacker
content into the generated PDF or, in the Node build, into the runtime
process. QPB's [REDACTED] hunt should know about the wider context
in case detection patterns overlap with adjacent advisories.

## The In-Scope Advisory

### [REDACTED] — [REDACTED] / [REDACTED]

- **CVE ID:** [REDACTED]
- **Published:** January 3, 2026
- **Reporter:** kilkat (Kwangwoon Kim)
- **Severity:** Critical
- **CVSS v4:** 9.2 (`AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:N/VA:N/SC:H/SI:N/SA:N`)
- **Affected versions:** `<=3.0.4`
- **Patched version:** `>=4.0.0`
- **CWEs:** [REDACTED] ([REDACTED]: `.../...//`), [REDACTED] (External
  Control of File Name or Path)
- **Affected methods:** `loadFile`, `addImage`, `html`, `addFont`
- **Affected build:** Node.js builds only (`dist/jspdf.node.js`,
  `dist/jspdf.node.min.js`). Browser builds are not affected.

**Impact statement (verbatim from advisory):**
> "User control of the first argument of the loadFile method in the
> node.js build allows [REDACTED]/[REDACTED]. If given
> the possibility to pass unsanitized paths to the loadFile method, a
> user can retrieve file contents of arbitrary files in the local file
> system the node process is running in. The file contents are
> included verbatim in the generated PDFs."

**Example attack vector (verbatim):**
```js
import { jsPDF } from "./dist/jspdf.node.js";
const doc = new jsPDF();
doc.addImage("./secret.txt", "JPEG", 0, 0, 10, 10);
doc.save("test.pdf"); // the generated PDF will contain the "secret.txt" file
```

**Fix summary ([REDACTED], title "restrict [REDACTED] in node build"):**
- Add `[REDACTED]` property as fs read allow-list.
- Read files only if Node `--permission` flag is set OR `[REDACTED]`
  is configured.
- Resolve symlinks via `fs.[REDACTED]` before all permission checks.
- Throw with a guidance-rich error if neither permission system is
  active.
- Source file: `src/modules/fileloading.js`. Vulnerable parent SHA:
  `a504e973eeebac633351b41860945ca2a2cdf096`.

**Workarounds documented for adopters who cannot upgrade:**
- Recommended: `node --permission --allow-fs-read=...`
- Fallback for older Node: sanitise paths in calling code.

## Adjacent Advisories (CVE-context only — not in scope but useful for
overlap-detection)

Listed in reverse chronological order from the same Security page.
These are PDF-content / process-DoS issues, not [REDACTED], but they share the
attacker model of "untrusted input flowing into jsPDF APIs" and the
same reporter (HackbrettXXX is also the maintainer who shipped the
[REDACTED] fix).

| GHSA | Published | Severity | Class | Notes |
|------|-----------|----------|-------|-------|
| [REDACTED] | Mar 17, 2026 | Critical | HTML Injection in output methods | Injection through PDF output |
| [REDACTED] | Mar 17, 2026 | High | PDF Object Injection via free text annotation color | Annotation color string not escaped |
| [REDACTED] | Feb 19, 2026 | High | PDF Injection / Arbitrary JS in AcroForm (RadioButton) | AcroForm child elements |
| [REDACTED] | Feb 19, 2026 | High | Client-Side/Server-Side DoS via Malicious GIF Dimensions | Image decoder DoS |
| [REDACTED] | Feb 19, 2026 | Critical | PDF Object Injection via Unsanitised Input in addJS | `addJS` PDF action injection |
| [REDACTED] | Feb 2, 2026 | High | PDF Injection in AcroForm allows arbitrary JS | AcroForm form fields |
| [REDACTED] | Feb 2, 2026 | Moderate | Stored XMP Metadata Injection | Spoofing/integrity |
| [REDACTED] | Feb 2, 2026 | Moderate | Shared State Race Condition in addJS | Concurrency |
| [REDACTED] | Feb 2, 2026 | High | DoS via Unvalidated BMP Dimensions in BMPDecoder | Image decoder DoS |
| **[REDACTED]** | **Jan 3, 2026** | **Critical** | **[REDACTED] / [REDACTED]** | **THE TARGET** |
| [REDACTED] | Aug 26, 2025 | High | Denial of Service | Generic DoS |
| [REDACTED] | Mar 18, 2025 | High | Bypass Regular Expression DoS (ReDoS) | Regex catastrophic backtracking |

## What These Adjacent Advisories Tell Us About the Codebase

1. **Multiple "addX takes a string and trusts it" advisories.** `addJS`
   (`[REDACTED]`, `[REDACTED]`) and `addImage`
   (the [REDACTED]) share a pattern: an `addX(input, ...)` method takes a
   string and routes it somewhere security-sensitive without
   validation. This is a recurring shape — QPB invariants for
   string-to-sink flow apply broadly here.
2. **AcroForm and free-text annotation injection.** These are PDF
   object-string injection — the PDF spec allows breaking out of an
   embedded string into the document tree. Adjacent to but distinct
   from [REDACTED].
3. **Image-decoder DoS (BMP, GIF).** Indicates the image-handling code
   does not bound input dimensions or buffer allocations. Not the
   same class as [REDACTED] but uses the same `addImage` entry point — a
   reviewer touching `addImage` for [REDACTED] mitigation should be aware
   the same input lane has decoder bugs.
4. **ReDoS on regex code paths.** Suggests jsPDF uses regex-based
   parsing for some path-like content (PDF object parsing, perhaps);
   not directly relevant to filesystem [REDACTED].

## Active GitHub Issues with Security Adjacency

From https://github.com/parallax/jsPDF/issues (as of June 2026):

- **#3963** "DOMPurify contains a Cross-site Scripting vulnerability"
  (Mar 9, 2026, open) — dependency-vulnerability surfaced by adopters.
  DOMPurify is used by the `html()` method.
- **#3927** "security issue - developer information disclosure"
  (Dec 10, 2025, open, `no-issue-activity`) — unrelated to [REDACTED] from
  the title; appears to be about debug/development info exposure.

## Reporter and Maintainer Context

- **HackbrettXXX** publishes most of the recent advisories AND is a
  co-maintainer. The [REDACTED] advisory is credited to external
  researcher kilkat (Kwangwoon Kim) but published by HackbrettXXX,
  who also authored the fix PR.
- **yWorks GmbH** co-maintains jsPDF and ships the advisories from
  this account.
- **Reporting channel:** `SECURITY.md` directs reporters to the GitHub
  "Report a vulnerability" private-advisory flow.

## Invariants

- **INV-ADVISORY-1 (single-CVE focus):** [REDACTED] /
  [REDACTED] is the [REDACTED] advisory. Any "fix" claimed for jsPDF
  filesystem access must reference [REDACTED] or its successor and must
  appear in releases `>= 4.0.0`. Versions `<=3.0.4` are unfixable
  without the patch.
- **INV-ADVISORY-2 (Node-build-only scope):** The [REDACTED] is inherent to
  the Node build only. Static analysis that flags the browser build
  for the same pattern produces false positives.
- **INV-ADVISORY-3 (companion adjacent CVEs):** The presence of
  `addJS` and `addImage` object-injection advisories adjacent to the
  [REDACTED] tells reviewers that jsPDF's "addX takes a string" surface is
  collectively undertrusted historically. Any [REDACTED] fix that doesn't
  address the broader pattern is incomplete from a defence-in-depth
  perspective, but the specific [REDACTED] fix is correctly
  scoped to filesystem access only.
- **INV-ADVISORY-4 (fix locus stability):** The fix lives in
  `src/modules/fileloading.js`. A "fix" placed elsewhere (e.g., in
  `addimage.js` only) would be incomplete — `addFont`, `html`, and
  `loadFile` callers would remain vulnerable.
