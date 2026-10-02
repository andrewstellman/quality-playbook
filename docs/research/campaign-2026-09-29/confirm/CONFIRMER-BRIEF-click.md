# Confirmer brief (click, campaign 2026-09-29)

You are confirming ONE candidate bug from an automated review of click at commit 06b2a678741131fd577ce170e23e5ca0aeba0309. Your job is to find out whether it is real, not to agree with the report.

Setup that already works:
- Source tree (read-only, do not modify): /tmp/clickw  (click installed editable into /tmp/clickw/.venv; run Python with /tmp/clickw/.venv/bin/python; pytest: cd /tmp/clickw && .venv/bin/python -m pytest -q -p no:cacheprovider -p no:xdist --basetemp=/tmp/clickpt/<bug-id> tests/<file>)
- Write repro.py in your work dir and run it with /tmp/clickw/.venv/bin/python; use click.testing.CliRunner where a command is needed.
- `import click` gives the editable install. Source: /tmp/clickw/src/click/.
- Citable docs: /sessions/kind-zealous-edison/mnt/QPB/repos/campaign-2026-09-29/click/reference_docs/cite/ (read-only; the project docs, filenames docs_*.md). Quote the exact sentence you rely on.
- Work only in /tmp/clickv/<bug-id>/. Do not write anywhere else. Do not push, post, or open anything on GitHub.

Steps:
1. Read your entry in /tmp/clickv/BUGS-snapshot.md. Restate the claim in one sentence: input, actual, expected, and the source of "expected" (a doc sentence, a spec, or an internal inconsistency such as a sibling function).
2. Write repro.py that prints the actual behaviour and exits 1 if the bug is present, 0 if not. Run it. Paste the output verbatim.
3. Check the "expected" side yourself. Does the cited doc really say that? Is there a test in /tmp/clickw/tests/ that pins the current behaviour (which would mean it is intended)? Is there a comment or changelog entry explaining it?
4. Duplicate search: use WebSearch / web_fetch against https://github.com/pallets/click/issues and /pulls for the key terms. Report the closest existing issue/PR (number, title, state) or "none found" with the queries you used.
5. Security angle? (auth bypass, DoS, injection, prototype pollution) yes/no, one line.
6. Verdict, one of: CONFIRMED (reproduces, expectation well-founded, not reported) / CONFIRMED-DUPLICATE (reproduces, already reported: cite) / NOT-A-BUG (behaviour is intended or expectation unsupported: say why) / UNCLEAR (reproduces but expectation debatable: say what a maintainer would need to decide) / COULD-NOT-RUN (say what blocked you).

Return, as text, in this order: bug id and title; one-sentence claim; verdict; repro.py contents; verbatim output; expectation check; duplicate search; security line; anything a maintainer would push back on. Keep it under 60 lines. No files outside /tmp/clickv/<bug-id>/.
