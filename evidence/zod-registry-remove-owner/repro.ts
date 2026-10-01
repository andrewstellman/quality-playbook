import * as z from "/tmp/zodw/packages/zod/src/index.js";

const r = z.registry<{ id?: string }>();
const a = z.string();
const b = z.number();
r.add(a, { id: "x" });
r.add(b, { id: "x" });
console.log("after 2 adds, _idmap.get('x') === b:", r._idmap.get("x") === b);
r.remove(a);
console.log("after remove(a): has(b) =", r.has(b), " _idmap.has('x') =", r._idmap.has("x"));
const out = z.toJSONSchema(r);
console.log("toJSONSchema(r) =", JSON.stringify(out));
const bug = !r._idmap.has("x") || !("x" in out.schemas);
console.log(bug ? "BUG PRESENT" : "BUG ABSENT");
process.exit(bug ? 1 : 0);
