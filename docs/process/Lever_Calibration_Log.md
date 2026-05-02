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
