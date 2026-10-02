# Oracle-location test: result

28 September 2026. Pre-registered in `../PREDICTIONS.md` before any classification ran. This file reports the outcome against those predictions. Method and inputs: `EXTRACTOR-BRIEF.md`, `CLASSIFIER-BRIEF.md`, the seven `findings-<repo>-blind.md` lists, `classifications/` (35 files: 3 Sonnet + 2 Opus per repository), and `unblind/` (hit matrices and id maps, never shown to classifiers). Analysis script: `unblind.py` logic is reproduced at the end of this file.

## Headline

**The pre-registered hypothesis failed.** Blind oracle classification does not predict whether standard review finds a defect.

- Mean hit rate (share of the 20 control runs that reported the finding) by majority oracle type, over the 201 findings in the five 20-run repositories: in-repo 0.17, implicit 0.13, known-external 0.22, none 0.13. The buckets overlap almost completely. Restricting to the 109 findings where all five classifiers agreed changes nothing (0.19 / 0.16 / 0.23 / 0.05).
- **No fetch-external bucket exists.** Across roughly 1,090 individual classifications, `fetch-external` was chosen 3 times. The category that was supposed to carry the hypothesis is empty.
- The six targets, which the hypothesis had to explain, were typed as follows (hits out of 20 in brackets):

| Target | Predicted type | Blind majority type | Agreement | Hits |
|---|---|---|---|---|
| bionemo AMPLIFY `_pad_weights` | in-repo | in-repo | 5/5 | 15 |
| aiohttp `readuntil` | known-external | in-repo | 3/5 | 5 |
| chi `GetHead` under mount | fetch-required | **in-repo** | 5/5 | 0 |
| express `maxAge` < 1 s | fetch-required | **known-external** | 4/5 | 0 |
| calibre OPDS hex → 500 | fetch-required | **implicit** | 3/5 | 0 |
| bionemo THD remainder | in-repo (pre-registered outlier) | in-repo | 4/5 | 0 |

Three of the four "fetch-required" predictions were wrong. Each of the four never-found targets landed in a bucket that also contains the most-found findings in the whole study. The single prediction that held was the THD outlier: it was typed in-repo and found 0/20, as predicted, which means the secondary variable ("consequence visibility") was needed. But calibre OPDS is a crash (typed implicit, the most visible consequence there is) and was also 0/20, so the secondary variable fails too.

The falsification conditions written in advance were "a substantial share of high-frequency findings typed fetch-required" or "the fetch-required bucket comparable to in-repo". Neither can be evaluated, because the bucket is empty. The stronger falsification is the target table above.

## Why it failed

1. **A capable reviewer can always find an in-repo oracle.** 114 of 201 findings were typed in-repo. Given any misbehaviour, the classifiers found a docstring, a sibling function, a comment, or a test that "shows the intent". For chi `GetHead` all five cited the docstring "route *undefined* HEAD requests to GET handlers". That is a perfectly good oracle. It did not help 20 reviewers find the bug, because knowing what the docstring says is not the hard part.
2. **Models don't say "I'd have to look that up".** The `fetch-external` option was there and almost never used. Whatever the model doesn't know, it doesn't know it doesn't know. So blind classification cannot measure the thing the hypothesis was about. This is consistent with the original intuition (review is bounded by the oracles the model has) but it means this test design can't detect the boundary.
3. **Oracle location isn't what separates found from unfound.** After the fact, the four unfound targets share something the classification scheme didn't ask about: none of them is visible in the cited lines. Each needs the reviewer to construct a scenario: a HEAD request under a `Mount`; `maxAge: 500`; `/opds/navcatalog/zz`; `cu_seqlens_padded = [0, 8, 18]` with `cp_world_size = 2`. The most-found findings are visible in the line itself: `self.method is HTTP1` (calibre-24, 13/20), `torch.zeros(n, d)` next to a sibling that passes `dtype=` (bionemo-04, 15/20), `strings.Contains(v, "gzip")` (chi-03, 15/20), a tuple unpack of `split('-', 1)` with no guard (calibre-53, 13/20). This is a post-hoc observation from the same data and is **not** a finding. It is the next hypothesis to pre-register.

## What did hold up

- **Inter-rater agreement** was moderate, as predicted: 120 of 218 findings unanimous; mean agreement with the majority 0.85; 54 findings with a 3/5 or weaker majority. The main disagreement, as predicted, was in-repo vs known-external where both exist (most HTTP-framing findings).
- **Opus classifiers use `none`; Sonnet classifiers don't.** Opus chose `none` 35 times, Sonnet 8 times. The clearest case: the three calibre `except A, B:` findings. Both Opus classifiers checked `pyproject.toml`, saw `requires-python = ">=3.14"`, and correctly said the syntax is valid (PEP 758). All three Sonnet classifiers called them real syntax errors. The same asymmetry appears on chi-14, chi-35, aiohttp-27 and aiohttp-32, where an Opus classifier read the tests or the call site and concluded the finding isn't a defect. This matches what the control reviews themselves showed (Sonnet reviewers reported those "syntax errors" as high-severity defects in six runs).
- **Confidence tracks hit rate slightly.** Findings the classifiers rated high-confidence were found at 0.19; medium 0.15; low 0.09. Findings where any classifier said `none` were found at 0.08 to 0.16. Standard review mostly reports things that a second reader also thinks are clearly wrong, which is what you'd expect.
- **Opus reviews and Sonnet reviews barely overlap.** Of 197 findings with at least one hit, 125 were reported only by Opus runs, 37 only by Sonnet runs, 35 by both.

## Caveats

- The classifiers are the same model families as the reviewers. A Sonnet classifier deciding "the oracle is in the repo" is close to a Sonnet reviewer deciding the same thing; independence is partial.
- The extractor stripped justification from the finding descriptions, but the *location* (file:line, function name) was given. That's necessary for classification but it means classifiers looked at exactly the lines the reviewers cited, never at the lines the reviewers missed.
- The orchestrating session knew the target hit rates throughout and wrote this analysis. Hit counts are mechanical (from the extractor's matrix); the interpretation in "Why it failed" is not.
- Two repositories (otel, assertj) have only 2 runs each and are excluded from the rate statistics.
- Six of the 20 control runs for express and two for aiohttp fetched upstream code against instructions; none found its target, so the numbers here are unaffected, but those runs were not clean.

## What to do next

1. **Retire the oracle-location claim.** Don't use it in the article. The phrase "standard AI review is bounded by the oracles the model already has" may still be true, but this test can't show it and the targets contradict its simple form.
2. **Pre-register the replacement before the GPT control runs**: *a defect is found by standard review when the wrong behaviour is visible in the cited lines; it is missed when the reviewer must construct an input or scenario, especially across files.* Blind test: give classifiers the same lists and ask one question per finding: "Can you tell this is wrong from the cited lines alone (yes / only with a sibling or docstring / only by constructing an input / only by tracing across files)?" Prediction to write down: hit rate falls monotonically across those four answers, and the four unfound targets land in the last two.
3. **Keep the GPT arm blind to all of this.** The GPT control protocol and prompt don't mention oracles; leave them as they are.
4. **Coverage is a confound to measure, not assume.** calibre's scope is 13.7K lines; `opds.py` was skimmed or skipped by most runs. Some 0/20 results are "never read the file", not "read it and missed it". The run reports list files read; that can be tabulated.

## Reproduction

`unblind.py` (run from this folder) parses `classifications/*.md` for `### <id>` / `Type:` / `Confidence:` blocks, maps old ids to new via `unblind/idmap-*.md`, reads the hit matrices in `unblind/findings-*-hits.md`, and prints the tables above. The per-finding rows are in `unblind/rows.json`.
