#!/bin/zsh
# Opens a DRAFT pull request for: Handle bracketed IPv6 hosts in UrlParser
# Run from anywhere: zsh "/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/submit-otel-urlparser.sh"
# Stops at the first failure. Never marks the PR ready; that is your call after you read it.
set -euo pipefail
UPSTREAM=open-telemetry/opentelemetry-java-instrumentation
DEFAULT=main
BRANCH=urlparser-ipv6
PATCH="/Users/andrewstellman/Documents/QPB/evidence/otel-java-urlparser-ipv6/v2/0001-Handle-bracketed-IPv6-hosts-in-UrlParser.patch"
BODY="/Users/andrewstellman/Documents/QPB/evidence/SUBMIT/otel-urlparser.body.md"
TITLE='Handle bracketed IPv6 hosts in UrlParser'
WORK=$HOME/src/pr-work/otel-java-instrumentation
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

echo "== Gradle (JDK 25 required; slow the first time)"
java -version
./gradlew spotlessApply
if [[ -n "$(git status --porcelain)" ]]; then echo "spotless reformatted files; folding into the commit"; git add -A; git commit --amend --no-edit; fi
./gradlew :instrumentation-api-incubator:check \
  :instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent-unit-tests:check \
  :instrumentation:reactor:reactor-netty:reactor-netty-1.0:javaagent:compileJava \
  :instrumentation:clickhouse:clickhouse-client-v2-0.8:javaagent:compileJava
echo "== push to fork"
git push -u origin "$BRANCH"

echo "== open draft PR"
URL=$(gh pr create --repo "$UPSTREAM" --draft --head "$ME:$BRANCH" --base "$DEFAULT" --title "$TITLE" --body-file "$BODY")
echo "$URL"

echo "== result"
gh pr view "$URL" --json number,url,isDraft,title
