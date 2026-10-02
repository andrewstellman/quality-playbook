import * as z from "/tmp/zodw/packages/zod/src/index.js";

// Claim: metadata.mdx:161-164 says `const B = A.refine(_ => true); B.meta(); // => undefined`.
// Code: $ZodRegistry.get walks _zod.parent, and .refine() clones with { parent: true }.
const A = z.string().meta({ description: "A cool string" });
const B = A.refine((_) => true);
console.log("A.meta():", JSON.stringify(A.meta()));
console.log("B.meta():", JSON.stringify(B.meta()));
console.log("B._zod.parent === A:", B._zod.parent === A);
console.log("A.min(1).meta():", JSON.stringify(A.min(1).meta()));
console.log("A.optional().meta():", JSON.stringify(A.optional().meta()));
console.log("A.meta({id:'x'}).refine(_=>true).meta():", JSON.stringify(A.meta({ id: "x" }).refine((_) => true).meta()));
const bug = B.meta() !== undefined; // docs promise undefined
console.log(bug ? "BUG PRESENT: docs say undefined, code returns inherited metadata" : "no bug: B.meta() is undefined as documented");
process.exit(bug ? 1 : 0);
