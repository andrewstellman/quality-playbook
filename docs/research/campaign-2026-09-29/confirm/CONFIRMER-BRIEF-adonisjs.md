# Confirmer brief (adonisjs http-server, campaign 2026-09-29)

You are confirming ONE candidate bug from an automated review of @adonisjs/http-server at commit 3bf3cde3200da459ec8977365cd3435924a258e3. Your job is to find out whether it is real, not to agree with the report.

Setup that already works:
- Source tree (read-only, do not modify): /tmp/adonw  (deps installed in node_modules; package source is /tmp/adonw/src and /tmp/adonw/index.ts; test suite: cd /tmp/adonw && HOME=/tmp/home node --import=@poppinss/ts-exec --enable-source-maps bin/test.ts  (japa; add --files=<name> to narrow))
- Run TypeScript directly:  cd /tmp/adonw && HOME=/tmp/home node --import=@poppinss/ts-exec /tmp/adonv/<bug-id>/repro.ts   (import from absolute paths like "/tmp/adonw/index.js" or "/tmp/adonw/src/<file>.js"; tests/*.spec.ts show how router, server, request and response are built in tests)
- The package has many runtime deps; they are installed. Do not npm install anything else.
- Citable docs: /sessions/kind-zealous-edison/mnt/QPB/repos/campaign-2026-09-29/adonisjs-http-server/reference_docs/cite/ (read-only; AdonisJS v6 docs, filenames v6-docs_*.md, plus README.md). Quote the exact sentence you rely on.
- Work only in /tmp/adonv/<bug-id>/. Do not write anywhere else. Do not push, post, or open anything on GitHub.

Steps:
1. Read your entry in /tmp/adonv/BUGS-snapshot.md. Restate the claim in one sentence: input, actual, expected, and the source of "expected" (a doc sentence, a spec, or an internal inconsistency such as a sibling function).
2. Write repro.ts that prints the actual behaviour and exits 1 if the bug is present, 0 if not. Run it. Paste the output verbatim.
3. Check the "expected" side yourself. Does the cited doc really say that? Is there a test in /tmp/adonw/tests/ that pins the current behaviour (which would mean it is intended)? Is there a comment or changelog entry explaining it?
4. Duplicate search: use WebSearch / web_fetch against https://github.com/adonisjs/http-server/issues and /pulls (also adonisjs/core, where many reports land) for the key terms. Report the closest existing issue/PR (number, title, state) or "none found" with the queries you used.
5. Security angle? (auth bypass, DoS, injection, prototype pollution) yes/no, one line.
6. Verdict, one of: CONFIRMED (reproduces, expectation well-founded, not reported) / CONFIRMED-DUPLICATE (reproduces, already reported: cite) / NOT-A-BUG (behaviour is intended or expectation unsupported: say why) / UNCLEAR (reproduces but expectation debatable: say what a maintainer would need to decide) / COULD-NOT-RUN (say what blocked you).

Return, as text, in this order: bug id and title; one-sentence claim; verdict; repro.ts contents; verbatim output; expectation check; duplicate search; security line; anything a maintainer would push back on. Keep it under 60 lines. No files outside /tmp/adonv/<bug-id>/.
