import cronstrue from "../src/cronstrue-i18n";
const exprs: string[] = [];
const fields = {
  min: ["0","*/5","0,30","5,10-20/5","0-10/2,30"],
  hour: ["9","*","9,17","8,9-17/2","0-6/3,12"],
  dom: ["*","1","1,15","1,10-20/5","*/2"],
  mon: ["*","1","1,6","2,3-9/2","*/3"],
  dow: ["*","5","5,0-4/2","1-5","MON,WED-FRI/2","0,6"],
};
for (const m of fields.min) for (const h of fields.hour) for (const d of fields.dom) for (const mo of fields.mon) for (const w of fields.dow) exprs.push(`${m} ${h} ${d} ${mo} ${w}`);
const locales = process.argv.slice(2);
for (const loc of locales) for (const e of exprs) for (const verbose of [false, true]) {
  let out: string; try { out = cronstrue.toString(e, { locale: loc, verbose }); } catch (x: any) { out = "ERR " + x; }
  console.log([loc, verbose ? "v" : "c", e, out].join("\t"));
}
