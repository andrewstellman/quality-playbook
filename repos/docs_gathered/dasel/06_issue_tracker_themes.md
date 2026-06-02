# dasel — Issue Tracker Themes (DoS, Parser, Memory, Performance)

## Sources

- https://github.com/TomWright/dasel/issues
- https://api.github.com/search/issues?q=repo:TomWright/dasel+yaml+is:issue
- https://api.github.com/search/issues?q=repo:TomWright/dasel+memory+is:issue
- https://api.github.com/search/issues?q=repo:TomWright/dasel+security+is:issue
- https://api.github.com/search/issues?q=repo:TomWright/dasel+parser+is:issue
- https://api.github.com/search/issues?q=repo:TomWright/dasel+panic+is:issue

All searches retrieved 2026-06-01. Counts below are GitHub-search totals.

## Method

GitHub Issues search across the dasel repo by keyword (`yaml`, `memory`, `security`, `parser`, `panic`) plus `is:issue` for both open and closed. The intent: find recurring themes in user-reported behaviour that QPB's parser-bound checks should also catch.

## Theme 1 — YAML parser correctness on edge inputs (highest signal)

The `yaml` search returned 30 results. The recurring shape is "the YAML reader handled an unusual but valid YAML construct incorrectly":

- **#374** `[BUG] Dasel crash when reading an empty file` — closed. Empty input crashed the parser; should return null gracefully.
- **#451** `Parser drops everything after empty yaml doc` — closed. Multi-doc YAML where one document is empty caused the parser to terminate early. Same family as #374 (empty-document handling) and directly relevant to V-4 (per-document budget reset) because per-doc handling is exactly where bookkeeping resets need to be correct.
- **#526** `Incorrectly parsing 'null' in YAML` — closed. The literal string `null` vs the YAML `!!null` tag was conflated.
- **#525** `Failure to parse hexadecimal and octal numbers in YAML` — closed. YAML 1.2 hex/octal int parsing missing; the fix added the `parseYAMLInt` helper visible in current `yaml_reader.go`.
- **#484** `Timestamp-like strings get reformatted in YAML` — closed. Round-tripping coerced strings that looked like timestamps.
- **#400** `Empty string becoming null when modifying YAML` — closed. Round-trip discipline.
- **#327** `Int instead of string added to a document` — closed. Type-tag handling.
- **#270** `Validate doesn't correctly validate yaml files per the spec` — open.
- **#285** `YAML anchors, aliases and references` — open. **The most relevant pre-CVE issue**: a feature/correctness discussion of how dasel handles anchors and aliases. The pre-fix code's empty-counter pattern existed in this context; the CVE-2026-33320 fix was scoped narrowly to bounds, not to write-side alias preservation.
- **#452** `Avoid string type quote stripping in yaml` — open.
- **#437** `Emoji is changed to Unicode in yaml` — open.
- **#178** `Preserve comments when editing files` — open. Round-trip comment fidelity (separate from CVE scope).
- **#161** `Frontmatter Support` — open.

**Significance for QPB**: YAML is the format with the most active edge-case maintenance. The maintainer ships YAML-reader fixes regularly, which means the file (`parsing/yaml/yaml_reader.go`) is high-churn — a setting where a future refactor could accidentally weaken the post-CVE bounds. QPB's check for "does the YAML reader still enforce both `maxExpansionDepth` and `maxExpansionBudget`?" needs to be robust to legitimate edits in nearby code.

## Theme 2 — Crash and panic reports (parser robustness)

The `panic` search returned 11 results, all closed. These show a sustained history of dasel parsers being driven into panics by unusual input — exactly the class of behaviour V-10 ("Reader errors must be returned as errors, never as panics") targets:

- **#374** `[BUG] Dasel crash when reading an empty file` — closed.
- **#392** `Dasel query crashes with go panic` — closed.
- **#296** `Panic when converting JSON null values` — closed.
- **#191** `Panic when value in TOML is missing` — closed.
- **#99** `Dasel fails to parse a "null" yaml file` — closed.
- **#500** `Crash on empty CDATA` — closed (XML).
- **#282** `dasel put -t json -s 'array.[]' -v "{…}"` to a TOML file crashes dasel` — closed.
- **#526** `Incorrectly parsing 'null' in YAML` — closed.
- **#451** `Parser drops everything after empty yaml doc` — closed.
- **#327** `Int instead of string added to a document` — closed.
- **#133** `Merge` — closed.

**Pattern**: empty/null/edge inputs across every supported format have at some point produced a crash. The project has a real history of "unhardened parser path → user-supplied input crashes the process." The CVE-2026-33320 fix is the latest entry in this history but the first one classified as a security advisory.

**Significance for QPB**: a hunt looking for "places where adversarial input could crash or hang the parser" has a real, documented prior probability of finding something in this codebase. The current `parsing/json/json_reader.go` lacking an explicit depth cap (per `03_input_handling.md`) fits the same pattern as the panic bugs that needed fixing.

## Theme 3 — Memory and performance concerns

The `memory` search returned 9 results, all but one closed:

- **#460** `[V3] Directory Loading and Begin Implementing Lazy-Loading` — open. The only open memory-related issue. Lazy-loading would shift the memory profile of large-document handling.
- **#451**, **#526** — overlap with theme 1.
- **#364** `Output formatting is not right in some arrays` — closed.
- **#392** — overlap with theme 2.
- **#381**, **#131**, **#35**, **#196** — assorted memory-tangential issues.

**Significance**: there is no open issue that calls out unbounded YAML alias expansion as a memory concern. The CVE-2026-33320 advisory was filed privately rather than as a public issue (correct per `SECURITY.md`), so it would not appear in this list. But the absence of public DoS reports is consistent with the disclosure path the maintainer set up.

## Theme 4 — Parser/format correctness across non-YAML formats

The `parser` search returned 30 results spanning every format:

- **#509** `TOML parser does not support sub tables in arrays of tables` — closed.
- **#516** `[BUG] toml: keys containing dashes (-) can't be queried` — closed.
- **#534** `How to query XML attributes?` — closed.
- **#483** `ndjson support` — closed (NDJSON now handled by JSON reader).
- **#280** `XML array with one member is not detected as array` — open.
- **#406** `Compile builds with tinygo for reasonable system file sizes` — closed.
- **#312** `Support slice operator` — closed.
- **#279** `-w does not always default to read parser` — closed.
- **#387** `Is it possible to get a raw value, i.e. without quotes?` — closed.

**Significance**: parser-correctness churn touches every format. The YAML CVE is the loudest example, but TOML and XML parsers have had their own fixes that, in a less defensive code style, could just as easily have introduced a resource-exhaustion path.

## Theme 5 — Trust/security in the issue tracker proper

The `security` search returned only **2** issues (#541 and #44), neither of them actually about security — both use the word incidentally. This is consistent with `SECURITY.md`'s explicit policy that security reports go to private channels, not the issue tracker.

**Significance**: the public issue tracker is *not* the place to look for unreported vulnerabilities, because the maintainer routes them elsewhere. Counterintuitively, this means that for QPB's purposes, the *absence* of security-tagged issues should not be read as "no security concerns" — it should be read as "any security concerns went through the private path."

## Theme 6 — Anchors and aliases as a recurring topic (pre-CVE awareness)

Worth pulling out separately. **Issue #285** — `YAML anchors, aliases and references` — has been open for a long time and was the public discussion of how dasel handles YAML's anchor/alias machinery. The pre-fix code's no-bound `AliasNode` handling existed during this entire discussion. Neither the issue thread nor any linked PR before 2026-03-18 surfaced the resource-exhaustion implication; the discussion was scoped to read/write round-trip semantics (which the post-fix code addresses via `yaml-alias` metadata preservation).

**Significance**: this is a small reminder that "the feature has been discussed for years without a security issue being raised" is not evidence of safety. The CVE was found by a researcher (kq5y) looking specifically for the resource-exhaustion shape, not by anyone in the feature discussion.

## Summary of themes mapped to invariants

| Theme | Maps to invariant |
| --- | --- |
| 1. YAML edge-case churn | V-5 (bounds must hold across all input paths); V-12 (named constants survive refactors) |
| 2. Parser crash history | V-10 (errors not panics) |
| 3. Memory/performance | V-1, V-2, V-3 (the explicit DoS bounds) |
| 4. Cross-format parser correctness | V-INP-5, V-INP-6 (per-format bounds), V-SEC-1 |
| 5. Security-via-private-channel | Reinforces that V-1..V-12 audit must come from code, not from issue search |
| 6. Pre-CVE feature discussion | Reinforces that DoS shapes need specific looking-for, not generic "is the code clean" review |
