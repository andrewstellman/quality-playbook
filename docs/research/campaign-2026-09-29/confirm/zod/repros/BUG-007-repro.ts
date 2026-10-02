import * as z from "/tmp/zodw/packages/zod/src/index.js";

const part = z.string().min(2).regex(/^[a-z]+$/);
const tl = z.templateLiteral(["id-", part]);

const partAlone = part.safeParse("a").success;
const inTemplate = tl.safeParse("id-a").success;
const lenOnly = z.templateLiteral(["id-", z.string().min(2)]).safeParse("id-a").success;
const twoRegex = z.templateLiteral(["", z.string().regex(/^[a-z]+$/).regex(/^.{2,}$/)]).safeParse("a").success;

console.log("template pattern     :", tl._zod.pattern.source);
console.log("part alone  'a'      : success =", partAlone);
console.log("template    'id-a'   : success =", inTemplate);
console.log("min(2) only 'id-a'   : success =", lenOnly);
console.log("two regexes 'a'      : success =", twoRegex, "(only last regex kept?)");

const bug = inTemplate === true && partAlone === false;
console.log(bug ? "BUG PRESENT" : "BUG ABSENT");
process.exit(bug ? 1 : 0);
