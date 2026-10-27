#!/bin/bash
# usage: knock_on.sh <checkout> <output-file>
# Copies knock_on.test.ts into <checkout>/test/ (in a scratch checkout only), runs it at two process time zones.
set -u
CO=$1; OUTF=$2; HERE=$(cd "$(dirname "$0")" && pwd)
cp "$HERE/knock_on.test.ts" "$CO/test/knock_on.test.ts"
: > "$OUTF"
for tz in UTC Asia/Tokyo America/New_York; do
  (cd "$CO" && TZ=$tz KNOCK_OUT="$OUTF.${tz//\//_}" ./node_modules/.bin/jest --silent --rootDir . test/knock_on.test.ts >/dev/null 2>&1; echo "jest exit $? at TZ=$tz" >&2)
  cat "$OUTF.${tz//\//_}" >> "$OUTF"; rm -f "$OUTF.${tz//\//_}"
done
rm -f "$CO/test/knock_on.test.ts"
