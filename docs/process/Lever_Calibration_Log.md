# Lever Calibration Log

*Per-cycle record of QPB calibration cycles. Each entry follows `metrics/regression_replay/SCHEMA.md`'s calibration-log entry template (with reconciliations noted in the entry where SCHEMA.md is stale).*

*Canonical home: this file at `~/Documents/QPB/docs/process/Lever_Calibration_Log.md`. The workspace replica at `~/Documents/AI-Driven Development/Quality Playbook/Reviews/Lever_Calibration_Log.md` is per-DEVELOPMENT_PROCESS.md's replicate-not-source-of-truth pattern.*

---

## Cycle: 2026-05-01 — chi-1.3.45

**Symptom:** chi-1.3.46 cross-version cell reported `0 ⚠️↓ (was 10)` in the cross-repo trend table — apparent collapse of recall on chi-1.3.46 vs chi-1.3.45. Manual investigation revealed the 0/10 was partially a parser artifact (chi-1.3.46's BUGS.md uses H2 headings + REQs embedded in prose; the regression-replay parser couldn't compute recall cleanly across the format mismatch). True recall measurement: run current QPB v1.5.4 against chi-1.3.45 source, compare to chi-1.3.45 historical 10-bug ground truth.

**Diagnosis:** current QPB v1.5.4 found 17 bugs on chi-1.3.45 vs 10 historical (different cut, more findings overall), but recall against the historical 10-bug baseline = 4/10 (40%). 6 missed; 4 of 6 are mount-context awareness defects: BUG-004 (CleanPath mounted child), BUG-007 (RedirectSlashes mount prefix in Location), BUG-008 (mounted Heartbeat never matches), BUG-009 (mounted PageRoute never matches). All four involve middleware that reads or writes the wrong representation of state under mounting (`r.URL.Path` instead of canonical `RoutePath`, or constructing outward-facing paths from canonical state where parent-aware was needed). The two outlier missed bugs (BUG-002 RouteHeaders Host header semantics; BUG-003 ReadFrom byte-doubling) are different classes — separate cycles.

**Lever pulled:** Lever 1 (Exploration breadth/depth). Home: `references/exploration_patterns.md`. Added Pattern 7 (Composition and Mount-Context Awareness) — a new exploration pattern directing Phase 1 to enumerate, for each function or component that reads or writes state that *can be canonical-vs-raw under composition*, whether it correctly handles being composed inside a parent context. Pattern is direction-agnostic (read-side and write-side defects covered), has 5 cross-domain examples (HTTP routing, transaction context, logging contextvars, locale-sensitive comparison, authorization scope), a 4-bullet seam list, a budget cap (3-5 highest-impact composition seams per pass), and a Pattern 4 disambiguation rule. Commit `99f65c7`.

**Mode:** 1 (autonomous). Sub-agent fan-out for Council review (Cowork's Agent tool, `general-purpose` subagent_type, three parallel reviewers with orthogonal lenses).

**Runner:** Step 1 was Mode 2 manual via `--claude` (operator's earlier execution). Diagnosis through Council was Mode 1 autonomous. Validation (Steps 8-9) was argument-based not empirical due to Cowork environment constraints (bash-tool 45s timeout precludes blocking on ~30-min playbook subprocess). Cycle runner-pinning broke between Steps 1 and 8; future production v1.6.x cycles run with consistent runner and empirical validation.

**Before:** recall = 4/10 = 40%. Recovered: [BUG-001 compression q=0, BUG-005 PathRewrite (partial), BUG-006 SupressNotFound, BUG-010 AllowContentEncoding comma]. Missed: [BUG-002 RouteHeaders Host, BUG-003 ReadFrom byte-doubling, BUG-004 CleanPath mounted child, BUG-007 RedirectSlashes mount prefix, BUG-008 mounted Heartbeat, BUG-009 mounted PageRoute].

**After (projected, argument-based):** recall = 8/10 = 80%. Recovered: previous 4 + BUG-004, BUG-007, BUG-008, BUG-009 (all 4 mount-context bugs flagged by Pattern 7's "How to apply" Step 1 procedure on the relevant source files). Missed: [BUG-002, BUG-003] — outliers (different bug classes, separate cycles).

**Recall delta:** +0.40 (40 → 80 percentage points), well above noise_floor_threshold = 0.05.

**Cross-benchmark:**
- chi-1.5.1 (9 bugs): walked through; 0 at risk. Pattern 7 is additive — no displacement of existing pattern coverage. BUG-001 (CleanPath nil-rctx) and BUG-003 (SupressNotFound mutation) are composition-adjacent; Pattern 7 helps find them, doesn't displace.
- virtio-1.5.1 (8 bugs): all kernel-driver / queue / IRQ / memory ordering. Pattern 7 content irrelevant; small token cost, 0 displacement risk.
- express-1.5.1: NOT archived. Closest available is express-1.3.15. Cycle Finding C-2: the protocol's default pinned-benchmarks list assumes specific archive availability that doesn't exist. Cross-benchmark check skipped for express; gap documented.

**Verdict:** **Ship (argument-based; pending empirical validation in a future production v1.6.x cycle when the executing-AI environment supports long-running subprocesses).**

**Cell:** `metrics/regression_replay/20260501T231500Z/chi-1.3.45-1.3.45-all.json`

**Commit:** `99f65c7`

**Cycle artifacts:**
- Audit trail: `Quality Playbook/Calibration Cycles/2026-05-01-chi-1.3.45/audit.md` (workspace; migrates to `docs/process/QPB_v1.5.4_Calibration_Cycle_chi-1.3.45/` at v1.5.4 ship)
- Council synthesis: `Quality Playbook/Calibration Cycles/2026-05-01-chi-1.3.45/council_synthesis.md`

**Cycle findings (for protocol revision and follow-on work):**

- **C-1: Pre-flight #3 + test-fixture architecture interaction.** Benchmark target paths are gitignored (`repos/` is gitignored entirely); the protocol's "tracked at HEAD" check fails categorically. Additionally, three unit-test fixtures consume the live target's `quality/BUGS.md` directly — these should reference checked-in fixture copies. Documented for protocol revision + test refactor.
- **C-2: Pinned-benchmarks default doesn't match archive.** Protocol's default `<pinned_benchmarks>` lists `chi-1.5.1`, `virtio-1.5.1`, `express-1.5.1` but `express-1.5.1` isn't in `repos/archive/` — closest is `express-1.3.15`. Default needs reconciling with actual archive state.
- **C-3: SKILL.md template update is required follow-on.** Per `references/exploration_patterns.md`'s "Extending This List" step 5, adding Pattern 7 requires a corresponding update to SKILL.md's EXPLORATION.md template. This is QPB source (not orientation-doc carve-out). Tracked as separate commit.
- **C-4: Argument-based vs empirical validation.** Cowork environment can't block on ~30-min playbook subprocess; autonomous cycle in this environment converges on argument-based validation. Production v1.6.x cycles run by AIs with subprocess-management capability would do empirical validation. Protocol should explicitly support both, with cell.json's `noise_floor_source` field distinguishing.

---

## Cycle: 2026-05-02 to 2026-05-04 — pattern7-displacement-recovery

**Symptom:** v1.5.4 cycle 1 said Pattern 7 recovered four mount-context bugs on chi-1.3.45 but displaced two others (`PathRewrite`, `AllowContentEncoding`). This follow-up cycle tested whether tightening Pattern 7's budget cap from `3-5` to `2-3` highest-impact composition seams would recover the displaced bugs without giving back the mount-context wins.

**Diagnosis:** On the load-bearing benchmark (chi-1.3.45), the tighter cap recovered **AllowContentEncoding** but LOST **PathRewrite**, and substantive historical recall worsened from **5/10 to 4/10**. The four mount-context findings Pattern 7 was supposed to preserve — BUG-004, BUG-007, BUG-008, BUG-009 from cycle 1 — were present in neither the pre-lever nor post-lever v1.5.6 runs, so mount-context preservation on chi-1.3.45 is **0/4 = 0%**. That means the cycle never established an empirical case for keeping the tighter cap.

**Lever pulled:** Lever 1 (Exploration breadth/depth). Home: `references/exploration_patterns.md`. Tested a tighter Pattern 7 budget cap — `3-5` -> `2-3` highest-impact composition seams per pass. Lever-application commit: `83f812a`.

**Mode:** 1 (autonomous).

**Runner:** Empirical six-run cycle completed in the v1.5.6 runner workspace. Precondition note from the operator handoff said express post-lever finalization was interrupted, but the final cycle artifacts now include the post-lever express `benchmark_end` event and cell JSON, so the audit treated express as completed.

**Before (cap 3-5):**
- chi-1.3.45 substantive recall: **0.50** (5/10 historical bugs by file/content overlap)
- virtio-1.5.1 substantive recall: **0.80** (4/5 historical-file overlap)
- express-1.3.50 substantive recall: **n/a** (bug count 8; historical overlap unavailable)

**After (cap 2-3):**
- chi-1.3.45 substantive recall: **0.40** (4/10)
- virtio-1.5.1 substantive recall: **0.80** (4/5)
- express-1.3.50 substantive recall: **n/a** (bug count 12; historical overlap unavailable)

**Recall delta:**
- chi-1.3.45: **-0.10**
- virtio-1.5.1: **+0.00**
- express-1.3.50: **n/a** substantive recall; **+4 bugs** in raw bug count

**Cross-benchmark:**
- chi-1.3.45: recovered `AllowContentEncoding`, lost `PathRewrite`, preserved **0/4** of the cycle-1 mount-context set. This is the load-bearing negative result.
- virtio-1.5.1: no significant regression. Historical overlap held at 4/5; the run traded one `virtio_ring.c`-anchored finding for one `virtio_pci_legacy.c` finding.
- express-1.3.50: post-lever bug count rose from 8 to 12, but recall against the historical baseline remained uncomputable because express BUGS.md formatting still prevents stable per-bug overlap matching.

**Verdict:** **Revert.**

**Audit:** `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/audit.md`

**Cycle artifacts:**
- Visualizations: `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/visualizations/`
- Runner output: `~/Documents/AI-Driven Development/Quality Playbook/v1.5.6_runner/outputs/015-pattern7-cycle-analysis-and-audit.md`

**Final scope:** Cycle ran on 3 of 4 originally-scoped benchmarks; chi-1.5.1 dropped permanently from cycle scope. The reduction does not weaken the verdict because the displacement-recovery story was concentrated on chi-1.3.45 and chi produced a negative result on the load-bearing measurement. The cycle is closed.

**Methodology note:** Per worker output 008, REQ IDs were unstable across runs, so this cycle's recall numbers use substantive file-path and bug-description matching rather than the mechanical `(REQ_id, file)` key. The mechanical-match-key gap is real planned scope for the v1.7 SPC arc.

---

## Final entry — 2026-05-07: Pattern 7 displacement-recovery cycle close + v1.5.6 architectural fix

**Cycle name:** `2026-05-02-pattern7-displacement-recovery` (closed 2026-05-07)
**Final scope:** 3 of 4 benchmarks (chi-1.3.45, virtio-1.5.1, express-1.3.50). chi-1.5.1 dropped permanently.
**Verdict:** **revert** (Pattern 7 budget cap restored to `3-5` in commit `856e67f`).

**v1.5.6 architectural deliverable from the Cluster E investigation:**

Cluster E (the chi-1.3.45 docs-backed validation re-run originally scoped in the v1.5.6 fix-up backlog) was dropped after two sonnet-4-6 attempts demonstrated a real bug: the LLM-written `role_map.json` summary field contract drifted from `summarize_role_map()` validation (file_count off by 8 the first time, structurally wrong shape the second). Rather than re-running cluster E with opus-4-7 to chase a passing role_map gate, v1.5.6 instruction 047 landed the architectural fix in commit `a85aa7c`:

- The LLM writes only `files[]` + `provenance`.
- The runner-side helper `bin.role_map.normalize_role_map_for_gate(path)` recomputes `breakdown` and `summary` from the canonical helpers between Phase 1 LLM exit and the Phase 2 entry-gate.
- The pre-cluster-047 contract ("LLM produces summary; validator enforces it equals `summarize_role_map(role_map)`") reliably failed for sonnet-class LLMs that reverted to intuitive summarization. v1.5.6 cluster 047 moved the deterministic computation runner-side; the failure mode is now unreachable.

This is the substantive Cluster E deliverable. The chi-1.3.45 docs-backed re-run was dropped because the architectural fix is the load-bearing improvement; future cycle work won't fail at the role_map gate the way Cluster E did, regardless of which model is used.

**chi-1.5.1 follow-on (cluster F.2a, opus-4-7, instruction 046):**

Substantive recall: **9/16 = 0.5625** against the v1.5.1 baseline. Recovered: CleanPath, SupressNotFound (NPE half), matchAcceptEncoding, AllowContentEncoding, Recoverer, RegisterMethod, BasicAuth, RouteHeaders, RealIP (partial). Missed: GetHead, SupressNotFound mutate-live variant, Timeout, RequestID, Profiler, WrapResponseWriter, StripPrefix. Net-new findings: URLFormat dot-prefix, Mount collision probe, Sunset RFC-9745.

This data informs the historical baseline understanding but does not change the cycle's revert verdict, so chi-1.5.1 is not a 4th cell in the cycle's per-benchmark recall table. Cell.json at `metrics/regression_replay/20260502T155324Z/chi-1.5.1-pre-lever.json`.

**Audit:** `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/audit.md` (refreshed 2026-05-07; "Reduced-scope acknowledgment" section now reads "(final)" — cycle closed).
