import * as z from "/tmp/zodw/packages/zod/src/index.js";

let bug = false;
function run(label: string, schema: any, input: unknown) {
  try {
    const r = schema.safeParse(input);
    console.log(label, "->", r.success ? "success" : "failure", r.success ? r.data : r.error.issues.map((i: any) => i.code));
  } catch (e: any) {
    bug = true;
    console.log(label, "-> THREW:", e.message);
  }
}
run("map&map  Map{a=>1}", z.intersection(z.map(z.string(), z.number()), z.map(z.string(), z.number())), new Map([["a", 1]]));
run("map&map  empty Map", z.intersection(z.map(z.string(), z.number()), z.map(z.string(), z.number())), new Map());
run("set&set.min(1) Set{1}", z.intersection(z.set(z.number()), z.set(z.number()).min(1)), new Set([1]));
run("set&set  wrong input 'x'", z.intersection(z.set(z.number()), z.set(z.number())), "x");
run("control: obj&obj", z.intersection(z.object({ a: z.string() }), z.object({ b: z.number() })), { a: "x", b: 1 });
run("control: arr&arr", z.intersection(z.array(z.number()), z.array(z.number()).min(1)), [1]);
process.exit(bug ? 1 : 0);
