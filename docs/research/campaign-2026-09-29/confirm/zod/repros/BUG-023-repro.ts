import * as z from "/tmp/zodw/packages/zod/src/index.js";

let bug = false;
function check(label: string, schema: any) {
  const a = schema.parse(undefined) as Date;
  const b = schema.parse(undefined) as Date;
  const same = a === b;
  a.setTime(1);
  const after = schema.parse(undefined).getTime();
  console.log(`${label}: sameInstance=${same} thirdParse.getTime()=${after} (expected 0)`);
  if (same || after !== 0) bug = true;
}
check("z.date().default(new Date(0))", z.date().default(new Date(0)));
check("z.date().prefault(new Date(0))", z.date().prefault(new Date(0)));
check("compiled default", z.compile(z.date().default(new Date(0))));
// Control: Map default is cloned
const m = z.map(z.string(), z.number()).default(new Map());
console.log("control Map: sameInstance=" + (m.parse(undefined) === m.parse(undefined)));
process.exit(bug ? 1 : 0);
