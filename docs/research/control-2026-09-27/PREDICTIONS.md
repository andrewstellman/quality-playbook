# Pre-registered predictions

Written 28 September 2026 by the orchestrating session (Claude Fable 5.1), **before** the blind oracle classification (test 1) was run and **before** the GPT control, the gson copilot run, and the otel/assertj repetitions were run. Commit this file before running any of those; the commit hash is the timestamp.

## Hypothesis

The chance that standard AI code review reports a given defect depends mainly on one variable: **where the test oracle is.**

| Oracle type | Meaning | Predicted control hit rate |
|---|---|---|
| Pseudo-oracle in the repo | Sibling code, a docstring, or a comment in the reviewed code shows the correct behaviour | High |
| Implicit | The failure is a crash, exception, hang, or resource leak | High |
| Memorized external contract | An RFC, stdlib, or platform contract the model already knows, and the function is small enough to simulate | Middle |
| Fetch-required external requirement | A spec, project contract, or boundary case the reviewer would have to go and get | At or near zero |

Secondary variable, added because of bionemo THD: a pseudo-oracle is not enough when the consequence is silent and only reachable under configurations the repo doesn't ship. Standard review applies a "does realistic input hit this?" filter. So the model is **oracle location × visibility of the consequence.**

## Test 1: what I expect the blind classification to show

Classifiers (3 Sonnet, 2 Opus per repository) will see only file:line and a neutral behaviour statement for every distinct finding the 100 control runs reported, with the six unfound/found targets mixed in unmarked.

Predictions, written before extraction:

1. Findings the classifiers type as *pseudo-oracle in repo* or *implicit* will have the highest mean hit frequency across the 20 runs per repo. Findings typed *fetch-required* will have mean hit frequency near zero.
2. The six targets will be typed as follows, and their known hit rates fit the hypothesis:
   - bionemo AMPLIFY `_pad_weights`: pseudo-oracle in repo (found 15/20)
   - aiohttp `readuntil`: memorized external contract (found 5/20)
   - express `maxAge`: fetch-required or "no oracle" (0/20)
   - calibre OPDS hex: fetch-required (0/20)
   - chi `GetHead` under mount: fetch-required, and I expect some classifiers to be *unable to name an oracle at all* (0/20)
   - bionemo THD remainder: **pseudo-oracle in repo** (the BSHD branch raises). This is the pre-registered outlier: 0/20 despite an in-repo oracle. If the classifiers type it that way, the secondary variable is needed; if they type it fetch-required, the primary variable alone survives.
3. Inter-rater agreement on oracle *type* will be moderate, not high. I expect most disagreement between *memorized external* and *fetch-required*, because that boundary is about what the model happens to know.
4. Opus and Sonnet classifiers will not differ much on in-repo and implicit cases; Sonnet will call more things "memorized" than Opus does.

What would falsify the hypothesis: a substantial share of the control's high-frequency findings (reported in, say, 8 or more of 20 runs) typed as fetch-required; or the fetch-required bucket having a mean hit frequency comparable to the in-repo bucket.

Caveats recorded in advance: the classifiers are the same model families as the reviewers, so "I already know this contract" is partly self-report. The orchestrating session has read all 100 run summaries and is not blind; that's why hit counts are computed mechanically from the extractor's matrix, not judged.

## Test 2: predicted hit rates for unrun controls

Rates are per run. "Sol" and "Terra" are the two GPT models the ChatGPT/Codex app will use; gson uses gpt-5.4 through copilot.

| Target | Oracle type | Opus (10 reps) | Sonnet (10 reps) | Sol | Terra |
|---|---|---|---|---|---|
| aiohttp `readuntil` | memorized external | seen: 4/10 | seen: 1/10 | 20–50% | 10–40% |
| chi `GetHead` under mount | fetch-required | seen: 0/10 | seen: 0/10 | 0–10% | 0–10% |
| express `maxAge` < 1 s | fetch-required / boundary | seen: 0/10 | seen: 0/10 | 0–10% | 0–10% |
| calibre OPDS hex → 500 | fetch-required, large scope | seen: 0/10 | seen: 0/10 | 0–10% | 0–10% |
| bionemo AMPLIFY `_pad_weights` | pseudo-oracle in repo, crash | seen: 9/10 | seen: 6/10 | 60–100% | 40–90% |
| bionemo THD remainder | pseudo-oracle, silent, unshipped config | seen: 0/10 | seen: 0/10 | 0–15% | 0–15% |
| otel `UrlParser` IPv6 | memorized external, small function | 60–90% | 20–50% | 50–90% | 30–70% |
| otel Forwarded IPv6 | memorized external, small function | 50–80% | 20–50% | 40–80% | 20–60% |
| assertj `Percentage.toString` | implicit-ish (wrong output on ordinary input), small file | 50–80% | 10–40% | 40–80% | 20–60% |
| gson (target TBD from QPB run) | — | — | — | not predicted until the QPB finding exists | |

Disclosure: for otel and assertj, run 01 already exists (Opus 1/1 on all three, Sonnet 0/1). Those rows predict a *rate*, not first detection. The GPT rows are clean predictions.

## Test 3 (later): the symmetric question

Classify the control's own high-frequency findings and check the historical QPB output for each. Prediction: QPB also finds most in-repo and implicit findings, so the variable does not distinguish QPB on those; it distinguishes QPB on the fetch-required bucket. This needs commit-matched QPB runs and isn't part of test 1.

---

## Outcome of test 1 (added 28 September 2026, after unblinding; the predictions above are unchanged)

**The hypothesis failed.** See `oracle-test/ORACLE-TEST.md`.

- Prediction 1 (in-repo/implicit high, fetch-required near zero): not supported. Mean hit rates by blind majority type: in-repo 0.17, implicit 0.13, known-external 0.22, none 0.13. The fetch-external bucket is empty (3 votes in ~1,090).
- Prediction 2 (target typing): 3 of 6 wrong. chi GetHead was typed in-repo (5/5), express maxAge known-external (4/5), calibre OPDS implicit (3/5). Only AMPLIFY, aiohttp (partly) and the THD outlier matched.
- Prediction 3 (moderate agreement, in-repo vs known-external the main split): held. 120/218 unanimous, mean 0.85.
- Prediction 4 (Sonnet calls more things memorized than Opus): not really; the model difference that showed up was that Opus used `none` (35 vs 8) and was right to on the PEP 758 findings.

Replacement hypothesis to pre-register before the GPT control: **visible-in-the-cited-lines vs requires-constructing-an-input**. Not yet registered; see ORACLE-TEST.md §What to do next.

---

## Test 2, pre-registered 28 September 2026 (before any classification ran; GPT control in progress and untouched)

**Hypothesis.** Standard review finds a defect when the wrong behaviour is visible in the cited lines, and misses it when the reviewer must construct an input or trace across components. Four levels, asked blind, one per finding:

1. `line`: wrong on inspection of the cited lines alone (wrong comparison, missing argument, substring match, unguarded unpack).
2. `nearby`: needs a sibling function, docstring, comment or test in the same or a closely related file to see that it is wrong.
3. `input`: needs a specific input, value or scenario to be constructed and executed, mentally or actually.
4. `trace`: needs behaviour followed across files or components (routing contracts, mount semantics, collator to model).

Same setup as test 1: 3 Sonnet + 2 Opus classifiers per repository, same blind lists, no access to hits.

**Predictions.**
1. Mean hit rate falls monotonically from level 1 to level 4 (over the five 20-run repositories, majority level).
2. The four unfound targets (chi-22, express-11, calibre-11, bionemo-03) get majority level 3 or 4. The two found targets (bionemo-04, aiohttp-10) get level 1 or 2.
3. Findings reported in 8 or more of 20 runs are mostly level 1 or 2.

**Falsification.** Any unfound target at majority level 1 or 2; or level 3 mean hit rate at or above level 1.

**Known weakness, recorded in advance.** The blind description already states the triggering input, so the classifier sees the scenario the reviewer had to invent. The brief asks them to judge what a reviewer *without the description* would have needed. That is a judgement about someone else's work and is weaker than test 1's question.

---

## Outcome of test 2 (added 28 September 2026, after unblinding; the predictions above are unchanged)

See `oracle-test/ORACLE-TEST-2.md`.

- Prediction 1 (monotone decrease line → trace): **failed.** Mean hit rate by majority level: line 0.20, nearby 0.15, input 0.19, trace 0.16. Pearson r −0.06.
- Prediction 2 (unfound targets at 3–4, found targets at 1–2): **5 of 6 held.** chi-22 trace, express-11 input, calibre-11 input, bionemo-03 input, bionemo-04 line. aiohttp-10 (5/20) was unanimously `input`, which misses.
- Prediction 3 (≥8/20 findings mostly at 1–2): **failed.** 15 of 31.
- Falsification conditions: neither strictly fired (no unfound target at 1–2; level 3 at 0.19 vs level 1 at 0.20). The hypothesis is nonetheless not supported as a predictor across findings.
- Recorded limitation, now the main one: the comparison population is the control's own output, so the only zero-hit findings are the inserted targets. Both tests are circular on that axis. The next test needs an independent population of known defects.
