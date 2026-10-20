#!/usr/bin/env bash
# One command for the operator, for harrisiirak/cron-parser, bug kit cron-parser-http-date-formats.
# Written by the batch workflow script (wf/submit/make_wrapper.py), not by a model.
#   1. searches the project's issues and pull requests for duplicates (your gh) and shows the hits
#   2. asks before going on            (YES=1 skips the question)
#   3. opens a DRAFT pull request      (SKIP_TESTS=1 skips the local test run inside submit.sh)
#   4. (nothing to renumber in this patch)
# It never marks the pull request ready, comments or merges.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM=harrisiirak/cron-parser
BRANCH=fix/http-date-formats
WORK="${QPB_WORK_DIR:-$HOME/src/pr-work}"/cron-parser
echo "== 1. duplicate search on $UPSTREAM"
bash "$HERE/../dup-search.sh"
OUT="$HERE/../dup-search.out"
echo "---- hits (full output: $OUT) ----"
grep -v -E '^(### |# dup-search|## |$)' "$OUT" | sort -u | head -60 || true
echo "---- end of hits ($(grep -c -E '^FAILED' "$OUT" || true) failed searches) ----"
if [[ "${YES:-0}" != 1 ]]; then
  read -r -p "Open the DRAFT pull request on $UPSTREAM now? [y/N] " ans
  [[ "$ans" == y || "$ans" == Y ]] || { echo "Stopped before opening anything."; exit 0; }
fi
echo "== 2. open the draft pull request"
LOG="$(mktemp)"
bash "$HERE/submit.sh" 2>&1 | tee "$LOG"
URL=$(grep -Eo "https://github.com/$UPSTREAM/pull/[0-9]+" "$LOG" | tail -1)
[[ -n "$URL" ]] || { echo "no pull-request URL in the output above"; exit 1; }
NUM="${URL##*/}"
gh pr view "$URL" --json number,url,isDraft,title
echo "Draft pull request: $URL"
echo "Paste this output to the agent. Marking it ready is yours to do."
