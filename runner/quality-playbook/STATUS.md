# quality-playbook runner — STATUS

**State:** instruction 033 (sources/classification simplification — read-and-judge,
three-lane promotion, close the extension side door) COMPLETE — **unanimous SHIP**
across a **12-round** 3-charter self-Council (A 5 rounds, B 4, C 3). All four steps
landed; 22 Council findings fixed, each reproduced by execution before being
accepted. The instruction's own premise was measured and **did not hold** — see
"The finding the operator should carry forward" below.
**Last instruction:** 033-sources-classification-simplification.md
**Last output:** 033-sources-classification-simplification.md
**Last update:** 2026-07-25

**Branch:** `1.6.0`. Python 3.14.6. Nothing pushed.

**Test suite:** 3041 / 0 failures / 17 skipped (was 2947 at 032; +94). Three errors
are environmental — `test_channel_install_e2e_090b` (×2) and
`test_full_build_publish_path_090f`, venv / console-script install — verified failing
at `f87c87f` in a clean detached worktree before being attributed elsewhere.

**Commits landed (local only), 21:**
- `44c58a8` step 1 — Lane A becomes a parse, not an extension
- `aba49ef` / `ea47b4a` step 2 — read-and-judge; three lanes wired
- `094f9ac` step 3 — one override channel replaces four
- `f87c87f` step 4 — the reproducibility cache removed
- `17a4fcc` + `8cfe7f7` fix-up 1 — panelist A r1 (5 FIX-REQUIRED + 2 NITs)
- `d84caac` + `7210ccb` fix-up 2 — A r2: the root cause, and the `cite/` label
- `734b7be` fix-up 3 — A r3: a regression I introduced in fix-up 2
- `225fa3a` fix-up 4 — A r4: the skip must be per ARM, not per document
- `a6d10da` fix-up 5 — A r5 SHIP; both NITs taken anyway
- `f387d1f` fix-up 6 — panelist B r1 (six of seven findings)
- `895786e` + follow-up fix-up 7 — B-1: **where the read lives**
- `3e73c74` fix-up 8 — B r2: B2-1 and four NITs
- `77f970a` fix-up 9 — B r3: B3-1, B3-2 and three NITs
- `268959e` fix-up 10 — B r4 SHIP
- `55768d5` fix-up 11 — panelist C r1: C-2, C-3
- `00713e2` fix-up 12 — C r2: D-1..D-5 + the gate/disclosure parity guard
- `76c9d29` fix-up 13 — C r3 SHIP: N-1..N-3
- `081ffbd` tracked synthesis + the three panelist verdicts
- `ee0c167` runner output

**Scope executed (033).** Step 1: `contract_content_validation` parses instead of
matching an extension — the `.thrift` prose exploit and the F1 signature-in-prose
bypass are refused, and the five anchorless F2 formats route to the operator rather
than being auto-cited or silently dropped. Step 2: the model's read replaces the
advisory / implementation / background-name genre floors and the `_SPEC_NAME_TOKENS`
tables; three lanes wired, with Lane B carrying `unconfirmed` from manifest to show
to gate. Step 3: `qpb_promote.txt`, `qpb_advisory_rescue.txt`, `qpb_authoritative.txt`
and `cite/` placement collapse into one content-keyed, operator-authored
`reference_docs/qpb_decisions.txt`, with named-signal confirmation and live
revocation. Step 4: the content-keyed `prior_records` cache is gone.

**One operator decision was taken during the work.** Panelist B found that step 4 had
removed the only channel by which the agent's read entered a run, leaving Lane B
unable to produce a byte-citable record (chi went 2 FORMAL_DOC → 0 on a re-ingest).
The instruction requires the read's location to be specified but does not legislate
its form, and step 4 had legislated on what may persist — so the options went to the
operator, who chose the per-run read artifact now at
`quality/classification_reads.json`. chi 2→2, express 1→1, virtio 1→1, each carrying
`lane=model-read` / `confirmation=unconfirmed`.

**The finding the operator should carry forward.** The layer did not get smaller:
**+24.1% code and +43.6% branches** against pre-033 (panelist C's measurement;
independently re-measured at +24.9% / +39.3% with a different branch definition — the
direction is not sensitive to the counting rule). Step 4 is the only negative row.
What genuinely shrank is the operator's surface: three override files to one, ten
floor rules to seven. The operator has accepted the trade as *bigger but more honest
and more capable*. **Outstanding:** the design doc's §8a framing still says the tower
is *replaced*; left uncorrected, the next instruction inherits a baseline that was
never true. That is a design decision and was not actioned here.

**Other release items outstanding:** `classification_disclosure` has no production
caller — the gate leg is real but deliberately re-implemented, while the Overview and
Stage-1 playback legs invariant 8 names were never wired (a gap predating 033);
`cite/` retires next release with its seeded-decision shim; six stated residuals are
recorded in `docs/process/QPB_v1.6.0_Instruction_033_Self_Council/synthesis.md` §5.

**Council artifacts:** `runner/quality-playbook/reviews/033_self_council/` (local,
gitignored) and the tracked copy at
`docs/process/QPB_v1.6.0_Instruction_033_Self_Council/`.

**Next:** polling. 33 instructions, 33 outputs — nothing unprocessed. No STOP file.
