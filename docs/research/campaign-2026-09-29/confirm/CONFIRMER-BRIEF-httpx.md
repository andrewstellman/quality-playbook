# Confirmer brief (httpx, campaign 2026-09-29)

You are confirming ONE candidate bug from an automated review of httpx at commit b5addb64f0161ff6bfe94c124ef76f6a1fba5254. Your job is to find out whether it is real, not to agree with the report.

Setup that already works:
- Source tree (read-only, do not modify): /tmp/httpxw  (httpx installed editable with extras into /tmp/httpxw/.venv; run Python with /tmp/httpxw/.venv/bin/python; pytest: cd /tmp/httpxw && .venv/bin/python -m pytest -q -rf -p no:cacheprovider -p no:xdist --basetemp=/tmp/httpxpt/<bug-id> tests/<file>. Baseline: 10 tests already fail in this sandbox for environment reasons (chardet autodetect, logging, trio write timeout, test_download); ignore those.)
- Write repro.py in your work dir and run it with /tmp/httpxw/.venv/bin/python. For network behaviour use httpx.MockTransport or a local uvicorn/socket server; do not contact external hosts.
- `import httpx` gives the editable install. Source: /tmp/httpxw/httpx/. httpcore is the transport dependency (installed).
- Citable docs: /sessions/kind-zealous-edison/mnt/QPB/repos/campaign-2026-09-29/httpx/reference_docs/cite/ (read-only; project docs docs_*.md plus RFC 9110, 9112, 9113, 6265, 3986 as rfc*.txt). Quote the exact sentence you rely on.
- Work only in /tmp/httpxv/<bug-id>/. Do not write anywhere else. Do not push, post, or open anything on GitHub.

Steps:
1. Read your entry in /tmp/httpxv/BUGS-snapshot.md. Restate the claim in one sentence: input, actual, expected, and the source of "expected" (a doc sentence, a spec, or an internal inconsistency such as a sibling function).
2. Write repro.py that prints the actual behaviour and exits 1 if the bug is present, 0 if not. Run it. Paste the output verbatim.
3. Check the "expected" side yourself. Does the cited doc really say that? Is there a test in /tmp/httpxw/tests/ that pins the current behaviour (which would mean it is intended)? Is there a comment or changelog entry explaining it?
4. Duplicate search: use WebSearch / web_fetch against https://github.com/encode/httpx issues, pulls AND discussions (httpx routes bug reports through "Potential Issue" discussions) for the key terms. Report the closest existing issue/PR (number, title, state) or "none found" with the queries you used.
5. Security angle? (auth bypass, DoS, injection, prototype pollution) yes/no, one line.
6. Verdict, one of: CONFIRMED (reproduces, expectation well-founded, not reported) / CONFIRMED-DUPLICATE (reproduces, already reported: cite) / NOT-A-BUG (behaviour is intended or expectation unsupported: say why) / UNCLEAR (reproduces but expectation debatable: say what a maintainer would need to decide) / COULD-NOT-RUN (say what blocked you).

Return, as text, in this order: bug id and title; one-sentence claim; verdict; repro.py contents; verbatim output; expectation check; duplicate search; security line; anything a maintainer would push back on. Keep it under 60 lines. No files outside /tmp/httpxv/<bug-id>/.
