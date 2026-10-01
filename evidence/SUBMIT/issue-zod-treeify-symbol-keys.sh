#!/bin/zsh
# Opens an ISSUE on colinhacks/zod (PRs are limited to collaborators there),
# after pushing the fix to a branch on your fork and linking it from the issue.
# Run: zsh "/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/issue-zod-treeify-symbol-keys.sh"
set -euo pipefail
UPSTREAM=colinhacks/zod
BRANCH=treeify-symbol-keys
PATCH="/Users/andrewstellman/Documents/QPB/evidence/zod-treeify-symbol-keys/0001-fix-file-symbol-path-keys-under-properties-in-treeif.patch"
BODY_TEMPLATE="/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/zod-treeify-symbol-keys.issue.md"
TITLE='treeifyError() files symbol-keyed issues under items instead of properties'
WORK=$HOME/src/pr-work/zod
ME=$(gh api user -q .login)
[[ "$ME" == "andrewstellman" ]] || { echo "gh is logged in as $ME, expected andrewstellman"; exit 1; }
gh repo fork "$UPSTREAM" --clone=false 2>&1 | tail -1
if [[ ! -d "$WORK/.git" ]]; then mkdir -p "$(dirname "$WORK")"; gh repo clone "$ME/zod" "$WORK" -- --filter=blob:none; fi
git -C "$WORK" remote get-url upstream >/dev/null 2>&1 || git -C "$WORK" remote add upstream "https://github.com/$UPSTREAM.git"
cd "$WORK"
git fetch upstream main
git switch -q --detach upstream/main
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then echo "branch $BRANCH exists; delete it first: git -C $WORK branch -D $BRANCH"; exit 1; fi
git switch -c "$BRANCH"
git am "$PATCH" || { echo "git am failed: upstream moved. Run 'git am --abort' and tell Claude."; exit 1; }
git push -u origin "$BRANCH"
COMPARE="https://github.com/$UPSTREAM/compare/main...$ME:zod:$BRANCH"
BODY=$(sed "s#__COMPARE__#$COMPARE#" "$BODY_TEMPLATE")
grep -q __COMPARE__ <<<"$BODY" && { echo "placeholder not replaced"; exit 1; }
URL=$(gh issue create --repo "$UPSTREAM" --title "$TITLE" --body "$BODY")
echo "$URL"
gh issue view "$URL" --json number,url,title,state
