import * as z from "/tmp/zodw/packages/zod/src/index.js";

z.config(z.locales.mk());
const a = z.literal(1).safeParse(2).error!.issues[0].message;
const b = z.email().safeParse("nope").error!.issues[0].message;
// control: sibling locales translate both templates
z.config(z.locales.bg());
const cA = z.literal(1).safeParse(2).error!.issues[0].message;
const cB = z.email().safeParse("nope").error!.issues[0].message;

console.log("mk literal(1)<-2 :", JSON.stringify(a));
console.log("mk email<-'nope' :", JSON.stringify(b));
console.log("bg literal(1)<-2 :", JSON.stringify(cA));
console.log("bg email<-'nope' :", JSON.stringify(cB));
const bug = /^Invalid input: expected/.test(a) || /^Invalid /.test(b);
console.log("BUG PRESENT:", bug);
process.exit(bug ? 1 : 0);
