import * as z from "/tmp/zodw/packages/zod/src/index.js";

const k = Symbol("k");
const schema = z.object({ [k]: z.string() });
const res = schema.safeParse({ [k]: 1 });
if (res.success) { console.log("unexpectedly parsed"); process.exit(2); }
const err = res.error;

console.log("issue paths:", err.issues.map((i) => i.path));
const tree: any = z.treeifyError(err);
console.log("treeifyError:", tree);
console.log("tree.properties:", tree.properties);
console.log("tree.items:", tree.items, "isArray:", Array.isArray(tree.items));
console.log("JSON.stringify(tree):", JSON.stringify(tree));
console.log("flattenError.fieldErrors keys:", Reflect.ownKeys(z.flattenError(err).fieldErrors));
console.log("formatError keys:", Reflect.ownKeys(z.formatError(err)));
console.log("prettifyError:", z.prettifyError(err));

const underItems = tree.items !== undefined && (tree.items as any)[k] !== undefined;
const underProps = tree.properties !== undefined && tree.properties[k] !== undefined;
console.log("symbol filed under items:", underItems, "| under properties:", underProps);
process.exit(underItems && !underProps ? 1 : 0);
