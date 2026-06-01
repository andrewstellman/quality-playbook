# Zod - Schema Types and Validation

## Primitive Types

Zod supports all JavaScript primitive types with dedicated schema constructors:

### String Types

```typescript
z.string()                      // any string
z.string().email()              // email format
z.string().url()                // URL format
z.string().uuid()               // UUID format
z.string().ip()                 // IP address (v4 or v6)
z.string().ipv4()               // IPv4 address
z.string().ipv6()               // IPv6 address
z.string().datetime()           // ISO 8601 datetime
z.string().date()               // ISO date (YYYY-MM-DD)
z.string().time()               // ISO time (HH:MM:SS)
z.string().cuid()               // Collision-resistant ID
z.string().cuid2()              // CUIDv2 format
z.string().ulid()               // Sortable unique ID
z.string().regex(/^[a-z]+$/)    // Custom regex pattern
z.string().includes("substring")
z.string().startsWith("prefix")
z.string().endsWith("suffix")
z.string().min(5)               // minimum length
z.string().max(10)              // maximum length
z.string().length(8)            // exact length
z.string().toLowerCase()        // transform to lowercase
z.string().toUpperCase()        // transform to uppercase
z.string().trim()               // trim whitespace
```

### Numeric Types

```typescript
z.number()                      // any number (including Infinity, NaN)
z.number().int()                // integer only
z.number().finite()             // excludes Infinity, -Infinity
z.number().safe()               // in JavaScript's safe integer range
z.number().positive()           // > 0
z.number().nonnegative()        // >= 0
z.number().negative()           // < 0
z.number().nonpositive()        // <= 0
z.number().multipleOf(5)        // divisible by n
z.number().min(0)               // minimum value
z.number().max(100)             // maximum value
z.number().gt(0)                // greater than (exclusive)
z.number().lt(100)              // less than (exclusive)
z.number().gte(0)               // greater than or equal
z.number().lte(100)             // less than or equal

z.bigint()                      // BigInt values
z.bigint().min(0n)              // minimum BigInt
z.bigint().max(100n)            // maximum BigInt

z.boolean()                     // true or false
z.null()                        // null literal
z.undefined()                   // undefined literal
z.void()                        // returns undefined
z.never()                       // rejects all values
```

### Date and Literal Types

```typescript
z.date()                        // Date objects
z.date().min(new Date("2020-01-01"))
z.date().max(new Date())

z.literal("value")              // literal string
z.literal(42)                   // literal number
z.literal(true)                 // literal boolean
z.enum(["small", "medium", "large"])  // string enum
```

## Coercion Types

Coercion schemas convert input to the target type before validation using JavaScript's standard constructors:

```typescript
z.coerce.string()               // String(input)
z.coerce.number()               // Number(input)
z.coerce.boolean()              // Boolean(input) - truthy/falsy
z.coerce.bigint()               // BigInt(input)
z.coerce.date()                 // new Date(input)

// Examples
z.coerce.number().parse("42")   // 42
z.coerce.boolean().parse("yes") // true
z.coerce.date().parse("2024-01-01")  // Date object
```

**Important Coercion Behavior**: Coercion schemas always return the primitive type, even with undefined or null input. `.optional()`, `.nullable()`, and `.nullish()` should not be used on coerce schemas.

## Objects

Object schemas validate objects with known properties:

```typescript
const schema = z.object({
  name: z.string(),
  age: z.number(),
  email: z.string().email()
});

// Inferred type: { name: string; age: number; email: string }
type User = z.infer<typeof schema>;
```

### Object Methods

```typescript
schema.shape                    // access field schemas as object
schema.keyof()                  // z.enum of all keys
schema.pick({ name: true })     // pick specific fields
schema.omit({ age: true })      // omit specific fields
schema.extend({
  phone: z.string()              // add new fields
})
schema.merge(otherSchema)       // merge two object schemas
schema.partial()                // make all fields optional
schema.partial({ age: true })   // make specific fields optional
schema.required()               // make all fields required
schema.required({ age: true })  // make specific fields required
schema.strict()                 // reject extra properties (default)
schema.strict(true)             // alias for strictObject
schema.loose()                  // allow extra properties (passthrough)
schema.passthrough()            // alias for loose
schema.catchall(z.string())     // define schema for extra properties
```

### Object Validation Modes

```typescript
z.strictObject({...})           // reject extra properties (default)
z.looseObject({...})            // pass through extra properties
z.object({...}).strict()        // reject extra properties
z.object({...}).loose()         // pass through extra properties
```

## Arrays

Array schemas validate arrays with homogeneous element types:

```typescript
z.array(z.number())             // array of numbers
z.array(z.string()).min(1)      // at least 1 element
z.array(z.string()).max(5)      // at most 5 elements
z.array(z.string()).length(3)   // exactly 3 elements

// Validation examples
z.array(z.number()).parse([1, 2, 3])    // [1, 2, 3]
z.array(z.number()).parse([1, "two"])   // throws error
```

## Tuples

Tuples are fixed-length arrays where each position has a specific type:

```typescript
z.tuple([z.string(), z.number()])
// type: [string, number]

z.tuple([z.string(), z.number().optional()])
// type: [string, number?]

z.tuple([z.string(), z.number()]).rest(z.boolean())
// type: [string, number, ...boolean[]]

// Examples
z.tuple([z.number(), z.number()]).parse([10, 20])           // [10, 20]
z.tuple([z.string(), z.number()]).parse(["x", "y"])         // throws
```

## Sets

```typescript
z.set(z.string())               // Set<string>
z.set(z.number()).min(1)        // at least 1 element
z.set(z.string()).max(5)        // at most 5 elements
```

## Maps

```typescript
z.map(z.string(), z.number())   // Map<string, number>
z.map(z.string(), z.object({...}))
```

## Records

Records are objects with arbitrary string keys and values of a specific type:

```typescript
z.record(z.string())            // Record<string, string>
z.record(z.number())            // Record<string, number>
z.record(z.enum(['a', 'b']), z.number())
// Record with enum keys: { a: number, b: number }
```

## Union Types

Unions represent a logical OR relationship. Validation tries each option until one succeeds:

```typescript
z.union([z.string(), z.number()])
// Equivalent to
z.string().or(z.number())
// Type: string | number

// Validation behavior
z.string().or(z.number()).parse("hello")  // "hello"
z.string().or(z.number()).parse(42)       // 42
z.string().or(z.number()).parse(true)     // throws - neither string nor number
```

**Union Validation Performance**: Regular unions have O(n) complexity because Zod attempts validation against all options, reporting errors from all failures. Use discriminated unions for O(1) performance when possible.

## Discriminated Unions

Discriminated unions use a shared "discriminator" property to quickly dispatch to the correct schema without trying all options:

```typescript
z.discriminatedUnion("type", [
  z.object({ type: z.literal("user"), name: z.string() }),
  z.object({ type: z.literal("admin"), name: z.string(), role: z.string() })
])

// Type: 
// { type: "user"; name: string } | 
// { type: "admin"; name: string; role: string }
```

**Discriminated Union Dispatch**: When validating, Zod:
1. Extracts the discriminator value from input
2. Selects the matching option schema
3. Validates only against that option (O(1) lookup)
4. Reports errors only from the matching option

This is dramatically faster than regular unions for large option sets.

## Optional and Nullable

```typescript
z.string().optional()           // string | undefined
z.string().nullable()           // string | null
z.string().nullish()            // string | null | undefined

// Default to undefined if missing
z.string().optional().default("default")
// Default to null if missing - must use prefault for optional
z.string().optional().prefault(null)
```

**Behavioral Distinction**: `.default()` only applies when the input value is `undefined`. If the input is `null` and the schema doesn't allow null, validation fails with an error (the default doesn't apply).

## Intersections

Intersections combine multiple schemas, validating against all of them:

```typescript
z.intersection(schemaA, schemaB)
// Equivalent to
schemaA.and(schemaB)
// Type: A & B

z.object({ name: z.string() })
  .and(z.object({ age: z.number() }))
// { name: string } & { age: number } = { name: string; age: number }
```
