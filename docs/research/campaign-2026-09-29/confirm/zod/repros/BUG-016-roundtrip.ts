import * as z from "/tmp/zodw/packages/zod/src/index.js";
const js = z.toJSONSchema(z.emoji()) as any;
console.log("toJSONSchema(z.emoji()).pattern =", js.pattern);
const back = z.fromJSONSchema(js);
console.log("z.emoji().safeParse('😀'):", z.emoji().safeParse("😀").success, " round-tripped:", back.safeParse("😀").success);
