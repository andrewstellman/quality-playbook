import * as z from "/tmp/zodw/packages/zod/src/index.js";

let bug = false;
function tryCase(label: string, fn: () => unknown) {
  try {
    const r: any = fn();
    console.log(label, "->", JSON.stringify(r, (_k, v) => (Number.isNaN(v) ? "NaN" : v)));
  } catch (e: any) {
    console.log(label, "-> THREW:", e.message);
    bug = true;
  }
}
tryCase("looseObject ∩ looseObject, extra c: NaN",
  () => z.looseObject({ a: z.string() }).and(z.looseObject({ b: z.string() })).safeParse({ a: "x", b: "y", c: NaN }));
tryCase("unknown ∩ unknown, NaN", () => z.unknown().and(z.unknown()).safeParse(NaN));
tryCase("nan ∩ nan, NaN", () => z.nan().and(z.nan()).safeParse(NaN));
tryCase("control: unknown ∩ unknown, 1", () => z.unknown().and(z.unknown()).safeParse(1));
process.exit(bug ? 1 : 0);
