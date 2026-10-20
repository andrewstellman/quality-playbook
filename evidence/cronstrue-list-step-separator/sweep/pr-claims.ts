import oldC from "/work/batch/runs/cronstrue/scratch/fix2-cronstrue-list-step-separator-fixer/sweep/src-old/cronstrue-i18n";
import newC from "/work/batch/runs/cronstrue/scratch/fix2-cronstrue-list-step-separator-fixer/sweep/src-new/cronstrue-i18n";
const cases: [string, any][] = [
  ["0 9 * * 5,0-4/2", {}], ["0 0 12 1,15-20/2 * ?", {}], ["0 9 * 1,3-9/2 *", {}], ["0 9 * * 0-4/2,5,6", {}], ["0 9 * * 1-3,*/2", {}],
  ["0 0 9 * 5,*/2 * *", { locale: "vi" }], ["0 0 9 * */2 * *", { locale: "vi" }], ["0 0 9 * 5,*/2 * *", { locale: "vi", verbose: true }],
  ["0 0 9 * */2 * *", { locale: "vi", verbose: true }], ["0 0 9 * 5,*/2 * *", { locale: "sw" }],
];
for (const [e, o] of cases) console.log(JSON.stringify(o), e, "\n  old:", oldC.toString(e, o), "\n  new:", newC.toString(e, o));
