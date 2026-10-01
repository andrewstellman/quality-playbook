#!/bin/zsh
# Opens a DRAFT pull request on colinhacks/zod for: fix(v4): shallow-clone a constant .catch() value on every parse
# Run: zsh "/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/submit-zod-catch-shared-reference.sh"
# Stops at the first failure. Never marks the PR ready.
set -euo pipefail
UPSTREAM=colinhacks/zod
DEFAULT=main
BRANCH=catch-shallow-clone
PATCH="/Users/andrewstellman/Documents/QPB/evidence/zod-catch-shared-reference/0001-fix-v4-shallow-clone-a-constant-.catch-value-on-ever.patch"
BODY="/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/zod-catch-shared-reference.body.md"
TITLE='fix(v4): shallow-clone a constant .catch() value on every parse'
WORK=$HOME/src/pr-work/zod
ME=$(gh api user -q .login)
[[ "$ME" == "andrewstellman" ]] || { echo "gh is logged in as $ME, expected andrewstellman"; exit 1; }
echo "== fork (no-op if it already exists)"
gh repo fork "$UPSTREAM" --clone=false 2>&1 | tail -1
FORK="$ME/zod"
if [[ ! -d "$WORK/.git" ]]; then mkdir -p "$(dirname "$WORK")"; gh repo clone "$FORK" "$WORK" -- --filter=blob:none; fi
git -C "$WORK" remote get-url upstream >/dev/null 2>&1 || git -C "$WORK" remote add upstream "https://github.com/$UPSTREAM.git"
cd "$WORK"
git fetch upstream "$DEFAULT"
git switch -q --detach "upstream/$DEFAULT"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then echo "branch $BRANCH exists; delete it first: git -C $WORK branch -D $BRANCH"; exit 1; fi
git switch -c "$BRANCH"
echo "== apply the reviewed patch on top of current upstream/$DEFAULT"
git am "$PATCH" || { echo "git am failed: upstream moved under this patch. Run 'git am --abort' and tell Claude."; exit 1; }
git log --oneline -1
echo "== push to fork"
git push -u origin "$BRANCH"
echo "== open draft PR"
URL=$(gh pr create --repo "$UPSTREAM" --draft --head "$ME:$BRANCH" --base "$DEFAULT" --title "$TITLE" --body-file "$BODY")
echo "$URL"
gh pr view "$URL" --json number,url,isDraft,title
