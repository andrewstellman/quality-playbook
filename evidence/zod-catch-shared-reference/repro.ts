import * as z from "/tmp/zodw/packages/zod/src/index.js";

let bug = false;

// 1. array catch value shared by reference?
const arr = z.array(z.string()).catch([]);
const a1 = arr.parse(1);
a1.push("leak");
const a2 = arr.parse(1);
console.log("catch([]) second parse:", JSON.stringify(a2), "same ref:", a1 === a2);
if (a2.length !== 0) bug = true;

// 2. Map catch value
const m = z.map(z.string(), z.number()).catch(new Map());
m.parse(1).set("k", 1);
const m2 = m.parse(1);
console.log("catch(new Map()) second parse size:", m2.size);
if (m2.size !== 0) bug = true;

// 3. sibling: default([]) clones
const d = z.array(z.string()).default([]);
const d1 = d.parse(undefined);
d1.push("leak");
const d2 = d.parse(undefined);
console.log("default([]) second parse:", JSON.stringify(d2), "same ref:", d1 === d2);

// 4. compiled path (if exposed)
const anyZ = z as any;
if (typeof anyZ.compile === "function") {
  const c = anyZ.compile(z.array(z.string()).catch([]));
  const c1 = c.parse(1); c1.push("leak");
  console.log("compiled catch([]) second parse:", JSON.stringify(c.parse(1)));
}

process.exit(bug ? 1 : 0);
