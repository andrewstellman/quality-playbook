#!/bin/zsh
# Opens a DRAFT pull request on sporkmonger/addressable for: Fix route_from when only the base URI has a query
# Panel: evidence/review-2026-09-30-wave2/ (SYNTHESIS.md, PANEL-2 re-review). Stops at the first failure.
# Run: zsh "/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/submit-addressable-route-from-base-query.sh"     (SKIP_TESTS=1 to skip the local check)
set -euo pipefail
UPSTREAM=sporkmonger/addressable
BRANCH=route-from-base-query
PATCH="/Users/andrewstellman/Documents/QPB/evidence/addressable-route-from-base-query/0001-Fix-route_from-when-only-the-base-URI-has-a-query.patch"
BODY="/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/addressable-route-from-base-query.body.md"
TITLE='Fix route_from when only the base URI has a query'
WORK=$HOME/src/pr-work/addressable
ME=$(gh api user -q .login)
[[ "$ME" == "andrewstellman" ]] || { echo "gh is logged in as $ME, expected andrewstellman"; exit 1; }
DEFAULT=$(gh repo view "$UPSTREAM" --json defaultBranchRef -q .defaultBranchRef.name)
gh repo fork "$UPSTREAM" --clone=false 2>&1 | tail -1
if [[ ! -d "$WORK/.git" ]]; then mkdir -p "$(dirname "$WORK")"; gh repo clone "$ME/addressable" "$WORK" -- --filter=blob:none; fi
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
  command -v bundle >/dev/null || { echo "bundler not found, or rerun with SKIP_TESTS=1"; exit 1; }
  bundle config set --local path vendor/bundle && bundle install --quiet && bundle exec rspec spec/addressable/uri_spec.rb
fi
echo "== push to fork"
git push -u origin "$BRANCH"
URL=$(gh pr create --repo "$UPSTREAM" --draft --head "$ME:$BRANCH" --base "$DEFAULT" --title "$TITLE" --body-file "$BODY")
echo "$URL"

gh pr view "$URL" --json number,url,isDraft,title
