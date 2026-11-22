status: merged
title: python-poetry/tomlkit: RecursionError from parse() on a valid document whose dotted key is within the nesting limit
link: https://github.com/python-poetry/tomlkit/issues/714
updated: 2026-11-22
note: Reported as issue #714 on 2026-11-16 (no fix sent; tomlkit is flooded with AI-drafted PRs, so this went as an issue only). Fixed by another contributor, Yshuro (Sami Chergui), in PR #716 ("Fixes #714"), merged by Frost Ming on 2026-11-22 as 1c551e5d; Frost Ming closed #714 as completed via #716. The quadratic dotted-key report (015) was held back.

## History

- Record as of 2026-11-16: send-*-title.txt and send-*-body.md are the text posted; the patch is as sent. Reviewed in the 13 Nov council (harness_runs/prs-2026-11-13/council/) and later rounds.
- 2026-11-22: closed by Frost Ming as completed via #716, a fix by Yshuro (Sami Chergui), merged as 1c551e5d. #716 says "Fixes #714". Recorded as merged: an issue QPB reported that someone else fixed counts (Andrew, 2026-11-22).
