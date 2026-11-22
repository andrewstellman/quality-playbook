status: open
title: cobra: PowerShell completion offered nothing for a shorthand flag with an equal sign (-o=<TAB>)
link: https://github.com/spf13/cobra/pull/2581
updated: 2026-11-22
note: Opened 2026-11-22 from Andrew's account (web editor; commits 11250f95 fix, 671da8fa test, author andrewstellman@users.noreply.github.com). CLA not yet signed at opening. No review yet. Found as cobra BUG-018 in the 29 Sep 2026 campaign run (QPB 1.6.0, Claude Opus 5.5).

## Files

- repro/: run.log, Andrew's Mac, PowerShell 7.7.0, a CLI built from cobra at adbc8813 (main.go, go.mod with a replace to the pinned tree); prog-completion.ps1 is the generated script; run.ps1 asks PowerShell's completer (TabExpansion2). `prog get -o=` gives no completions, `prog get --output=` gives both values.
- fix-check/: run-fixed.log, the same test with cobra main (still adbc8813) plus the fix: `-o=` gives -o=json, -o=yaml; the other three cases unchanged. The darwin binaries both runs used were built from main.go in a cloud workspace and are not kept here (rebuild with go build).
- cobra-pwsh-shorthand-equal.patch: the diff as pushed (one-line change in powershell_completions.go, one test in powershell_completions_test.go). COMMIT-MESSAGE.txt: the fix commit's message. PR.md: the PR title and description as posted.
- go test ./... in the cloud workspace: only TestFailGenFishCompletionFile fails, the same on unpatched main (the workspace runs as root).
- Confirmation path: reproduced independently in the research chat's full confirmation of the study codebases (haiku-reqdoc-2026-11/study-sample/confirm/cobra-BUG-018/), marked ENV-BLOCKED in the cloud (no PowerShell), then confirmed on the Mac.
