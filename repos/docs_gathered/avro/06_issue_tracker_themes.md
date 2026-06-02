# 06 — Issue Tracker Themes: Jira and GitHub

## Sources

- `https://issues.apache.org/jira/projects/AVRO/issues` — the canonical Apache Avro Jira (project key `AVRO`). Apache Avro uses Jira, not GitHub Issues, for its formal issue tracking.
- `https://issues.apache.org/jira/browse/[REDACTED]` — the audit-target ticket.
- `https://issues.apache.org/jira/browse/AVRO-3985` — the schema-parse-time arbitrary-code-execution ticket ([REDACTED]).
- `https://github.com/apache/avro/pulls` — the GitHub PR list (where Jira-tracked work lands as code).
- `https://github.com/apache/avro[REDACTED]` — [REDACTED] PR.
- `https://github.com/apache/avro/pull/2934` and `https://github.com/apache/avro/pull/2980` — AVRO-3985 PRs.

## How Tracking Works for Apache Avro

Apache Avro uses Apache Jira (project key `AVRO`) as the canonical issue tracker. GitHub Issues are open on `apache/avro` but are nearly always reflected back into Jira; the dev mailing list (`dev@avro.apache.org`) is the discussion channel. Pull requests on GitHub conventionally carry the Jira key as a prefix (`AVRO-XXXX: short description`), and the merging commit's message carries the same key. This means:

- Every issue mentioned below has both a Jira URL (`https://issues.apache.org/jira/browse/AVRO-XXXX`) and one or more GitHub PR URLs.
- The reverse-direction lookup — "for this commit, what's the Jira" — uses the `AVRO-XXXX` prefix in the commit message. The fix commit for our CVE (`[REDACTED]`) opens with `[REDACTED]: doc consistency in velocity templates`.

The Jira-issues page renders client-side and does not respond to a simple GET (the page body is empty without JavaScript). The themes below are reconstructed from the GitHub PR titles, commit log, security advisory cross-references, and the project's known historical focus areas as visible from the README and security policy.

## Theme 1 — Code generation safety (the cluster [REDACTED] sits in)

Tickets in this cluster touch `lang/java/compiler/` and the Velocity templates. They tend to read as Javadoc/cosmetic cleanups but several have security implications.

- **[REDACTED]** — the audit target. "Improve doc consistency in SpecificRecord." Landed as [REDACTED]; commit `[REDACTED]`. Adds `[REDACTED]`, escapes Javadoc, renames `javaEscape` -> `escapeForJavaString`.
- General pattern: each template family (`classic` is the only one currently shipped, but other vendors and internal forks have added their own) needs parallel escape-helper coverage. Anything added under `lang/java/compiler/src/main/velocity/.../templates/` without going through the central helpers is a regression risk.
- Related work: tickets that add `escapeForJavadoc` call sites incrementally (Section 02's table of `+/-` changes in `record.vm` shows fifteen distinct call sites needed; smaller follow-up fixes plug one-off omissions).

## Theme 2 — Schema-parse safety (the cluster [REDACTED] sits in)

Tickets in this cluster touch `lang/java/avro/`'s `Schema.Parser` and related classes. They are higher-severity on average than the codegen cluster, because parsing happens at runtime in production deployments.

- **AVRO-3985** — schema parsing in the Java SDK could be coerced into arbitrary code execution. Landed as PRs #2934 and #2980; commits `8f89868d` and `f6b3bd7e`. Fixed in 1.11.4 / 1.12.0. [REDACTED] (Critical, 9.3).
- Related earlier work: AVRO-3819 / [REDACTED] (improper input validation; DoS via crafted schemas).
- Pattern: schemas are JSON, and JSON parsing in Avro historically passed through Jackson with permissive settings (including, at points, polymorphic-type handling). Reining in the parser's exposure to the underlying JSON library is the recurring fix.

## Theme 3 — Cross-language test consistency

A non-trivial fraction of Avro Jira traffic is "the Java implementation does X but the Python/C/C++ implementation does Y" tickets. These are not directly security issues but they matter for QPB because they shape the trust model:

- A Java reader and a Python writer must agree on schema semantics, including how user properties are preserved/discarded.
- If the Java compiler accepts a schema and the Python runtime rejects it (or vice versa), downstream systems may end up handing schemas through Java codegen that Python's wire-encoder would have refused.
- The interop test suite under `share/test/` is the cross-language acceptance gate; tickets that strengthen it indirectly strengthen the security posture.

## Theme 4 — IDL parser features and quirks

The `.avdl` IDL has its own parser (Java; under `lang/java/compiler/src/main/javacc/`) and a long backlog of feature requests. The two security-relevant patterns:

- **IDL annotations forward arbitrary properties to the JSON schema.** This is by design — the IDL is meant to be a complete authoring surface for any Avro schema — but it means a sanitizer that lives only in the JSON parser will miss IDL-sourced payloads. The [REDACTED] fix (in `SpecificCompiler`, downstream of both parsers) handles this correctly.
- **Doc comments in IDL.** The IDL uses `/** ... */` syntax for doc strings, which then become `doc` fields in the generated JSON. An attacker who controls an IDL file controls those doc strings the same way as one who controls a JSON file. Same threat, same fix.

## Theme 5 — Dependency hygiene (Dependabot bumps)

A large fraction of merged PRs are dependabot updates to Maven, npm, NuGet, and pip dependencies. The bot is highly active (it's the top-contributor avatar on the repo). For QPB purposes:

- Avro itself ships transitive Jackson, SLF4J, Velocity, JavaCC dependencies. Each has had its own CVEs. Dependabot bumps keep these current.
- Velocity in particular matters here: the templates are rendered through Apache Velocity, and Velocity has historically had its own template-injection CVEs ([REDACTED] et al.). The Avro fix at `SpecificCompiler` doesn't depend on Velocity behaviour beyond `$variable` substitution, so Velocity CVEs are mostly orthogonal — but a downgrade of Velocity to a vulnerable version *could* re-introduce escape semantics changes.

## Theme 6 — Specific tickets that are easy to confuse with [REDACTED]

When QPB searches Jira/GitHub for [REDACTED] by string match, these are the false-positive candidates worth flagging:

- **AVRO-3985 / [REDACTED]** — the "other Avro Java SDK code execution" CVE. Schema parsing, not codegen.
- **[REDACTED] / [REDACTED]** — Parquet Avro module CVEs. Same year, same word in the title; downstream package.
- Doc-only PRs in the same window ([REDACTED] ships as a "doc consistency" PR, so neighbouring doc-cleanup PRs around the same dates look superficially similar).

The disambiguator is always the file path: [REDACTED]'s fix touches `lang/java/compiler/`. AVRO-3985's fix touches `lang/java/avro/`. The Parquet CVEs touch a different repo entirely (`apache/parquet-mr`).

## Invariants

- **Apache Jira is the canonical tracker.** Search Jira (project key `AVRO`) first for ticket-level context; GitHub PRs are the implementation record. The GitHub Issues tab is open but secondary.
- **PR titles begin with the Jira key.** `AVRO-XXXX: <description>`. This is the durable cross-reference even if Jira links rot. The fix commit for the audit target opens with `[REDACTED]: doc consistency in velocity templates`.
- **Vulnerable-codepath localization comes from the file path, not the ticket title.** [REDACTED]'s title is cosmetic; its file paths (under `lang/java/compiler/`) are the signal.
- **The dev mailing list at `lists.apache.org/list.html?dev@avro.apache.org`** carries discussion that doesn't make it into Jira. The CVE coordination thread `https://lists.apache.org/thread/fy88wmgf1lj9479vrpt12cv8x73lroj1` was cited from the GHSA — historically this is where security disclosures get announced even when the corresponding Jira ticket isn't updated with the CVE.
