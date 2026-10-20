import oldC from "./sweep/src-old/cronstrue-i18n";
import newC from "./sweep/src-new/cronstrue-i18n";
for (const e of ["1-3,*/2 9 * * *", "0 1-3,*/2 * * *", "0 9 1-3,*/2 * *", "0 9 * 1-3,*/2 *"]) console.log(e, "\n  old:", oldC.toString(e), "\n  new:", newC.toString(e));
