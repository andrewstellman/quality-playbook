// Prints cRonstrue's output for a fixed set of inputs, one per line.
// Run from a checkout: ./node_modules/.bin/ts-node knock_on.ts
import cronstrue from "./src/cronstrue-i18n";

type Case = [string, any?];

const cases: Case[] = [
  // ordinary, no list
  ["*/5 * * * *"],
  ["0 9 * * 1-5"],
  ["0 0 12 1,15 * ?"],
  // lists without a step
  ["0 9 1,15-20 * *"],
  ["0 9 * * 1,3,5"],
  ["5,10,15 * * * *"],
  ["0 9 * * 1-3,5"],
  // step first, then plain values (the case fixed in 286434e, test/cronstrue.ts:753)
  ["0 9 * * 0-4/2,5,6"],
  // minutes and hours lists with steps (must not change)
  ["5-45/10,*/5,9 * * * *"],
  ["1-3,*/2 9 * * *"],
  ["0 1-3,*/2 * * *"],
  ["0 5,*/2 * * *"],
  // the bug: plain first value, later member has a step
  ["0 9 * * 5,0-4/2"],
  ["0 0 12 1,15-20/2 * ?"],
  ["0 9 * 1,3-9/2 *"],
  ["0 0 9 * * * 2020,2022-2030/2"],
  ["0 9 * * 1,3,5-6/2"],
  // range first, later step (not fixed)
  ["0 9 * * 1-3,*/2"],
  // options and locales
  ["0 9 * * 5,0-4/2", { verbose: true }],
  ["0 9 * * 5,0-4/2", { use24HourTimeFormat: true }],
  ["0 9 * * 5,0-4/2", { locale: "de" }],
  ["0 9 * * 5,0-4/2", { locale: "fr" }],
  ["0 0 9 * 5,*/2 * *", { locale: "vi" }],
];

for (const [expr, opts] of cases) {
  let out: string;
  try {
    out = cronstrue.toString(expr, opts);
  } catch (e) {
    out = "THROWS: " + e;
  }
  console.log(JSON.stringify(opts ?? {}) + " " + expr + " => " + out);
}
