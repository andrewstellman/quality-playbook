#!/bin/bash
# otel-verify.sh <repo> <outdir> <suite:SEL>...   (repo has tags: base-less; branch fix, tag v1; base = fix~1)
set -u
R=$1; O=$2; shift 2
cd $R; BASE=$(git rev-parse fix~1); FIX=$(git rev-parse fix)
MAIN=$(git diff --name-only $BASE $FIX | grep '/src/main/'); TESTS=$(git diff --name-only $BASE $FIX | grep '/src/test/')
mkdir -p $O
hdr(){ echo "# $1"; echo "# tree: HEAD=$(git rev-parse HEAD); working-tree changes vs HEAD:"; git status --short | sed 's/^/#   /'; }
runall(){ local sel=$1; for spec in "${SPECS[@]}"; do S=${spec%%:*}; SL=${spec#*:}; echo "########## suite: $S"; if [ $sel = full ]; then /tmp/harness/run.sh $R $S; else SEL_OVERRIDE="$SL" /tmp/harness/run.sh $R $S; fi; done; }
SPECS=("$@")
git checkout -q --detach $BASE
{ hdr "suite-before: unmodified upstream $BASE, existing tests, module suite selection"; runall full; } > $O/suite-before.log 2>&1
git checkout -q $FIX -- $TESTS
{ hdr "red (tests only): upstream $BASE main code + test files from $FIX: $TESTS"; runall reg; } > $O/red.log 2>&1
git checkout -q -f fix
{ hdr "green (full): $FIX = fix + tests"; runall reg; } > $O/green.log 2>&1
{ hdr "suite-after: $FIX, module suite selection"; runall full; } > $O/suite-after.log 2>&1
git checkout -q $BASE -- $MAIN
{ hdr "revert: $FIX with non-test files reverted to $BASE ($MAIN), tests kept"; runall reg; } > $O/revert.log 2>&1
git checkout -q -f fix
if git rev-parse -q --verify v1 >/dev/null && [ "${V1CHECK:-}" = 1 ]; then
  git checkout -q v1 -- $MAIN
  { hdr "v1-code-v2-tests: v1 main code (tag v1 $(git rev-parse v1)) with v2 tests"; runall reg; } > $O/v1-code-v2-tests.log 2>&1
  git checkout -q -f fix
fi
git status --short
for f in $O/*.log; do echo "$(basename $f): $(grep -E 'tests (successful|failed)|exit code' $f | tr -s ' ' | tr '\n' ' ')"; done
