import * as z from "/tmp/zodw/packages/zod/src/index.js";
const k = Symbol("k");
const r = z.object({ [k]: z.string() }).safeParse({ [k]: "ok", extra: 1 });
console.log(r.success, r.success ? Reflect.ownKeys(r.data) : r.error.issues);
