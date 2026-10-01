#!/bin/zsh
# Opens a DRAFT pull request for: Fix readuntil() missing a separator split across chunks
# Run from anywhere: zsh "/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/submit-aiohttp-readuntil.sh"
# Stops at the first failure. Never marks the PR ready; that is your call after you read it.
set -euo pipefail
UPSTREAM=aio-libs/aiohttp
DEFAULT=master
BRANCH=fix-readuntil-split-separator
PATCH="/Users/andrewstellman/Documents/QPB/evidence/aiohttp-readuntil-split-separator/v2/0001-Fix-readuntil-missing-a-separator-split-across-chunk.patch"
BODY="/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/aiohttp-readuntil.body.md"
TITLE='Fix readuntil() missing a separator split across chunks'
WORK=$HOME/src/pr-work/aiohttp
ME=$(gh api user -q .login)
[[ "$ME" == "andrewstellman" ]] || { echo "gh is logged in as $ME, expected andrewstellman"; exit 1; }
gh repo view "$UPSTREAM" --json name >/dev/null

echo "== fork (no-op if it already exists)"
gh repo fork "$UPSTREAM" --clone=false 2>&1 | tail -1
FORK="$ME/${UPSTREAM#*/}"

echo "== clone or update $WORK"
if [[ ! -d "$WORK/.git" ]]; then
  mkdir -p "$(dirname "$WORK")"
  gh repo clone "$FORK" "$WORK" -- --filter=blob:none
fi
if ! git -C "$WORK" remote get-url upstream >/dev/null 2>&1; then
  git -C "$WORK" remote add upstream "https://github.com/$UPSTREAM.git"
fi
cd "$WORK"
git fetch upstream "$DEFAULT"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo "branch $BRANCH already exists locally; delete it first if you want to start over:"
  echo "  git -C $WORK branch -D $BRANCH"; exit 1
fi
git switch -c "$BRANCH" "upstream/$DEFAULT"

echo "== apply the reviewed patch on top of current upstream/$DEFAULT"
git am "$PATCH" || { echo "git am failed: upstream moved under this patch. Run 'git am --abort' and tell Claude."; exit 1; }
git log --oneline -1

echo "== run the affected tests (AGENTS.md: prove it works before opening the PR)"
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements/test.in
AIOHTTP_NO_EXTENSIONS=1 PYTHONPATH=. .venv/bin/python -m pytest tests/test_streams.py --numprocesses=0 --no-cov -q
echo "== push to fork"
git push -u origin "$BRANCH"

echo "== open draft PR"
URL=$(gh pr create --repo "$UPSTREAM" --draft --head "$ME:$BRANCH" --base "$DEFAULT" --title "$TITLE" --body-file "$BODY")
echo "$URL"

NUM=$(gh pr view "$URL" --json number -q .number)
echo "== rename the news fragment to PR #$NUM (towncrier requires it)"
git mv CHANGES/PRNUMBER.bugfix.rst "CHANGES/$NUM.bugfix.rst"
git commit --amend --no-edit
git push --force-with-lease
echo "== result"
gh pr view "$URL" --json number,url,isDraft,title
