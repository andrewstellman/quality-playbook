import oldC from "./src-old/cronstrue-i18n";
import newC from "./src-new/cronstrue-i18n";
const members = ["5", "1", "MON", "*/2", "0-4/2", "3-9/2", "1-3", "2-6", "10", "0", "*/5", "5/3", "L", "1W", "5#2", "2020", "2022-2030/2"];
const fields: [number, string[]][] = [[0, []], [1, []], [2, []], [3, []], [4, []], [5, []], [6, []]];
const locales = ["af", "ar", "az", "be", "bg", "ca", "cs", "da", "de", "en", "es", "fa", "fi", "fr", "he", "hr", "hu", "id", "it", "ja", "ko", "my", "nb", "nl", "nn", "pl", "pt_BR", "pt_PT", "ro", "ru", "sk", "sl", "sr", "sv", "sw", "tg", "th", "tr", "uk", "vi", "zh_CN", "zh_TW"];
const base = ["0", "0", "9", "*", "*", "*", "*"]; // sec min hr dom mon dow year
const lists: string[] = [];
for (const a of members) for (const b of members) { lists.push(`${a},${b}`); for (const c of ["5", "0-4/2", "*/3", "1-2"]) lists.push(`${a},${b},${c}`); }


let enNewBad=0; let total=0, diff=0, viol=0, f012=0; const ex: string[] = []; const vs: string[] = [];
for (let f = 0; f < 7; f++) for (const l of lists) for (const loc of locales) for (const verbose of [false, true]) {
  const parts = base.slice(); parts[f] = l; const expr = parts.join(" ");
  const opts: any = { locale: loc, verbose };
  let o: string, n: string;
  try { o = oldC.toString(expr, opts); } catch (e) { o = "ERR"; }
  try { n = newC.toString(expr, opts); } catch (e) { n = "ERR"; }
  total++;
  if (loc==='en' && o!==n && (/ , |, ,|[AP]M[a-z]/.test(n))) enNewBad++;
  if (o !== n) { diff++;
    const m = l.split(",");
    const pred = f >= 3 && !/[-\/]/.test(m[0]) && m.slice(1).some(x => x.includes("/"));
    const pred2 = f >= 3 && m.slice(1).some(x => x.includes("/")) ;
    if (f < 3) f012++;
    if (!pred2) { viol++; if (vs.length < 15) vs.push(`[${loc}${verbose?",v":""}] ${expr}\n  old: ${o}\n  new: ${n}`); }
  }
}
console.log({total,diff,viol,f012,enNewBad}); console.log(vs.join("\n"));
