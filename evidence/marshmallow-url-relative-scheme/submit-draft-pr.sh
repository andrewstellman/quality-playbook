#!/usr/bin/env bash
# One command for the operator: opens the DRAFT pull request, then puts the real PR number into the
# CHANGELOG.rst entry (the patch carries the placeholder NNNN, because the number does not exist
# until the PR is open), amends the single commit and force-pushes it to the operator's fork.
# Written by hand by the orchestrating session on 2026-10-05: QPB's script generator can rename a
# file after the PR is created but cannot edit one. It never marks the PR ready, comments or merges.
# SKIP_TESTS=1 skips the local test run inside submit.sh.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${QPB_WORK_DIR:-$HOME/src/pr-work}"/marshmallow
LOG="$(mktemp)"
bash "$HERE/submit.sh" 2>&1 | tee "$LOG"
URL=$(grep -Eo 'https://github.com/marshmallow-code/marshmallow/pull/[0-9]+' "$LOG" | tail -1)
[[ -n "$URL" ]] || { echo "no pull-request URL in the output above; nothing was renumbered"; exit 1; }
NUM="${URL##*/}"
cd "$WORK"
[[ "$(git rev-parse --abbrev-ref HEAD)" == "fix-url-relative-scheme-in-query" ]] || { echo "unexpected branch in $WORK; CHANGELOG.rst still says NNNN"; exit 1; }
[[ "$(grep -c '(:pr:`NNNN`)' CHANGELOG.rst)" == 1 ]] || { echo "expected exactly one NNNN placeholder in CHANGELOG.rst; left unchanged"; exit 1; }
echo "== put the PR number $NUM into CHANGELOG.rst, amend, force-push"
perl -pi -e 's/\(:pr:`NNNN`\)/(:pr:`'"$NUM"'`)/' CHANGELOG.rst
[[ "$(git diff --numstat | awk '{print $1" "$2" "$3}')" == "1 1 CHANGELOG.rst" ]] || { echo "unexpected diff after the edit; not pushed"; git diff --stat; exit 1; }
git add CHANGELOG.rst
git commit -q --amend --no-edit
git push --force-with-lease
git log --oneline -1
gh pr view "$URL" --json number,url,isDraft,title
echo "Draft PR $URL now carries its own number in CHANGELOG.rst. Paste this output to the agent."
