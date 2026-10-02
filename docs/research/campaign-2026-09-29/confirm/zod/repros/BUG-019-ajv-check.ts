import Ajv2020 from "ajv/dist/2020.js";
const ajv = new (Ajv2020 as any)();
const v = ajv.compile({ allOf: [ { type: "object", properties: { a: { type: "number" } }, additionalProperties: false }, { type: "object", properties: { b: { type: "number" } } } ] });
console.log("ajv valid:", v({ a: 1, b: 1 }), JSON.stringify(v.errors));
