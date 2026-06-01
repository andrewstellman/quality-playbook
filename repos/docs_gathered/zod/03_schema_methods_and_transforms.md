# Zod - Schema Methods and Transforms

## Parse and Validation Methods

### .parse()

Validates input against the schema and returns the validated (possibly transformed) value. Throws `ZodError` on validation failure.

```typescript
const schema = z.number();
schema.parse("42")           // throws ZodError
schema.parse(42)             // 42
schema.parse(Infinity)       // Infinity (allowed by default)
schema.parse(NaN)            // NaN (allowed by default)
```

**Parse Behavior**: 
- Returns the processed value (after transforms and coercions)
- Throws immediately on validation failure
- Does not catch errors - they propagate to caller
- Used when you want strict error handling

### .safeParse()

Validates input and returns a discriminated union result object:

```typescript
const result = schema.safeParse(input);
// Type: { success: true; data: T } | { success: false; error: ZodError }

if (result.success) {
  const value = result.data;  // T
} else {
  const error = result.error; // ZodError
  console.log(error.issues);
}
```

**SafeParse Behavior**:
- Never throws
- Returns `{ success: true; data }` on success
- Returns `{ success: false; error }` on failure
- Safe for uncertain input sources
- Allows type guards on the result

### Async Variants

```typescript
// Async versions for asynchronous refinements/transforms
schema.parseAsync(input)           // Promise<T> or throws
schema.safeParseAsync(input)       // Promise<{ success: boolean; ... }>

// Example with async refinement
const schema = z.string()
  .email()
  .refine(async (email) => {
    const exists = await checkEmailExists(email);
    return !exists;
  }, { message: "Email already registered" });

const result = await schema.parseAsync("user@example.com");
```

## Refinements

Refinements add custom validation logic to schemas. Refinement functions must never throw; they return boolean to indicate validity.

### .refine()

Basic refinement with custom logic:

```typescript
z.string()
  .refine((value) => value.length > 3, {
    message: "Must be longer than 3 characters"
  })

// Specify error path
z.object({
  password: z.string(),
  confirmPassword: z.string()
}).refine(
  (data) => data.password === data.confirmPassword,
  {
    message: "Passwords don't match",
    path: ["confirmPassword"]  // error appears on this field
  }
)

// fatal: true stops validation chain on failure (default: false)
z.string().refine(
  (v) => v.length > 0,
  { message: "Cannot be empty", fatal: true }
)
```

**Refine Behavior**:
- Function receives the validated value (after previous validations)
- Return falsy value to indicate failure
- Can specify `path` to place error on specific field
- Can use `message` for custom error text
- `fatal: true` stops processing remaining refinements

### .superRefine()

Low-level refinement API for multiple issues or advanced control:

```typescript
z.string().superRefine((value, ctx) => {
  if (value.length < 3) {
    ctx.addIssue({
      code: z.ZodIssueCode.too_small,
      minimum: 3,
      type: "string",
      inclusive: true,
      message: "String must be at least 3 characters long"
    });
  }
  
  if (value.includes("admin")) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Reserved word",
      path: [""]  // error on current location
    });
  }
})

// Multiple issues in objects
z.object({ name: z.string() }).superRefine((obj, ctx) => {
  if (obj.name === "admin") {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Admin is reserved",
      path: ["name"]
    });
  }
})
```

**SuperRefine Behavior**:
- Receives validation context `ctx` with `addIssue()` method
- Can add multiple issues in single refinement
- Issues can specify `path` for nested errors
- Provides fine-grained control over error reporting
- Better for performance-critical validations

## Transforms and Pipes

### .transform()

Transforms the validated value to a new value:

```typescript
z.string()
  .transform((value) => value.toUpperCase())
  .parse("hello")           // "HELLO"

// Chaining transforms
z.number()
  .transform((v) => v * 2)
  .transform((v) => v + 1)
  .parse(5)                 // (5 * 2) + 1 = 11

// Async transform
z.string()
  .email()
  .transform(async (email) => {
    const user = await lookupUser(email);
    return user;
  })

// Transform can change type
z.string()
  .transform((v) => v.split(","))
  .transform((arr) => arr.map(s => s.trim()))
  .parse("a, b, c")        // ["a", "b", "c"]
```

**Transform Behavior**:
- Receives the validated value (after all validations and previous transforms)
- Return value becomes the output
- Can transform to different types
- Transforms run sequentially in order
- Type changes are reflected in inferred types

### .pipe()

Chains schemas together: validates with first schema, then validates the result with second schema:

```typescript
// Parse number from string, then validate constraints
z.coerce.number()
  .pipe(z.number().int().positive())
  .parse("42")              // 42

// Equivalent to:
z.coerce.number()
  .refine((v) => Number.isInteger(v))
  .refine((v) => v > 0)
  .parse("42")

// Useful for separation of concerns
const parseInteger = z.coerce.number().pipe(z.number().int());
const parsePositiveInt = parseInteger.pipe(z.number().positive());
const parsePercentage = parsePositiveInt.pipe(z.number().max(100));
```

**Pipe Behavior**:
- First schema validates and transforms input
- Output of first schema is input to second schema
- Both schemas are validated in sequence
- Errors from either schema are reported
- Enables schema composition and reuse

### .preprocess()

Convenience function for common transform-then-validate pattern:

```typescript
// Preprocess before core validation
const schema = z.preprocess(
  (arg) => {
    if (typeof arg === "string") {
      return parseInt(arg);
    }
    return arg;
  },
  z.number()
);

schema.parse("123")         // 123
schema.parse(123)           // 123

// Cleaner than:
z.union([
  z.string().transform(v => parseInt(v)),
  z.number()
])
```

**Preprocess Behavior**:
- First argument receives raw input (before validation)
- Return value is validated by the schema
- Useful for type conversion before validation
- More explicit than transform for preprocessing

## Default and Fallback Values

### .default()

Applies a default value when input is **undefined**:

```typescript
z.string().default("unnamed")
  .parse(undefined)         // "unnamed"
  .parse("Alice")           // "Alice"
  .parse(null)              // throws - null is not handled

z.object({
  name: z.string().default("User"),
  age: z.number()
}).parse({})                // { name: "User", age: ??? }
```

**Default Behavior**:
- Only applies when input is `undefined`
- Does NOT apply for `null` (validation fails if null not allowed)
- Does NOT apply for falsy values like empty string, 0, false
- Value is the output, not the input type

### .prefault()

Applies a default value when input is **undefined** for optional fields:

```typescript
z.string().optional()
  .prefault("default")      // applies at input level
  .parse(undefined)         // "default"

// Useful for distinguishing input and output types
z.string().optional()
  .prefault(null)           // input default is null
  .parse(undefined)         // processes as null
```

### .catch()

Returns a fallback value when validation fails:

```typescript
z.number()
  .catch(0)
  .parse("not a number")    // 0 (error caught)
  .parse(42)                // 42 (valid)

z.object({ count: z.number().catch(0) })
  .parse({ count: "invalid" })  // { count: 0 }
```

**Catch Behavior**:
- Returns fallback when validation fails
- Converts error to success
- Useful for lenient validation
- Can catch errors and provide defaults

## Readonly

### .readonly()

Marks schema output as readonly using `Object.freeze()`:

```typescript
z.object({ name: z.string() })
  .readonly()
  .parse(input)             // frozen object

z.array(z.number())
  .readonly()
  .parse([1, 2, 3])         // frozen array
```

**Readonly Behavior**:
- Returns frozen object (via `Object.freeze()`)
- TypeScript infers readonly properties
- Prevents accidental mutations
- Static type safety combined with runtime protection

## Branding

### .brand()

Adds nominal typing to distinguish between types with identical structures:

```typescript
type UserId = z.infer<typeof UserIdSchema> & z.Brand<"UserId">;
const UserIdSchema = z.number().brand<"UserId">();

const AdminIdSchema = z.number().brand<"AdminId">();

// Types are different at compile time
const userId: UserId = UserIdSchema.parse(1);
const adminId: z.infer<typeof AdminIdSchema> = AdminIdSchema.parse(1);
// userId = adminId;  // TypeScript error: incompatible brands

// No runtime overhead - brand is compile-time only
const raw = 42;
// raw satisfies UserId;  // TypeScript error
// UserIdSchema.parse(raw) satisfies UserId;  // OK
```

**Brand Behavior**:
- Compile-time only - no runtime overhead
- Distinguishes types with identical structures
- Requires parsing to obtain branded type
- Plain data is not assignable to branded types
- Useful for domain-specific IDs and types

## Additional Utilities

### .getType()

Returns a string representation of the schema type:

```typescript
z.string().getType()        // "string"
z.number().getType()        // "number"
z.object({ name: z.string() }).getType()  // "ZodObject"
```

### .describe()

Adds a description to the schema (useful for documentation):

```typescript
z.string()
  .describe("User's email address")
  .email()

// Used in generated documentation
z.object({
  email: z.string().describe("User email")
})
```

### .meta()

Attaches custom metadata to schemas:

```typescript
z.string()
  .meta({ customData: "value" })
  .email()

// Accessible for documentation generation
schema._meta  // { customData: "value" }
```
