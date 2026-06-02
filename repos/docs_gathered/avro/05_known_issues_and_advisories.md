# 05 — Known Issues and Security Advisories

## Sources

- `https://github.com/advisories?query=avro` — GitHub Advisory Database, filtered to Avro-named packages (17 advisories returned).
- `https://github.com/advisories/GHSA-rp46-r563-jrc7` — CVE-2025-33042 (the audit target).
- `https://github.com/advisories/GHSA-r7pg-v2c8-mfg3` — CVE-2024-47561.
- `https://nvd.nist.gov/vuln/detail/CVE-2025-33042` — NVD record for the audit target.
- `https://avro.apache.org/project/security/` — Apache Avro Security Policy.
- `https://issues.apache.org/jira/browse/AVRO-4053` — Apache Jira ticket (title is misleadingly soft; see Section 03).
- `https://lists.apache.org/thread/fy88wmgf1lj9479vrpt12cv8x73lroj1` — the oss-security thread Apache cited for the CVE (referenced from the advisory; not fetched directly due to upstream timeout, but listed here as the canonical announcement).

## CVE-2025-33042 / AVRO-4053 (the audit target)

| Field | Value |
|---|---|
| CVE | CVE-2025-33042 |
| GHSA | GHSA-rp46-r563-jrc7 |
| Jira | AVRO-4053 |
| Pull Request | apache/avro#3150 |
| Vulnerable parent commit | `80400781a796bc0e90dd8ea1db42234926db33e9` |
| Fix commit | `84bc7322ca1c04ab4a8e4e708acf1e271541aac4` |
| Affected Maven coordinate | `org.apache.avro:avro-compiler` |
| Affected versions | All versions through 1.11.4 inclusive; 1.12.0 |
| Patched versions | 1.11.5, 1.12.1 |
| CWE | CWE-94 (Improper Control of Generation of Code / "Code Injection") |
| CVSS v4 base | 6.9 / Moderate. Vector: `AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:L/VA:N/SC:N/SI:N/SA:N` |
| EPSS | 0.057% (18th percentile) at time of publication |
| Published | 2026-02-13 to GHSA; 2026-02-12 to oss-security |
| Discovered by | levpachmanov (credited on the GHSA) |

### Verbatim advisory description

From `https://github.com/advisories/GHSA-rp46-r563-jrc7`:

> Improper Control of Generation of Code ('Code Injection') vulnerability in Apache Avro Java SDK when generating specific records from untrusted Avro schemas.
>
> This issue affects Apache Avro Java SDK: all versions through 1.11.4 and version 1.12.0.
>
> Users are recommended to upgrade to version 1.12.1 or 1.11.5, which fix the issue.

### What the patch does

(Detail in `02_codegen_contract.md` and `03_specific_compiler_pipeline.md`.) Three changes, all in `lang/java/compiler/`:

1. Adds `isValidAsAnnotation(String)` plus a `VALID_AS_ANNOTATION` `Pattern` constant to `SpecificCompiler.java`. Gates the `javaAnnotation` property.
2. Wraps every Velocity-template `doc` substitution in `$this.escapeForJavadoc(...)` across `enum.vm`, `fixed.vm`, `protocol.vm`, `record.vm`.
3. Renames `javaEscape` to `escapeForJavaString` (preserves `javaEscape` as a deprecated alias) and updates the three templates that embed schema JSON into `SCHEMA$`.

### Why the Jira title is misleading

AVRO-4053's Jira title reads "Improve doc consistency in SpecificRecord," not "Fix code injection in SpecificCompiler." The PR title (#3150) is similarly soft: "AVRO-4053: doc consistency in velocity templates." The CVE was assigned and disclosed about 16 months after the PR landed — the security framing arrived retrospectively. QPB should treat the AVRO-4053 Jira and PR pages as low-signal for security context; the GHSA and the commit diff are the high-signal sources.

### Reference links from the advisory

- `https://nvd.nist.gov/vuln/detail/CVE-2025-33042`
- `https://lists.apache.org/thread/fy88wmgf1lj9479vrpt12cv8x73lroj1`
- `http://www.openwall.com/lists/oss-security/2026/02/12/2`
- `https://github.com/apache/avro/pull/3150`
- `https://github.com/apache/avro/commit/84bc7322ca1c04ab4a8e4e708acf1e271541aac4`
- `https://issues.apache.org/jira/browse/AVRO-4053`
- `https://security.snyk.io/vuln/SNYK-JAVA-ORGAPACHEAVRO-15282783`

## Prior Avro CVEs (context, not the audit target)

These are the other Apache-Avro CVEs in the GitHub Advisory Database. Listed so QPB has the pattern history when distinguishing CVE-2025-33042 from look-alikes during a search:

| CVE | GHSA | Severity | Language | Summary |
|---|---|---|---|---|
| CVE-2024-47561 | GHSA-r7pg-v2c8-mfg3 | Critical (9.3) | Java | Schema parsing in `org.apache.avro:avro` < 1.11.4 allowed arbitrary code execution. CWE-502 (Deserialization of Untrusted Data). Linked to AVRO-3985. Fixed in 1.11.4 / 1.12.0. **Distinct from AVRO-4053**: this is at *parse time*, not codegen; it's in the runtime `avro` package, not `avro-compiler`. |
| CVE-2023-39410 | GHSA-rhrv-645h-fjfh | High | Java | `org.apache.avro:avro` "Improper Input Validation" — DoS via specially crafted schemas. |
| CVE-2021-43045 | GHSA-868x-rg4c-cjqg | High | C# | "Allocation of Resources Without Limits or Throttling" — DoS in the .NET implementation. |
| CVE-2022-35724 | GHSA-v456-chpw-6mmw | High | Rust | Reader looping endlessly, CPU exhaustion. |
| CVE-2022-36124 | GHSA-wcm8-86x6-8mv3 | High | Rust | Memory consumption beyond constraints. |
| CVE-2022-36125 | GHSA-3w5g-989p-35r8 | High | Rust | Corrupted-data crash. |

Two related Parquet advisories also surface in an "avro" search because the affected module is `parquet-avro`:

| CVE | GHSA | Severity | Notes |
|---|---|---|---|
| CVE-2025-30065 | GHSA-2c59-37c4-qrx5 | Critical | Parquet Avro module arbitrary code execution. |
| CVE-2025-46762 | GHSA-53wx-pr6q-m3j5 | High | Potential malicious code execution from trusted packages in `parquet-avro` when reading an Avro schema from Parquet file metadata. |

These are downstream of Avro's design but live in `org.apache.parquet:parquet-avro`, not `apache/avro`. They reinforce the theme: untrusted schema content is the recurring attack surface across the Avro ecosystem.

There are also several `iskorotkov/avro` (a Go fork) and `hamba/avro` (another Go library) advisories in the database. Those are not Apache Avro; QPB searches should filter to the `org.apache.avro:*` Maven group and `apache-avro` Rust crate to stay on-target.

## Apache Security Policy (relevant to disclosure expectations)

Apache Avro defers to the ASF security policy at `https://www.apache.org/security/`. The Avro-specific page (`https://avro.apache.org/project/security/`) summarizes the threat model (see Section 01). Disclosures are coordinated via `security@avro.apache.org`. The pattern visible in the AVRO-4053 timeline:

- Issue reported privately to security@.
- Patch lands as a normal PR with a non-alarming title (so as not to advertise the vulnerability while old versions are still in the wild).
- After downstream consumers have had time to upgrade, the CVE is assigned and the advisory is published.

This explains why grepping the AVRO-4053 Jira ticket for "CVE" returns nothing: the public ticket was never updated with the CVE designation. The link runs the other direction — the CVE references the Jira, not vice versa.

## Invariants

- The *only* Apache Avro Java SDK CVE in the codegen path (as of June 2026) is CVE-2025-33042 / AVRO-4053. All other Avro CVEs are either in the runtime parser, in a non-Java SDK, or in downstream `parquet-avro`.
- The fix landed in `lang/java/compiler/` exclusively. Any vulnerable copy of the code lives in that directory; no other Avro SDK or non-Java language binding is affected by this specific CVE.
- The patched versions are `1.11.5` (back-port to the 1.11.x line) and `1.12.1` (forward fix on the 1.12.x line). Any Maven coordinate `org.apache.avro:avro-compiler:[1.0,1.11.5)` or `org.apache.avro:avro-compiler:1.12.0` is vulnerable.
- Disclosure timeline: PR #3150 landed in late 2024 (the `meta-og:updated_time` on the commit page is 1728031796 = 2024-10-04); CVE-2025-33042 was published 2026-02-13. The gap means tools that key off the CVE date will miss vulnerable code that's been "fixed in main" for over a year.
