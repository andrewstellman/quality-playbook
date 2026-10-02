#!/usr/bin/env bash
# Control arm, gson: standard code review of the pre-fix commit with GPT-5.4 via the copilot CLI.
# Matches the model the original Quality Playbook gson run used (GPT-5.4, April 2026).
#
#   bash ~/Documents/QPB/docs/research/control-2026-09-27/run-gson-control.sh        # 10 runs
#   bash ~/Documents/QPB/docs/research/control-2026-09-27/run-gson-control.sh 20     # 20 runs
#   MODEL=gpt-5.4 bash .../run-gson-control.sh 10
#
# Each run gets a fresh copy of a history-free checkout of google/gson at 27d9ba1e (the parent of the
# fix commit f4d371d, PR #3006), the verbatim standard review prompt, and the same directory scope rule
# as the rest of the control arm. Results land in docs/research/control-2026-09-27/results/.
set -uo pipefail

N="${1:-10}"
MODEL="${MODEL:-gpt-5.4}"
QPB="$HOME/Documents/QPB"
CTRL="$QPB/docs/research/control-2026-09-27"
RESULTS="$CTRL/results"
PRISTINE="$QPB/repos/control-2026-09-27/gson-pristine"   # repos/ is git-ignored
WORK="${TMPDIR:-/tmp}/qpb-gson-control/work"              # outside QPB; reused so copilot trusts one folder
COMMIT=27d9ba1eeeeb156540cf5397504a4f9f256e911f
SCOPE='gson/src/main/java/com/google/gson/internal/bind/'
BUGFILE='gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java'

command -v copilot >/dev/null || { echo "copilot CLI not found (brew install copilot-cli)"; exit 1; }

# 1. A checkout with no history and no remote, so the later fix commit is unreachable.
if [ ! -f "$PRISTINE/$BUGFILE" ]; then
  mkdir -p "$PRISTINE"
  git -C "$PRISTINE" init -q
  git -C "$PRISTINE" remote add origin https://github.com/google/gson.git
  git -C "$PRISTINE" fetch -q --depth 1 origin "$COMMIT" || { echo "fetch failed"; exit 1; }
  git -C "$PRISTINE" checkout -q --detach FETCH_HEAD
  /bin/rm -rf "$PRISTINE/.git"
fi
grep -q 'replaced != null' "$PRISTINE/$BUGFILE" \
  || { echo "The pre-fix code isn't in $PRISTINE; wrong checkout. Delete it and rerun."; exit 1; }

# 2. The prompt: the control arm's standard prompt, verbatim, plus the scope row.
PROMPT="$(cat "$CTRL/STANDARD_REVIEW_PROMPT.md")

---

| Repo | Upstream | Pinned commit | Review scope (paths relative to the checkout) |
|---|---|---|---|
| gson | https://github.com/google/gson | $COMMIT | \`$SCOPE\` |

Your checkout is the current directory. The review scope is relative to it. Write your full review to ./REVIEW.md in the current directory."

mkdir -p "$RESULTS"
VERSION="$(copilot --version 2>/dev/null | head -1)"

# 3. N independent runs. No --allow-all-urls: the prompt forbids web access and this enforces it.
for i in $(seq -w 1 "$N"); do
  /bin/rm -rf "$WORK"; mkdir -p "$(dirname "$WORK")"; cp -R "$PRISTINE" "$WORK"
  OUT="$RESULTS/${MODEL}-gson-run$i"
  START="$(date -u +%FT%TZ)"
  echo "run $i of $N started $START"
  ( cd "$WORK" && copilot --model "$MODEL" --allow-all-tools -p "$PROMPT" ) > "$OUT.stdout.txt" 2>&1
  RC=$?
  END="$(date -u +%FT%TZ)"
  {
    echo "model: $MODEL"
    echo "tool: copilot CLI $VERSION"
    echo "repo: gson"
    echo "pinned commit: $COMMIT"
    echo "scope: $SCOPE"
    echo "started: $START"
    echo "finished: $END"
    echo "exit code: $RC"
    echo "run: $i of $N"
    echo
    if [ -f "$WORK/REVIEW.md" ]; then cat "$WORK/REVIEW.md"; else echo "(no REVIEW.md written; the full transcript is in $(basename "$OUT").stdout.txt)"; fi
  } > "$OUT.md"
  # Anything that suggests the run saw the answer.
  if grep -Eiq 'pull/3006|#3006|f4d371d|fix-duplicate-key|Documents/QPB|/evidence/' "$OUT.stdout.txt"; then
    echo "run $i: possible leak, read $OUT.stdout.txt" | tee -a "$RESULTS/${MODEL}-gson-LEAKS.txt"
  fi
  echo "run $i finished $END (exit $RC): $OUT.md"
done

# 4. Candidate hits only. Every run still has to be read and scored by hand.
echo
echo "Runs whose review mentions the map duplicate-key check (candidates; read them to score):"
grep -l -Ei 'replaced != null|duplicate key' "$RESULTS"/"${MODEL}"-gson-run*.md 2>/dev/null || echo "  none"
