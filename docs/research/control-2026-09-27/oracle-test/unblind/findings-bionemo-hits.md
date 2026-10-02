# Hits: bionemo

| ID | Reports that include it as a finding | Reports that mention it but do not report it |
|---|---|---|
| bionemo-01 | opus-run01, opus-run02, opus-run03, opus-run05, opus-run09 | — |
| bionemo-02 | opus-run02, opus-run06 | — |
| bionemo-03 | opus-run01 | — |
| bionemo-04 | opus-run02, opus-run05, opus-run07, opus-run09 | — |
| bionemo-05 | opus-run09 | — |
| bionemo-06 | sonnet-run06 | sonnet-run07 |
| bionemo-07 | opus-run06, opus-run09 | opus-run03 |
| bionemo-08 | opus-run03 | — |
| bionemo-09 | opus-run01, opus-run09, sonnet-run01 | — |
| bionemo-10 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run08, opus-run09, sonnet-run05, sonnet-run10 | — |
| bionemo-11 | opus-run06, opus-run10 | — |
| bionemo-12 | opus-run05 | — |
| bionemo-13 | sonnet-run01 | — |
| bionemo-14 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run10, sonnet-run02, sonnet-run03, sonnet-run04, sonnet-run05, sonnet-run07, sonnet-run09 | — |
| bionemo-15 | opus-run06, opus-run08 | — |
| bionemo-16 | opus-run07 | — |
| bionemo-17 | opus-run03 | opus-run05 |
| bionemo-18 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10, sonnet-run01, sonnet-run07, sonnet-run08 | sonnet-run02, sonnet-run04 |
| bionemo-19 | sonnet-run02, sonnet-run10 | — |
| bionemo-20 | sonnet-run01 | — |
| bionemo-21 | opus-run01, opus-run03 | opus-run02, opus-run05, opus-run06, opus-run07, opus-run09 |
| bionemo-22 | opus-run01, opus-run08, opus-run10 | opus-run09 |
| bionemo-23 | sonnet-run08 | — |
| bionemo-24 | opus-run01, opus-run07, opus-run09, opus-run10 | opus-run08 |
| bionemo-25 | opus-run01, opus-run04, opus-run09, opus-run10 | — |
| bionemo-26 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run09, opus-run10, sonnet-run03, sonnet-run09 | sonnet-run10 |
| bionemo-27 | opus-run01, opus-run02, opus-run06 | — |
| bionemo-28 | opus-run02, opus-run05, opus-run07, opus-run09 | — |
| bionemo-29 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10, sonnet-run02, sonnet-run03, sonnet-run08 | sonnet-run04 |

## Deduplication judgement calls

- **bionemo-29 / bionemo-17 / bionemo-11** (THD token-dropout): opus-run03 bundles the padded-offset count (29) with the CP-sharding case where the rank-local buffer is shorter than the global offsets (17). A fix to the offsets for 29 does not address 17, so they are split. opus-run05's "token dropout with CP is a known incompatibility, not reported" is counted as a mention of 17. The `in kwargs` / value-`None` crash (11) appears only as an aside in the fix sections of opus-run06 and opus-run10; it is a separate behaviour, so it is listed separately and credited to both.
- **bionemo-29**: sonnet-run02 labels it "lower confidence" but lists it as Defect 2, so it counts as a finding. sonnet-run04 explicitly declines to report it, so it counts as a mention.
- **bionemo-18** (AMPLIFY TE int64-only mask): sonnet-run08 presents it as a "Secondary observation (lower confidence)" with severity and fix, outside its "Not flagged" section, so it counts as a finding. sonnet-run02 ("considered but not reported") and sonnet-run04 ("not reported as a defect") are mentions. sonnet-run06 and sonnet-run10 only say the int64 inversion is correct and do not discuss non-int64 masks, so they are in neither column.
- **bionemo-26 / bionemo-01 / bionemo-05 / bionemo-08 / bionemo-25** (AMPLIFY `layer_norm_before_last_layer=False` and related config paths): opus-run01 #10 bundles 25, 26 and 01; opus-run09 #6 bundles 26, 01 and 05; opus-run03 #4 bundles 26, 01 and 08. They are split because each needs a separate fix. sonnet-run03 proposes a different fix (branch the converter) for the same shape mismatch, so it is merged into 26. sonnet-run10 explicitly calls the `vocab_size`-sized decoder "not a bug" (it names amplify_hf.py, but the construct it describes is in amplify_te.py), so it is a mention of 26. sonnet-run02 and sonnet-run06 only call the logit slice a harmless no-op in that branch; they are not counted.
- **bionemo-24 / bionemo-09** (ContextParallelDataLoaderWrapper re-iteration): the lost-batch race from assigning the new iterator before `close()` (24) and the 10 s join timeout that lets two scatter threads run (09) are split. opus-run01 and opus-run09 bundle both. sonnet-run01's defect is the timeout, so it is credited to 09 only. The persistent-workers variant in opus-run07 and opus-run10 has the same fix as 24 and is merged into it. opus-run08's "iterator-reset race too speculative to report" is a mention of 24.
- **bionemo-16**: opus-run07 bundles "state is one batch ahead" with "state read while the prefetch thread runs"; one fix (join and snapshot before prefetch) covers both, so they stay one finding. opus-run07 also lists 24 as "Related (low)" under the same heading; it is credited to 24.
- **bionemo-28 / bionemo-04** (`_pad_sequences_to_be_divisible_by`): all four reports bundle `attention_mask` and `position_ids`; they are split because each tensor needs its own fix. opus-run05's remark that the CP collator does not shard `position_ids` is treated as part of 04.
- **bionemo-20 / bionemo-13**: sonnet-run01 bundles BSHD and THD zero-length NaN under one heading; they are in different functions, so they are split.
- **bionemo-27**: the duplicated-kwarg `TypeError` occurs at three call sites (two in esm2/convert.py, one in the AMPLIFY converter). Treated as one finding because the reports describe it as one pattern with one fix; opus-run06 names only two of the three sites but is credited.
- **bionemo-21**: opus-run01 bundles the `ctx.source` vs `ctx.target` config read with the Megatron-attribute `AttributeError`; kept together because the source-vs-target difference is not described as an observable behaviour on its own. opus-run02, run05, run06, run07 and run09 each dismiss these helpers as unused, so they are mentions.
- **bionemo-22**: opus-run09 lists `NVEsmEncoder` mutating `config.layer_precision` as intentional, so it is a mention.
- **bionemo-07**: opus-run03 discusses the non-StopIteration hang and declines to report it, so it is a mention.
- **bionemo-06**: sonnet-run07 calls the module-level `Perplexity` "a minor design smell ... not a defect per se", so it is a mention.
- **bionemo-23**: sonnet-run02 notes that the THD branch of the same loop computes `max_length` from the pre-split `cu_seq_lens_q_padded` and declines to report it. That is a different branch (THD) from sonnet-run08's BSHD finding, so sonnet-run02 is not credited as a mention of 23, and the THD variant is not listed because no report includes it as a finding.
- **Excluded (discussed only in "not reported" sections, never reported as a defect):** the shared `revision="d918a9e8"` for AMPLIFY_120M and AMPLIFY_350M in amplify/export.py (opus-run01, run03); the separator label not applied to the first sequence (opus-run01); the `amplify_hf.py:360` all-zero-mask short-circuit and the per-row all-padding NaN (sonnet-run01, run02, run03, run07, run08); the lack of a divisibility check in `_process_tensor_thd` (sonnet-run06); division by zero when a whole sequence is mask tokens (sonnet-run10).
