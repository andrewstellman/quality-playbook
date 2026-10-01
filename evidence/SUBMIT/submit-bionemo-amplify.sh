#!/bin/zsh
# Opens a DRAFT pull request for: amplify: keep dtype/device of padding rows in `_pad_weights`
# Run from anywhere: zsh "/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/submit-bionemo-amplify.sh"
# Stops at the first failure. Never marks the PR ready; that is your call after you read it.
set -euo pipefail
UPSTREAM=NVIDIA-BioNeMo/bionemo-recipes
DEFAULT=main
BRANCH=amplify-pad-weights-dtype
PATCH="/Users/andrewstellman/Documents/QPB/evidence/bionemo-amplify-pad-weights-dtype/v2/0001-amplify-keep-dtype-device-of-padding-rows-in-_pad_we.patch"
BODY="/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/bionemo-amplify.body.md"
TITLE='amplify: keep dtype/device of padding rows in `_pad_weights`'
WORK=$HOME/src/pr-work/bionemo-recipes
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

echo "== regenerated copies must match (repo CI check)"
python3 ci/scripts/check_copied_files.py
echo "== push to fork"
git push -u origin "$BRANCH"

echo "== open draft PR"
URL=$(gh pr create --repo "$UPSTREAM" --draft --head "$ME:$BRANCH" --base "$DEFAULT" --title "$TITLE" --body-file "$BODY")
echo "$URL"

echo "== result"
gh pr view "$URL" --json number,url,isDraft,title
