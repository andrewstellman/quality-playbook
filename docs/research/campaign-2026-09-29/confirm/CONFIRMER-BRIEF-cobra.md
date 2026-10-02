# Confirmer brief (cobra, campaign 2026-09-29)

You are confirming ONE candidate bug from an automated review of cobra at commit adbc8813901bba65827259daa8e22ff94ec1f30e. Your job is to find out whether it is real, not to agree with the report.

Setup that already works:
- Source tree (read-only, do not modify): /tmp/cobraw  (Go module github.com/spf13/cobra). Go toolchain: export PATH=/tmp/go/bin:$PATH GOPATH=/tmp/gopath GOCACHE=/tmp/gocache HOME=/tmp/home. Project tests: cd /tmp/cobraw && go test ./... (all pass at baseline).
- Write a repro as a tiny Go module in your work dir: go.mod with `module repro`, `require github.com/spf13/cobra v1.10.1` and `replace github.com/spf13/cobra => /tmp/cobraw`, then main.go; run with `go mod tidy && go run .`. Alternatively write a _test.go and run it with `go test` from a COPY of /tmp/cobraw placed in your work dir (never edit /tmp/cobraw).
- Source: /tmp/cobraw/*.go (flag parsing comes from github.com/spf13/pflag, a dependency; the bug must be in cobra itself to count).
- Citable docs: /sessions/kind-zealous-edison/mnt/QPB/repos/campaign-2026-09-29/cobra/reference_docs/cite/ (read-only; cobra.dev source, site_content_*.md, plus README.md). Quote the exact sentence you rely on.
- Work only in /tmp/cobrav/<bug-id>/. Do not write anywhere else. Do not push, post, or open anything on GitHub.

Steps:
1. Read your entry in /tmp/cobrav/BUGS-snapshot.md. Restate the claim in one sentence: input, actual, expected, and the source of "expected" (a doc sentence, a spec, or an internal inconsistency such as a sibling function).
2. Write the repro so that it prints the actual behaviour and exits 1 if the bug is present, 0 if not. Run it. Paste the output verbatim.
3. Check the "expected" side yourself. Does the cited doc really say that? Is there a test in /tmp/cobraw/*_test.go that pins the current behaviour (which would mean it is intended)? Is there a comment or changelog entry explaining it?
4. Duplicate search: use WebSearch / web_fetch against https://github.com/spf13/cobra/issues and /pulls for the key terms. Report the closest existing issue/PR (number, title, state) or "none found" with the queries you used.
5. Security angle? (auth bypass, DoS, injection, prototype pollution) yes/no, one line.
6. Verdict, one of: CONFIRMED (reproduces, expectation well-founded, not reported) / CONFIRMED-DUPLICATE (reproduces, already reported: cite) / NOT-A-BUG (behaviour is intended or expectation unsupported: say why) / UNCLEAR (reproduces but expectation debatable: say what a maintainer would need to decide) / COULD-NOT-RUN (say what blocked you).

Return, as text, in this order: bug id and title; one-sentence claim; verdict; repro source; verbatim output; expectation check; duplicate search; security line; anything a maintainer would push back on. Keep it under 60 lines. No files outside /tmp/cobrav/<bug-id>/.
