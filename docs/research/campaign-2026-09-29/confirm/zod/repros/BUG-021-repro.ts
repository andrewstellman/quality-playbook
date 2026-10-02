import * as z from "/tmp/zodw/packages/zod/src/index.js";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const slow = z.string().transform(async (v) => { await sleep(20); return v; });

async function main() {
let bug = false;

// 1. object key order
const objSync = Object.keys(z.object({ a: z.string(), b: z.string() }).parse({ a: "x", b: "y" }));
const objAsync = Object.keys(await z.object({ a: slow, b: z.string() }).parseAsync({ a: "x", b: "y" }));
console.log("object sync keys :", JSON.stringify(objSync));
console.log("object async keys:", JSON.stringify(objAsync));
if (objAsync.join() !== "a,b") bug = true;

// 2. array issue order
const arr = z.array(z.number().refine(async (n) => { await sleep(30 - n * 10); return false; }));
const r = await arr.safeParseAsync([0, 1, 2]);
const paths = r.error!.issues.map((i) => JSON.stringify(i.path));
console.log("array async issue paths:", paths.join(" "));
if (paths.join(" ") !== "[0] [1] [2]") bug = true;

// 3. record entry order
const rec2 = await z.record(z.string(), z.string().transform(async (v) => { if (v === "x") await sleep(20); return v; })).parseAsync({ a: "x", b: "y" });
console.log("record async keys:", JSON.stringify(Object.keys(rec2)));
if (Object.keys(rec2).join() !== "a,b") bug = true;

// 4. map entry order
const m = await z.map(z.string(), z.string().transform(async (v) => { if (v === "x") await sleep(20); return v; })).parseAsync(new Map([["a", "x"], ["b", "y"]]));
console.log("map async keys   :", JSON.stringify([...m.keys()]));
if ([...m.keys()].join() !== "a,b") bug = true;

// 5. set entry order
const s = await z.set(z.string().transform(async (v) => { if (v === "x") await sleep(20); return v; })).parseAsync(new Set(["x", "y"]));
console.log("set async values :", JSON.stringify([...s]));
if ([...s].join() !== "x,y") bug = true;

console.log(bug ? "BUG PRESENT" : "no bug");
process.exit(bug ? 1 : 0);
}
main();
