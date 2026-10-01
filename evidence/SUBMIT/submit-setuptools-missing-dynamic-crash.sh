#!/bin/zsh
# Opens a DRAFT pull request on pypa/setuptools for: Ignore readme and requires-python not listed in dynamic
# Panel: evidence/review-2026-09-30-wave2/ (SYNTHESIS.md, PANEL-2 re-review). Stops at the first failure.
# Run: zsh "/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/submit-setuptools-missing-dynamic-crash.sh"     (SKIP_TESTS=1 to skip the local check)
set -euo pipefail
UPSTREAM=pypa/setuptools
BRANCH=missing-dynamic-readme-requires-python
PATCH="/Users/andrewstellman/Documents/QPB/evidence/setuptools-missing-dynamic-crash/0001-Ignore-readme-and-requires-python-not-listed-in-dyna.patch"
BODY="/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/setuptools-missing-dynamic-crash.body.md"
TITLE='Ignore readme and requires-python not listed in dynamic'
WORK=$HOME/src/pr-work/setuptools
ME=$(gh api user -q .login)
[[ "$ME" == "andrewstellman" ]] || { echo "gh is logged in as $ME, expected andrewstellman"; exit 1; }
DEFAULT=$(gh repo view "$UPSTREAM" --json defaultBranchRef -q .defaultBranchRef.name)
gh repo fork "$UPSTREAM" --clone=false 2>&1 | tail -1
if [[ ! -d "$WORK/.git" ]]; then mkdir -p "$(dirname "$WORK")"; gh repo clone "$ME/setuptools" "$WORK" -- --filter=blob:none; fi
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
  VENV="$WORK-venv"; [[ -d "$VENV" ]] || python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -e ".[test]"
  "$VENV/bin/python" -m pytest -q -p no:cacheprovider setuptools/tests/config/test_apply_pyprojecttoml.py
fi
echo "== push to fork"
git push -u origin "$BRANCH"
URL=$(gh pr create --repo "$UPSTREAM" --draft --head "$ME:$BRANCH" --base "$DEFAULT" --title "$TITLE" --body-file "$BODY")
echo "$URL"

NUM=$(gh pr view "$URL" --json number -q .number)
echo "== rename the news fragment to PR #$NUM"
git mv newsfragments/+missing-dynamic-readme-requires-python.bugfix.rst "newsfragments/$NUM.bugfix.rst"
git commit -q --amend --no-edit
git push --force-with-lease
gh pr view "$URL" --json number,url,isDraft,title
