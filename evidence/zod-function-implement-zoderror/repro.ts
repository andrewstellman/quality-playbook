import * as z from "/tmp/zodw/packages/zod/src/index.js";

const f = z.function({ input: [z.string()], output: z.number() }).implement((s) => s.length);
let bug = false;
try { f(1 as any); console.log("no throw"); bug = true; }
catch (e: any) {
  console.log("sync: ctor =", e.constructor.name, "| instanceof z.ZodError =", e instanceof z.ZodError,
    "| flatten:", typeof e.flatten, "| format:", typeof e.format);
  if (!(e instanceof z.ZodError)) bug = true;
}
(async () => {
const g = z.function({ input: [z.string()], output: z.number() }).implementAsync(async (s) => s.length);
try { await g(1 as any); console.log("async: no throw"); bug = true; }
catch (e: any) {
  console.log("async: ctor =", e.constructor.name, "| instanceof z.ZodError =", e instanceof z.ZodError);
  if (!(e instanceof z.ZodError)) bug = true;
}
// baseline: schema.parse
try { z.string().parse(1); } catch (e: any) { console.log("parse: ctor =", e.constructor.name, "| instanceof z.ZodError =", e instanceof z.ZodError); }
process.exit(bug ? 1 : 0);
})();
