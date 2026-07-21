# VERDICT: FIX-REQUIRED

**Panelist D — F-2a cross-run durability of operator confirmations**
Charter: Design §8 F-2a. Commits reviewed: ca483e2, 5f1b3d6, dd03e77, bcc5585 (reviewed at branch tip `bcc5585`, detached in this worktree — the four commits are on branch `1.6.0`, which the main worktree holds; my worktree HEAD started at 646b703, predating them).
Method: read the F-2a contract in full (Design §8, schemas.md §9.5, requirements_interview.md, requirements_pipeline.md), executed a 16-case invariant probe, ran the fixture suite (14 green), and performed both required mutation bites. Worktree confirmed clean at end; both mutated files restored byte-identical to a pristine `shutil` snapshot; 313 gate/supersession tests + 14 fixture tests green post-restore.

Headline: **the append-only invariant itself is correct and robust, but the durability *guarantee* it is supposed to deliver is not mechanically enforced in any real re-derivation path.** That is the finding this charter exists to surface (Question 2), and it is P1.

---

## P1 — the durability guarantee is not enforced in production (Question 2)

**The gate can only catch a truncation when a `.prior.jsonl` snapshot exists, and nothing creates that snapshot.**

- `check_operator_confirmations_append_only` enforces the invariant **only** inside `if prior_path.is_file():` — `quality_gate.py:7830`. The snapshot it compares against is `quality/operator_confirmations.prior.jsonl`.
- A repo-wide grep (`*.py`, `*.md`, excluding `repos/` and tests) for `prior.jsonl` / any writer of that snapshot returns **zero** production writers. The **only** things that ever create `.prior.jsonl` are the test fixtures themselves — `test_feature_d_interview_fixture_v160.py:418` and `:445` — which write it by hand immediately before truncating. The fixture comment even narrates the assumed-but-absent mechanism: *"A well-behaved re-derivation: snapshot the log…"* (`:416-418`).
- Neither `references/requirements_pipeline.md` nor any phase guide instructs any step to snapshot the file before re-derivation.

Consequence — a re-derivation that truncates or overwrites the live file (the exact hazard F-2a names) **passes the gate silently**:
- no snapshot present → the `elif shape_ok:` branch reports **PASS** (`quality_gate.py:7845-7849`);
- file absent entirely (a fresh `quality/`) → `"not present — no interview has run"` **PASS** (`quality_gate.py:7785-7787`).

Yet Design §8 F-2a (`docs/design/QPB_v1.6.0_Design.md:231`) and the protocol (`references/requirements_interview.md:227-230`) both flatly advertise *"a run that would delete or truncate it fails the gate."* **That is false as implemented.** The gate catches a truncation only when the truncating re-derivation *voluntarily snapshots first* — i.e. a cooperative or accidental truncation by well-behaved code — and never the wipe-or-overwrite scenario the feature exists to prevent. The guarantee currently rests entirely on the unstated, unenforced precondition that **no code path ever truncates the file**. That is true *today* only because no production code writes this file at all (see the corroborating gap below) — so the advertised mechanical safety net is presently inoperative, providing a false sense of protection. It ships green, and it would still ship green the day someone lands a re-derivation that clobbers `quality/`.

Why P1 and not P0: no current production code path truncates the file, and if `quality/` is stable the file persists by virtue of the append-only helper being the only writer, so operator data is not *actively* being destroyed today. It is the *enforcement mechanism* that is a no-op, not the data that is being lost right now. This becomes **P0 the moment any automated re-derivation writes to `quality/` across runs** without an accompanying snapshot step.

**Fix (any one):** (a) give the pipeline a snapshot-at-run-start step — copy live `operator_confirmations.jsonl` → `.prior.jsonl` before any derivation that could touch `quality/`, so the gate has its reference on every re-run; or (b) have the gate persist and compare against prior-run state by some other durable means; or, at minimum, (c) make the "no prior snapshot" branch stop silently PASSing when a prior run's confirmations are detectable. Option (a) is the cleanest and matches the design's own mental model.

### Corroborating gap (same root cause) — the read-path never executes either

F-2a's sibling promise — *"where a run finalizes the manifest, it reads the file and reports 'N operator-confirmed requirements from prior sessions'"* (`requirements_interview.md:237-242`; asserted again in `requirements_pipeline.md:461`) — is likewise **not wired into any autonomous step**. `run_state_lib.read_confirmations` has **zero production callers** (grep of `*.py` excluding tests: only the fixture calls it). So neither half of F-2a's cross-run contract — enforce survival, surface prior work — actually runs in a real re-derivation. Both are described in prose and exercised only by fixtures. This is completeness evidence that the cross-run wiring, not just the snapshot, is missing.

---

## Mutation bites (Question 3) — as required, both performed

- **Mutation A** — forced `run_state_lib.confirmations_append_only` to `return True`. Ran the F2a tests: **all 14 still PASS, nothing went RED.** The charter predicted `test_truncating_rederive_fails` would go red; it did not, because that test drives the gate's *inline mirror* `_opconf_is_append_only` (`quality_gate.py:7759`), not the `run_state_lib` function. This proves `run_state_lib.confirmations_append_only` is **untested** (see P2 below).
- **Mutation B** — forced the gate's `_opconf_is_append_only` to `return True`. `test_truncating_rederive_fails` went **RED** (`AssertionError: 0 not greater than or equal to 1`; gate emitted a false `PASS: … append-only … (0 record(s))`). The gate's enforcement, *where it fires*, is properly mutation-covered.

Both files restored from pristine snapshot (sha256 MATCH) and re-verified green.

---

## P2 findings

1. **`run_state_lib.confirmations_append_only` is dead + untested; the invariant lives in two drift-prone copies.** It has zero production callers and, per Mutation A, zero test coverage. The invariant is duplicated at `run_state_lib.py:1763` and `quality_gate.py:7759` (the gate re-declares it "so the gate imports nothing" — `:7748-7749`). Only the gate copy is mutation-covered. The two can silently drift. Fix: delete the `run_state_lib` copy, or give it a direct unit test.

2. **Doc drift — schemas.md §9.5.2 misdescribes the mechanism (and undersells it).** §9.5.2 (`schemas.md:1043-1044`) says *'"Shortens" is measured by line count: the file may only grow.'* The implementation is a **byte-prefix** check, which is strictly stronger — it catches a same-line-count in-place rewrite that a line-count check would miss (probe case 2: `f("a\nb\n","a\nX\n")` → `False`, correctly). The code is better than the doc; correct §9.5.2 to describe the byte-prefix property.

3. **Gate shape-check is more permissive than the sanctioned writer.** The gate requires only field *presence* (`f not in obj`, `quality_gate.py:7812`), while `append_confirmation` requires each required field be a non-null **string** (`run_state_lib.py:1716`). A hand-edited record with `conditions_of_satisfaction: null` passes the gate though the sanctioned writer would reject it. Low impact (the helper is the only sanctioned writer) but the gate is the last line of defense against a hand-edited durability log.

---

## What is genuinely correct (SHIP-worthy in isolation)

- **Q1 — the append-only invariant is correct and robust.** A 16-case execution probe of `confirmations_append_only` behaved exactly as required on every case: truncate/delete-lines → FAIL; **same-line-count content overwrite → FAIL** (byte-based prefix catches it — the sharp case the charter flagged); reorder → FAIL; legitimate append → PASS; mid-byte edit of a prior line while appending → FAIL; empty prior → PASS; empty current vs non-empty prior → FAIL; both empty → PASS; prior without trailing newline (equal, +newline-then-append, last-line-modified) → PASS/PASS/FAIL correctly; CRLF prior with LF-normalized content → FAIL, CRLF preserved+append → PASS; trailing-newline-only removal → FAIL. The only normalization is the documented trailing-newline tolerance (`run_state_lib.py:1780`); nothing else is normalized, so content changes are always caught.
- **Q3 — the gate's enforcement is mutation-covered** (Mutation B → RED), where it fires.
- **Q4 — record shape carries content, not identity.** `append_confirmation` enforces `req_title` + `conditions_of_satisfaction` + `operator_statement` (verbatim) + `session_id` + `ts` + `move`, each a required non-empty-typed string (`run_state_lib.py:1688-1717`). **Nothing is keyed on REQ id** — matches §9.5.1's "content, not identity" and "deliberately NOT keyed on REQ id" (renumber-safe). `read_confirmations` returns records verbatim, so the operator's words survive (fixture `test_rederive_reports_prior_confirmations` confirms). `transcript_citation` is correctly optional in both writer and gate, per §9.5.1's conditional/save-gate.
- **Q5 — the append helper is genuinely append-only.** Opens `"a"` mode (`run_state_lib.py:1730`); there is no truncate/rewrite path for this file anywhere in `run_state_lib`. The embedded-newline guard (`:1724-1728`) is present; note it is effectively belt-and-suspenders — `json.dumps` (default `ensure_ascii=True`, compact separators, no indent) already escapes any newline inside a string value to `\n`, so a literal newline in the encoded line is unreachable — but harmless and correct to keep.

---

## Bottom line

The invariant, the record shape, and the append helper are correctly built and well-tested. The feature nonetheless **fails its own headline promise**: the append-only *guarantee* is enforced only against a snapshot that nothing in production ever creates, and the cross-run surfacing read-path is never invoked by a real run — both are exercised solely by fixtures that manufacture the missing setup by hand. The gate advertises protection it cannot deliver in the scenario F-2a exists to prevent. **FIX-REQUIRED, P1** (snapshot/enforcement wiring), with P2 cleanups (delete/test the dead `run_state_lib` invariant copy; correct the §9.5.2 line-count wording to byte-prefix; tighten the gate's field-type check to match the writer).

*Worktree clean at end (tracked files); mutations restored and hash-verified; this review file lives under the gitignored `reviews/` path.*
