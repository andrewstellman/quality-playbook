# Test 2 (visibility level): result

28 September 2026. Pre-registered in `../PREDICTIONS.md` ("Test 2, pre-registered") before any classification ran. Inputs: the same seven blind lists as test 1, `CLASSIFIER-BRIEF-2.md`, `classifications-2/` (35 files: 3 Sonnet + 2 Opus per repository), `unblind/` (hit matrices, never shown to classifiers). Analysis: `unblind2.py`; per-finding rows in `unblind/rows2.json`.

Levels asked, one per finding: `line` (wrong on inspection of the cited lines), `nearby` (needs a sibling, docstring, comment or test), `input` (needs a constructed input or scenario), `trace` (needs behaviour followed across files or components).

## Headline

**Prediction 1 failed. Prediction 2 held for five of six targets. Prediction 3 failed.** The visibility level does not predict hit rate across the control's own findings; it does separate the QPB targets, but that separation is weak evidence because of how the finding population was built (see Caveats).

Mean hit rate (share of the 20 control runs reporting the finding) by blind majority level, 201 findings in the five 20-run repositories:

| Level | n | mean hit rate | median | found in ≥ 8/20 |
|---|---|---|---|---|
| line | 56 | 0.20 | 0.10 | 9 |
| nearby | 58 | 0.15 | 0.10 | 6 |
| input | 66 | 0.19 | 0.10 | 12 |
| trace | 21 | 0.16 | 0.10 | 4 |

Not monotone: `input` sits above `nearby`. Pearson r between mean level (1–4, averaged over the five classifiers) and hit rate is −0.06; Spearman ρ −0.04. Restricting to the 93 unanimous findings gives 0.23 / 0.15 / 0.21 / 0.11, same shape. Every repository individually shows the same flatness; in chi and express `input` is the highest bucket. Sonnet-only and Opus-only majorities give the same picture.

The pre-registered falsification conditions were (a) any unfound target at majority level 1 or 2, and (b) level-3 mean at or above level-1 mean. Neither strictly fires: no unfound target is at 1–2, and level 3 (0.19) is just under level 1 (0.20). But the hypothesis as stated ("hit rate falls monotonically from level 1 to level 4") is not supported. The 0.01 gap between `line` and `input` is not a signal.

## Targets

| Target | Hits | Five classifications | Majority | Predicted |
|---|---|---|---|---|
| bionemo AMPLIFY `_pad_weights` | 15/20 | line, line, line, nearby, nearby | line | 1–2 ✓ |
| aiohttp `readuntil` | 5/20 | input ×5 | input | 1–2 ✗ |
| chi `GetHead` under mount | 0/20 | trace ×5 | trace | 3–4 ✓ |
| express `maxAge` < 1 s | 0/20 | input ×5 | input | 3–4 ✓ |
| calibre OPDS hex → 500 | 0/20 | line, input ×4 | input | 3–4 ✓ |
| bionemo THD remainder | 0/20 | input ×5 | input | 3–4 ✓ |

The four never-found targets are the only findings in the whole set with zero hits, and all four were placed at `input` or `trace` with 19 of 20 votes. That part of prediction 2 held. aiohttp `readuntil` (found 5/20) was unanimously `input`, which is a miss for the prediction, though a small one: 5/20 is the lowest non-zero target rate, and `input` is where the classifiers put both never-found and moderately-found things.

## Prediction 3

31 findings were reported in 8 or more of 20 runs. Majority levels: line 9, nearby 6, input 12, trace 4. That is 15 of 31 at level 1–2, not "mostly". Examples of high-frequency findings the classifiers put at `input` or `trace`: chi-03 `strings.Contains(v, "gzip")` (15/20, `input`); chi-28 `RedirectSlashes` (10/20, `trace`); chi-32 `SupressNotFound` (12/20, `trace`); express-02 `res.set` (9/20, `trace`); bionemo-19 decoder shape mismatch (9/20, `trace`).

chi-03 is worth a look because in ORACLE-TEST.md I called it "visible in the line itself". Three classifiers said a reviewer needs to think of an `Accept-Encoding` value containing `gzip` as a substring of something else (or with a `q=0` parameter) to see that `Contains` is wrong. They are right: the line is not wrong on its face, it is wrong for a specific input. So my post-hoc reading of the test 1 data was already stretching the category, before the test ran.

## What did hold

- **Agreement** was slightly lower than test 1: 104 of 218 unanimous (test 1: 120), mean agreement with majority 0.83 (test 1: 0.85). Sonnet classifiers leaned toward `input` (235 of 654 votes) and Opus toward `line` (153 of 436). The level scale is more subjective than the oracle-type scale; the brief's own "known weakness" (the description already states the input, so the classifier is judging what someone else would have needed) was visible in the justifications, which often said "once you think of X, it's obvious".
- **The four never-found targets are cleanly separated from everything else** by both hit count (0 vs ≥1) and level (3–4). This is consistent with the hypothesis but is not strong evidence for it, for the reason in the next section.

## Caveats

1. **The comparison population is the control's own output.** Every non-target finding in the lists exists *because* at least one control run reported it. Hit rate within that population measures run-to-run consistency of the control, not findability. The only findings that came from outside the control are the six targets. So "zero-hit findings are all at level 3–4" is true but circular: the zero-hit findings are exactly the inserted ones, and there are only four. A real test of the hypothesis needs an independent population of known defects (fixed-bug commits, issue trackers) that the control did not choose, then blind classification of those, then a control run scored against them. That is the study we have not done.
2. **The classifiers are the same model families as the reviewers.** Same caveat as test 1.
3. **The orchestrating session knew the target hit rates throughout** and wrote this file. Hit counts and bucket means are mechanical; the interpretation is not.
4. Two of five aiohttp classifiers (S2, S3) read only about half of the cited lines before answering; their votes are included. otel and assertj (2 runs each) are excluded from the rate statistics.
5. Some `/tmp` checkouts vanished mid-run; affected classifiers were rerun against the pinned checkouts under `repos/control-2026-09-27/`, read-only. See `classifications-2/README.md`.

## What this means for the article

Two pre-registered attempts to name the variable that separates what standard review finds from what QPB finds have both failed as *predictors across findings*. Both were consistent with the six targets, and both fell apart when applied to the 200 findings around them. The honest statement is narrower than either hypothesis:

> On six defects QPB found, standard AI review (Opus and Sonnet, 10 runs each) found two, one of them in 15 of 20 runs and one in 5 of 20. The other four were found in 0 of 20 runs. Blind classification by five independent model instances placed all four unfound defects in the categories "needs a constructed input" or "needs a cross-component trace", and none of them in "wrong on the cited line". The same classification does not predict how often standard review reports its own findings.

That last sentence has to stay in. Without it the first three overclaim.

The oracle-location framing (test 1) and the visibility framing (test 2) may still be *true* descriptions of what QPB adds; what they are not is *measured* by these two tests. The measurement that would show it is the independent-population study in Caveat 1.

## Feature implication

Andrew asked whether "name your oracle" should become a QPB feature (proposed for 1.6.1). Test 1 showed classifiers can always name an oracle, so as a filter it does nothing. Test 2 suggests the more useful question is the one the four unfound targets all answer: **"what input or scenario demonstrates this?"** Every unfound target has a concrete one (a HEAD request under `Mount`; `maxAge: 500`; `/opds/navcatalog/zz`; `cu_seqlens_padded=[0,8,18], cp_world_size=2`). Requiring that of every finding is cheap, it is checkable (the scenario can be run), and it is what turns a review comment into a test. Whether standard review would find more with that requirement is a separate experiment, not something these tests show.
