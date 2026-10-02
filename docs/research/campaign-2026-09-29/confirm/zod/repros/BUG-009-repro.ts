import * as z from "/tmp/zodw/packages/zod/src/index.js";

// Docs (api.md:1393): "Regular `.extend()` will throw an error when used on schemas with refinements."
const refined = z.object({ a: z.string() }).refine((d) => d.a.length > 0);

let threwOnNewKey = false;
let extended: any;
try {
  extended = refined.extend({ b: z.string() }); // non-overlapping key
} catch (e) {
  threwOnNewKey = true;
  console.log("extend({b}) threw:", (e as Error).message);
}
if (!threwOnNewKey) {
  console.log("extend({b}) returned a schema; parse ok:", JSON.stringify(extended.parse({ a: "x", b: "y" })));
  console.log("refinement carried over (empty a rejected):", !extended.safeParse({ a: "", b: "y" }).success);
}

let threwOnOverlap = false;
try { refined.extend({ a: z.number() }); } catch (e) { threwOnOverlap = true; console.log("extend({a}) threw:", (e as Error).message); }

console.log("sibling .merge() throws:", (() => { try { refined.merge(z.object({ b: z.string() })); return false; } catch { return true; } })());

// Bug present (per report) = extend on a refined schema does NOT throw for a non-overlapping key
process.exit(threwOnNewKey ? 0 : 1);
