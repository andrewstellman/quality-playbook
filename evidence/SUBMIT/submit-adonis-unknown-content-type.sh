#!/bin/zsh
# Opens a DRAFT pull request on adonisjs/http-server (base 9.x) for: fix(response): fall back to octet-stream for unknown content types
# Runs the project's own tests on this Mac before pushing. Stops at the first failure.
# Run: zsh "/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/submit-adonis-unknown-content-type.sh"
set -euo pipefail
UPSTREAM=adonisjs/http-server
DEFAULT=9.x
BRANCH=unknown-content-type-octet-stream
PATCH="/Users/andrewstellman/Documents/QPB/evidence/adonis-unknown-content-type/0001-fix-response-fall-back-to-octet-stream-for-unknown-c.patch"
BODY="/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/adonis-unknown-content-type.body.md"
TITLE='fix(response): fall back to octet-stream for unknown content types'
WORK=$HOME/src/pr-work/adonis-http-server
ME=$(gh api user -q .login)
[[ "$ME" == "andrewstellman" ]] || { echo "gh is logged in as $ME, expected andrewstellman"; exit 1; }
gh repo fork "$UPSTREAM" --clone=false 2>&1 | tail -1
if [[ ! -d "$WORK/.git" ]]; then mkdir -p "$(dirname "$WORK")"; gh repo clone "$ME/http-server" "$WORK" -- --filter=blob:none; fi
git -C "$WORK" remote get-url upstream >/dev/null 2>&1 || git -C "$WORK" remote add upstream "https://github.com/$UPSTREAM.git"
cd "$WORK"
git fetch upstream "$DEFAULT"
git switch -q --detach "upstream/$DEFAULT"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then echo "branch $BRANCH exists; delete it first: git -C $WORK branch -D $BRANCH"; exit 1; fi
git switch -c "$BRANCH"
git am "$PATCH" || { echo "git am failed: upstream moved. Run 'git am --abort' and tell Claude."; exit 1; }
git log --oneline -1
echo "== npm install + project checks (the PR text says these were run)"
npm install --no-audit --no-fund
npm run quick:test
npm run typecheck
echo "== push to fork"
git push -u origin "$BRANCH"
URL=$(gh pr create --repo "$UPSTREAM" --draft --head "$ME:$BRANCH" --base "$DEFAULT" --title "$TITLE" --body-file "$BODY")
echo "$URL"
gh pr view "$URL" --json number,url,isDraft,title
