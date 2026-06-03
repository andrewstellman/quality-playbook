# ADVERSARIAL Iteration — Counterexamples to Baseline SATISFIED claims
Date: 2026-05-19
Strategy: adversarial
REQs challenged: 8 (REQ-001..REQ-008)
Demoted candidates re-investigated: 2 (Phase 4 SKILL.md fallback dismissal; PARITY BUG-012 SKILL.md operator-prose drift extension)

## Methodology

For each baseline REQ, the existing bug (if any) closes ONE failure mode. This
iteration constructs counterexamples — concrete inputs where a DIFFERENT
failure mode of the same requirement still triggers. Where the baseline
treats a REQ as fully SATISFIED, the counterexample probes a different shape
of the same predicate (extension support, case sensitivity, regex divergence
across surfaces, content-shape gates the validator skips).

Source-of-truth reads:
- Patched code as currently on disk (BUG-001..006 fix patches all applied to
  the working tree, plus the v1.5.7 089c three-state verdict change).
- Spec text in `references/phase1_exploration_guide.md`, `SKILL.md`, and
  `schemas.md`.
- The three install-location enums (`SKILL_INSTALL_LOCATIONS` in benchmark_lib,
  `SKILL_FALLBACK_GUIDE` and `_GATE_INSTALL_LOCATIONS` in run_playbook,
  `KNOWN_ENVIRONMENTS`/`AI_TOOL_MAP` in install_skill).

---

## REQ-001: cite-only docs-backed startup warning

- Baseline disposition: SATISFIED by BUG-001 fix (`docs_present` now delegates
  to `_reference_docs_plaintext()` which scans both `reference_docs/` top
  level and `reference_docs/cite/`).
- Counterexample probe: a repo with ONLY `reference_docs/cite/virtio.rst`
  (a citable reStructuredText spec — the format Linux-kernel / Python docs
  use, explicitly supported by ingest).
- Trace:
  - `bin/reference_docs_ingest.py:76` — `SUPPORTED_EXTENSIONS = frozenset({".txt", ".md", ".rst"})`.
  - `bin/reference_docs_ingest.py:68-75` — comment block confirms `.rst` is
    a first-class plaintext extension for ingest (instruction 060 / A-12).
  - `bin/run_playbook.py:2021` — `_REFERENCE_DOCS_PLAINTEXT_EXTS = frozenset({".txt", ".md"})`.
    NO `.rst`.
  - `bin/run_playbook.py:2053, 2065` — `_reference_docs_plaintext()` filters
    against `_REFERENCE_DOCS_PLAINTEXT_EXTS`, so `virtio.rst` is dropped.
  - `bin/run_playbook.py:2015` — `docs_present()` calls
    `_reference_docs_plaintext()` first; on `.rst`-only it returns False.
  - `bin/run_playbook.py:2170-2182` — `_evaluate_documentation_state()` calls
    the same predicate; returns `"code_only"`.
  - `bin/run_playbook.py:2100-2147` — `formal_docs_guard_banner()` likewise
    emits the WARN banner.
- Expected behavior (REQ-001 COS 1): "A repo with only `reference_docs/cite/spec.md`
  is classified as docs-backed." The same condition naturally extends to
  `spec.rst` since ingest treats `.rst` as supported plaintext (ingest will
  hash it, write a FORMAL-* record, and surface it via `formal_docs_manifest.json`).
- Actual behavior: ingest accepts `virtio.rst` and writes its formal-doc
  record; all three startup-classification surfaces (`docs_present`,
  `_evaluate_documentation_state`, `formal_docs_guard_banner`) classify the
  repo as code-only and emit the WARN banner. This is the SAME failure-mode
  shape as BUG-001 (cite-only tree silently downgraded), just on a different
  extension. The patch closed `.md` but left `.rst` open.
- Verdict: CONFIRMED new bug — promote as BUG-016-ADV.

## REQ-002: one recognized-docs predicate across surfaces

- Baseline disposition: SATISFIED by BUG-002 fix (the three surfaces
  `docs_present`, `_evaluate_documentation_state`, `formal_docs_guard_banner`
  all consult `_reference_docs_plaintext`).
- Counterexample probe: extension-list divergence between the three startup
  surfaces and the ingest pipeline they're supposed to mirror.
- Trace:
  - `bin/run_playbook.py:2021` — startup surfaces use `{".txt", ".md"}`.
  - `bin/reference_docs_ingest.py:76` — ingest uses `{".txt", ".md", ".rst"}`.
  - `bin/run_playbook.py:2028-2040` — the docstring of
    `_reference_docs_plaintext` explicitly says "this function MUST mirror
    `bin/reference_docs_ingest._iter_candidates()` in scope" — but it does
    NOT mirror its extension set.
- Expected behavior (REQ-002 COS 4): "The three helper surfaces agree across
  cite-only, README-only, binary-only, and plaintext-top-level cases." With
  ingest accepting `.rst`, the three surfaces no longer agree with ingest;
  a `.rst`-backed cite tree is "with_docs" by ingest's lights and "code_only"
  by the startup surfaces. The contract REQ-002 names is cross-surface
  agreement; the patched code agrees ONLY among the three startup surfaces
  but not between the startup surfaces and ingest.
- Actual behavior: same as REQ-001 trace above. The asymmetry the patch
  docstring DECLARES it closes (parity with `_iter_candidates()`) is not
  actually closed — only `.md`/`.txt` were aligned.
- Verdict: CONFIRMED new bug — promote as BUG-017-ADV (same root cause as
  BUG-016 but covers a separate REQ; consolidates with BUG-016 via the
  shared "extend `_REFERENCE_DOCS_PLAINTEXT_EXTS` to include `.rst`" fix).

## REQ-003: Tier 4 ingest scoped to documented surface

- Baseline disposition: SATISFIED by BUG-003 fix (`load_tier4_context` now
  iterates only `reference_docs/` top level via `ref_dir.iterdir()`).
- Counterexample probe 1 (extension consistency with REQ-001/REQ-002): a
  `reference_docs/notes.rst` is included in Tier 4 context (it passes the
  `path.suffix.lower() not in SUPPORTED_EXTENSIONS` filter at
  `bin/reference_docs_ingest.py:343`), but the same `notes.rst` does NOT
  count toward `docs_present()` — so a repo with only `notes.rst` at the
  top level of `reference_docs/` gets a code-only WARN banner WHILE
  `load_tier4_context()` returns the file to Phase 1 as Tier 4 context.
  Operator-visible state contradicts ingest state.
- Counterexample probe 2 (symlink boundary): `load_tier4_context()` uses
  `path.is_file()` at line 339, which follows symlinks. A symlink
  `reference_docs/shortcut.md` pointing to `reference_docs/nested/archive/notes.md`
  would be loaded as Tier 4 context (with rel_path `reference_docs/shortcut.md`)
  even though the target lives in nested archival territory the REQ-003
  whitelist explicitly excludes. Low-likelihood operator footgun, not a
  promotion candidate by itself.
- Trace: `bin/reference_docs_ingest.py:332-348` (`load_tier4_context` body);
  `bin/run_playbook.py:2015` (`docs_present` predicate).
- Verdict: probe 1 is CONFIRMED — it's a face of the same extension-set
  divergence captured by BUG-016/BUG-017, not an independent REQ-003
  violation. Probe 2 is INCONCLUSIVE (no actual misuse vector identified;
  symlinks under `reference_docs/` are not a documented operator pattern).
  No standalone REQ-003 promotion; the BUG-016/BUG-017 fix would close
  probe 1 simultaneously.

## REQ-004: bootstrap mirror preserves cite/ placement

- Baseline disposition: SATISFIED by BUG-004 fix (the helper now copies
  `docs_gathered/cite/*` into `reference_docs/cite/`).
- Counterexample probe: extension support divergence between bootstrap
  mirror and ingest pipeline.
- Trace:
  - `bin/bootstrap_self_audit_docs.py:35` — `PLAINTEXT_EXTENSIONS = {".md", ".txt"}`.
    NO `.rst`.
  - `bin/bootstrap_self_audit_docs.py:62, 69, 77, 88` — every loop body
    filters against `PLAINTEXT_EXTENSIONS`.
  - `bin/reference_docs_ingest.py:76` — ingest accepts `.rst`.
- Expected behavior (REQ-004 COS): "mirrors both top-level context docs
  and `docs_gathered/cite/*` into `reference_docs/` with placement preserved."
  The contract does not name an extension list explicitly, but the mirror
  is a feeder for ingest; if ingest accepts `.rst`, the mirror must too
  for the self-audit path to work end-to-end with `.rst` citable specs.
- Actual behavior: a `docs_gathered/cite/virtio.rst` is silently dropped
  by the mirror. The destination `reference_docs/cite/` ends up empty for
  this file, and a subsequent QPB self-audit run gets the SAME false
  code-only classification that BUG-016/BUG-017 describe — but here it's
  because the file never made it to the destination in the first place.
  This compounds with BUG-016/BUG-017: even if the startup surfaces were
  fixed to accept `.rst`, the mirror would have already lost the file.
- Verdict: CONFIRMED new bug — promote as BUG-018-ADV.

## REQ-005: full Phase 1 exploration gate mechanically enforced

- Baseline disposition: SATISFIED by BUG-005 fix (`_validate_phase1` now
  enforces 5 required headings + Pattern Deep Dive count + PROGRESS check
  + 8 additional analytical-content checks added beyond the original
  patch).
- Counterexample probe 1: spec ↔ validator content-rule drift. The
  written gate in `references/phase1_exploration_guide.md:692-704` has
  12 checks. The validator enforces a SUBSET. Items the validator DOES
  NOT enforce:
  - Check 3 (spec): "Derived Requirements section contains at least one
    REQ-NNN with specific file paths and function names." The validator
    has no `## Derived Requirements` heading check and no `REQ-NNN`
    pattern check.
    - Trace: search `bin/run_state_lib.py` for `Derived Requirements`
      or `REQ-NNN` — zero matches.
  - Check 4 (spec, second half): "At least 4 must reference different
    modules or subsystems." The validator counts ≥8 findings with
    file:line citations (line 360) but does NOT verify multi-module
    spread. An EXPLORATION.md with 8 findings ALL citing
    `bin/run_playbook.py` passes the validator.
  - Check 6 (spec): `## Quality Risks` must contain "≥5 domain-driven
    failure scenarios" each naming a function, file, line, edge case,
    and explanation. The validator only checks that the heading exists
    (line 321-326); it does NOT verify ≥5 sub-items, line citations,
    or domain-driven content.
  - Check 7 (spec): the matrix "evaluates all six patterns from
    `exploration_patterns.md`" — but `references/exploration_patterns.md`
    actually contains SEVEN patterns (lines 13, 55, 99, 143, 189, 230,
    272). The validator counts FULL cells in the matrix (line 382) but
    does NOT verify the matrix lists every documented pattern. A matrix
    with only 3 rows (all FULL) passes the validator at
    `_FULL_CELL_RE.findall(matrix_body) → 3` (within the 3-4 inclusive
    range).
- Counterexample probe 2: numbered-entry format requirement. The
  validator uses `_NUMBERED_ENTRY_RE = re.compile(r"^(\d+)\.\s", re.MULTILINE)`
  at line 91. A Phase 1 author who writes findings as bullet lists
  (`- finding 1 ...`) instead of numbered lists fails the entry-count
  checks even when the analytical content is sufficient. This is a
  format-strictness vs spec-fidelity mismatch — the spec at line 695
  says "at least 8 concrete bug hypotheses or suspicious findings, each
  with a file path and line number" without prescribing numbering. The
  validator imposes a numbering convention the spec doesn't require.
- Counterexample probe 3: the BUG-005 regression test only asserts the
  validator REJECTS a degenerate placeholder; it does not assert the
  validator ACCEPTS a structurally-valid EXPLORATION.md. So a regression
  that makes the validator over-strict (e.g., a future "must have
  Derived Requirements heading" addition) would pass the existing test
  while breaking real Phase 1 runs.
- Verdict for probe 1: CONFIRMED spec-vs-code drift — the validator
  enforces ~6 of 12 documented checks. Three of the missing checks (3,
  6, 7) are load-bearing for the failure mode REQ-005 names ("shallow
  exploration artifacts"). Promote as BUG-019-ADV.
- Verdict for probe 2: INCONCLUSIVE — format-strictness call; spec
  silence on numbering is ambiguous, so the validator's stricter rule
  is defensible. No promotion.
- Verdict for probe 3: NOTE — regression-test coverage gap, not a code
  bug. Recorded in the promotion table but not a separate BUG entry.

## REQ-006: archive bug counting on titled headings

- Baseline disposition: SATISFIED by BUG-006 fix
  (`_BUG_HEADING_PATTERN = re.compile(r"^###\s+BUG-([A-Za-z0-9][A-Za-z0-9\-]*)(?::\s+.+)?\s*$", re.MULTILINE)`
  — accepts alphanumeric + hyphen IDs with optional title suffix).
- Counterexample probe: triple-regex divergence across three surfaces
  that all parse the same `BUG-NNN` headings.
- Trace:
  - `bin/archive_lib.py:69` — `^###\s+BUG-([A-Za-z0-9][A-Za-z0-9\-]*)(?::\s+.+)?\s*$`
    (alphanumeric + hyphen, optional `: title`).
  - `bin/run_state_lib.py:586-589` (Phase 3 validator) —
    `r"^###\s+BUG-([A-Za-z0-9][A-Za-z0-9\-]*)(?::\s+.+)?\s*$"`
    (matches archive).
  - `.github/skills/quality_gate/quality_gate.py:286` — `_BUG_HEADING_RE = re.compile(r"^###\s+BUG-(\d+):", re.MULTILINE)`
    (DIGITS ONLY, colon REQUIRED — narrower than the other two).
- Expected behavior: archive, Phase 3 validator, and terminal gate
  should all see the same set of bug headings. REQ-006 covers the
  archive-side undercount; the implicit corollary is "the gate sees
  the same bugs the archive sees," because the gate is the terminal
  authority on whether the BUG ledger is well-formed.
- Actual behavior: a `### BUG-007-PARITY: Title` heading (the convention
  used by parity-iteration findings, but more generally any future
  hyphen-suffixed ID like `BUG-001-fix-2`):
  - matches archive's `_BUG_HEADING_PATTERN` ✓
  - matches Phase 3 validator's `bug_id_re` ✓
  - does NOT match the gate's `_BUG_HEADING_RE` ✗
  Consequences: `_split_bug_blocks()` returns an empty list for these
  headings, so `validate_cardinality_gate()` at quality_gate.py:481
  silently skips the bug's `Covers:` entries. A parity-bug ledger
  with cross-site REQ tagging would pass cardinality despite the gate
  never having seen it.
- Verdict: CONFIRMED new bug — promote as BUG-020-ADV. This is REQ-006's
  failure mode on a different surface (the terminal gate, not the archive).

## REQ-007: role-map normalization

- Baseline disposition: SATISFIED by `normalize_role_map_for_gate`
  recomputing `breakdown` and `summary` from `files[]`, after which
  `validate_role_map` accepts the result.
- Counterexample probe 1: malformed `files[]` entries pass through
  normalization. `compute_breakdown` at line 494 skips non-dict entries
  silently; if `files` contains `[{...valid...}, "string-instead-of-dict",
  {...valid...}]`, normalize succeeds, breakdown is recomputed correctly
  for the two valid entries, AND `validate_role_map` then accepts the
  written-back document — but the resulting role map has a junk
  string entry in `files[]` that downstream consumers walking
  `files[]` (e.g., the writers in `run_playbook.py` that render
  EXPLORATION.md narratives) may stumble on.
- Trace: `bin/role_map.py:494-505` (skip-on-non-dict in
  `compute_breakdown`); `bin/role_map.py:357-360` (`validate_role_map`
  rejects non-dict entries — `errors.append(f"files[{idx}] is not an
  object")`). So actually `validate_role_map` WOULD reject the post-
  normalize file because the junk entry remains. The two functions
  disagree on tolerance: normalize is permissive, validate is strict.
  COS 2 says "After normalization, validate_role_map accepts the
  result without schema errors" — but normalize doesn't sanitize the
  `files[]` array, so a raw input with non-dict entries can't actually
  reach a state where the COS holds. Operator would need to fix
  `files[]` manually first.
- Verdict: NOT a code bug — REQ-007's COS 2 is a precondition statement
  ("WHEN the role map is well-formed but has wrong breakdown/summary,
  normalize fixes it"), not a guarantee that normalize sanitizes any
  arbitrary input. The validator's stricter check at line 358 catches
  what normalize doesn't. LEGITIMATELY SATISFIED for in-scope inputs.

## REQ-008: playbook-output accounting

- Baseline disposition: SATISFIED — `playbook-output` is in `VALID_ROLES`
  (role_map.py:151-157), `compute_breakdown` does NOT include it in
  `SKILL_PROSE_ROLES`/`SKILL_TOOL_ROLES`/`CODE_ROLES`, so it lands in
  `other_share = 1 - skill - tool - code`.
- Counterexample probe: cross-surface coverage. Does every consumer of
  the role-map breakdown route `playbook-output` consistently?
- Trace:
  - `bin/role_map.py:514-526` — `compute_breakdown` excludes
    `playbook-output` from numerators; `other` = remainder. ✓
  - `bin/role_map.py:553-560` — `summarize_role_map` includes the
    `playbook-output` row in `role_breakdown`. ✓
  - `bin/role_map.py:841-868` — `render_role_map_narrative` renders
    `role_breakdown` with all roles (sorted), so `playbook-output`
    appears in the EXPLORATION.md File Inventory section. ✓
  - No `playbook-output` aggregation gap found in the breakdown
    consumers.
- Verdict: LEGITIMATELY SATISFIED. No counterexample.

---

## Re-investigation of demoted candidates

### DC-1: Phase 4 triage "documentation-gap finding, no real-code bug" (SKILL.md fallback list)

- Source: `quality/spec_audits/2026-05-08-triage.md` F-001 — SKILL.md:195-200
  said to list only 4 fallback locations vs. the canonical 6 in runtime/
  helper/test surfaces.
- Original dismissal reason: "prose-contract drift, not a new real-code
  defect in the scoped implementations."
- Re-investigation evidence: SKILL.md:213-224 now lists ALL 10 canonical
  install layouts (v1.5.7 instruction 046 broadened from 6 to 10). The
  prose at SKILL.md:195-200 referenced by F-001 is no longer a fallback
  list at all — it's an artifacts table. F-001's evidence pointer is
  stale; the underlying drift it described has been closed by the v1.5.7
  SKILL.md rewrite that produced the 10-layout list at lines 213-224.
- New determination: FALSE POSITIVE in the current source (the drift
  F-001 described is resolved). PARITY BUG-009 covers a DIFFERENT,
  still-present surface (the WARN message at run_playbook.py:1051-1062
  enumerating only 6 layouts), so the underlying class of finding is
  not gone — it has just moved.

### DC-2: PARITY BUG-012 (089c three-state verdict has no `gate_verdict` enum) — extension probe

- Source: `quality/EXPLORATION_ITER1.md` BUG-012 — schemas.md and
  validator enum don't include `pass_with_cleanup`.
- Original determination: PROMOTED (BUG-012).
- Re-investigation evidence: ADDITIONAL operator-prose drift surface
  beyond what BUG-012 already names:
  - `SKILL.md:209` — "The gate verdict in `quality/INDEX.md` (`pass` /
    `partial` / `fail`) is the operator-facing summary of how the run
    went." This is the OPERATOR-FACING explainer of the three valid
    `gate_verdict` values; it predates 089c and was not updated when
    the gate added "PASS WITH CLEANUP NEEDED".
  - `bin/validate_phase_artifacts.py:109` — `_INDEX_VALID_VERDICTS = ("pass", "partial", "fail")` (already known via BUG-012).
- New determination: BUG-012 stands and is REINFORCED by an extra
  SKILL.md operator-prose drift surface. Recommend the BUG-012
  remediation explicitly include a SKILL.md:209 update, not just
  schemas.md / validator. No separate ADV bug — this is BUG-012
  scope-expansion, captured here for the writeup.

---

## Promotion summary

| Finding ID | Source                 | Severity | File:line                                                                                                    | Recommendation         |
|------------|------------------------|----------|--------------------------------------------------------------------------------------------------------------|------------------------|
| BUG-016-ADV| REQ-001 adversarial    | MEDIUM   | `bin/run_playbook.py:2021` + `bin/reference_docs_ingest.py:76`                                               | PROMOTE                |
| BUG-017-ADV| REQ-002 adversarial    | MEDIUM   | `bin/run_playbook.py:2021, 2028-2040, 2053, 2065`                                                            | PROMOTE                |
| BUG-018-ADV| REQ-004 adversarial    | MEDIUM   | `bin/bootstrap_self_audit_docs.py:35, 62, 69, 77, 88`                                                        | PROMOTE                |
| BUG-019-ADV| REQ-005 adversarial    | HIGH     | `bin/run_state_lib.py:61-78, 294-470` vs `references/phase1_exploration_guide.md:692-704`                    | PROMOTE                |
| BUG-020-ADV| REQ-006 adversarial    | MEDIUM   | `.github/skills/quality_gate/quality_gate.py:286, 481`                                                       | PROMOTE                |
| Probe REQ-003 #2 (symlink) | REQ-003 adversarial | LOW | `bin/reference_docs_ingest.py:339`                                                                   | INCONCLUSIVE / no promotion |
| Probe REQ-005 #2 (numbering) | REQ-005 adversarial | LOW | `bin/run_state_lib.py:91`                                                                            | INCONCLUSIVE / no promotion |
| Probe REQ-007 (normalize tolerance) | REQ-007 adversarial | n/a | `bin/role_map.py:494-505`                                                                  | LEGITIMATELY SATISFIED |
| Probe REQ-008 (cross-surface)| REQ-008 adversarial | n/a | `bin/role_map.py:514-526, 841-868`                                                              | LEGITIMATELY SATISFIED |
| DC-1 Phase 4 fallback drift  | Phase 4 dismissal  | n/a | `SKILL.md:195-200` (stale citation; current text lists 10 layouts at 213-224)                    | FALSE POSITIVE (resolved)|
| DC-2 BUG-012 SKILL.md prose  | PARITY BUG-012 ext | (within BUG-012) | `SKILL.md:209`                                                                          | reinforces BUG-012     |

Net new ADV bug promotions: 5 (BUG-016 through BUG-020).

---

## Bugs to promote into BUGS.md

### BUG-016: `_REFERENCE_DOCS_PLAINTEXT_EXTS` omits `.rst`; cite-only `.rst` trees misclassified as code-only
- Primary requirement: REQ-001
- Severity: MEDIUM
- Source: Adversarial iteration (REQ-001 counterexample)
- File:line: `bin/run_playbook.py:2021` (extension set definition); `bin/run_playbook.py:2053, 2065` (the two filter sites in `_reference_docs_plaintext`); `bin/reference_docs_ingest.py:76` (canonical `SUPPORTED_EXTENSIONS` includes `.rst`)
- Spec basis: `quality/REQUIREMENTS.md:19-25` (REQ-001 COS 1 — cite-only docs-backed)
- Expected behavior: a repo with only `reference_docs/cite/virtio.rst` (the canonical Linux-kernel / Python spec format, explicitly supported by ingest per instruction 060 / A-12) is classified as docs-backed by every startup surface, matching BUG-001's contract for `.md`.
- Actual behavior: `_reference_docs_plaintext()` filters against `{".txt", ".md"}` — `.rst` is excluded. `docs_present()` returns False; `_evaluate_documentation_state()` returns `"code_only"`; `formal_docs_guard_banner()` emits the WARN banner — all on a repo whose `reference_docs/cite/virtio.rst` ingest WILL successfully read and write to `formal_docs_manifest.json`. The patch closed `.md`/`.txt` but left the `.rst` recreation of the same failure mode.
- Regression test (not yet authored): `quality/test_regression.py::CodeReviewRegressionTests::test_bug_016_docs_present_recognizes_cite_only_rst_docs` — `reference_docs/cite/virtio.rst` + empty top level → `docs_present()` must return True.
- Fix sketch: extend `_REFERENCE_DOCS_PLAINTEXT_EXTS` to `{".txt", ".md", ".rst"}` to mirror `SUPPORTED_EXTENSIONS`.

### BUG-017: Cross-surface predicate parity drift between `_reference_docs_plaintext` and `_iter_candidates` extension sets
- Primary requirement: REQ-002
- Severity: MEDIUM
- Source: Adversarial iteration (REQ-002 counterexample; consolidates with BUG-016)
- File:line: `bin/run_playbook.py:2021` (startup-side `{".txt", ".md"}`); `bin/run_playbook.py:2028-2040` (docstring DECLARING parity with `_iter_candidates`); `bin/reference_docs_ingest.py:76` (`SUPPORTED_EXTENSIONS = {".txt", ".md", ".rst"}`)
- Spec basis: `quality/REQUIREMENTS.md:35-42` (REQ-002 COS 4 — three helper surfaces agree across cite-only, README-only, binary-only, plaintext-top-level)
- Expected behavior: `_reference_docs_plaintext()`'s docstring promises mirror parity with `_iter_candidates()`; the three startup surfaces classify a tree the same way ingest does. Operator-facing classification matches ingest-side intake.
- Actual behavior: the two extension sets diverge on `.rst`. A `reference_docs/cite/virtio.rst` is ingested but operator-classified as code-only. The docstring claim of parity is structurally broken — the alignment was only done for `.md`/`.txt`, not for the full `SUPPORTED_EXTENSIONS` set. This is the same root cause as BUG-016 but covers a different REQ; consolidates via the shared one-line fix.
- Regression test (not yet authored): `quality/test_regression.py::CodeReviewRegressionTests::test_bug_017_startup_surfaces_match_ingest_extensions` — for each ext in `SUPPORTED_EXTENSIONS`, a cite-only repo with one file of that extension must produce `docs_present == True` AND `_evaluate_documentation_state == "with_docs"` AND `formal_docs_guard_banner is None`.
- Consolidation rationale: same fix as BUG-016 (extend `_REFERENCE_DOCS_PLAINTEXT_EXTS`).

### BUG-018: Bootstrap mirror silently drops `.rst` plaintext from `docs_gathered/`
- Primary requirement: REQ-004
- Severity: MEDIUM
- Source: Adversarial iteration (REQ-004 counterexample)
- File:line: `bin/bootstrap_self_audit_docs.py:35` (`PLAINTEXT_EXTENSIONS = {".md", ".txt"}`); `bin/bootstrap_self_audit_docs.py:62, 69, 77, 88` (every loop body filtering against it); `bin/reference_docs_ingest.py:76` (ingest accepts `.rst`)
- Spec basis: `quality/REQUIREMENTS.md:72-78` (REQ-004 COS — bootstrap mirrors both top-level and `cite/` sources into `reference_docs/`)
- Expected behavior: `bin.bootstrap_self_audit_docs` mirrors every plaintext file that ingest would later read — including `.rst`. A `docs_gathered/cite/virtio.rst` is mirrored to `reference_docs/cite/virtio.rst` so the self-audit run sees the same documentation surface the curated source carries.
- Actual behavior: the mirror's `PLAINTEXT_EXTENSIONS` is `{".md", ".txt"}` (no `.rst`). A `docs_gathered/cite/virtio.rst` is silently dropped; `reference_docs/cite/` ends up empty for that file; the post-mirror self-audit run has nothing for ingest to find. This compounds with BUG-016/BUG-017: even if the startup surfaces were fixed to recognize `.rst`, the file never made it to the destination — the bootstrap step itself is the data-loss gate.
- Regression test (not yet authored): `quality/test_regression.py::CodeReviewRegressionTests::test_bug_018_bootstrap_mirror_preserves_rst_files` — `docs_gathered/notes.rst` and `docs_gathered/cite/virtio.rst` mirrored to the corresponding `reference_docs/` paths.
- Fix sketch: change `PLAINTEXT_EXTENSIONS` in `bootstrap_self_audit_docs.py` to `{".md", ".txt", ".rst"}`. Bonus: factor out the extension set so all three modules (`run_playbook.py`, `reference_docs_ingest.py`, `bootstrap_self_audit_docs.py`) read from one source.

### BUG-019: Phase 1 validator enforces only ~half of the documented 12-check gate
- Primary requirement: REQ-005
- Severity: HIGH
- Source: Adversarial iteration (REQ-005 counterexample; spec-vs-code drift)
- File:line: `bin/run_state_lib.py:61-78` (constants); `bin/run_state_lib.py:294-470` (`_validate_phase1` body); `references/phase1_exploration_guide.md:692-704` (the 12 gate checks)
- Spec basis: `quality/REQUIREMENTS.md:90-99` (REQ-005 COS — mechanical validation aligns with the stronger Phase 2 entry gate)
- Expected behavior: every check in the written Phase 1 gate (12 items at phase1_exploration_guide.md:692-704) has a mechanical analogue in `_validate_phase1`, so the documented "shallow exploration won't pass" contract is enforced.
- Actual behavior: the validator implements roughly 6 of 12 checks. Specific missing enforcements:
  - Check 3 ("Derived Requirements section contains at least one REQ-NNN with file paths and function names") — NO validator code matches `Derived Requirements` or REQ-NNN tokens. A Phase 1 artifact missing the Derived Requirements section passes mechanically.
  - Check 4 second half ("At least 4 [findings] must reference different modules or subsystems") — the validator counts ≥8 findings with file:line citations (line 360) but does not verify multi-module spread. An EXPLORATION.md with 8 findings all citing `bin/run_playbook.py` passes.
  - Check 6 ("≥5 domain-driven failure scenarios" under `## Quality Risks` each with function/file/line/edge-case/explanation) — the validator only checks heading existence; content sub-items are unvalidated.
  - Check 7 ("evaluates all six patterns from exploration_patterns.md") — `exploration_patterns.md` actually defines SEVEN patterns (a separate doc-drift artifact), and the validator counts FULL cells but does not verify the matrix lists every documented pattern. A 3-row all-FULL matrix passes the 3-4 inclusive range without ever mentioning patterns 4-7.
- The contract REQ-005 names ("mechanical validation stays aligned with the stronger Phase 2 entry gate") is structurally broken — alignment exists for ~half the checks. The same "shallow exploration artifact" failure mode the gate was added to catch can still pass.
- Regression test (not yet authored): `quality/test_regression.py::CodeReviewRegressionTests::test_bug_019_phase1_validator_enforces_derived_requirements_and_module_spread` — an EXPLORATION.md that omits `## Derived Requirements` entirely OR has 8 findings all citing one file must fail validation.
- Fix sketch: add a `## Derived Requirements` heading check + `REQ-NNN` regex check (mirroring `_REQ_HEADING_PATTERN` in archive_lib); add a distinct-modules spread check on the file:line citations the validator already extracts; harden the matrix check to verify the FULL+SKIP row count equals the canonical pattern count (6 per spec, or refresh the spec to 7 if Pattern 7 is intended to be in scope).

### BUG-020: Terminal gate's `_BUG_HEADING_RE` only matches digit-only IDs; archive and validator accept alphanumeric+hyphen
- Primary requirement: REQ-006 (corollary surface: the terminal gate that consumes the same BUGS.md the archive renders)
- Severity: MEDIUM
- Source: Adversarial iteration (REQ-006 counterexample on a different surface)
- File:line: `.github/skills/quality_gate/quality_gate.py:286` (`_BUG_HEADING_RE = re.compile(r"^###\s+BUG-(\d+):", re.MULTILINE)`); `.github/skills/quality_gate/quality_gate.py:314-321` (`_split_bug_blocks` consumer); `.github/skills/quality_gate/quality_gate.py:481` (`validate_cardinality_gate` consumer); `bin/archive_lib.py:69` (canonical `[A-Za-z0-9][A-Za-z0-9\-]*` form); `bin/run_state_lib.py:586-589` (Phase 3 validator's matching form)
- Spec basis: `quality/REQUIREMENTS.md:139-150` (REQ-006 COS — canonical heading form counted everywhere)
- Expected behavior: every consumer of the BUGS.md heading set sees the same set of bugs — archive renderer, Phase 3 validator, terminal gate (cardinality / consolidation rationale enforcement). REQ-006 was filed on the archive side; the gate is the other production consumer and must agree.
- Actual behavior: the gate's `_BUG_HEADING_RE` accepts only `BUG-(\d+):` (digits, colon REQUIRED). A `### BUG-007-PARITY: Title` heading — the convention used by the PARITY iteration's bugs, and the same shape as any future `BUG-001-fix` / `BUG-001-fix-2` follow-up — does NOT match. Consequences:
  - `_split_bug_blocks()` returns empty positions for these bugs, so the cardinality gate at line 481 silently skips their `Covers:` entries.
  - A bug ledger with cross-site REQ tagging on hyphen-suffixed IDs (e.g., the `Consolidation rationale:` check at lines 483-489) is never evaluated by the gate, even though both the archive and the Phase 3 validator counted those bugs.
- Regression test (not yet authored): `quality/test_regression.py::CodeReviewRegressionTests::test_bug_020_gate_recognizes_hyphenated_bug_ids` — a BUGS.md with `### BUG-007-PARITY: Title` + Covers list ≥ 2 entries must produce a cardinality check that sees the entry (e.g., emits the missing-rationale FAIL when rationale is absent; passes when present).
- Fix sketch: widen `_BUG_HEADING_RE` to `r"^###\s+BUG-([A-Za-z0-9][A-Za-z0-9\-]*)(?::\s+.+)?\s*$"`, matching `bin/archive_lib.py:69` and `bin/run_state_lib.py:586-589`. Add a cross-module consistency test (similar in spirit to `bin/tests/test_skill_resolution_order.py`'s CANONICAL_ORDER pin) so future BUG-heading-pattern changes have to land on all three regexes simultaneously.
