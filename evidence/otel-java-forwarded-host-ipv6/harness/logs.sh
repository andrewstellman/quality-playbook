#!/bin/bash
# logs.sh <branch> <suite> <outdir> <regression SEL>
# Produces module-tests-before/after, red, green logs for a single-commit branch on top of the pinned SHA.
set -u
BR=$1; SUITE=$2; OUTD=$3; RSEL=$4
BASE=78d71b585a77d7f2312c1b8751ff6c95a72722d7
R=/tmp/otel-java
mkdir -p $OUTD
rm -rf /tmp/wt-base /tmp/wt-red /tmp/wt-green
git -C $R worktree prune
git -C $R worktree add -q --detach /tmp/wt-base $BASE
git -C $R worktree add -q --detach /tmp/wt-red $BASE
git -C $R worktree add -q --detach /tmp/wt-green $BR
# red = pinned SHA + only the test-file changes from the branch commit
TESTS=$(git -C $R diff --name-only $BASE $BR | grep '/src/test/')
(cd /tmp/wt-red && git -C $R diff $BASE $BR -- $TESTS | git apply && git status --short)
{ echo "# module-tests-before: unmodified upstream $BASE, existing tests only"; /tmp/harness/run.sh /tmp/wt-base $SUITE; } > $OUTD/module-tests-before.log 2>&1
{ echo "# red: upstream $BASE main code + regression tests from branch $BR ($(git -C $R rev-parse --short $BR)) applied; test files: $TESTS"; SEL_OVERRIDE="$RSEL" /tmp/harness/run.sh /tmp/wt-red $SUITE; } > $OUTD/red.log 2>&1
{ echo "# green: branch $BR ($(git -C $R rev-parse $BR)) = fix + regression tests"; SEL_OVERRIDE="$RSEL" /tmp/harness/run.sh /tmp/wt-green $SUITE; } > $OUTD/green.log 2>&1
{ echo "# module-tests-after: branch $BR ($(git -C $R rev-parse $BR)), full suite selection"; /tmp/harness/run.sh /tmp/wt-green $SUITE; } > $OUTD/module-tests-after.log 2>&1
for f in module-tests-before red green module-tests-after; do echo "$f: $(grep -E 'tests successful|tests failed' $OUTD/$f.log | tr -s ' ' | tr '\n' ' ') $(grep 'junit exit code' $OUTD/$f.log)"; done
git -C $R worktree remove --force /tmp/wt-base; git -C $R worktree remove --force /tmp/wt-red; git -C $R worktree remove --force /tmp/wt-green
