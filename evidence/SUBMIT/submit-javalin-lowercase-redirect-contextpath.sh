#!/bin/zsh
# Opens a DRAFT pull request on javalin/javalin for: [plugins] Keep the context path in lowercase-path redirects
# Panel: evidence/review-2026-09-30-wave2/ (SYNTHESIS.md, PANEL-2 re-review). Stops at the first failure.
# Run: zsh "/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/submit-javalin-lowercase-redirect-contextpath.sh"     (SKIP_TESTS=1 to skip the local check)
set -euo pipefail
UPSTREAM=javalin/javalin
BRANCH=lowercase-redirect-context-path
PATCH="/Users/andrewstellman/Documents/QPB/evidence/javalin-lowercase-redirect-contextpath/0001-plugins-Keep-the-context-path-in-lowercase-path-redi.patch"
BODY="/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/javalin-lowercase-redirect-contextpath.body.md"
TITLE='[plugins] Keep the context path in lowercase-path redirects'
WORK=$HOME/src/pr-work/javalin
ME=$(gh api user -q .login)
[[ "$ME" == "andrewstellman" ]] || { echo "gh is logged in as $ME, expected andrewstellman"; exit 1; }
DEFAULT=$(gh repo view "$UPSTREAM" --json defaultBranchRef -q .defaultBranchRef.name)
gh repo fork "$UPSTREAM" --clone=false 2>&1 | tail -1
if [[ ! -d "$WORK/.git" ]]; then mkdir -p "$(dirname "$WORK")"; gh repo clone "$ME/javalin" "$WORK" -- --filter=blob:none; fi
git -C "$WORK" remote get-url upstream >/dev/null 2>&1 || git -C "$WORK" remote add upstream "https://github.com/$UPSTREAM.git"
cd "$WORK"
git fetch upstream "$DEFAULT"
git switch -q --detach "upstream/$DEFAULT"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then echo "branch $BRANCH exists; delete it first: git -C $WORK branch -D $BRANCH"; exit 1; fi
git switch -c "$BRANCH"
git am "$PATCH" || { echo "git am failed: upstream moved. Run 'git am --abort' and tell Claude."; exit 1; }
git log --oneline -1
if [[ "${SKIP_TESTS:-0}" != 1 ]]; then
  echo "== local check"
  java -version 2>&1 | head -1
  ./mvnw -B -q -pl javalin test -Dtest=TestRedirectToLowercasePathPlugin
fi
echo "== push to fork"
git push -u origin "$BRANCH"
URL=$(gh pr create --repo "$UPSTREAM" --draft --head "$ME:$BRANCH" --base "$DEFAULT" --title "$TITLE" --body-file "$BODY")
echo "$URL"

gh pr view "$URL" --json number,url,isDraft,title
