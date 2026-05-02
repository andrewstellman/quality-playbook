# Iteration 5 Exploration — `adversarial` strategy

Date: 2026-04-28
Project: quality-playbook (repo-root self-audit)
Strategy: re-investigate dismissed / demoted findings with a deliberately lower evidentiary bar; challenge SATISFIED verdicts that rest on thin evidence

This iteration challenges the previous run's conclusions. Iterations 3 (unfiltered) and 4 (parity) each enumerated several candidate findings (BUG-011 through BUG-027) that the orchestrator's downstream Phase 2–5 cycle reported as "0 net-new" — i.e., the candidates were never promoted to `quality/BUGS.md`. Pool A targets those de-facto demoted candidates. Pool B targets the formal Demoted Candidates Manifest (DC-001 through DC-007). Pool C challenges Pass 2 SATISFIED verdicts in the Phase 3 code review.

Per `references/iteration.md`: the adversarial strategy uses a deliberately lower evidentiary bar than earlier strategies. A code-path trace showing observable semantic drift from a documented contract is sufficient to re-confirm — no runtime crash required. Permissive behavior is not automatically a design choice; check the spec, docs, or API contract.

---

## Pool A — re-investigate unpromoted iteration candidates

Each finding below was re-investigated by reading the cited code independently of the previous iteration's analysis. Each ends with an explicit CONFIRMED, NEEDS-EVIDENCE, or FALSE-POSITIVE determination.

### A-1 — BUG-011 candidate: `verify_citation()` allows path traversal outside the repo root

- **Source:** Iteration 3 (unfiltered), pending Phase 2 promotion.
- **Cited code:** `bin/citation_verifier.py:244-266`.
- **Fresh re-read:**
  ```python
  source_path = citation.get("document") or formal_doc.get("source_path")
  if not source_path:
      return VerificationResult(ok=False, error_code=ERROR_DOCUMENT_NOT_FOUND, ...)
  doc_path = Path(root) / source_path
  try:
      document_bytes = doc_path.read_bytes()
  ```
  No `doc_path.resolve().is_relative_to(Path(root).resolve())` check. No filtering of absolute paths or `..` segments. `source_path` flows from two trust boundaries:
  1. `quality/formal_docs_manifest.json` — written by `bin/reference_docs_ingest.py`. A tampered manifest can carry any `source_path` value.
  2. The `citation` dict — produced by Council member responses (auditors). The Phase 4 prompt asks each auditor to supply citation records; an auditor returning `{"document": "../../etc/passwd"}` would be honored by `verify_citation`.
- **Adversarial determination:** **CONFIRMED.** `Path(root) / "/etc/passwd"` evaluates to `/etc/passwd` (Python `Path` `__truediv__` with an absolute right-hand operand discards the left). `Path(root) / "../../etc/passwd"` resolves outside `root` after `read_bytes()`. The verifier becomes an inadvertent file-read primitive when manifest or auditor input is hostile. SKILL.md treats `formal_docs_manifest.json` as a gate-validated artifact (line 94, line 1865-1868 of the gate); the trust model does not warn about path-traversal hostile inputs.
- **Severity:** HIGH (security boundary).
- **Re-promotion outcome:** Promoted to BUG-011 in this iteration (see `quality/BUGS.md` and `quality/test_regression.py`). Adds REQ-011 (Citation verifier must enforce repository-root containment).

### A-2 — BUG-012 candidate: gate `bug_count` drops `deep_headings` in the asymmetric branch

- **Source:** Iteration 3 (unfiltered), pending Phase 2 promotion.
- **Cited code:** `.github/skills/quality_gate.py:802-829`.
- **Fresh re-read:**
  - Line 802: `bug_count = correct_headings`.
  - Line 821 (one branch): `bug_count = wrong_headings + deep_headings + bold_headings + bullet_headings`.
  - Line 824 (other branch): `bug_count = correct_headings + wrong_headings + bold_headings + bullet_headings` — **omits `deep_headings`**.
  The two else-branch arms differ in whether `deep_headings` participates in the rebound `bug_count`. Both arms trigger after the FAIL diagnostics, so the gate already FAILs in this case — but `bug_count` is then propagated into `check_tdd_logs()` (line ~953) and `check_tdd_sidecar()` (line 834), where it is compared against `bug_ids` (line 827, regex over the whole BUGS.md body). A mismatch produces inconsistent diagnostics: the gate reports "expected N TDD logs" against a `bug_count` that may not match the regex-extracted ID set.
- **Adversarial determination:** **CONFIRMED.** The asymmetry is real and observable in error output. Severity is bounded because both branches also FAIL on the heading-format check upstream — but the fix is one line and the diagnostic confusion is real.
- **Severity:** MEDIUM (diagnostic-only; gate already FAILs).
- **Re-promotion outcome:** Adversarial-confirmed candidate. Logged in EXPLORATION_MERGED.md for the next iteration's Phase 2 promotion. Not promoted in this iteration to keep the adversarial scope tight; the bug is gate-internal arithmetic that does not change pass/fail outcomes today.

### A-3 — BUG-013 candidate: TDD sidecar per-bug field check uses `>=` instead of `==`

- **Source:** Iteration 3 (unfiltered), pending Phase 2 promotion.
- **Cited code:** `.github/skills/quality_gate.py:875-883`.
- **Fresh re-read:**
  ```python
  for field in ["id", "requirement", "red_phase", "green_phase",
                "verdict", "fix_patch_present", "writeup_path"]:
      fcount = count_per_bug_field(bugs_list, field)
      if fcount >= bug_count:
          pass_(f"per-bug field '{field}' present ({fcount}x)")
      elif fcount > 0:
          warn(f"per-bug field '{field}' found {fcount}x, expected {bug_count}")
      else:
          fail(f"per-bug field '{field}' missing entirely")
  ```
  `fcount >= bug_count` accepts excess. A stale `tdd-results.json` carrying 12 bug entries against a current `BUGS.md` of 10 bugs PASSes this check — operator never sees the staleness.
- **Adversarial determination:** **CONFIRMED.** This is a clear over-permissive comparator. The contract is "per-bug field is present for every bug in BUGS.md" — `==` would express that; `>=` allows silent accumulation of stale bug rows. Real-world manifestation: a BUGS.md edit that drops a bug between runs leaves the older sidecar passing the field-presence check.
- **Severity:** MEDIUM.
- **Re-promotion outcome:** Adversarial-confirmed candidate. Logged in EXPLORATION_MERGED.md.

### A-4 — BUG-014 candidate: TDD sidecar `summary` values checked for presence but not value

- **Source:** Iteration 3 (unfiltered), pending Phase 2 promotion.
- **Cited code:** `.github/skills/quality_gate.py:894-901`.
- **Fresh re-read:**
  ```python
  summary = data.get("summary") if isinstance(data, dict) else None
  if not isinstance(summary, dict):
      summary = {}
  for skey in ["total", "verified", "confirmed_open", "red_failed", "green_failed"]:
      if skey in summary:
          pass_(f"summary has '{skey}'")
      else:
          fail(f"summary missing '{skey}' count")
  ```
  Only key presence is checked. Values are never validated. A sidecar with `summary: {total: 10, verified: -5, confirmed_open: 99, red_failed: -1, green_failed: -1}` PASSes this entire block. No invariant is enforced (`total >= 0`, `verified + confirmed_open + red_failed + green_failed <= total`, all values non-negative).
- **Adversarial determination:** **CONFIRMED.** Schema-shape validation without value sanity is a known anti-pattern. The contract intent is observable totals; the implementation just checks the keys exist.
- **Severity:** MEDIUM.
- **Re-promotion outcome:** Adversarial-confirmed candidate.

### A-5 — BUG-015 candidate: `bug_ids` regex over whole BUGS.md inflates expected red-log set

- **Source:** Iteration 3 (unfiltered), pending Phase 2 promotion.
- **Cited code:** `.github/skills/quality_gate.py:826-831`.
- **Fresh re-read:**
  ```python
  raw = re.findall(r"BUG-(?:[HML][0-9]+|[0-9]+)", bugs_content)
  filtered = [b for b in raw if re.fullmatch(r"BUG-(?:[HML][0-9]+|[0-9]+)", b)]
  bug_ids = sorted(set(filtered))
  ```
  Regex runs over the entire BUGS.md body. Any prose mention — "this regression touches the same area as BUG-099 from a prior run" — adds `BUG-099` to `bug_ids`. The downstream `check_tdd_logs()` then expects a `BUG-099.red.log` and reports a missing-log FAIL.
- **Adversarial determination:** **CONFIRMED.** Reproducible: append a sentence "Compare with BUG-099 (historical)" to BUGS.md, re-run the gate, observe a FAIL for the missing red log. The regex needs to anchor on the heading lines (`### BUG-NNN`) not the full body.
- **Severity:** LOW (manifests only when prose accidentally mentions a non-existent BUG ID).
- **Re-promotion outcome:** Adversarial-confirmed candidate.

### A-6 — BUG-016 candidate: `check_run_metadata()` emits `pass_("run-metadata JSON present")` after potentially-failing per-file validation

- **Source:** Iteration 3 (unfiltered), pending Phase 2 promotion.
- **Cited code:** `.github/skills/quality_gate.py:1538-1562`.
- **Fresh re-read (lines visible in current gate log):** The terminal `pass_("run-metadata JSON present")` runs after the per-file loop. If a parse error or missing field caused a `fail(...)` inside the loop, the same artifact accumulates both a FAIL and a PASS. The gate's textual diagnostic is contradictory.
- **Adversarial determination:** **CONFIRMED** as a diagnostic artifact (the same artifact gets both FAIL and PASS). Because the gate aggregates FAILs disjunctively (any FAIL → gate FAIL), the contradictory PASS is informational drift, not a missed-FAIL.
- **Severity:** LOW.
- **Re-promotion outcome:** Adversarial-confirmed candidate.

### A-7 — BUG-018 candidate: empty `reviews[]` ambiguous between Spec Gap and total auditor failure

- **Source:** Iteration 3 (unfiltered), reinforced by Iteration 4 C-5.
- **Cited code:** `bin/council_semantic_check.py:451-457` (Spec Gap path) and `:393-411` (`write_semantic_check`).
- **Fresh re-read:**
  ```python
  if not reqs:
      _clear_prompt_files(prompts_dir)
      path = write_semantic_check(repo, [])
      return ([], path)
  ```
  Spec Gap calls `write_semantic_check(repo, [])` with an empty review list. The same call shape is used when assembly receives no auditor responses at all — both produce `reviews=[]` in `quality/citation_semantic_check.json`. The gate's invariant #17 is satisfied by the file's existence, not by the distinction between "no Tier 1/2 REQs to review" and "all auditors unavailable."
- **Adversarial determination:** **CONFIRMED.** Distinct outcomes share an output shape. The fix is a top-level `mode` field in the manifest (`"spec_gap"` vs `"council_outage"` vs `"completed"`) so consumers can distinguish them.
- **Severity:** MEDIUM (council outage hides behind Spec Gap shape).
- **Re-promotion outcome:** Adversarial-confirmed candidate.

### A-8 — BUG-021 candidate: `_iter_candidates()` follows symlinks via `is_file()`

- **Source:** Iteration 3 (unfiltered), pending Phase 2 promotion.
- **Cited code:** `bin/reference_docs_ingest.py:90-93`.
- **Fresh re-read:**
  ```python
  def _iter_candidates(root: Path) -> Iterable[Path]:
      if not root.exists():
          return []
      return sorted(p for p in root.rglob("*") if p.is_file())
  ```
  `Path.is_file()` follows symlinks (returns True if the symlink target is a regular file). `Path.rglob("*")` follows symlinked directories by default in Python 3 (the `follow_symlinks` parameter was added to `rglob` only in Python 3.13; this codebase supports earlier versions and does not use it). A symlink at `reference_docs/cite/foo.txt → /etc/passwd` is resolved and ingested into `formal_docs_manifest.json`, where its bytes become Tier 1 citable content. The downstream Layer 1 verifier (re-investigated in A-1) then re-reads it via the same path-traversal pathway.
- **Adversarial determination:** **CONFIRMED.** The boundary is missing. A correct implementation calls `p.is_symlink()` first and either skips symlinks or resolves them and verifies `resolved.is_relative_to(root.resolve())`.
- **Severity:** MEDIUM (filesystem boundary; pairs with A-1 to form a privileged-read chain).
- **Re-promotion outcome:** Adversarial-confirmed candidate. Pairs with A-1; the BUG-011 fix should consider both the verifier and the ingest boundary.

### A-9 — BUG-022 candidate: phase prompts split the PROGRESS.md authorship contract

- **Source:** Iteration 4 (parity), F-1.
- **Cited code:** `bin/run_playbook.py:749, 905, 961, 1080, 1107, 1127-1134`.
- **Fresh re-read:**
  - `phase2_prompt`–`phase6_prompt` each say `"use the checkbox format - [x] Phase N - <name> — do NOT switch to a table"`. None of them mentions the orchestrator-vs-iteration boundary.
  - `iteration_prompt` (the only prompt that does teach the boundary) says: `"Any updates to quality/PROGRESS.md must keep the existing phase tracker in checkbox format ... The orchestrator appends ## Iteration: <strategy> started/complete sections itself; iteration work should not touch the existing phase tracker lines."`
  - A phase prompt invoked during an iteration (e.g., gap-iteration's Phase 3 review) does not receive the orchestrator-appends rule. A phase agent could legitimately rewrite an iteration heartbeat block while believing it was honoring the checkbox-format rule.
- **Adversarial determination:** **CONFIRMED.** Contract drift between prompts. Fix is mechanical — copy the orchestrator-appends-iteration-sections sentence into each phase-prompt's PROGRESS.md guidance block.
- **Severity:** LOW–MEDIUM (manifests only in multi-agent runs that interleave iteration heartbeats with phase work).
- **Re-promotion outcome:** Adversarial-confirmed candidate.

### A-10 — BUG-023 candidate: Phase 5 prompt does not enumerate verdict / recommendation closed-sets

- **Source:** Iteration 4 (parity), F-2 (separate from BUG-024).
- **Cited code:** `bin/run_playbook.py:1060` (Phase 5) vs `bin/run_playbook.py:948-949` (Phase 4).
- **Fresh re-read:**
  - Phase 4 prompt (line 949): `"Every entry must have req_id, verdict (supports|overreaches|unclear), and reasoning."` — closed-set inline.
  - Phase 5 prompt (line 1060): `"Generate sidecar JSON: quality/results/tdd-results.json and quality/results/integration-results.json (schema_version "1.1", canonical fields: id, requirement, red_phase, green_phase, verdict, fix_patch_present, writeup_path)."` — names `verdict` but **does not enumerate** `{"TDD verified", "red failed", "green failed", "confirmed open", "deferred"}` (per `SKILL.md:160-161`). Also does not enumerate `recommendation ∈ {"SHIP", "FIX BEFORE MERGE", "BLOCK"}` for `integration-results.json` (per `SKILL.md:178`).
  - Result: a Phase 5 sub-agent can write `verdict: "passed"` or `recommendation: "DEPLOY"` without violating any rule it was told. The terminal gate would catch the bad value (gate has `recommendation 'BLOCK' is canonical` check), but the loop wastes a phase round-trip.
- **Adversarial determination:** **CONFIRMED.** Phase 4 inline-enumerates; Phase 5 does not. The asymmetry is observable and one-line to fix.
- **Severity:** MEDIUM (catch-late bugs are more expensive than inline guidance).
- **Re-promotion outcome:** Adversarial-confirmed candidate.

### A-11 — BUG-025 candidate: gate-validated JSON manifests written non-atomically

- **Source:** Iteration 4 (parity), F-3.
- **Cited code:** `bin/council_semantic_check.py:407-410`, `bin/reference_docs_ingest.py:296-299`, `bin/skill_derivation/pass_d.py:401-406`.
- **Fresh re-read:**
  - `bin/council_semantic_check.py:407-410`: `path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")` — direct write.
  - `bin/reference_docs_ingest.py:296-299`: `out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")` — direct write.
  - `bin/skill_derivation/pass_d.py:401-406`: `.tmp` + `os.replace()` atomic rename pattern (sibling helper).
  Both top-level gate-validated manifests skip the atomic-write pattern that an internal Phase 2 helper already uses. A SIGTERM / SIGKILL / kernel panic mid-write leaves a half-written file. Reproducible with `kill -9` against the runner during ingest.
- **Adversarial determination:** **CONFIRMED.** The drift is internal to this codebase (the atomic pattern exists in pass_d.py). The fix is mechanical — adopt `.tmp` + `os.replace()` in both writers.
- **Severity:** LOW–MEDIUM.
- **Re-promotion outcome:** Adversarial-confirmed candidate.

### A-12 — BUG-024 candidate: Phase 2 entry contract enforced by four enforcers covering different subsets

- **Source:** Iteration 4 (parity), F-2.
- **Note:** This candidate overlaps with BUG-002 (already confirmed) on the runtime-gate slice. Adversarial re-read confirms the four-way spread is a separate parity bug — the runtime gate, mechanical contract file, terminal gate, and SKILL.md spec each cover different non-nesting subsets. Criteria 9-12 (content-depth checks) are silently never enforced by any mechanical surface; they live only in the spec.
- **Adversarial determination:** **CONFIRMED** as a parity gap distinct from BUG-002. BUG-002 fixes the runtime gate's slice; this candidate is the four-way spread.
- **Severity:** MEDIUM.
- **Re-promotion outcome:** Adversarial-confirmed candidate.

---

## Pool B — re-investigate the formal Demoted Candidates Manifest

For each DC, the re-promotion criterion is checked against the current code state.

### DC-001: heartbeat rewrites phase tracker — **status unchanged**

Re-read `bin/run_playbook.py:2388-2410`. `_append_iteration_heartbeat` opens `progress_path` in mode `"a"` (append-only) and writes `line + "\n"`. Both call sites at `:2639-2642` and `:2673-2677` prefix the line with `\n`. The function cannot rewrite or truncate the existing tracker. Re-promotion criterion not met. **FALSE POSITIVE — confirmed in adversarial re-read.**

### DC-002: generic orchestrator drops nested Copilot path — **status unchanged**

Re-read `agents/quality-playbook.agent.md:37-45`. All four documented paths are listed in canonical order. Re-promotion criterion not met. **FALSE POSITIVE — confirmed in adversarial re-read.**

### DC-003: heartbeat needs trailing newline — **status unchanged**

Re-read `bin/run_playbook.py:2388-2410` and the two call sites. Each call prefixes the heartbeat line with `\n`, and the helper writes `line + "\n"`. Append-mode open with `mkdir(parents=True, exist_ok=True)` covers the missing-file case. Re-promotion criterion not met. **FALSE POSITIVE — confirmed in adversarial re-read.**

### DC-004: `--iterations` early-stop ignores explicit list — **status unchanged**

Re-read `bin/run_playbook.py:414-450, 2690, 2755` and `bin/tests/test_iterations_explicit.py`. `_mark_iterations_explicit(argv)` is called at parse time; both split (`--strategy adversarial`) and combined (`--strategy=parity,adversarial`) forms set `args._iterations_explicit = True`. The early-stop logic at `:2690` and `:2755` checks this flag before short-circuiting on zero gain. Re-promotion criterion not met. **FALSE POSITIVE — confirmed in adversarial re-read.**

### DC-005: PID file lifecycle drift — **status unchanged**

Re-read `bin/run_playbook.py:2826-2833, 3007-3008, 3017-3018`. `write_pid_file()` is invoked only from the parallel dispatcher path. The sequential dispatcher calls `run_one()` directly without writing a PID file. Sequential mode does not create a PID file, so it cannot leak one. Re-promotion criterion not met. **FALSE POSITIVE — confirmed in adversarial re-read.**

### DC-006: manifest `skill_version` omission — **status unchanged**

Re-read `SKILL.md:1091-1103, 138-178` and the writers at `bin/council_semantic_check.py:393-405` / `bin/reference_docs_ingest.py:284-299`. Manifest wrapper convention (§1.6) requires `schema_version` + `generated_at` only. Sidecars (§4.x) require `schema_version` + `skill_version`. The two writers correctly follow the manifest convention. Re-promotion criterion not met. **FALSE POSITIVE — confirmed in adversarial re-read.**

### DC-007: iteration ask-user gating diverges — **status unchanged**

Re-read `agents/quality-playbook.agent.md:106` and `agents/quality-playbook-claude.agent.md:88`. Both agents instruct the orchestrator to ask the user before running iterations. Wording differs; contract is the same. Re-promotion criterion not met. **FALSE POSITIVE — confirmed in adversarial re-read.**

---

## Pool C — challenge SATISFIED verdicts in the Phase 3 code review

### REQ-001 SATISFIED verdict — challenged, sustained with caveats

- **Pass 2 evidence (Phase 3 review):** `quality/mechanical/skill_entry_hashes.txt:1-2` — both entry points hash to `46351a7d84fc6255c230eb9c89ded91680a28aa147f47168684838c849b7e421`.
- **Adversarial inspection:** the mechanical contract hashes only the two existing install paths in this checkout (repo-root `SKILL.md` and `.github/skills/SKILL.md`, where the latter is a symlink to the former — `ls -la` shows `lrwxr-xr-x ... .github/skills/SKILL.md -> ../../SKILL.md`). The two paths trivially hash-match because they are byte-identical via the symlink. SKILL.md:49-58 advertises four documented install paths; the other two (`.claude/skills/quality-playbook/SKILL.md`, `.github/skills/quality-playbook/SKILL.md`) are absent from this checkout.
- **Fresh challenge:** is the SATISFIED verdict tautological? Two paths sharing byte content via a symlink is a single artifact, not parity across alternative installs. The requirement's third condition of satisfaction is "Packaging changes cannot introduce instruction skew between the two supported skill paths." The current evidence is "two paths hashing the same content because one is a symlink to the other" — that proves nothing about behavior under a *non-symlink* install (e.g., a tarball-distributed install where each path is an independent file copy).
- **Adversarial determination:** SATISFIED is technically correct for the shipped product but the evidence is **trivially satisfied** by the symlink. A non-trivial test would create copies (not symlinks) at both paths and assert byte-equality. The mechanical contract should hash all four documented paths if they exist; if they don't exist, the contract should record that absence explicitly rather than proving parity over an empty subset.
- **Re-promotion outcome:** Not promoted to a new BUG. Logged as a hardening recommendation: strengthen `quality/mechanical/skill_entry_hashes.txt` to document non-existence of the other two documented paths and to assert byte-copy parity (not symlink parity) when non-symlink install paths exist.

### REQ-002 through REQ-010 — all VIOLATED

The other Pass 2 verdicts are VIOLATED, not SATISFIED, so they are not adversarial targets for the SATISFIED-challenge step. Each VIOLATED finding is already tracked as a BUG.

---

## Iteration 5 yield summary

- 12 candidate findings re-investigated with fresh code traces (A-1 through A-12).
- 7 formal demoted candidates re-checked against re-promotion criteria — all sustained as FALSE POSITIVE.
- 1 SATISFIED verdict challenged (REQ-001); sustained with caveats about trivial hash-match via symlink.
- 1 candidate promoted to confirmed bug status this iteration: BUG-011 (citation verifier path traversal). New REQ-011 (Citation verifier must enforce repository-root containment) added to support the promotion.
- 11 remaining candidates (A-2 through A-12) recorded as **adversarial-confirmed** in `quality/EXPLORATION_MERGED.md` for future iteration cycles. Each has fresh code-trace evidence and an explicit CONFIRMED determination.

The adversarial strategy's contribution this iteration: it surfaced a HIGH-severity security boundary (path traversal in Layer 1 citation verification) that the previous unfiltered iteration enumerated as a candidate but the orchestrator's Phase 2–5 cycle did not promote. The candidate had complete evidence in iteration 3; the demotion was a Type II error that conservative triage produced. Re-promotion is justified by the documented contract (gate-validated manifest input → file-read primitive without root containment).
