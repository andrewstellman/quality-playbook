> Quality Playbook v1.5.7 — Data Contract (`schemas.md`)
> Versioned with the playbook skill. Do not edit per-run.
>
> v1.5.7 reaffirms the v1.5.3 data contract; no record-shape changes since v1.5.3.
> Two v1.5.7 fixes reinforced existing rules via Phase 2/3 prompts (not new fields):
> - Q3 (commit `16c3214`): the §3.3 `severity` enum is MANDATORILY uppercase
>   (`HIGH` / `MEDIUM` / `LOW`). Phase 3 prompt + `phase2_generation_guide.md`
>   explicitly require it; the gate WARNs on case drift (auto-normalizes for
>   downstream invariant checks).
> - Q2 (commit `c017f89`): `FORMAL_DOC.role` (§3.6) and `BUG.divergence_type`
>   (§3.8) — both "conditional" per §3.10 — are now explicit mandates in the
>   Phase 2/3 prompts. `bin/reference_docs_ingest.py` emits
>   `role: "external-spec"` automatically; agents writing BUG records must
>   include `divergence_type` per §3.8. The gate WARN-vs-FAIL choice is
>   preserved (legacy back-compat); the prompt+ingest path is forward-only.

# Quality Playbook Data Schemas

This file defines the **static data contract** for every structured record the
Quality Playbook produces or consumes: `FORMAL_DOC`, `REQ`, `UC`, `BUG`, and the
embedded `citation` block, plus the enums that constrain their fields.

It ships alongside `SKILL.md` and is versioned with the playbook itself. It is
NOT generated per run. Two runs of the same playbook version against the same
project must agree on record shape — that invariance is what lets the quality
gate validate artifacts mechanically instead of asking an LLM whether the output
"looks right." Schema changes are breaking changes and must bump the playbook
minor version.

Protocols — *how* to produce and validate records at each phase — live inline in
`SKILL.md` where they are used. This file defines *what the records look like*,
nothing more. If you find yourself describing a process here, move it to
`SKILL.md`.

---

## 1. Scope and Design Notes

### 1.1 What `schemas.md` covers

- Record shapes for `FORMAL_DOC`, `REQ`, `UC`, `BUG`.
- The embedded `citation` block used by Tier 1/2 requirements.
- Enums: `tier`, `disposition`, `severity`, `fix_type`, `verdict`.
- The list of supported plaintext extensions for `reference_docs/` and
  `reference_docs/cite/`.

Plaintext inputs live under `reference_docs/` in the target repo. Files at
the top level are Tier 4 context — loaded into Phase 1 prompts as background
but not cited with byte-verification. Files under `reference_docs/cite/` are
citable sources — each produces a `FORMAL_DOC` record with a mechanical
`citation_excerpt` that `quality_gate.py` byte-verifies against the on-disk
bytes. Tier 1 is the default for `cite/` contents; files may override to
Tier 2 with an optional in-file marker on the first non-blank line:
`<!-- qpb-tier: 2 -->` (Markdown) or `# qpb-tier: 2` (plaintext). The Tier 1 /
Tier 2 distinction is internal to the playbook's authority hierarchy.

### 1.2 What `schemas.md` does NOT cover

- On-disk file layout, directory conventions, run archival policy — see the
  v1.5.1 design doc and `SKILL.md`.
- Phase-by-phase prompts or review protocols — `SKILL.md`.
- Gate check sequencing — `SKILL.md` and `quality_gate.py`.

### 1.3 Serialization format

The playbook maintains two parallel renderings of the same underlying records:

1. **Machine-readable JSON manifests** — canonical source of truth for the
   gate. Examples: `quality/formal_docs_manifest.json` (sourced from
   `reference_docs/cite/`),
   `quality/requirements_manifest.json`, `quality/use_cases_manifest.json`,
   `quality/bugs_manifest.json`. Validated field-by-field by
   `quality_gate.py` using stdlib `json` and explicit checks (no
   `jsonschema`). Each top-level manifest is a JSON object with the wrapper
   defined in §1.6.

2. **Human-readable markdown artifacts** — `quality/REQUIREMENTS.md`,
   `quality/USE_CASES.md`, `quality/BUGS.md`. Rendered from the manifests by
   the phase scripts so humans can read narrative prose with full context.
   The gate does NOT parse these markdown files structurally — they are
   presentation, the manifests are contract.

Both renderings MUST stay in sync. A phase script that writes to one without
updating the other is a bug.

### 1.4 Stdlib-only constraint

Every validator that consumes these records must run on stock Python 3 with no
`pip install` and no virtualenv — see the "Stdlib-Only Python" section of the
v1.5.1 design doc. Concretely: manifests are JSON (`json` module), hashes are
computed with `hashlib`, dates are ISO 8601 strings parsed with `datetime`. No
`PyYAML`, no `jsonschema`, no external HTTP. That rules out YAML frontmatter in
manifests even where it would read more nicely.

### 1.5 Field conventions

- Field names are `lower_snake_case`.
- Optional fields may be omitted from the JSON object OR present as JSON
  `null` — validators MUST accept both forms.
- Required fields must be present and non-null. Empty strings are not a valid
  substitute for `null`.
- Array fields default to `[]`, not `null`, when empty.
- All timestamps are ISO 8601 with explicit timezone. Prefer `Z` for UTC.
- Record IDs use fixed prefixes with a zero-padded sequence:
  - `REQ-NNN` (three digits, e.g. `REQ-017`)
  - `UC-NN` (two digits)
  - `BUG-NNN` (three digits)
  - `FORMAL_DOC` records have no synthetic ID — they are identified by
    `source_path` (see §4).

**Authoring guidance vs Layer-1 gate checks.** Some field descriptions in
this document include quality expectations like "imperative", "sufficient to
derive tests from", "direct quote or close paraphrase", or "patch-shaped."
Descriptions of that form are *authoring guidance* evaluated by the Phase 4
Council, not Layer-1 gate checks. Layer 1 only verifies non-emptiness and
type. Where a field carries such an expectation, the field table prefixes it
with "Authoring guidance (not gate-enforced):" to make the distinction
explicit.

### 1.6 Manifest wrapper

Every JSON manifest produced by the playbook (`formal_docs_manifest.json`,
`requirements_manifest.json`, `use_cases_manifest.json`,
`bugs_manifest.json`, `citation_semantic_check.json`) is a JSON object
whose top-level shape is fixed by this wrapper schema:

| Field            | Type            | Required | Notes                                                                           |
|------------------|-----------------|----------|---------------------------------------------------------------------------------|
| `schema_version` | string          | yes      | Semver string. MUST equal the playbook's `SKILL.md` `metadata.version`.         |
| `generated_at`   | string          | yes      | ISO 8601 timestamp with explicit timezone, e.g. `2026-04-19T14:30:22Z`.          |
| `records`        | array of object | yes      | Ordered list of records of the manifest's record type. `[]` is legal when empty.|

`citation_semantic_check.json` uses `reviews` in place of `records` — see
§9 for its shape. Every other manifest uses `records`.

Example:

```json
{
  "schema_version": "1.5.3",
  "generated_at": "2026-04-19T14:30:22Z",
  "records": []
}
```

---

## 2. Supported Plaintext Extensions

`reference_docs/` and `reference_docs/cite/` accept plaintext files only. This list is
authoritative; ingest rejects anything not listed.

| Extension | Notes                                                       |
|-----------|-------------------------------------------------------------|
| `.txt`    | Plain UTF-8 text. Preferred for spec excerpts from PDF.     |
| `.md`     | CommonMark-ish Markdown. Allowed for spec bodies and notes. |

Common extensions that are **deliberately excluded** and will fail ingest:

- `.pdf` — binary, no stdlib parser. Convert outside the playbook
  (`pdftotext virtio-v1.1.pdf virtio-v1.1.txt`) and commit the `.txt`.
- `.docx`, `.doc`, `.rtf` — office formats. Export to `.txt` or `.md`.
- `.html`, `.htm` — markup noise interferes with line-number citations. If
  HTML is the only source, run a text-mode converter (`pandoc -t plain`,
  `lynx -dump`) and commit the plaintext.
- `.odt`, `.epub`, and other formatted documents — same policy.

Extending the list: a benchmark project that legitimately needs another
plaintext format may propose it in a PR that (a) adds the extension here,
(b) updates `reference_docs_ingest.py` accordingly, and (c) adds a fixture
exercising it. Don't add extensions speculatively.

**Why this matters:** the citation gate reads the raw bytes of the plaintext
file and resolves `section`, `line`, and `page` references directly against
it. A binary or heavily-marked-up file would require a parser, and any
parser we ship pulls in a dependency or breaks the stdlib-only constraint.

---

## 3. Enums

Enum values are literals — string or integer per each enum's definition
below. String enums are case-sensitive; validators compare with `==`, not
`lower()`. Integer enums are compared numerically.

### 3.1 `tier` — authority of the source behind a requirement

| Value | Meaning                                                               |
|-------|-----------------------------------------------------------------------|
| `1`   | Project's own formal spec. Highest authority.                         |
| `2`   | External formal standard — RFC, W3C, ISO, published API contract, etc.|
| `3`   | Source-of-truth code when no formal spec exists; the code IS the spec.|
| `4`   | Informal documentation — AI chats, design notes, scratch writeups.    |
| `5`   | Inferred from code behavior with no documentation of any kind behind it.|

Stored as a JSON **integer** (`1`), not a string (`"1"`).

**Conflict rule.** When a Tier 1 claim and a Tier 2 claim contradict each other,
Tier 1 wins. A project's own documented deviation from an external standard is
authoritative intent, not a defect.

**Distribution is a metric, not a gate.** A project with 0 Tier 1/2
requirements is valid — the run degrades gracefully into a Spec Gap
Analyzer and the meta-finding "0 Tier 1/2 requirements" is reported.

### 3.2 `disposition` — how a BUG should be resolved

| Value                  | Meaning                                                                                   |
|------------------------|-------------------------------------------------------------------------------------------|
| `code-fix`             | The divergence is real and the code should change.                                        |
| `spec-fix`             | The divergence is real and the project's own spec (Tier 1) should change.                |
| `upstream-spec-issue`  | Divergence from an external spec (Tier 2) that is ambiguous or broken; code is defensible.|
| `mis-read`             | The playbook misread spec or code; no real divergence.                                    |
| `deferred`             | Known divergence, explicit decision to accept for now.                                    |

**`upstream-spec-issue` vs `spec-fix`.** `upstream-spec-issue` applies only
when the external (Tier 2) spec is the source of the problem AND the project
has not documented its own position. If the project's own spec (Tier 1)
already explains the deviation, there is no bug — Tier 1 wins. If the
project's spec is silent and the external spec is broken, that is
`upstream-spec-issue`, not `spec-fix` — the project shouldn't be asked to
fix an upstream body's document.

### 3.3 `severity` — impact rating on a BUG

| Value    | Meaning                                                                        |
|----------|--------------------------------------------------------------------------------|
| `HIGH`   | Correctness or security impact; data loss; visible user-facing failure.         |
| `MEDIUM` | Behavior diverges from spec but impact is contained; workaround exists.         |
| `LOW`    | Cosmetic, documentation-only, or a divergence with negligible observable effect.|

Uppercase literals. Validators reject `high`, `High`, etc.

### 3.4 `fix_type` — what surface the proposed fix touches on a BUG

| Value   | Meaning                                                          |
|---------|------------------------------------------------------------------|
| `code`  | Fix changes code only.                                           |
| `spec`  | Fix changes documentation only (project's own spec or upstream). |
| `both`  | Fix requires coordinated code and spec changes.                  |

**Legal combinations of `disposition` × `fix_type`.** The following matrix
is enforced by §10 invariant #12. `L` = legal, `—` = illegal.

| disposition \ fix_type | `code` | `spec` | `both` |
|------------------------|:------:|:------:|:------:|
| `code-fix`             |  L     |  —     |  L     |
| `spec-fix`             |  —     |  L     |  L     |
| `upstream-spec-issue`  |  —     |  L     |  L     |
| `mis-read`             |  L     |  L     |  —     |
| `deferred`             |  L     |  L     |  L     |

Illegal combinations, with rationale:

- `code-fix` × `spec` — if the fix is spec-only, the disposition is
  `spec-fix`, not `code-fix`.
- `spec-fix` × `code` — if the fix is code-only, the disposition is
  `code-fix`, not `spec-fix`.
- `upstream-spec-issue` × `code` — the project shouldn't patch external
  specs by changing its own code silently. Either document the deviation
  locally (`spec`) or do both (`both`).
- `mis-read` × `both` — a mis-read is not a shipped change. If something
  is shipping, the record is not a mis-read.

11 of the 15 combinations are legal. Validators reject the remaining 4.

### 3.5 `verdict` — per-REQ output of the Council-of-Three semantic citation check

| Value          | Meaning                                                                |
|----------------|------------------------------------------------------------------------|
| `supports`     | The `citation_excerpt` clearly supports the requirement as stated.     |
| `overreaches`  | The citation exists but the requirement claims more than the excerpt says. |
| `unclear`      | The reviewer cannot tell whether the excerpt supports the requirement. |

Used only in `quality/citation_semantic_check.json` (Phase 6). Gate fails if
a majority (≥2 of 3) Council members record `overreaches` for the same REQ.

### 3.6 `formal_doc_role` — origin of a `FORMAL_DOC` record (v1.5.3+)

Constrains `FORMAL_DOC.role` (see §4.1). Distinguishes external authoritative
specs from project-internal specs from the SKILL.md-as-its-own-formal-spec
case introduced for Skill and Hybrid projects in v1.5.3.

| Value             | Meaning                                                                                       |
|-------------------|-----------------------------------------------------------------------------------------------|
| `external-spec`   | RFC, IEEE standard, third-party authoritative spec. Tier 1 in code projects.                  |
| `project-spec`    | Internal design document or architecture spec authored by the project. Tier 1/2 in code projects. |
| `skill-self-spec` | `SKILL.md` itself, when the target is a Skill or Hybrid project. The skill is its own formal documentation. Tier 1. |
| `skill-reference` | A reference file (`references/*.md`) for a Skill or Hybrid project. Tier 2. Supporting material; SKILL.md wins on conflict — see §3.9. |

The `skill-self-spec` vs `skill-reference` distinction is what enables the
precedence rule in §3.9.

### 3.7 `req_source_type` — origin of a REQ record (v1.5.3+)

Constrains `REQ.source_type` (see §6.1). Indicates which class of input
produced the REQ.

| Value                  | Meaning                                                                                              |
|------------------------|------------------------------------------------------------------------------------------------------|
| `code-derived`         | REQ extracted from observable code behavior; the historical default for Code projects.               |
| `skill-section`        | REQ derived from a section of SKILL.md prose. Populates `REQ.skill_section`.                          |
| `reference-file`       | REQ derived from a QPB-shipped reference file (i.e., a file under `references/` such as `references/exploration_patterns.md`). |
| `docs-derived`         | v1.5.6+. REQ derived from operator-supplied informal documentation under the target repo's `reference_docs/` tree (Tier 4 context — AI chats, design notes, retrospectives — or Tier 1/2 citable material under `reference_docs/cite/`). Distinct from `reference-file`, which names QPB-shipped reference files; `docs-derived` names target-repo reference docs. |
| `execution-observation`| REQ inferred from observed run-time behavior captured in archived runs (Phase 5; reserved for forward-compat). |

### 3.8 `bug_divergence_type` — kind of divergence a BUG records (v1.5.3+)

Constrains `BUG.divergence_type` (see §8.1). Distinguishes the
v1.5.0-baseline code-vs-spec divergence from the three skill-specific
categories introduced by v1.5.3.

| Value             | Meaning                                                                                                  |
|-------------------|----------------------------------------------------------------------------------------------------------|
| `code-spec`       | Divergence between formal documentation (Tier 1/2 spec) and implementation. The historical default for Code projects. |
| `internal-prose`  | Within-prose contradiction in a skill (e.g., SKILL.md section X says "do Y," reference file Z contradicts X). |
| `prose-to-code`   | SKILL.md prose makes a claim about code behavior the code does not match (e.g., "the gate runs 45 checks" but `quality_gate.py` runs 43). |
| `execution`       | SKILL.md promise vs. observed behavior across archived runs (Phase 5; reserved for forward-compat).      |

### 3.9 SKILL.md vs reference-file precedence (v1.5.3+)

When a `FORMAL_DOC` with `role == "skill-self-spec"` (i.e., SKILL.md itself
on a Skill or Hybrid project) and a `FORMAL_DOC` with `role == "skill-reference"`
(a file under `references/`) make conflicting claims about the same
behavior, **SKILL.md wins.** Reference files are supporting material;
SKILL.md is the primary contract for the skill.

This rule resolves Open Question #3 in `QPB_v1.5.3_Design.md` (line 343-344);
v1.5.2 expressed it as a "lean," v1.5.3 settles it as the binding rule.

**Disposition consequence.** Phase 4's internal-divergence detection
(`BUG.divergence_type == "internal-prose"`) surfaces conflicts between
SKILL.md and a reference file. The precedence rule decides which side
gets which `disposition`:

- The reference-file claim is the side that diverges → its containing
  document gets `disposition: spec-fix`.
- The SKILL.md claim is authoritative → SKILL.md is not edited as part of
  resolving the conflict; the fix lands in the reference file.

**Worked example.** SKILL.md §"Phase 1" says "the explorer must produce
≥8 concrete findings." `references/exploration_patterns.md` says
"the explorer must produce ≥6 concrete findings." Phase 4 surfaces the
contradiction as a `BUG` with `divergence_type: internal-prose`. The
precedence rule pins `references/exploration_patterns.md` as the side to
fix (`disposition: spec-fix`, `fix_type: spec`); SKILL.md's "≥8" stands
unmodified. If the operator believes SKILL.md is wrong instead, the
explicit move is to edit SKILL.md first (a separate action), then re-derive
requirements; the precedence rule does NOT block such an edit, it just
constrains the default disposition the gate suggests when the conflict is
first surfaced.

This is additive prose — no existing field's type or required/optional
status changes — but it introduces precedence semantics for `disposition`
resolution on `internal-prose` BUGs.

### 3.10 v1.5.3 field-presence detection (v1.5.3+ shape signal)

Phase 2's new fields (`REQ.source_type`, `REQ.skill_section`,
`BUG.divergence_type`, `FORMAL_DOC.role`) become required when a manifest
is detected as **v1.5.3-shaped**. The trigger is **field presence**, not a
`schema_version` value comparison: if any record in a manifest has
`source_type`, `divergence_type`, or `role` populated, the validator
treats the entire manifest as v1.5.3-shaped and enforces every v1.5.3
invariant; otherwise the manifest is treated as legacy and the validator
emits a single soft warning per check function before skipping the
v1.5.3 invariants for that manifest.

This decouples the new-field requirement from §1.6's rule that
`schema_version` MUST equal SKILL.md `metadata.version` — `schema_version`
keeps mirroring the SKILL.md version unchanged, and adopters can begin
populating v1.5.3 fields against a v1.5.2-stamped skill without touching
the version coupling. Once a manifest carries any v1.5.3 field, all of
them are required on that manifest's record type — no half-populated
v1.5.3 manifests.

---

## 4. `FORMAL_DOC`

One record per plaintext document in `reference_docs/cite/`. Produced by
`reference_docs_ingest.py` (Phase 1). Stored in
`quality/formal_docs_manifest.json` (file name preserved for back-compat).

### 4.1 Fields

| Field             | Type    | Required | Notes                                                                 |
|-------------------|---------|----------|-----------------------------------------------------------------------|
| `source_path`     | string  | yes      | Repo-relative path, e.g. `reference_docs/cite/virtio-v1.1.txt`. Natural key.  |
| `document_sha256` | string  | yes      | Lowercase hex SHA-256 of the file's raw bytes. Computed at ingest.     |
| `tier`            | integer | yes      | `1` or `2` only. `3/4/5` have no `FORMAL_DOC` record by definition.    |
| `version`         | string  | no       | Human-readable version string, e.g. `"1.1"`, `"RFC 7230 §4"`.          |
| `date`            | string  | no       | Publication date, ISO 8601 `YYYY-MM-DD`.                               |
| `url`             | string  | no       | Canonical URL where the document was retrieved from.                   |
| `retrieved`       | string  | no       | Date the plaintext was captured, ISO 8601 `YYYY-MM-DD`. Important for specs that change under the same version label. |
| `bytes`           | integer | no       | File size in bytes at ingest. Diagnostic only; recomputed on each run. |
| `role`            | string  | conditional | v1.5.3+. Member of the `formal_doc_role` enum (§3.6). REQUIRED on every record in a v1.5.3-shaped manifest (any record carrying a v1.5.3 field — see §3.10); absent on legacy manifests, where the validator emits one WARN per check function and treats it as `external-spec` for back-compat. |

There is intentionally no `plaintext_path` field — per the Document Format
Policy, `source_path` IS the plaintext file.

### 4.2 Example

```json
{
  "source_path": "reference_docs/cite/virtio-v1.1.txt",
  "document_sha256": "a3f4c8e2b7d5f1a9c6b0e3d7f8a2c5b9d4e6f1a3c7b5d8e0f2a4c6b8d0e3f5a7",
  "tier": 1,
  "version": "1.1",
  "date": "2019-06-05",
  "url": "https://docs.oasis-open.org/virtio/virtio/v1.1/cs01/virtio-v1.1-cs01.pdf",
  "retrieved": "2026-04-15",
  "bytes": 481293
}
```

### 4.3 Common mistakes

- **Committing the original PDF and expecting ingest to parse it.** Ingest
  rejects non-text files with a message pointing at `pdftotext`. Run the
  conversion outside the playbook and commit the `.txt`.
- **Leaving `document_sha256` stale after re-saving the plaintext.** The
  hash is computed at ingest and compared to the hash embedded in every
  `citation.document_sha256`. On mismatch, the gate reports
  `citation_stale` for each affected citation in
  `quality_gate_report.json` and fails. `citation_stale` is a
  gate-report marker, not a field on the citation record itself.
  Re-ingest after any edit to a document under `reference_docs/cite/`.
- **Marking a Tier 3/4/5 source as a `FORMAL_DOC`.** Code (Tier 3) and
  informal notes (Tier 4/5) are not formal documents. They do not get
  `FORMAL_DOC` records and cannot be cited in a `citation` block.
- **Omitting `retrieved` for an external spec with a living URL.** When an
  external spec is updated silently under the same version label, the only
  evidence of what you actually cited is the `retrieved` date combined with
  the hash. Record it.

---

## 5. `citation` (embedded)

Embedded inside every Tier 1 and Tier 2 `REQ`. Populated by
`citation_verifier.py` at ingest — the `citation_excerpt` field is a
deterministic text slice from the referenced document, not LLM-generated
prose.

### 5.1 Fields

| Field               | Type   | Required | Notes                                                                  |
|---------------------|--------|----------|------------------------------------------------------------------------|
| `document`          | string | yes      | `FORMAL_DOC.source_path` being cited.                                  |
| `document_sha256`   | string | yes      | Copied from the `FORMAL_DOC` at ingest. Mismatch with the current `FORMAL_DOC.document_sha256` is reported as `citation_stale` in the gate report (not stored on the record — see §5.3). |
| `section`           | string | conditional | e.g. `"2.4"`. At least one of `section` or `line` MUST be present.  |
| `line`              | integer| conditional | 1-based line number in the plaintext file.                          |
| `page`              | integer| no       | Diagnostic-only pointer back to the original paginated source. Never a sufficient sole locator. |
| `version`           | string | no       | When present, MUST equal `FORMAL_DOC.version` (§10 invariant #16). Redundant with the FORMAL_DOC record; present for standalone readability. |
| `date`              | string | no       | When present, MUST equal `FORMAL_DOC.date`.                            |
| `url`               | string | no       | When present, MUST equal `FORMAL_DOC.url`.                             |
| `retrieved`         | string | no       | When present, MUST equal `FORMAL_DOC.retrieved`.                       |
| `citation_excerpt`  | string | yes      | Deterministic text slice at the cited location. Mechanically populated at ingest per §5.4; never LLM-authored. Byte-verified by the gate. |

**Locator rule.** At least one of `section` or `line` MUST be present and
MUST resolve in the plaintext document (per §5.4 and §5.5), or ingest fails
the REQ's validation and the REQ cannot be promoted to Tier 1 or Tier 2.
`page` is diagnostic-only and is ignored by the verifier.

### 5.2 Example

```json
{
  "document": "reference_docs/cite/virtio-v1.1.txt",
  "document_sha256": "a3f4c8e2b7d5f1a9c6b0e3d7f8a2c5b9d4e6f1a3c7b5d8e0f2a4c6b8d0e3f5a7",
  "version": "1.1",
  "date": "2019-06-05",
  "section": "2.4",
  "line": 142,
  "page": 34,
  "url": "https://docs.oasis-open.org/virtio/virtio/v1.1/cs01/virtio-v1.1-cs01.pdf",
  "retrieved": "2026-04-15",
  "citation_excerpt": "A device MUST reset itself when a VIRTIO_F_VERSION_1 feature bit negotiation fails, and MUST NOT accept further driver writes until RESET has completed."
}
```

### 5.3 Common mistakes

- **Allowing the LLM to author `citation_excerpt`.** The excerpt is a
  deterministic slice of the plaintext file, produced by
  `citation_verifier.py` per the algorithm in §5.4. The gate re-runs that
  extraction at verification time and requires the stored excerpt to be
  *byte-equal* to the freshly-extracted one (§10 invariant #11). A clean,
  paraphrased, or convenient excerpt will fail this check.
- **Citing a location that does not exist.** `section=2.4` in a document
  that has no §2.4, or `line=142` in a 50-line file, fails ingest. The REQ
  cannot be promoted to Tier 1/2.
- **Omitting both `section` and `line`.** A citation with only `document`
  (or only `page`) is not verifiable. Ingest rejects it. `page` alone is
  never sufficient.
- **Hand-editing `document_sha256` to match after swapping the source file.**
  Defeats citation-staleness detection. Always re-ingest instead. Note that
  `citation_stale` is a *gate-report marker*, not a field on the citation
  record — it surfaces in `quality_gate_report.json` when the stored
  `citation.document_sha256` diverges from the live
  `FORMAL_DOC.document_sha256`. The citation record itself is not mutated
  by the gate.
- **Using `page` in lieu of `line` for a plaintext-only source.** Plaintext
  has no pages. `page` is a diagnostic pointer back to the original PDF or
  paginated source and the verifier never reads it. Store a `section` or
  `line` locator alongside.
- **Letting `citation.version`/`date`/`url`/`retrieved` drift from the
  cited `FORMAL_DOC`.** The redundant metadata on the citation is a
  readability convenience. When any of those fields is present it MUST
  equal the corresponding `FORMAL_DOC` field (§10 invariant #16);
  mismatches fail the gate. Leaving them off entirely is legal; leaving
  stale copies in place is not.

### 5.4 Deterministic excerpt extraction algorithm

This is the exact, byte-deterministic procedure that `citation_verifier.py`
runs at ingest to populate `citation_excerpt`, and that `quality_gate.py`
re-runs at verification time to check byte-equality. Two implementations
that follow this algorithm MUST produce identical output on the same
`(document_bytes, section, line)` input.

**Inputs.** The raw bytes of the cited `FORMAL_DOC` (read by
`pathlib.Path.read_bytes()`), plus the locator `(section, line)` from the
citation record.

**Algorithm.**

1. Decode the document bytes as UTF-8 with `errors="strict"`. Ingest
   failure on decode error is expected — plaintext sources must be valid
   UTF-8. Ingest MAY reject common-case byte-order-mark bytes (`\ufeff`)
   at position 0 before decoding; it MUST NOT strip any other bytes.
2. Split the decoded text with `str.splitlines()` (no `keepends`). This
   normalizes `\r\n`, `\r`, and `\n` line endings to a terminator-free
   list of lines — the same list every implementation will see regardless
   of the file's original line-ending convention.
3. Determine the anchor line number `L` (1-based):
   - If `line` is present, `L = line`. If `section` is also present,
     ingest SHOULD cross-check that `section` resolves (per §5.5) to the
     same `L` and warn on mismatch; `line` is authoritative regardless.
   - Else if `section` is present, resolve `L` per §5.5. If resolution
     fails, extraction fails.
   - Else extraction fails (locator rule in §5.1).
4. Compute the window size `N`:
   - Start at index `k = L - 1` (0-based).
   - If `k >= len(lines)` or `lines[k].strip() == ""`, extraction fails
     (anchor is out of range or blank).
   - Walk forward: while `k < len(lines)` AND `lines[k].strip() != ""`
     AND `(k - (L - 1)) < 10`: increment `k`.
   - `N = k - (L - 1)`. N is in the range `[1, 10]`.
5. The excerpt is `"\n".join(lines[L - 1 : L - 1 + N])` — no leading or
   trailing whitespace stripped, no trailing newline appended. Joined with
   literal `"\n"` regardless of the document's original line-ending
   convention (consistency with step 2).

The window size is bounded at 10 lines so that large specifications do
not produce unbounded excerpts, and bounded by the first blank line so
that the excerpt stays within a single paragraph. If a requirement's
supporting text spans more than one paragraph, split it into multiple
REQs, each citing a single paragraph anchor.

### 5.5 Section resolution

When a citation provides `section` but no `line`, the extractor resolves
the section string to an anchor line `L` by matching the section against
each document line with a deterministic regex. The regex differs by the
cited document's file extension:

**Markdown sources (`.md`).** For section string `S`:

```
^#{1,6}[ \t]+<re.escape(S)>(?:[ \t]|$)
```

This matches ATX-style headings (`# 2.4`, `## 2.4 Device reset`, up through
`######`). The regex is applied to each raw line (no stripping). The first
line that matches is the anchor; `L` is that line's 1-based index.

**Plaintext sources (`.txt`).** For section string `S`:

```
^<re.escape(S)>(?:[ \t]|$)
```

Applied to each line after `lstrip()` (removing leading whitespace only).
The first line whose left-stripped content matches is the anchor.

**Resolution rules.**

- Matching uses `re.search` / `re.match` from the stdlib `re` module;
  `re.escape(S)` is used to make section identifiers like `"2.4"` and
  `"A.2-bis"` safe to embed in the regex.
- Exactly zero matches → resolution fails; ingest and the gate both
  reject the citation.
- Exactly one match → that line is `L`.
- Two or more matches → resolution fails (ambiguous section identifier).
  The fix is either a more specific section string (e.g. `"2.4.1"`
  instead of `"2.4"`) or adding an explicit `line` locator to
  disambiguate.

No other resolution strategies are permitted. Headings in formats not on
the supported-extensions list (§2) are by construction out of scope.

---

## 6. `REQ`

A requirement record — one claim about what the system is supposed to do,
anchored at a specific tier. Stored in
`quality/requirements_manifest.json`; rendered to
`quality/REQUIREMENTS.md`.

### 6.1 Fields

| Field                 | Type       | Required | Notes                                                                      |
|-----------------------|------------|----------|----------------------------------------------------------------------------|
| `id`                  | string     | yes      | `REQ-NNN` with zero-padded three-digit sequence.                            |
| `title`               | string     | yes      | Short, one-line. Authoring guidance (not gate-enforced): imperative form.   |
| `description`         | string     | yes      | Prose explanation of the requirement. Authoring guidance (not gate-enforced): sufficient to derive tests from. |
| `tier`                | integer    | yes      | Member of `tier` enum.                                                      |
| `functional_section`  | string     | yes      | LLM-derived grouping (e.g. `"Authentication"`, `"Bus enumeration"`). Reviewed by Council in Phase 4. |
| `citation`            | object     | conditional | Required if `tier in {1,2}`; must be absent or `null` if `tier in {3,4,5}`. Shape: §5. |
| `use_cases`           | array      | no       | List of `UC-NN` IDs this REQ participates in. One-way forward link; `[]` when none. Values MUST be unique (§10 invariant #18). |
| `pattern`             | string     | no       | If present, one of `whitelist`, `parity`, `compensation`. Marks the REQ as requiring a Phase 3 compensation grid (Lever 2). Missing → no grid required. Invalid value → gate fails. |
| `source_type`         | string     | conditional | v1.5.3+. Member of the `req_source_type` enum (§3.7). REQUIRED on every REQ in a v1.5.3-shaped manifest (any record carrying a v1.5.3 field — see §3.10); absent on legacy manifests, where the validator emits one WARN per check function and treats it as `code-derived` for back-compat. |
| `skill_section`       | string     | conditional | v1.5.3+. Heading text from SKILL.md (e.g. `"Phase 1: Explore the Codebase"`); a reader should be able to grep SKILL.md for the heading and find it. REQUIRED non-empty when `source_type == "skill-section"`. MUST be absent or `null` when `source_type` is any other value (§10 invariant #21). |

### Pattern tags and Phase 3 grids

When a REQ's `pattern` field is set, Phase 3 MUST produce a compensation grid
for that REQ (see §Phase 3 prompt contract). The grid enumerates
(authoritative item × site) cells. Each cell becomes either a BUG entry with
`Covers:` citing the cell ID, or a structured downgrade record in
`quality/compensation_grid_downgrades.json`. The Phase 5 cardinality gate
hard-fails on any uncovered cell.

Grid cell shape: every cell carries `cell_id`, `item`, `site`, and `present`
(boolean). Cells where `present` is `true` MUST additionally carry an
`evidence` field: a non-empty string in `<relative-path>:<line>` or
`<relative-path>:<line-start>-<line-end>` form. Absent/empty/malformed
`evidence` on a `present:true` cell fails the cardinality gate. This closes
the C13.6/B2 bypass where a reviewer could claim a cell was present without
supplying any anchor for the claim.

Valid `pattern` values:

- `whitelist` — authoritative list of items (e.g. feature bits, syscalls)
  that every site must handle.
- `parity` — symmetric operations that must match (encode↔decode,
  setup↔teardown).
- `compensation` — sites that must compensate for a shared gap in a common
  mechanism (shared filter, shared validator).

REQ records do not carry a `disposition` field. Disposition information is
authoritative on `BUG` records; aggregate disposition per REQ is computed
at render time by the phase script from `bugs_manifest.json` and shown in
`REQUIREMENTS.md` as presentation only.

### 6.2 Examples

**Tier 1 REQ (project's own spec):**

```json
{
  "id": "REQ-017",
  "title": "Device reset on failed feature negotiation",
  "description": "When VIRTIO_F_VERSION_1 negotiation fails, the device must reset itself and reject subsequent driver writes until the reset completes.",
  "tier": 1,
  "functional_section": "Device initialization",
  "citation": {
    "document": "reference_docs/cite/virtio-v1.1.txt",
    "document_sha256": "a3f4c8e2b7d5f1a9c6b0e3d7f8a2c5b9d4e6f1a3c7b5d8e0f2a4c6b8d0e3f5a7",
    "version": "1.1",
    "section": "2.4",
    "line": 142,
    "citation_excerpt": "A device MUST reset itself when a VIRTIO_F_VERSION_1 feature bit negotiation fails, and MUST NOT accept further driver writes until RESET has completed."
  },
  "use_cases": ["UC-03", "UC-05"]
}
```

**Tier 3 REQ (code is the authority, no formal doc):**

```json
{
  "id": "REQ-042",
  "title": "Non-zero exit code on missing SKILL.md",
  "description": "run_playbook exits non-zero when the target repo has no SKILL.md at any of the four documented install paths.",
  "tier": 3,
  "functional_section": "CLI entry points",
  "use_cases": ["UC-01"]
}
```

Note the Tier 3 record has **no** `citation` field. The locator for a Tier 3
requirement is source code and is recorded in the prose `description`, not
in a structured citation. A `citation` on a Tier 3 REQ is a validation
error — citations are only legal when the authority is a FORMAL_DOC.

### 6.3 Common mistakes

- **Tier 1/2 without a citation.** Fails Layer 1 of the hallucination gate.
  If you can't cite it, it's at most Tier 3.
- **Tier 3/4/5 with a citation.** Citation is for `FORMAL_DOC` references
  only. Code snippets and file paths belong in `description`, not
  `citation`. Validators reject citation blocks on non-Tier-1/2 REQs.
- **Promoting a REQ to Tier 1 because it "feels authoritative."** Tier 1 is
  mechanical: a `FORMAL_DOC` record with `tier=1` backs the citation. No
  backing doc, no Tier 1.
- **Letting the LLM write `functional_section` as a near-duplicate of
  `title`.** The section is a grouping across many REQs; if each section has
  one REQ, the grouping does nothing. Phase 4 Council catches this.
- **Back-filling `use_cases` from a UC's REQ list.** Traceability is one-way,
  REQ → UC. Populate this list when the REQ is derived, not retroactively
  from UC records.
- **Adding a `disposition` field to a REQ record.** There is no such field
  on the REQ record. Dispositions live on `BUG` records; aggregate
  disposition per REQ is rendered at presentation time from
  `bugs_manifest.json`.

---

## 7. `UC`

A use case record — an end-to-end scenario from an actor's point of view.
Stored in `quality/use_cases_manifest.json`; rendered to
`quality/USE_CASES.md`.

### 7.1 Fields

| Field              | Type           | Required | Notes                                                                |
|--------------------|----------------|----------|----------------------------------------------------------------------|
| `id`               | string         | yes      | `UC-NN` with zero-padded two-digit sequence.                          |
| `title`            | string         | yes      | Short, one-line statement of the scenario.                            |
| `description`      | string         | yes      | Prose describing actor, goal, preconditions, flow, and acceptance.    |
| `actors`           | array of string| yes      | At least one actor name. Human or system roles (e.g. `"Benchmark operator"`, `"AI agent"`). |
| `steps`            | array of string| yes      | Ordered flow steps. At least one.                                     |
| `formal_doc_refs`  | array of string| no       | `FORMAL_DOC.source_path` values that back this UC. `[]` when none. Values MUST be unique (§10 invariant #18). |

Note: there is no explicit `requirements[]` field on `UC`. Traceability is
**one-way**, REQ → UC. The UC → REQ direction is derived by querying REQ
records by their `use_cases` field, not persisted.

### 7.2 Example

```json
{
  "id": "UC-03",
  "title": "Benchmark operator compares multiple AI agents against the same target",
  "description": "A researcher replicating published benchmark numbers runs the playbook against the same target repo with different AI agents and compares bug yield.",
  "actors": ["Benchmark operator", "AI agent"],
  "steps": [
    "Operator runs bin/run_playbook.py <target> --agent claude",
    "Operator runs bin/run_playbook.py <target> --agent copilot",
    "Harness produces two parallel quality/ trees, one per agent",
    "Operator diffs BUGS.md and quality_gate verdicts across runs"
  ],
  "formal_doc_refs": []
}
```

### 7.3 Common mistakes

- **Steps that describe code internals.** UC steps describe what the actor
  does and what the system visibly does in response, not function call
  chains. If a step reads like a stack trace, it belongs in a REQ or an
  exploration note, not a UC.
- **Single-actor scenarios with no trigger.** Every UC has at least one
  actor and one trigger step. A UC with empty `actors` or `steps` is a
  validation error.
- **Filling `formal_doc_refs` with documents the UC doesn't actually
  depend on.** Only list documents whose content meaningfully shapes the
  scenario. Speculative references inflate the trace graph without adding
  evidence.
- **Using UC as a place to park REQ back-links.** The REQ → UC link lives
  on the REQ. The UC record stays clean.

---

## 8. `BUG`

A defect record — a specific divergence between documented intent (REQ) and
code behavior. Stored in `quality/bugs_manifest.json`; rendered to
`quality/BUGS.md` and `quality/writeups/BUG-NNN.md`.

### 8.1 Fields

| Field                    | Type    | Required | Notes                                                               |
|--------------------------|---------|----------|---------------------------------------------------------------------|
| `id`                     | string  | yes      | `BUG-NNN` zero-padded three-digit sequence.                          |
| `title`                  | string  | yes      | Short statement of the divergence. Authoring guidance (not gate-enforced): observation, not a value judgment. |
| `severity`               | string  | yes      | Member of `severity` enum.                                           |
| `divergence_description` | string  | yes      | Summary of what diverges from what. Authoring guidance (not gate-enforced): one paragraph. |
| `documented_intent`      | string  | yes      | The REQ / spec language for the intent side of the divergence. Authoring guidance (not gate-enforced): direct quote or close paraphrase. |
| `code_behavior`          | string  | yes      | What the code actually does. Authoring guidance (not gate-enforced): include file:line references. |
| `disposition`            | string  | yes      | Member of `disposition` enum.                                        |
| `disposition_rationale`  | string  | yes      | Explanation of why this disposition, not an adjacent one. Authoring guidance (not gate-enforced): one paragraph. |
| `req_id`                 | string  | yes      | The primary REQ that revealed the divergence (`REQ-NNN`). Singular. |
| `proposed_fix`           | string  | conditional | Required unless `disposition == "mis-read"`. When `disposition == "mis-read"`, the field is optional and — when present — documents the re-read (what the playbook mis-read and how the correct reading was established), not a shipped fix. Authoring guidance (not gate-enforced): patch-shaped when `fix_type` includes `code`, textual redline when `spec`. |
| `fix_type`               | string  | yes      | Member of `fix_type` enum. Combination with `disposition` constrained by §3.4 / §10 invariant #12. |
| `covers`                    | array[string] | no | Array of cell IDs this BUG addresses, form `REQ-N/cell-<item>-<site>`. REQUIRED when the BUG's primary requirement has `pattern:` set. |
| `consolidation_rationale`   | string        | no | REQUIRED when `covers` has ≥2 entries. Explains why cells share a BUG (shared fix path, same function, etc.). Non-empty. |
| `divergence_type`           | string        | conditional | v1.5.3+. Member of the `bug_divergence_type` enum (§3.8). REQUIRED on every BUG in a v1.5.3-shaped manifest (any record carrying a v1.5.3 field — see §3.10); absent on legacy manifests, where the validator emits one WARN per check function and treats it as `code-spec` for back-compat. |

### Cell-identity invariants

For any BUG whose primary requirement carries `pattern:`, the following
invariants are gate-enforced:

1. `covers` MUST be present and MUST be non-empty.
2. Every cell ID in `covers` MUST match the form `REQ-N/cell-<item>-<site>`.
3. Every cell ID in `covers` MUST appear in the Phase 3 grid for that REQ.
4. When `covers` has ≥2 entries, `consolidation_rationale` MUST be present
   with non-empty text.
5. The union of `covers` across all BUGs for a pattern-tagged REQ, combined
   with the cell IDs in `quality/compensation_grid_downgrades.json`, MUST
   equal the cell set from the Phase 3 grid. Uncovered cells fail the Phase
   5 cardinality gate.

The choice of singular `req_id` (not `req_ids[]`) is deliberate: every bug has
one primary REQ that frames the divergence. If a bug appears to touch multiple
REQs, either (a) the REQs are duplicates and should be merged, or (b) there are
several bugs, one per REQ, sharing a common root cause — file them separately
and cross-link in `disposition_rationale`.

### 8.2 Examples

**`code-fix` bug:**

```json
{
  "id": "BUG-017",
  "title": "Device does not reset on failed VERSION_1 negotiation",
  "severity": "HIGH",
  "divergence_description": "The virtio spec requires a device reset when VIRTIO_F_VERSION_1 negotiation fails; the driver silently proceeds with legacy behavior instead.",
  "documented_intent": "virtio 1.1 §2.4: 'A device MUST reset itself when a VIRTIO_F_VERSION_1 feature bit negotiation fails...'",
  "code_behavior": "src/virtio/init.c:312 — feature_negotiate() returns ENOTSUP on VERSION_1 failure, and the caller (init_device() at src/virtio/init.c:96) treats ENOTSUP as 'fall back to legacy' without invoking device_reset().",
  "disposition": "code-fix",
  "disposition_rationale": "Tier 1 spec is unambiguous (MUST). No project-level documentation of a deviation. Code is wrong.",
  "req_id": "REQ-017",
  "proposed_fix": "In init_device() at src/virtio/init.c:96, before the legacy fallback, invoke device_reset() and block on reset completion. See quality/patches/BUG-017-fix.patch.",
  "fix_type": "code"
}
```

**`upstream-spec-issue` bug:**

```json
{
  "id": "BUG-042",
  "title": "Chunked encoding trailer handling ambiguous in RFC 7230",
  "severity": "LOW",
  "divergence_description": "RFC 7230 §4.1.2 does not define behavior when a trailer field name duplicates a header field name. The implementation drops the trailer silently; other implementations merge.",
  "documented_intent": "RFC 7230 §4.1.2: 'A sender MUST NOT generate a trailer that contains a field necessary for...'",
  "code_behavior": "src/http/trailer.c:88 — drops trailers whose name collides with any prior header.",
  "disposition": "upstream-spec-issue",
  "disposition_rationale": "The external spec (Tier 2) does not resolve the collision case. The project's own spec (Tier 1) is silent. The behavior is defensible but should be documented locally rather than treated as a project defect.",
  "req_id": "REQ-089",
  "proposed_fix": "Add a paragraph to docs/http-trailers.md pinning the drop-on-collision behavior as our documented deviation; no code change.",
  "fix_type": "spec"
}
```

### 8.3 Common mistakes

- **Writing `title` as a value judgment.** `"Sloppy trailer handling"` is
  a critique; `"Trailers dropped when name collides with header"` is a
  divergence statement. Bugs are observations, not accusations.
- **Blurring `documented_intent` and `code_behavior`.** The two fields are
  deliberately separate so the reader can read them as a side-by-side diff.
  If `documented_intent` contains speculation about what the spec "seems to
  mean," the bug is not ready to file — go re-read the spec.
- **Setting `disposition=code-fix` without citing a REQ that backs the
  "documented intent."** Divergence requires two sides. If there is no REQ
  for the intent side, you have an exploration finding, not a bug.
- **`disposition=spec-fix` when the project has no formal spec (Tier 0
  documentation posture).** There's nothing to fix. Most of these are
  `code-fix` against a Tier 3/5 REQ or a `mis-read`.
- **`disposition=upstream-spec-issue` when the project's own Tier 1 spec
  explicitly documents the deviation.** Tier 1 wins over Tier 2. If the
  project already says "we deviate from RFC X for reason Y," there is no
  bug at all — close it as `mis-read`.
- **Empty or formulaic `disposition_rationale`.** "Code is wrong because
  spec says so" is not a rationale. The rationale explains why THIS
  disposition and not an adjacent one (code-fix vs spec-fix, or spec-fix
  vs upstream-spec-issue).
- **Multiple `req_id`s smuggled into a single BUG.** Split into one bug
  per REQ, share the underlying diagnosis in the writeup.
- **`fix_type=code` but `proposed_fix` is a paragraph of rationale with no
  patch.** The patch lives in `quality/patches/BUG-NNN-fix.patch`; the
  `proposed_fix` field references it and summarizes the change.
- **`disposition=mis-read` with a shipped fix in `proposed_fix`.** A
  mis-read means no divergence exists and nothing ships. If `proposed_fix`
  is present on a mis-read record, it documents the re-read itself (what
  was misread and how the correct reading was established), not a code or
  spec change. A mis-read record with `fix_type=both` is rejected outright
  (§3.4 legal-combination matrix).
- **Picking an illegal `disposition` × `fix_type` combination.** The gate
  rejects `code-fix`+`spec`, `spec-fix`+`code`, `upstream-spec-issue`+`code`,
  and `mis-read`+`both`. Consult §3.4 before authoring the record.

---

## 9. `citation_semantic_check.json`

Output of the Phase 6 Council-of-Three semantic citation check. One file
per run, stored at `quality/citation_semantic_check.json`. Consumed by
`quality_gate.py` to enforce §10 invariant #17.

### 9.1 Wrapper

Uses the §1.6 manifest wrapper, except the record array is named `reviews`
instead of `records`:

| Field            | Type            | Required | Notes                                                                   |
|------------------|-----------------|----------|-------------------------------------------------------------------------|
| `schema_version` | string          | yes      | MUST equal the playbook's `SKILL.md` `metadata.version`.                 |
| `generated_at`   | string          | yes      | ISO 8601 timestamp with explicit timezone.                               |
| `reviews`        | array of object | yes      | One entry per (Tier 1/2 REQ, council member) pair. See §9.2 for shape.  |

### 9.2 Review entry

| Field      | Type   | Required | Notes                                                                  |
|------------|--------|----------|------------------------------------------------------------------------|
| `req_id`   | string | yes      | `REQ-NNN` matching an existing REQ in `requirements_manifest.json`. The REQ MUST have `tier ∈ {1, 2}`. |
| `reviewer` | string | yes      | Identifier of the council member, e.g. `"claude-opus-4.7"`, `"gpt-5.5"`, `"claude-sonnet-4.6"`. Free-form but stable across entries from the same reviewer. The canonical roster lives at `bin/council_config.DEFAULT_COUNCIL_MEMBERS`. |
| `verdict`  | string | yes      | Member of the `verdict` enum (§3.5).                                   |
| `notes`    | string | yes      | Reviewer's reasoning for the verdict. May be empty string. Not gate-enforced for content. |

### 9.3 Example

```json
{
  "schema_version": "1.5.3",
  "generated_at": "2026-04-19T14:30:22Z",
  "reviews": [
    {
      "req_id": "REQ-017",
      "reviewer": "claude-opus-4.7",
      "verdict": "supports",
      "notes": "Excerpt directly states the MUST reset requirement and the no-further-writes precondition."
    },
    {
      "req_id": "REQ-017",
      "reviewer": "gpt-5.5",
      "verdict": "supports",
      "notes": "Clear match."
    },
    {
      "req_id": "REQ-017",
      "reviewer": "claude-sonnet-4.6",
      "verdict": "supports",
      "notes": ""
    }
  ]
}
```

### 9.4 Common mistakes

- **Missing reviews for a Tier 1/2 REQ.** Every Tier 1/2 REQ MUST have at
  least three review entries (one per council member). Ingest must
  produce them; absence is a gate failure.
- **Including reviews for Tier 3/4/5 REQs.** The semantic check applies
  only to REQs whose citations can be verified. Non-Tier-1/2 REQs have no
  `citation` field, so there is nothing to assess.
- **Inconsistent `reviewer` identifiers.** Use the same string for the
  same council member across all of their reviews in the file — the
  majority computation in §10 invariant #17 is performed by grouping on
  `reviewer`.

---

## 10. Cross-Record Invariants

These invariants span multiple records. The quality gate enforces them at
Layer 1 (mechanical checks):

1. **Citation tier gating.** A REQ with `tier in {1,2}` MUST have a
   `citation` block. A REQ with `tier in {3,4,5}` MUST NOT have one.

2. **Citation document exists.** `citation.document` MUST match the
   `source_path` of a record in `formal_docs_manifest.json`.

3. **Citation hash match.** `citation.document_sha256` MUST equal the
   current `document_sha256` of that `FORMAL_DOC` record. Mismatch is
   reported as `citation_stale` in `quality_gate_report.json` and fails
   the gate.

4. **Citation excerpt presence and locatability.** Every Tier 1/2 citation
   MUST have a non-empty `citation_excerpt` AND at least one of
   `section`/`line` MUST be present AND that locator MUST resolve in the
   referenced plaintext file per §5.5. `page` is never a sufficient sole
   locator. Re-verified at gate time, not just at ingest, to catch
   post-ingest tampering.

5. **Bug → REQ resolution.** Every `BUG.req_id` MUST match the `id` of an
   existing REQ record.

6. **Forward-link resolution.** Every `UC-NN` in any `REQ.use_cases` list
   MUST match the `id` of an existing UC record. (The reverse direction
   is not required — UC → REQ is derived, not persisted.)

7. **Disposition completeness.** Every BUG MUST have a non-null
   `disposition` AND a non-empty `disposition_rationale`.

8. **Functional section presence.** Every REQ MUST have a non-empty
   `functional_section` string.

9. **No orphan reference docs.** Every file under `reference_docs/cite/` whose
   extension is in the supported list MUST appear as a `FORMAL_DOC` record
   (ingest ran and was complete). Files with unsupported extensions MUST
   cause ingest to fail with a clear error, not be silently skipped.

10. **Run index presence and fields.** `quality/INDEX.md` (for the
    current run) MUST exist and contain every required field listed in
    §11 "Per-Run `INDEX.md` Fields."

11. **Citation excerpt byte-equality.** For every Tier 1/2 citation,
    `citation.citation_excerpt` MUST be byte-equal to the output of the
    deterministic extraction algorithm in §5.4 applied to
    `(document_bytes, section, line)`. The gate re-runs §5.4 at
    verification time and rejects any mismatch.

12. **Legal `fix_type` × `disposition` combination.** Every `BUG` record
    MUST satisfy the legal-combinations matrix in §3.4. Illegal
    combinations are `code-fix`+`spec`, `spec-fix`+`code`,
    `upstream-spec-issue`+`code`, and `mis-read`+`both`.

13. **Manifest wrapper validity.** Every JSON manifest produced by the
    playbook MUST be a JSON object with the three wrapper fields defined
    in §1.6 (`schema_version`, `generated_at`, `records` — or `reviews`
    for `citation_semantic_check.json`). `schema_version` MUST equal the
    playbook's `SKILL.md` `metadata.version`. `generated_at` MUST parse
    as ISO 8601 with explicit timezone.

14. **REQ tier bound to cited FORMAL_DOC tier.** For every REQ with
    `tier ∈ {1, 2}`, `REQ.tier` MUST equal the `tier` of the `FORMAL_DOC`
    record whose `source_path` matches `citation.document`. A Tier 1 REQ
    cannot cite a Tier 2 FORMAL_DOC and vice versa.

15. **ID uniqueness.** Within each manifest, record `id` values MUST be
    unique (`REQ-NNN`, `UC-NN`, `BUG-NNN`). `FORMAL_DOC.source_path`
    values MUST be unique within `formal_docs_manifest.json`.

16. **Redundant citation metadata MUST match FORMAL_DOC.** When any of
    `citation.version`, `citation.date`, `citation.url`, or
    `citation.retrieved` is present, its value MUST equal the
    corresponding field on the cited `FORMAL_DOC` record. Missing is
    permitted; mismatched fails the gate.

17. **Semantic check majority rule.** Using the reviews in
    `citation_semantic_check.json` grouped by `req_id`, the gate fails
    if any Tier 1/2 REQ has two or more reviews with
    `verdict == "overreaches"`. Single-member `unclear` or `overreaches`
    verdicts are surfaced as warnings but do not fail the gate.

18. **Array value uniqueness.** Values within `REQ.use_cases` MUST be
    unique. Values within `UC.formal_doc_refs` MUST be unique. Duplicate
    entries fail the gate.

19. **Pattern-tagged REQs have complete grid coverage.** For every REQ with
    a `pattern:` field, every (authoritative item × site) cell from the
    Phase 3 compensation grid MUST appear either in some BUG's `covers` array
    or in a structured downgrade record in
    `quality/compensation_grid_downgrades.json`.

20. **Structured downgrade records are complete.** Every record in
    `quality/compensation_grid_downgrades.json` MUST have all five fields:
    `cell_id`, `authority_ref`, `site_citation`, `reason_class`,
    `falsifiable_claim`. `reason_class` MUST be one of
    `out-of-scope | deprecated | platform-gated | handled-upstream |
    intentionally-partial`. `falsifiable_claim` MUST have non-zero length.
    Missing fields or invalid `reason_class` → cell reverts to BUG at gate
    time.

21. **v1.5.3 source_type / skill_section consistency.** On a v1.5.3-shaped
    requirements manifest (per §3.10), every REQ MUST have `source_type`
    populated with a member of `req_source_type` (§3.7); every REQ with
    `source_type == "skill-section"` MUST have a non-empty `skill_section`
    string; and every REQ with any other `source_type` value MUST have
    `skill_section` either absent OR explicitly `null` (per §1.5's rule
    that optional fields may be omitted or present as null). Populated
    `skill_section` paired with a non-`skill-section` `source_type` fails
    the gate.

22. **v1.5.3 divergence_type presence.** On a v1.5.3-shaped bugs manifest
    (per §3.10), every BUG MUST have `divergence_type` populated with a
    member of `bug_divergence_type` (§3.8). Missing or invalid value
    fails the gate.

23. **v1.5.3 formal_doc role presence.** On a v1.5.3-shaped formal_docs
    manifest (per §3.10), every record MUST have `role` populated with a
    member of `formal_doc_role` (§3.6). Missing or invalid value fails
    the gate.

---

## 11. Per-Run `INDEX.md` Fields

The per-run `INDEX.md` (at `quality/INDEX.md` for the current run, and
copied to `quality/previous_runs/<ts>/INDEX.md` at archive time —
v1.5.4 Phase 3.6.2 (B-19) renamed the archive directory from the
legacy `quality/runs/`; legacy archives at the old path remain
readable) is a structured record of run metadata. It is produced by
the orchestrator (not the gate), which alone knows phase timing and
model assignments. The gate validates that the file exists and that
every required field below is present and non-empty.

| Field                    | Type            | Required | Notes                                                                                                                       |
|--------------------------|-----------------|----------|------------------------------------------------------------------------------------------------------------------------------|
| `schema_version`         | string          | yes (v1.5.4+) | INDEX schema generation. `"2.0"` for v1.5.4+ runs (carries `target_role_breakdown`); `"1.0"` (or absent) for legacy v1.5.3 runs that carried `target_project_type`. |
| `run_timestamp_start`    | string          | yes      | ISO 8601 with explicit timezone. Run start.                                                                                  |
| `run_timestamp_end`      | string          | yes      | ISO 8601 with explicit timezone. Run end.                                                                                    |
| `duration_seconds`       | integer         | yes      | End minus start, rounded to whole seconds.                                                                                   |
| `qpb_version`            | string          | yes      | Playbook version that produced the run, e.g. `"1.5.4"`.                                                                      |
| `target_repo_path`       | string          | yes      | Absolute or repo-root-relative path to the target repo.                                                                      |
| `target_repo_git_sha`    | string          | yes      | Git SHA of the target repo HEAD at run start. May be `"unknown"` for non-git targets.                                        |
| `target_role_breakdown`  | object \| null  | yes (v1.5.4+) | Phase-1 role-map breakdown subtree (`files_by_role`, `size_by_role`, `percentages` with `skill_share`/`code_share`/`tool_share`/`other_share`). `null` is legitimate for the stub INDEX written before Phase 1 has produced `quality/exploration_role_map.json`. |
| `phases_executed`        | array of object | yes      | One entry per phase run. Each: `{phase_id, model, start, end, exit_status}`.                                                  |
| `summary.requirements`   | object          | yes      | Counts by tier — keys `"1"`..`"5"`, integer values.                                                                          |
| `summary.bugs`           | object          | yes      | Counts by severity and disposition. Keys include every enum value from §3.2 and §3.3; integer values.                        |
| `summary.gate_verdict`   | string          | yes      | One of `"pass"`, `"fail"`, `"partial"`.                                                                                      |
| `artifacts`              | array of string | yes      | Relative paths (within the run folder) to every artifact produced during this run.                                           |

**INDEX schema migration (v1.5.3 → v1.5.4).** v1.5.3 INDEX files
required `target_project_type` (a `Code` / `Skill` / `Hybrid` enum
string); v1.5.4 retired that field in favor of `target_role_breakdown`,
which carries the per-role file counts and percentage shares emerging
from the Phase-1 file role tagging (`quality/exploration_role_map.json`,
described in `docs/design/QPB_v1.5.4_Design.md` Part 1). Both shapes
remain readable by the gate:

  - **`schema_version: "2.0"`** (or missing on a NEW run produced by
    v1.5.4+ tooling) → the gate requires `target_role_breakdown` and
    accepts `null` for the stub INDEX written before Phase 1 produces
    the role map.
  - **`schema_version: "1.0"`** (or any pre-2.0 string) → the gate
    treats the file as a legacy archive, accepts `target_project_type`
    in place of `target_role_breakdown`, and emits a single WARN per
    file noting that the schema is frozen at the v1.5.3 shape. This
    path exists exclusively to keep historical archives under either
    `quality/previous_runs/` (current archive directory, v1.5.4+) or
    the legacy `quality/runs/` (pre-v1.5.4) legible to today's
    tooling without rewriting them retroactively. v1.5.4 Phase 3.6.2
    (B-19) also retired the `-PARTIAL` filename suffix in favour of
    an in-archive `.partial` sentinel file (`<archive>/.partial` is
    written when `status="partial"`); legacy archives carrying the
    `-PARTIAL` suffix remain readable.

New runs MUST emit `schema_version: "2.0"`. Migrating an archived
INDEX in place is OPTIONAL (the schema-routing path covers reads); if
it happens, the file becomes a v1.5.4 INDEX and gains the
`target_role_breakdown` field.

The format is markdown with a fenced JSON block carrying the structured
fields (the gate parses the JSON block, not the surrounding prose). The
exact markdown shape is defined in `SKILL.md` so the gate has one place to
look for required fields (this file) and one place to look for rendering
(SKILL.md).

Missing or empty fields fail §10 invariant #10.

---

## 11.1. Phase-1 Role Map (`quality/exploration_role_map.json`)

v1.5.4 Phase 1 produces a role map that drives every downstream
pipeline-activation decision (see `bin/role_map.py` for the canonical
schema constants and `docs/design/QPB_v1.5.4_Design.md` Part 1 for
the rationale). The role map IS the v1.5.4 replacement for the
v1.5.3 mechanical Code/Skill/Hybrid classifier — the trichotomy is
gone; per-file role tags carry the routing semantics.

| Field             | Type            | Required | Notes                                                                                                                       |
|-------------------|-----------------|----------|------------------------------------------------------------------------------------------------------------------------------|
| `schema_version`  | string          | yes      | Currently `"1.0"`. Bumped only on breaking changes to the role-map JSON shape (distinct from the INDEX.md `schema_version`). |
| `timestamp_start` | string          | yes      | ISO 8601 UTC at the start of Phase 1.                                                                                        |
| `provenance`      | string          | yes (v1.5.4 Phase 3.6.1+) | One of `"git-ls-files"` (preferred — target is a git repo), `"filesystem-walk-with-skips"` (target is not a git repo), `"unknown"` (legacy maps written before this field was required), `"exclude-filtered"` (v1.5.6 cluster 049+ — emitted when `bin.role_map.maybe_recover_role_map` auto-recovers a too-large role_map by filtering vendored/build/cache content via the deterministic in-scope predicate; the filter uses hardcoded glob patterns + optional `.gitignore`/`.hgignore` parsing and does NOT shell out to git, so the marker explicitly does NOT mean "git filter ran" — it means "an exclude-pattern filter ran"). |
| `files`           | array of object | yes      | One entry per in-scope file. Per-entry shape below.                                                                          |
| `breakdown`       | object          | yes (runner-generated as of v1.5.6 cluster 047) | Aggregate counts + percentages (subtree shape below). The Phase 1 LLM SHOULD NOT include this field; `bin.run_playbook.check_phase_gate` calls `bin.role_map.normalize_role_map_for_gate` between Phase 1 LLM exit and the Phase 2 entry-gate, which recomputes `breakdown` via `bin.role_map.compute_breakdown(files)` and overwrites whatever the LLM wrote. Legacy role maps with LLM-written `breakdown` continue to load — the runner's recomputation is idempotent on a correctly-written breakdown. |
| `summary`         | object          | yes (runner-generated as of v1.5.6 cluster 047) | Single-source-of-truth summary feeding both this role map's `summary` AND EXPLORATION.md's "File inventory" section. The Phase 1 LLM SHOULD NOT include this field; the runner-side normalize step (above) computes it via `bin.role_map.summarize_role_map()` and overwrites whatever the LLM wrote. EXPLORATION.md's file-inventory section is the output of `bin.role_map.render_role_map_narrative()` (which itself reads `summarize_role_map`). The pre-v1.5.6 contract was "LLM produces summary; validator enforces it equals `summarize_role_map(role_map)`"; that contract reliably failed for sonnet-class LLMs that reverted to intuitive summarization. v1.5.6 cluster 047 moved the deterministic computation to the runner. |

**`files[]` entry shape:**

| Field                     | Type    | Required | Notes                                                                                       |
|---------------------------|---------|----------|----------------------------------------------------------------------------------------------|
| `path`                    | string  | yes      | Repo-relative POSIX path.                                                                    |
| `role`                    | string  | yes      | One of: `skill-prose`, `skill-reference`, `skill-tool`, `code`, `test`, `docs`, `config`, `fixture`, `formal-spec`, `playbook-output`. See `bin.role_map.ROLE_DESCRIPTIONS` for the canonical taxonomy. |
| `size_bytes`              | integer | yes      | Non-negative; file size in bytes.                                                             |
| `rationale`               | string  | yes      | One-or-two-sentence content-based justification for the tag.                                 |
| `skill_prose_reference`   | string  | yes when `role == "skill-tool"`; optional otherwise | Pointer to the SKILL.md / reference-file location that names this script (e.g. `"SKILL.md:47"` or `"references/forms.md:section-3"`). The Phase 4 prose-to-code divergence check anchors against this. |

**`breakdown` subtree:**

```
breakdown:
  files_by_role: { "<role>": <count>, ... }
  size_by_role:  { "<role>": <total bytes>, ... }
  percentages:
    skill_share: <skill-prose + skill-reference share of total bytes>
    code_share:  <code share of total bytes>
    tool_share:  <skill-tool share of total bytes>
    other_share: <remainder; everything else>
```

Percentages are floats in `[0, 1]` and MUST sum to ~1.0 when total
size > 0 (validator tolerance: 0.01).

**Disallowed-path constraints (v1.5.4 Phase 3.6.1, codex-prevention):**

The validator at `bin.role_map.validate_role_map` rejects role maps
containing paths under any of:

  `.git/`, `.venv/`, `venv/`, `node_modules/`, `__pycache__/`,
  `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.tox/`

…or paths whose components end in `.egg-info` or `.dist-info`. These
are .gitignored content / vendored deps that should never be tagged
as part of the target's intrinsic surface. Operator override:
`--allow-disallowed-prefix PREFIX` (repeatable) on
`bin.run_playbook` for legitimately-tracked content.

**Entry-count ceiling:** `MAX_ROLE_MAP_ENTRIES = 2000` (default). A
role map exceeding the ceiling almost certainly indicates Phase 1
walked .gitignored content; the validator fails with a diagnostic
naming the count and the limit. Operator override:
`--max-role-map-entries N`.

**Validation activation:** the v1.5.4 Phase 2 gate
(`bin/run_playbook.check_phase_gate("2")`) refuses to advance unless
the role map exists, parses, and validates against the constraints
above. Pre-Phase-1 invocations and pre-iteration targets without a
role map skip the validation; v1.5.3 code-review behaviour is
preserved as a backward-compat fallback (see Site 2 asymmetry note
in `bin/run_playbook._code_review_should_skip`).

---

## 11.2. End-of-Run Quality Folder Layout (v1.5.4 Phase 3.6.4 — REMOVED in v1.5.7 F-4z)

**Status: the v1.5.4 Phase 3.6.4 `workspace/` reshape described below
was removed in v1.5.7 F-4z. The gate now actively FAILS any run that
emits a `workspace/` directory under `quality/` — see
`check_no_workspace_dir` at
`.github/skills/quality_gate/quality_gate.py`. The
`_finalize_quality_layout` runner-side reshape function was deleted in
the same fix; do not look for it in `bin/run_playbook.py`.**

**Current canonical end-of-run layout (v1.5.7):**

- **Phase artifacts** (REQUIREMENTS.md, QUALITY.md, BUGS.md, the four
  `RUN_*.md` audits, EXPLORATION.md, INDEX.md, PROGRESS.md,
  exploration_role_map.json) land at the top of the per-target
  `quality/` tree. No `workspace/` subdirectory.
- **Per-run logs** (playbook log, `run_state.jsonl`, RUN_MODE.md,
  control_prompts transcripts) are centralized under
  `quality/logs/<run-id>/` per the v1.5.7 D3 deliverable, with a
  `quality/logs/latest` symlink updated at run completion. The
  `--logs-flat` CLI flag (or `QPB_LOGS_LEGACY=1` env var) restores the
  v1.5.6 scattered layout for adopter tooling that hasn't migrated.
- **Phase 2 gate-failure preservation** (v1.5.7 D1): when the Phase 2
  gate aborts, the failed `quality/` directory is preserved as
  `quality.gate-failed-<UTC-timestamp>/` so operators can inspect the
  rejected agent output. Implementation:
  `bin/run_playbook.py::_preserve_quality_on_gate_failure` (invoked
  from `run_one_phase()`).
- **Archive subtree** at `quality/previous_runs/` (legacy `runs/` also
  accepted) per B-19.

**Cross-references for the current layout:**

- `ai_context/BENCHMARK_PROTOCOL.md` — operator-facing description of
  the v1.5.7 D1 + D3 layout.
- `references/run_state_schema.md` — canonical schema for the
  centralized run-state log, including the `run_id` / `log_layout`
  discriminator fields on the `run_start` event.
- `references/what_just_happened.md` — D1 preservation mechanics
  cross-reference.

The v1.5.4 Phase 3.6.4 section heading is preserved here so future
readers searching for "workspace/" or "Phase 3.6.4" find the deletion
record. The tree diagram and the "idempotent reorganization" prose
that previously occupied this section are removed; consult the git
history (`git log --all -- schemas.md`) for the pre-F-4z text if
forensic context on the deprecated layout is needed.

---

## 12. Versioning

`schemas.md` carries the playbook version in the banner at the top of this
file. The string MUST match `metadata.version` in `SKILL.md`. The
bootstrap self-audit checks both.

Backwards-incompatible schema changes (renaming a field, dropping a field,
changing a required/optional flag, modifying an enum value) require a minor
version bump at minimum. Additive changes (new optional fields, new enum
values consumed only when written by new code) may ship in a patch release
but must be reflected here before any code depends on them.

**Schema additions and the per-manifest `schema_version` field.** Schema
*additions* in a new release (e.g., v1.5.3's `REQ.source_type`,
`BUG.divergence_type`, and `FORMAL_DOC.role`) do NOT require a manifest's
`schema_version` to bump — the additions become required by field-presence
detection in the validator (see §3.10), not by the version string. The
`schema_version`-MUST-equal-`metadata.version` invariant in §1.6 is
preserved: `schema_version` keeps mirroring SKILL.md's `metadata.version`
unchanged across additive releases, and adopters can begin populating the
new fields against an unchanged version stamp. Bumping `metadata.version`
remains the trigger for breaking schema changes.

If a field is being deprecated, leave it in `schemas.md` with a "deprecated
in v1.X.Y" note for at least one minor version before removing it — this is
the only signal a re-running operator has that their manifests need to be
regenerated.

---

## 13. Change Log

| Version     | Change                                                                 |
|-------------|------------------------------------------------------------------------|
| 1.5.1       | Initial version. `FORMAL_DOC`, `REQ`, `UC`, `BUG`, `citation`, enums.  |
| 1.5.1-rc1   | Council-of-Three Phase 1 revisions: added byte-equality extraction algorithm (§5.4) and section resolution (§5.5); removed `REQ.disposition` (resolves enum contradiction); locked `fix_type × disposition` legal-combination matrix; schematized manifest wrapper (§1.6) and `citation_semantic_check.json` (§9); inlined per-run `INDEX.md` fields (§11); tightened locator rule to `section`/`line` only; bound `REQ.tier` to cited `FORMAL_DOC.tier`; added ID uniqueness, redundant-metadata match, and array-uniqueness invariants; reframed `citation_stale` as gate-report marker (not record field); wrapped authoring-guidance field descriptions with explicit "not gate-enforced" prefix. |
| 1.5.3 (Phase 2) | Introduced `REQ.source_type` (§6.1, enum §3.7), `REQ.skill_section` (§6.1), `BUG.divergence_type` (§8.1, enum §3.8), and `FORMAL_DOC.role` (§4.1, enum §3.6). Added the SKILL.md-vs-reference-file precedence rule for `internal-prose` BUG dispositions (§3.9). Added field-presence detection rule (§3.10): the new fields are required when any v1.5.3 field is populated anywhere in a manifest; absent on legacy manifests, the validator emits one WARN per check function and skips v1.5.3 invariants for that manifest. Added invariants #21–#23 covering the new fields. Amended §12 to clarify that schema additions do NOT require a per-manifest `schema_version` bump — the `schema_version`-MUST-equal-`metadata.version` invariant is preserved. The schemas.md banner version is unchanged; the per-manifest `schema_version` keeps mirroring `SKILL.md` `metadata.version`. Additive at the field level; introduces precedence semantics for SKILL.md vs reference-file conflicts. |
