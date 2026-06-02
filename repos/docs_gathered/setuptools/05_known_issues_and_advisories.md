# Known Issues and Advisories

## Sources

- GHSA-5rjg-fvgr-3xxf (CVE-2025-47273, this audit's focus):
  https://github.com/advisories/GHSA-5rjg-fvgr-3xxf
- Source advisory on the project:
  https://github.com/pypa/setuptools/security/advisories/GHSA-5rjg-fvgr-3xxf
- Tracking issue: https://github.com/pypa/setuptools/issues/4946
- Patch commit: https://github.com/pypa/setuptools/commit/250a6d17978f9f6ac3ac887091f2d32886fbbb0b
- NVD entry: https://nvd.nist.gov/vuln/detail/CVE-2025-47273
- PyPA advisory database entry:
  https://github.com/pypa/advisory-database/tree/main/vulns/setuptools/PYSEC-2025-49.yaml
- Huntr report (initial disclosure):
  https://huntr.com/bounties/d6362117-ad57-4e83-951f-b8141c6e7ca5
- Debian LTS announce: https://lists.debian.org/debian-lts-announce/2025/05/msg00035.html
- GHSA-cx63-2mw6-8hw5 (CVE-2024-6345 — prior RCE in same module):
  https://github.com/advisories/GHSA-cx63-2mw6-8hw5
- GHSA-r9hx-vwmv-q579 (CVE-2022-40897 — prior ReDoS in same module):
  https://github.com/advisories/GHSA-r9hx-vwmv-q579
- Listing of all advisories on the project:
  https://github.com/pypa/setuptools/security/advisories

## Context

setuptools' public advisory history contains exactly one open security
advisory at the time of audit (CVE-2025-47273), but the file
`setuptools/package_index.py` has been the locus of three CVEs in three
years. The pattern matters: each CVE found a new way to weaponize the
same internet-facing scraping/downloader code path, and each fix has
been local to the offending function rather than a structural change.
This is the relevant history for an audit because the QPB run should
expect to find a path-traversal-flavored bug in the same file.

## CVE-2025-47273 / GHSA-5rjg-fvgr-3xxf (THIS AUDIT'S TARGET)

| Field | Value |
|---|---|
| CVE | CVE-2025-47273 |
| GHSA | GHSA-5rjg-fvgr-3xxf |
| PYSEC | PYSEC-2025-49 |
| Title | "setuptools has a path traversal vulnerability in PackageIndex.download that leads to Arbitrary File Write" |
| Affected | setuptools < 78.1.1 |
| Patched in | 78.1.1 |
| CVSS v4 | 7.7 High (`AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:H/VA:N/SC:N/SI:N/SA:N`) |
| GHSA severity | Moderate (note: GHSA scored moderate, NVD/CVSS scored high) |
| EPSS | 0.18% (39th percentile, as of last refresh) |
| CWE | CWE-22 — Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal') |
| Reporter | SCH227 (via Huntr) |
| Published | May 17, 2025 by jaraco |
| Last updated | Jun 13, 2025 |
| Patch SHA | `250a6d17978f9f6ac3ac887091f2d32886fbbb0b` |
| Parent SHA (vulnerable) | `d8390feaa99091d1ba9626bec0e4ba7072fc507a` |
| File | `setuptools/package_index.py` |
| Function | `PackageIndex._resolve_download_filename` |
| Lines | 810–825 of `package_index.py` at the parent SHA |
| Issue | pypa/setuptools#4946 |

### Summary

Path traversal in the `package_index` download pipeline allows arbitrary
file write outside the caller's `tmpdir`. The function
`_resolve_download_filename` derives a download filename from a URL via
`egg_info_for_url`, replaces literal `..` with `.`, and then calls
`os.path.join(tmpdir, name)` without verifying the result remains inside
`tmpdir`.

### Why the sanitizer failed

Two independent reasons:

1. **`os.path.join` discards `tmpdir` when `name` is absolute.** A
   URL-encoded payload like
   `https://anyhost/%2fhome%2fuser%2f.ssh%2fauthorized_keys` produces a
   `name` of `/home/user/.ssh/authorized_keys` (absolute), which causes
   `os.path.join` to throw away `tmpdir`.
2. **The `..` replacement was the wrong defense.** The payload contains
   no `..`, so the `while '..' in name` loop is a no-op. Even with `..`
   present, the absolute-path footgun above would still apply.

### Fix

A startswith check on the constructed path, raising `ValueError` on
escape. Patch is 16 lines added, 2 lines removed, all in one static
method. Verbatim diff is in `02_package_index_contract.md`.

### Impact

CVSS scores integrity-high only — no confidentiality impact (this is a
write, not a read) and no availability impact (the process is not
DoS'd). The advisory description suggests the realistic escalation is
"depending on the context, RCE": writing into `~/.ssh/authorized_keys`,
`~/.bashrc`, a Python `site-packages` file that will be imported later,
a `crontab`, etc.

### Disclosure timeline

- Discovered/reported via Huntr (bounty d6362117-ad57-4e83-951f-b8141c6e7ca5).
- GitHub private advisory GHSA-5rjg-fvgr-3xxf opened.
- Patch committed 2025-04-19 (Jason R. Coombs).
- Public disclosure May 17, 2025 with setuptools 78.1.1 release.
- Debian LTS announcement May 2025.
- Backport question discussed in issue #4946 — see
  `06_issue_tracker_themes.md` for the backport-to-75.3.x discussion
  driven by virtualenv bundling.

### What this audit must detect

For QPB to pass on this target, it should:

1. Identify `_resolve_download_filename` (or equivalent function under a
   different name) as a path-derivation site.
2. Note that `os.path.join(tmpdir, name)` is used without a containment
   check.
3. Note that `name` is URL-derived through `egg_info_for_url`.
4. Either flag the `..` replacement as insufficient OR construct (or
   reference) a payload that bypasses it — the `%2f`-encoded absolute
   path payload is the canonical example.

## CVE-2024-6345 / GHSA-cx63-2mw6-8hw5 — prior precedent

| Field | Value |
|---|---|
| CVE | CVE-2024-6345 |
| GHSA | GHSA-cx63-2mw6-8hw5 |
| Title | "setuptools vulnerable to Command Injection via package URL" |
| Affected | setuptools < 70.0.0 |
| Patched in | 70.0.0 |
| CVSS v4 | 7.5 High |
| CWE | CWE-94 (Code Injection) |
| Fix commit | `88807c7062788254f654ea8c03427adc859321f0` |
| Fix PR | pypa/setuptools#4332 |

### Why it matters to this audit

CVE-2024-6345 is the precedent the CVE-2025-47273 advisory points at
("could be exploited in a similar fashion like GHSA-r9hx-vwmv-q579, and
as described by POC 4 in GHSA-cx63-2mw6-8hw5 report: via malicious URLs
present on the pages of a package index"). The same `package_index`
module, the same threat model (attacker-controlled URLs reaching
internal pipelines), the same maintainer fix pattern (a small local
defense added to a single function).

For QPB this is signal that the file `package_index.py` is a known
hotspot for URL-driven security bugs, and that the audit should treat
*every* URL-→-internal-string flow in that file as a candidate for
re-examination.

## CVE-2022-40897 / GHSA-r9hx-vwmv-q579 — earlier precedent

| Field | Value |
|---|---|
| CVE | CVE-2022-40897 |
| GHSA | GHSA-r9hx-vwmv-q579 |
| Title | "pypa/setuptools vulnerable to Regular Expression Denial of Service (ReDoS)" |
| Affected | setuptools < 65.5.1 |
| Patched in | 65.5.1 |
| CVSS v4 | 8.7 High |
| CWE | CWE-1333 (Inefficient Regular Expression Complexity) |
| Fix commit | `43a9c9bfa6aa626ec2a22540bea28d2ca77964be` |

### Why it matters to this audit

This is the third CVE in `package_index.py` and the longest-standing one.
It established that the HTML-parsing regexes in `package_index.py`
(`HREF`, `PYPI_MD5`, `REL`, `EGG_FRAGMENT`) are exposed to adversarial
input via PyPI pages. The CVE-2025-47273 advisory cites this CVE as the
template for "exploited via malicious HTML on a PyPI page."

## Other setuptools-flavored security history (context only)

- **CVE-2024-47081 / netrc credential leak** — affects `requests`, not
  setuptools directly, but the PyPI ecosystem context is the same.
- **PYSEC-2014-87 / CVE-2014-0474** — older `pkg_resources` symbolic
  link traversal in egg extraction. Same family of bug ("setuptools
  extracts archives that may escape their intended directory"), much
  older. Predates the current advisory database structure.

## Invariants (derived from the advisory history)

1. **`setuptools/package_index.py` has had three CVEs in three years.**
   The audit should treat it as the highest-risk file in the
   repository regardless of `easy_install`'s deprecation status.

2. **All three CVEs originate from URL-driven inputs reaching internal
   pipelines without sufficient sanitization.** The pattern is stable:
   a URL or HTML page from the network is parsed, and some
   substring/decoded fragment of it flows into an internal sink (regex
   complexity in 2022-40897, subprocess invocation in 2024-6345,
   filesystem write in 2025-47273).

3. **Fixes are surgical, not structural.** Each CVE has been patched by
   adding a defense local to the offending function. The maintainer has
   not yet attempted a wholesale rewrite or removal of
   `package_index.py` despite its deprecation.

4. **Security disclosure is via Huntr or Tidelift, not GitHub Issues.**
   The project's `SECURITY.md` and the advisory history both confirm
   this. Issue #4946 was opened as a placeholder ("Undisclosed security
   vulnerability") only after the patch had landed.

5. **Backports lag because of virtualenv bundling.** Issue #4946 has an
   active discussion about whether to backport the fix to setuptools
   75.3.x because virtualenv still bundles that version for Python 3.8
   support. This is signal that any audit assuming "vulnerable versions
   are all dead" is wrong — virtualenv-installed venvs may carry the
   vulnerable code well past the headline "fixed in 78.1.1" announcement.
