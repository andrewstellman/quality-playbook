# Confirmer brief (zod, campaign 2026-09-29)

You are confirming ONE candidate bug from an automated review of zod at commit 2bf7b0630d5378033e90bcee82cb32b0fe04628e. Your job is to find out whether it is real, not to agree with the report.

Setup that already works:
- Source tree (read-only, do not modify): /tmp/zodw  (zod monorepo; the library is packages/zod/src, entry /tmp/zodw/packages/zod/src/index.js which resolves to index.ts)
- Run TypeScript directly:  cd /tmp/zodv/<bug-id> && HOME=/tmp/home npm_config_cache=/tmp/npmcache npx -y tsx repro.ts
- Import with:  import * as z from "/tmp/zodw/packages/zod/src/index.js";
- Citable docs: /tmp/zodw has none; the docs the report cites are at /sessions/kind-zealous-edison/mnt/QPB/repos/campaign-2026-09-29/zod/reference_docs/cite/ (read-only). Quote the exact sentence you rely on.
- Work only in /tmp/zodv/<bug-id>/. Do not write anywhere else. Do not push, post, or open anything on GitHub.

Steps:
1. Read your entry in /tmp/zodv/BUGS-snapshot.md. Restate the claim in one sentence: input, actual, expected, and the source of "expected" (a doc sentence, a spec, or an internal inconsistency such as a sibling function).
2. Write repro.ts that prints the actual behaviour and exits 1 if the bug is present, 0 if not. Run it. Paste the output verbatim.
3. Check the "expected" side yourself. Does the cited doc really say that? Is there a test in packages/zod/src/**/tests/ that pins the current behaviour (which would mean it is intended)? Is there a comment or changelog entry explaining it?
4. Duplicate search: use WebSearch / web_fetch against https://github.com/colinhacks/zod/issues and /pulls for the key terms. Report the closest existing issue/PR (number, title, state) or "none found" with the queries you used.
5. Security angle? (auth bypass, DoS, injection, prototype pollution) yes/no, one line.
6. Verdict, one of: CONFIRMED (reproduces, expectation well-founded, not reported) / CONFIRMED-DUPLICATE (reproduces, already reported: cite) / NOT-A-BUG (behaviour is intended or expectation unsupported: say why) / UNCLEAR (reproduces but expectation debatable: say what a maintainer would need to decide) / COULD-NOT-RUN (say what blocked you).

Return, as text, in this order: bug id and title; one-sentence claim; verdict; repro.ts contents; verbatim output; expectation check; duplicate search; security line; anything a maintainer would push back on. Keep it under 60 lines. No files outside /tmp/zodv/<bug-id>/.
