import * as z from "/tmp/zodw/packages/zod/src/index.js";

// Claim: docs say registering two schemas with the same id throws. Test both a custom and the global registry.
let threw = false;
const r = z.registry<{ id?: string }>();
const a = z.string();
const b = z.number();
r.add(a, { id: "dup" });
try {
  r.add(b, { id: "dup" });
} catch (e) {
  threw = true;
  console.log("custom registry threw:", (e as Error).message);
}
console.log("custom registry: second add threw =", threw);
console.log("custom registry: _idmap.get('dup') is", r._idmap.get("dup") === b ? "second schema (overwritten)" : r._idmap.get("dup") === a ? "first schema" : "neither");
console.log("custom registry: both schemas still registered =", r.has(a) && r.has(b));

let gthrew = false;
const ga = z.string();
const gb = z.boolean();
z.globalRegistry.add(ga, { id: "gdup" });
try {
  z.globalRegistry.add(gb, { id: "gdup" });
} catch (e) {
  gthrew = true;
  console.log("global registry threw:", (e as Error).message);
}
console.log("global registry: second add threw =", gthrew);

// For contrast: toJSONSchema rejects duplicates when both are converted together
try {
  z.toJSONSchema(r);
  console.log("toJSONSchema(registry): no error");
} catch (e) {
  console.log("toJSONSchema(registry) threw:", (e as Error).message);
}

process.exit(threw && gthrew ? 0 : 1);
