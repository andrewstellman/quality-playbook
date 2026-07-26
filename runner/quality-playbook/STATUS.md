# quality-playbook runner — STATUS

**State:** instruction 034 (classifier bar — content-authority, not authorship
provenance) COMPLETE — **unanimous SHIP** across a **9-round** 3-charter self-Council
(A 3 rounds, B 3, C 3). Guidance-only fix: **zero lines of any script changed**.
22 Council findings closed, each reproduced by execution before being accepted.
**Last instruction:** 034-classifier-bar-content-authority.md
**Last output:** 034-classifier-bar-content-authority.md
**Last update:** 2026-07-26

**Branch:** `1.6.0`. Python 3.14.6. Nothing pushed.

**Test suite:** 3069 / 0 failures / 17 skipped (was 3055 at `ac30c60`; +14). Three
errors are environmental — `test_channel_install_e2e_090b` (×2) and
`test_full_build_publish_path_090f`, venv / console-script install — verified
pre-existing at `f87c87f` in a clean detached worktree during 033.

**Commits landed (local only), 11:**
- `ac30c60` the guidance edit + the 034 fixture
- `c6dc3d3` / `1b73cda` / `dd91453` fix-ups 1-3 — panelist A (F1-F4 + 9 NITs)
- `e793fde` / `f3990e4` / `1963685` fix-ups 4-6 — panelist B (B-1..B-11)
- `d7987d0` / `b23cfce` / `39bc78e` fix-ups 7-9 — panelist C (C-1..C-9)
- `1707919` runner output

**Scope executed (034).** The read-and-judge classifier was gating promotion on
authorship provenance ("were these written by the project's maintainers?") instead of
content authority. Fixed in `references/phase1_exploration_guide.md`: provenance is
never a reason to demote (gathered docs are third-party-compiled by construction);
the bar is content-authority with **both** halves required (authoritative genre AND
contract-shaped content), and the genre is read from the body, not the title;
authoritative-genre-but-uncertain is Lane B `unconfirmed`, cited *and* surfaced; a
mixed document goes up, not down; a minor inaccuracy is Lane B, with a floor on
"pervasively wrong" and routes for wrong-project and superseded-version documents;
"on genuine ambiguity, background" scoped to ambiguity **of genre**; and Step 1b's
depth ladder is explicitly not a citation bar. Tasks 3 and 4 both resolved as "no
edit needed", with reasons recorded — `phase1.md` delegates and never restates the
bar, and every operator-facing reason string is already about what a document
*states* rather than who wrote it.

**Evidence reproduced, not taken on faith.** chi's `classification_reads.json`: 18
reads, all tier 4, `zero_citable`. Document 14 is the one that settles it — its own
read records the content matches the source, so provenance was doing all the work.
Document 13's `Use()` error is real (`chi.go:71`, `mux.go:100` return void;
`mux.go:236` `With()` returns Router) but §8a makes that a Lane B cite. Express
promoted three same-provenance `api-reference` docs to Lane B.

**Acceptance criteria: 4 PASS, 1 PASS WITH A STATED CAVEAT.** Criterion 5's gate leg:
`quality_gate.py` runs clean and its classification checks fire, but all three
benchmarks return `FAIL` for unverified bugs in their **own recorded runs** —
byte-identical with and without this edit, and the gate never reads the guide.
Reading criterion 5 as "the gate passes" would be false.

**Four patterns for the improvement loop**, all in the output:
1. An assertion not tied to the clause it named — **six instances, all mine**, all in
   the fixture's text half, nine bites over three rounds to work out.
2. Each fix **appended** a clause to a load-bearing sentence and arrived with a defect
   the old text could not have had: B-4 begat B-8, B-7 begat B-11, C-1 begat C-8.
3. Panelist C's formulation: *in a guidance-only change, the assertions that need
   executing are not the ones about the guidance — they are the ones the guidance
   makes about the code.* Three false mechanics claims in three rounds.
4. Inverted test sensitivity — Markdown emphasis had become a CI-enforced contract;
   now emphasis/dash/whitespace-insensitive, verified on a 12-case matrix.

**Operational finding.** The first panelist-B attempt **stalled mid-bite and left the
Lane C guard disabled** (`unacknowledged = []`) in the working tree. Detected by
diffing every file a bite could touch, restored from the HEAD blob, 203 stale `.pyc`
purged, guard re-verified as *enforcing*. Two rules came out of it and held for the
rest of the Council: never hold a mutation across more than one command, and never
run the full suite with a mutation live. Also: a bite whose anchor matches **zero**
occurrences, or matches in the **wrong location**, proves nothing — both bit me.

**Flagged, not fixed (out of 034's scope):** N5 — the guide still calls a
self-classifying doc "a signal toward background", superseded by §8a Revision rule 3.
N7 — the coverage table and Step-7a gate key on "Deep", so a Shallow Lane B cite
carries no obligation to produce a requirement; field trigger is a chi re-run
yielding Lane B `13`/`14` with zero Tier-1/2 requirements tracing to them. And the
pervasively-wrong / wrong-project / superseded-version demotion route has no
counterpart in §8a's text and belongs there on its next revision.

**Council artifacts:** `runner/quality-playbook/reviews/v034_self_council/` (local,
gitignored — 034's instruction specified `reviews/` only, so unlike 033 no tracked
copy was requested).

**Next:** polling. 34 instructions, 34 outputs — nothing unprocessed. No STOP file.
