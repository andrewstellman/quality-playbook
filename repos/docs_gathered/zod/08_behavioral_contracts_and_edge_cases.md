# Zod - Behavioral Contracts and Edge Cases

## Coercion Rules and Behavior

### Primitive Coercion

Zod coerces using JavaScript's standard constructors:

```typescript
// String coercion (String(value))
z.coerce.string().parse(42)                    // "42"
z.coerce.string().parse(true)                  // "true"
z.coerce.string().parse(null)                  // "null"
z.coerce.string().parse(undefined)             // "undefined"
z.coerce.string().parse([1, 2, 3])             // "1,2,3"
z.coerce.string().parse({ a: 1 })             // "[object Object]"

// Number coercion (Number(value))
z.coerce.number().parse("42")                  // 42
z.coerce.number().parse("3.14")                // 3.14
z.coerce.number().parse("invalid")             // NaN
z.coerce.number().parse(true)                  // 1
z.coerce.number().parse(false)                 // 0
z.coerce.number().parse(null)                  // 0
z.coerce.number().parse(undefined)             // NaN
z.coerce.number().parse("")                    // 0
z.coerce.number().parse("   ")                 // 0

// Boolean coercion (Boolean(value))
z.coerce.boolean().parse("true")               // true
z.coerce.boolean().parse("false")              // true (non-empty string!)
z.coerce.boolean().parse("0")                  // true (non-empty string!)
z.coerce.boolean().parse("")                   // false
z.coerce.boolean().parse(0)                    // false
z.coerce.boolean().parse(1)                    // true
z.coerce.boolean().parse(null)                 // false
z.coerce.boolean().parse(undefined)            // false

// Date coercion (new Date(value))
z.coerce.date().parse("2024-01-01")            // Date object
z.coerce.date().parse(1234567890000)           // Date from timestamp
z.coerce.date().parse("invalid")               // Invalid Date object
```

### BigInt Coercion

```typescript
z.coerce.bigint().parse("123")                 // 123n
z.coerce.bigint().parse(123)                   // 123n
z.coerce.bigint().parse("invalid")             // throws SyntaxError
```

### Coercion Edge Cases

```typescript
// Array coercion results in string representation
z.coerce.string().parse([1, 2, 3])             // "1,2,3"
z.coerce.number().parse([42])                  // 42 (single element converted)
z.coerce.number().parse([1, 2])                // NaN (multiple elements)

// Object stringification
z.coerce.string().parse({ toString: () => "custom" })  // "custom"
```

## Nullable vs Optional vs Nullish

These three modifiers have distinct semantics:

```typescript
// .optional() - allows undefined
z.string().optional()
.parse("hello")      // "hello"
.parse(undefined)    // undefined
.parse(null)         // throws - null not allowed

type OptionalString = string | undefined;

// .nullable() - allows null
z.string().nullable()
.parse("hello")      // "hello"
.parse(null)         // null
.parse(undefined)    // throws - undefined not allowed

type NullableString = string | null;

// .nullish() - allows both null and undefined
z.string().nullish()
.parse("hello")      // "hello"
.parse(null)         // null
.parse(undefined)    // undefined

type NullishString = string | null | undefined;

// In objects
z.object({
  required: z.string(),
  optional: z.string().optional(),
  nullable: z.string().nullable(),
  nullish: z.string().nullish()
})

type Example = {
  required: string;                      // must be provided
  optional?: string;                     // can be undefined
  nullable: string | null;               // can be null, must be provided
  nullish?: string | null;               // can be undefined or null
}
```

## Default Value Behavioral Contract

`.default()` has a precise behavioral contract:

```typescript
// Default ONLY applies when input is undefined
z.string().default("default")
.parse("value")      // "value" (not default)
.parse(undefined)    // "default" (applies)
.parse(null)         // throws - null not handled
.parse("")           // "" (empty string is not undefined)
.parse(0)            // throws if string not expected
.parse(false)        // throws if string not expected

// Default does NOT apply for empty strings
z.string().default("default")
.parse("")           // "" (empty string passes through)

// Default does NOT apply for zero
z.number().default(42)
.parse(0)            // 0 (zero passes through)

// Default does NOT apply for false
z.boolean().default(true)
.parse(false)        // false (false passes through)

// In objects, missing fields are undefined
z.object({
  name: z.string().default("Anonymous"),
  age: z.number().default(0)
})
.parse({})           // { name: "Anonymous", age: 0 }

.parse({ name: "Alice" })  // { name: "Alice", age: 0 }

.parse({ name: undefined })  // { name: "Anonymous", age: 0 }

.parse({ age: 0 })   // { age: 0, name: "Anonymous" } but 0 is not replaced
```

**Default Rule**: Only `undefined` triggers the default. `null`, falsy values, and missing object properties are different scenarios.

## Prefault vs Default

```typescript
// prefault - applies to input before validation
z.string().optional().prefault("default")

// default - applies to output after validation
z.string().default("default")

// For optional fields:
z.string().optional().default(undefined)
// After parsing undefined input:
// - Input undefined becomes the default (undefined)
// - Output includes the field with undefined value

// Using prefault for input-level defaults
z.object({
  country: z.string().prefault("US")
}).parse({})
// The prefault applies at input level, so:
// { country: "US" } gets parsed normally
```

## Union Resolution Order

Union schemas try options in order when no discriminator exists:

```typescript
// Careful with union order
const UnionBad = z.union([
  z.object({ type: z.string() }),          // matches any object
  z.object({ type: z.literal("specific") }) // never reached
]);

UnionBad.parse({ type: "specific" })  // uses first schema

const UnionGood = z.union([
  z.object({ type: z.literal("specific") }),  // try specific first
  z.object({ type: z.string() })              // fallback to generic
]);

UnionGood.parse({ type: "specific" })  // uses specific schema
```

## Discriminated Union Dispatch Behavior

Discriminated unions have specific dispatch rules:

```typescript
const DiscriminatedSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("a"), value: z.string() }),
  z.object({ type: z.literal("b"), value: z.number() })
]);

// Missing discriminator
DiscriminatedSchema.safeParse({}).error.issues
// Error: discriminator value cannot be extracted

// Non-literal discriminator doesn't work well with dispatch
z.discriminatedUnion("type", [
  z.object({ type: z.string() }),  // problematic - not a literal
  z.object({ type: z.string() })
])

// Discriminator must be present in all options
z.discriminatedUnion("type", [
  z.object({ type: z.literal("a"), value: z.string() }),
  z.object({ value: z.number() })  // error: missing discriminator
])

// Discriminator must have the same key across all options
z.discriminatedUnion("type", [
  z.object({ type: z.literal("a") }),
  z.object({ kind: z.literal("b") })  // error: different key
])
```

## Object Extra Property Handling

Objects have strict behavior by default:

```typescript
// Default: strict (reject extra properties)
z.object({ name: z.string() })
.parse({ name: "Alice", extra: "field" })
// throws: unrecognized_keys error

// Loose/passthrough (allow extra properties)
z.object({ name: z.string() }).loose()
.parse({ name: "Alice", extra: "field" })
// { name: "Alice", extra: "field" }

// Catchall (define schema for extra properties)
z.object({ name: z.string() })
.catchall(z.string())
.parse({ name: "Alice", extra: "field" })
// { name: "Alice", extra: "field" }

z.object({ name: z.string() })
.catchall(z.string())
.parse({ name: "Alice", extra: 123 })
// throws: extra is not a string
```

## Type Narrowing and Refinement Order

Refinements run after base validations, not before:

```typescript
z.string()
.email()           // base validation
.refine((v) => !bannedEmails.includes(v))  // runs after email check

z.string()
.email()
.refine((v) => v.length > 20)
.parse("bad@example.com")
// throws: invalid_string (email validation fails first)
// refinement never executes

z.string()
.email()
.refine((v) => v.length > 20)
.parse("verylongemailaddress@example.com")
// throws: custom error from refinement (email passed, refinement failed)
```

## Transformation Side Effects

Transforms are applied in sequence:

```typescript
z.string()
.transform((v) => v.toUpperCase())
.transform((v) => v.split(""))
.parse("hello")
// "HELLO" -> ["H", "E", "L", "L", "O"]

type Inferred = z.infer<typeof schema>;  // string[]

// Transforms are applied in parse, but not in type inference until all transforms applied
z.string()
.transform((v, ctx) => {
  console.log("transform 1", v);  // "hello"
  return v.toUpperCase();
})
.transform((v, ctx) => {
  console.log("transform 2", v);  // "HELLO"
  return v.length;
})
.parse("hello")
// Logs: "transform 1 hello", "transform 2 HELLO"
// Returns: 5
```

## Async Validation Behavior

Async validations only run in async contexts:

```typescript
const schema = z.string().refine(
  async (v) => {
    const exists = await checkEmailExists(v);
    return !exists;
  }
);

// Synchronous parse fails
schema.parse("user@example.com")
// throws: cannot use async refinements in sync context

// Async parse works
const result = await schema.parseAsync("user@example.com")
// executes async refinement

// SafeParse also fails without async
const result = schema.safeParse("user@example.com")
// throws: async refinement in sync context

// SafeParseAsync works
const result = await schema.safeParseAsync("user@example.com")
```

## Array and Tuple Validation Order

Arrays and tuples validate length constraints after element validation:

```typescript
const ArraySchema = z.array(z.number()).min(2);

ArraySchema.safeParse([])
// error: too_small (array too short)

ArraySchema.safeParse([1, "two", 3])
// error: invalid_type (second element not number)
// Does NOT report array too short because element validation fails first

ArraySchema.safeParse(["a", "b"])
// error: invalid_type (first element not number)
// Does NOT validate length because elements are invalid
```

## Set and Map Validation

Sets and maps have special iteration semantics:

```typescript
// Sets normalize values (eliminate duplicates)
z.set(z.number()).parse(new Set([1, 2, 2, 3]))
// Set { 1, 2, 3 }

// Maps validate key and value separately
z.map(z.string(), z.number())
.parse(new Map([
  ["a", 1],
  ["b", 2]
]))
// Map { "a" => 1, "b" => 2 }

// Invalid key
z.map(z.enum(["x", "y"]), z.number())
.parse(new Map([["z", 1]]))
// throws: invalid_enum_value for key "z"

// Invalid value
z.map(z.string(), z.number())
.parse(new Map([["key", "not-a-number"]]))
// throws: invalid_type for value
```

## Record Validation

Records use string keys by default:

```typescript
// Record with string keys
z.record(z.string())
.parse({ a: "value" })
// { a: "value" }

// Record with enum keys
z.record(z.enum(["x", "y"]), z.number())
.parse({ x: 1, y: 2 })
// { x: 1, y: 2 }

// Extra keys not in enum throw error
z.record(z.enum(["x", "y"]), z.number())
.parse({ x: 1, z: 3 })
// throws: unrecognized_keys error for "z"
```

## Readonly Semantics

Readonly uses Object.freeze():

```typescript
const schema = z.object({
  name: z.string()
}).readonly();

const result = schema.parse({ name: "Alice" });
Object.isFrozen(result)  // true
result.name = "Bob"      // throws TypeError in strict mode, silent fail otherwise
```

## String Trim Behavior

The `.trim()` method removes whitespace before validation:

```typescript
z.string().email().trim()
.parse("  user@example.com  ")
// "user@example.com" (trimmed before email validation)

z.string().min(5).trim()
.parse("   hi   ")
// throws: too_small (checks length "hi" = 2)
```

## Empty String Handling

Empty strings are valid unless constrained:

```typescript
z.string().parse("")        // "" (valid)

z.string().min(1).parse("")
// throws: too_small

z.string().refine((v) => v.length > 0)
.parse("")
// throws: custom error

z.string().optional().parse("")
// "" (empty string is not undefined)
```

## Literal and Enum Constraints

Literals and enums use strict equality:

```typescript
z.literal("admin").parse("admin")   // "admin"
z.literal("admin").parse("Admin")   // throws (case sensitive)

z.literal(1).parse(1)               // 1
z.literal(1).parse(true)            // throws (1 and true are not equal)

// Enums use exact string matching
z.enum(["low", "medium", "high"])
.parse("medium")       // "medium"
.parse("Medium")       // throws (case sensitive)
```

## Intersection and And Behavior

Intersections merge schemas:

```typescript
z.object({ a: z.string() })
.and(z.object({ b: z.number() }))
.parse({ a: "value", b: 42 })
// { a: "value", b: 42 }

// Can override field types
z.object({ a: z.string() })
.and(z.object({ a: z.number() }))
// Later schema wins, a is number
```
