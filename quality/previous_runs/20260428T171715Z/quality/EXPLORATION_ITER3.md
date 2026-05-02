# Iteration 3 Exploration — `unfiltered` strategy

Date: 2026-04-28
Project: quality-playbook (repo-root self-audit)
Strategy: pure domain-driven, no template / no pattern-matrix / no gate self-check

This iteration ignores the three-stage gated structure and reads the runtime, gate, and audit code with no section template. Findings are a flat list with file:line citations and bug hypotheses. Cross-function traces are noted where they exist.

---

## F-1 — `bin/citation_verifier.py:252` allows path traversal out of the repository root

`verify_citation()` takes `root: Path` and reads `doc_path = Path(root) / source_path`, then `doc_path.read_bytes()` (lines 244-254). `source_path` comes from either the citation record (auditor-supplied) or the `formal_doc` record (manifest-supplied). Neither origin is validated against `root`.

Cross-function trace:
- `bin/reference_docs_ingest.py::_collect()` writes `formal_docs_manifest.json` records with a `source_path` field (project-relative by intent).
- `.github/skills/quality_gate.py::check_citation_layer1()` (and similar callers) loads the manifest and calls `verify_citation(citation, formal_doc, root)` with `root = repo_dir`.
- If the manifest has been edited (or a citation in `quality/spec_audits/...` references `../../etc/passwd`), `Path(root) / "../../etc/passwd"` resolves outside `root` and `read_bytes()` succeeds.

Bug hypothesis: a tampered `formal_docs_manifest.json` or an auditor-supplied citation with a relative path (`..`) or an absolute path can cause the gate to read arbitrary files from the operator's filesystem and surface their contents in error messages (line 259, 265, 275, 286 all interpolate paths into messages). On a CI host the gate could exfiltrate file fragments via the gate log. **Fix shape:** resolve `doc_path` and require `doc_path.resolve().is_relative_to(root.resolve())` before reading.

Severity: **HIGH** (security-relevant; reachable via either auditor output or manifest tampering).

---

## F-2 — `.github/skills/quality_gate.py:824` drops `deep_headings` from `bug_count`

`check_bugs_heading()` returns `(bug_count, bug_ids)` (lines 802-831). When malformed-but-non-deep headings exist alongside correct headings, line 824 sets:

```
bug_count = correct_headings + wrong_headings + bold_headings + bullet_headings
```

It omits `deep_headings`. The earlier sibling branch at line 821 (taken only when `correct_headings == 0 and wrong_headings == 0`) correctly adds `deep_headings`. The asymmetry is real.

Cross-function trace: the returned `bug_count` flows into `check_tdd_sidecar()` (line 3049-3051 caller) as the comparison anchor for per-bug-field counts, into `check_tdd_logs()` (line 953) for log existence, and into manifest cross-checks. A `#### BUG-NNN` heading is FAILed at line 811, but the silently-low `bug_count` then under-counts expected logs / sidecar entries downstream, masking other failures.

Bug hypothesis: a BUGS.md with `#### BUG-NNN` formatting lowers the threshold every downstream check uses. The gate emits the heading-format FAIL, but downstream PASSes claim coverage that does not exist for the deep-formatted bugs.

Severity: **MEDIUM** (downstream gate decisions taken against a wrong total).

---

## F-3 — `.github/skills/quality_gate.py:878` per-bug field count uses `>=`, accepting excess sidecar entries

In `check_tdd_sidecar()`, the per-bug field check at line 877-883 is:

```
fcount = count_per_bug_field(bugs_list, field)
if fcount >= bug_count:
    pass_(...)
elif fcount > 0:
    warn(...)
else:
    fail(...)
```

`>=` instead of `==` means: if BUGS.md declares 10 bugs but `tdd-results.json` has 11 bug entries (each with the field), the gate PASSes. Cross-function trace: `bug_count` is the BUGS.md heading count from F-2's caller; `bugs_list` is the JSON array from the sidecar. The two are produced by independent steps (Phase 3 review writes BUGS.md; Phase 5 TDD finalization writes the sidecar). Drift in either direction is possible — and only the under-count direction is policed.

Bug hypothesis: a stale or merged sidecar carrying bugs from a previous run can pass while contradicting the live BUGS.md. The gate cannot detect "sidecar carries phantom bug entries" — exactly the failure mode that benchmarking iterations are most likely to cause. **Fix shape:** require equality, or at minimum WARN on `fcount > bug_count` so the operator sees the divergence.

Severity: **MEDIUM** (silent acceptance of a real consistency failure).

---

## F-4 — `.github/skills/quality_gate.py:897-901` validates summary keys but never their values

The summary-keys loop in `check_tdd_sidecar()`:

```
for skey in ["total", "verified", "confirmed_open", "red_failed", "green_failed"]:
    if skey in summary:
        pass_(...)
    else:
        fail(...)
```

It checks key presence only. There is no check that:

- `total == len(bugs_list)`
- `verified + confirmed_open + red_failed + green_failed <= total` (or `== total`)
- values are non-negative integers (a `total: -3` would PASS)
- the verdict count and these summary numbers are mutually consistent (e.g., `verified` should equal the count of `bugs[i].verdict == "TDD verified"`)

Bug hypothesis: a sidecar with `summary.total = 100` and `len(bugs) = 5` PASSes the gate. The summary section's purpose is to report per-run totals; its values are unenforced and operators reading the gate output may take them as ground truth.

Severity: **MEDIUM** (failure mode: misleading summary stats reported as verified).

---

## F-5 — `.github/skills/quality_gate.py:827-829` collects `bug_ids` from the entire BUGS.md body, not from headings

After counting headings, the function extracts canonical IDs with:

```
raw = re.findall(r"BUG-(?:[HML][0-9]+|[0-9]+)", bugs_content)
filtered = [b for b in raw if re.fullmatch(...)]
bug_ids = sorted(set(filtered))
```

`bugs_content` is the entire BUGS.md file. Casual references in body text — e.g., "duplicates BUG-099 from a prior run" or "see BUG-005 for context" — are pulled into `bug_ids`.

Cross-function trace: `bug_ids` is returned to the caller (line 3050) and then passed into `check_tdd_logs()` (line ~953), which iterates `for bug_id in bug_ids: expect quality/results/{bug_id}.red.log`. Every casual mention demands its own red log.

Bug hypothesis: an editor mentioning a previously-closed bug in BUGS.md prose causes `check_tdd_logs` to FAIL with "missing red-phase log for BUG-099". This is a Type I error — the gate flags an issue that is not a real coverage gap. The current run's BUGS.md happens not to mention any non-heading IDs, but the regression test that documents the iteration cycle (BUG-006 references prior versions, etc.) makes this brittle.

Severity: **LOW** (false-positive risk; not a missed bug, but a misleading FAIL once authoring conventions evolve).

---

## F-6 — `.github/skills/quality_gate.py:1562` emits unconditional `pass_()` after possibly-failing run-metadata loop

`check_run_metadata()` (lines 1538-1562):

```
for path in matches:
    ...
    data = load_json(Path(path))
    if data is None:
        fail(...)
        continue
    for field in required_fields:
        if not data.get(field):
            fail(...)
pass_("run-metadata JSON present")
```

The terminal `pass_("run-metadata JSON present")` runs unconditionally after the for-loop, even when every iteration FAILed. The function therefore reports both `FAIL` (parse error or missing field) and `PASS` (file present) for the same artifact.

Bug hypothesis: the gate's per-check counters get an artificially-inflated PASS for an artifact whose validation actually failed. Operators reading the gate log see `[Run Metadata] PASS run-metadata JSON present` directly above `FAIL run-metadata missing or empty field 'model'`. The PASS is technically true ("the file exists") but it masks the FAIL when the operator scans the summary line. **Fix shape:** only emit PASS when no FAIL was recorded for any path.

Severity: **LOW** (cosmetic / operator-confusion class, not a missed defect).

---

## F-7 — `bin/council_semantic_check.py:319` greedy regex for JSON-array extraction

`_JSON_ARRAY_PATTERN = re.compile(r"\[[\s\S]*\]")` is greedy. `_extract_first_json_array()` first tries to parse the entire stripped payload, and only falls back to the regex when the payload doesn't start with `[`. The fallback search greedily captures from the first `[` to the last `]` in the entire response.

Cross-function trace:
- `parse_member_response()` (line 252) calls `_extract_first_json_array(text)`.
- If a model wraps the array in prose or emits a fenced code block plus prose plus another bracketed token, the greedy capture grabs both the JSON array and the trailing prose.
- `json.loads(match.group(0))` raises, the function returns `None`, `parse_member_response` raises `SemanticCheckError`, and `write_semantic_check()` is never reached for that auditor.

Bug hypothesis: the parser is fragile for any model output that mixes prose with the JSON array. The error message "member response does not contain a JSON array" (raised when `_extract_first_json_array` returns None) misattributes the cause — the array IS present, but the greedy capture concatenated extra trailing text. The non-greedy `\[[\s\S]*?\]` (or a balanced-bracket parser) would pick the first valid array.

Severity: **LOW–MEDIUM** (silent failure of an auditor; manifests with `reviews[]` shorter than expected even though the auditor produced valid output).

---

## F-8 — Empty `reviews[]` in `quality/citation_semantic_check.json` is ambiguous

`bin/council_semantic_check.py::write_semantic_check()` writes the manifest with `reviews=[]` in two semantically distinct cases:

1. **Spec Gap run** (`collect_tier_12_reqs()` returns `[]`, no auditor work to do — line ~456 calls `write_semantic_check(repo, [])` directly). This is a legitimate zero-review state.
2. **All auditors unavailable** (every member fails, no review entries collected). This is a partial-failure state that the Council Layer-2 contract should flag, since SKILL.md §"Phase 4" specifies "one prompt per reviewer, structured per-REQ verdicts for every Tier 1/2 citation".

Cross-function trace:
- `collect_tier_12_reqs()` → `plan_prompts()` → `write_semantic_check()` with `reviews=[]` (Spec Gap path).
- `run()` per-auditor loop → `write_semantic_check()` with `reviews=[]` when nothing was collected.
- Gate's invariant #17 (schemas.md §10) reads `reviews[]` and treats them as equivalent.

Bug hypothesis: the operator cannot tell from the JSON shape alone whether the council ran with no work to do or the council was fully unavailable. The current PROGRESS.md note "this is a Spec Gap run with zero Tier 1/2 requirements" is hand-authored documentation, not enforced by the schema. **Fix shape:** add a top-level field like `reason: "spec_gap"` vs `reason: "auditors_unavailable"`, or count the prompts attempted vs. completed and surface that ratio.

Severity: **MEDIUM** (legitimate audit failure can hide behind a Spec Gap-shaped manifest).

---

## F-9 — `bin/run_playbook.py:2964` mixes naive local time with UTC across one run's artifacts

The runner generates the run timestamp at line 2964 and 3103:

```
run_timestamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
```

`datetime.now()` returns naive local time. Meanwhile `_iso_utc_now()` (line 2412-2415) returns `datetime.now(timezone.utc)` for PROGRESS.md heartbeats and run finalization. Both timestamps appear in the same artifact set:

- Log filename uses local time: `quality-playbook-1.5.3-playbook-20260428-102513.log`.
- `## Iteration: ... started/complete` heartbeat in `quality/PROGRESS.md` uses `2026-04-28T<UTC>:Z`.
- `quality/results/run-YYYY-MM-DDTHH-MM-SS.json` filename pattern (gate enforces `run-\d{4}-...\.json`) — the gate accepts any time literal in the filename, but the spec sample at SKILL.md:182 pairs ISO 8601 with `Z`-suffix UTC.

Bug hypothesis: an operator correlating the log filename (`20260428-102513`) with the heartbeat timestamp (`2026-04-28T17:25:13Z`) on a UTC-7 machine sees a 7-hour discrepancy. Across DST boundaries the offset shifts mid-run. The gate cannot detect the inconsistency. **Fix shape:** generate the runtime timestamp from `datetime.now(timezone.utc)` and format it identically.

Severity: **MEDIUM** (operator confusion, multi-run correlation broken; benign for single-run analysis).

---

## F-10 — `bin/run_playbook.py:2964` 1-second timestamp resolution allows filename collisions

Same site as F-9. `"%Y%m%d-%H%M%S"` resolves to one second. Two `run_playbook.py` invocations starting in the same second (CI matrix, `xargs -P`, parallel benchmark targets, scripted retries) generate identical `timestamp` strings.

Cross-function trace: `timestamp` flows into log filenames (line ~3120 area) and into archive directory naming (`bin/archive_lib.py::_seed_run` uses `run-{timestamp}` keys for archive collation). When two runs collide on the same second, the second run overwrites the first run's log file (open mode `"w"`) and the archive's `run-*` key clashes.

Bug hypothesis: in benchmark sweeps the runner may stomp on its own logs. Today the parallel-mode helpers serialize through `run_one()` enough to make this rare; once the user runs two `run_playbook.py` processes from two terminals within one second, collisions are silent. **Fix shape:** include sub-second precision (e.g., `"%Y%m%d-%H%M%S.%f"` truncated to milliseconds) or a 4-char random suffix.

Severity: **LOW–MEDIUM** (rare today, easy to trip in CI tomorrow).

---

## F-11 — `bin/reference_docs_ingest.py::_iter_candidates()` follows symlinks via `is_file()`

`_iter_candidates()` walks `reference_docs/` (or the `cite/` subtree) with `root.rglob("*")` and filters with `p.is_file()`. On POSIX, `Path.is_file()` follows symlinks. A symlink under `reference_docs/cite/` pointing to `/etc/passwd`, a sibling project's source, or a credentials file is happily ingested.

Cross-function trace:
- `_iter_candidates()` → `_collect()` → `_build_record()` (which hashes the file with sha256 and stores `source_path` set to the symlink path relative to root, but reads bytes from the symlink target).
- `formal_docs_manifest.json` then carries a `source_path` that points at the symlink (project-relative) and a `document_sha256` computed from the *target* file's bytes.
- `bin/citation_verifier.py::verify_citation()` later opens `Path(root) / source_path` (the symlink), follows it, and re-hashes. Sha matches today, but if the symlink target rotates (log file, daily file, etc.), the manifest goes stale silently.

Bug hypothesis: ingest accepts symlinks without sanitizing. Combined with F-1 (`Path(root) / source_path` accepting `..`), an attacker who can place a file in `reference_docs/cite/` can cause arbitrary-file disclosure into the citation manifest. **Fix shape:** skip symlinks in `_iter_candidates`, or resolve and require the resolved path to stay within `root`.

Severity: **MEDIUM** (compounds with F-1; on its own, gives non-deterministic manifest content).

---

## Domain-knowledge questions (answered inline above)

- **API surface inconsistencies between similar methods?** The two arms of `check_bugs_heading()` (lines 821 vs 824) compute `bug_count` with different summands. The two `_extract_first_json_array()` parse paths (fast / fallback) tolerate different shapes silently. Both surfaced findings (F-2, F-7).
- **Ad-hoc string parsing of structured formats?** The greedy-regex JSON-array extraction (F-7) is the worst offender. The `bug_ids` regex over the whole BUGS.md file (F-5) is the second.
- **Inputs a domain expert would try?** Symlinks under `reference_docs/cite/`, absolute / `..`-prefixed `source_path` values in citation records, BUGS.md prose mentioning prior bug IDs, sub-second-clock CI invocations, model responses with prose plus JSON-array. All produced findings.
- **Metadata or configuration values silently wrong?** The summary block of `tdd-results.json` (F-4) and the empty-`reviews[]` ambiguity (F-8) are both shape-valid but value-misleading. The local-vs-UTC mix (F-9) is metadata that drifts within a single run.

---

## Candidate Bugs for Phase 2 (net-new in Iteration 3)

### BUG-011 candidate — `verify_citation()` allows path traversal outside the repo root
- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `bin/citation_verifier.py:244-266` (and downstream callers in `.github/skills/quality_gate.py`).
- **Severity guess:** HIGH

### BUG-012 candidate — gate's `bug_count` drops `#### BUG-NNN` headings from the downstream coverage anchor
- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `.github/skills/quality_gate.py:802-829` (asymmetric branches at lines 821 vs 824).
- **Severity guess:** MEDIUM

### BUG-013 candidate — TDD sidecar per-bug field check accepts excess entries via `>=`
- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `.github/skills/quality_gate.py:875-883`.
- **Severity guess:** MEDIUM

### BUG-014 candidate — TDD sidecar `summary` values are checked for presence but never sanity
- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `.github/skills/quality_gate.py:894-901`.
- **Severity guess:** MEDIUM

### BUG-015 candidate — gate's `bug_ids` is collected from the whole BUGS.md body, inflating expected red-log set
- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `.github/skills/quality_gate.py:826-831` flowing into `check_tdd_logs()` at ~line 953.
- **Severity guess:** LOW

### BUG-016 candidate — `check_run_metadata` emits `pass_("run-metadata JSON present")` after possibly-failing per-file validation
- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `.github/skills/quality_gate.py:1538-1562`.
- **Severity guess:** LOW

### BUG-017 candidate — greedy `\[[\s\S]*\]` regex breaks JSON-array extraction from mixed-prose model responses
- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `bin/council_semantic_check.py:319-343`.
- **Severity guess:** LOW–MEDIUM

### BUG-018 candidate — empty `reviews[]` in `citation_semantic_check.json` is ambiguous between Spec Gap and auditor failure
- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `bin/council_semantic_check.py::write_semantic_check()` plus the gate's invariant on the manifest shape.
- **Severity guess:** MEDIUM

### BUG-019 candidate — runner timestamps mix naive local time (filenames) with UTC (PROGRESS.md heartbeat)
- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `bin/run_playbook.py:2964`, `bin/run_playbook.py:3103`, `bin/run_playbook.py:2412-2415`.
- **Severity guess:** MEDIUM

### BUG-020 candidate — `"%Y%m%d-%H%M%S"` 1-second resolution allows two parallel runs to overwrite each other's logs
- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `bin/run_playbook.py:2964`, `bin/run_playbook.py:3103`, archive collation in `bin/archive_lib.py:358`.
- **Severity guess:** LOW–MEDIUM

### BUG-021 candidate — `reference_docs_ingest._iter_candidates()` ingests symlinks via `is_file()`, breaking project-tree boundary
- **Source:** [Iteration 3: unfiltered]
- **Evidence:** `bin/reference_docs_ingest.py::_iter_candidates()` (uses `p.is_file()` with no `is_symlink()` filter).
- **Severity guess:** MEDIUM

---

## Demoted candidates (this iteration)

### DC-003 — `_append_iteration_heartbeat` corrupts PROGRESS.md when the file lacks a trailing newline
- **Source:** [Iteration 3: unfiltered]
- **Dismissal reason:** the call sites (lines 2639-2642 and 2673-2677) prefix the line with `\n`, so the appended block always starts on its own line regardless of the file's prior trailing-newline state.
- **Code location:** `bin/run_playbook.py:2388-2410` and call sites at 2639-2677.
- **Re-promotion criteria:** show a call site that passes a non-newline-prefixed line, or a path where `progress_path` is overwritten via mode other than `"a"`.
- **Status:** FALSE POSITIVE [Iteration 3: unfiltered]

### DC-004 — `--iterations` early-stop ignores user's explicit list
- **Source:** [Iteration 3: unfiltered]
- **Dismissal reason:** `_mark_iterations_explicit(argv)` is called at `bin/run_playbook.py:450` and stores its result on `args._iterations_explicit`. Tests in `bin/tests/test_iterations_explicit.py` exercise the parsing for both split and combined token forms.
- **Code location:** `bin/run_playbook.py:414-450`, `bin/run_playbook.py:2690`, `bin/run_playbook.py:2755`.
- **Re-promotion criteria:** demonstrate a CLI shape (e.g., a future flag spelling) that bypasses `_mark_iterations_explicit` so the early-stop fires despite an explicit user list.
- **Status:** FALSE POSITIVE [Iteration 3: unfiltered]
