# Zod - Type Inference and TypeScript Integration

## Type Inference with z.infer

The `z.infer<>` utility type automatically extracts the TypeScript type from a Zod schema:

```typescript
import { z } from 'zod';

const UserSchema = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string().email(),
  age: z.number().optional()
});

// Automatically inferred type
type User = z.infer<typeof UserSchema>;
// Equivalent to: { id: number; name: string; email: string; age?: number }

const user: User = UserSchema.parse(data);
```

**Type Inference Rules**:
- Required fields → non-optional properties
- `.optional()` fields → optional properties with `T | undefined`
- `.nullable()` fields → properties with `T | null`
- `.nullish()` fields → properties with `T | null | undefined`
- `.default()` fields → non-optional (default is applied at parse time)
- Transformed fields → type matches transform output

## Input and Output Types

Schemas can have different input and output types when using transforms:

```typescript
const TransformSchema = z.string()
  .transform((v) => parseInt(v))
  .transform((v) => v * 2);

type Output = z.infer<typeof TransformSchema>;  // number
type Input = z.input<typeof TransformSchema>;   // string

TransformSchema.parse("5")  // returns 10 (number)
```

### Input Type Extraction

Use `z.input<typeof schema>` to get the input type:

```typescript
const DateSchema = z.string()
  .datetime()
  .transform((v) => new Date(v));

type DateInput = z.input<typeof DateSchema>;    // string (raw input)
type DateOutput = z.infer<typeof DateSchema>;   // Date (after transform)

const input: DateInput = "2024-01-01T00:00:00Z";
const output: DateOutput = DateSchema.parse(input);
```

### Output Type Extraction

Use `z.output<typeof schema>` (equivalent to `z.infer<>`) to get the output type:

```typescript
type ExplicitOutput = z.output<typeof DateSchema>;  // Date
```

## Complex Type Scenarios

### Objects with Nested Transforms

```typescript
const UserWithDatesSchema = z.object({
  name: z.string(),
  createdAt: z.string().transform((v) => new Date(v)),
  updatedAt: z.string().transform((v) => new Date(v))
});

type User = z.infer<typeof UserWithDatesSchema>;
// {
//   name: string;
//   createdAt: Date;    (not string!)
//   updatedAt: Date;
// }

type UserInput = z.input<typeof UserWithDatesSchema>;
// {
//   name: string;
//   createdAt: string;
//   updatedAt: string;
// }
```

### Arrays and Tuples

```typescript
const ArraySchema = z.array(z.string().transform((v) => v.length));
type ArrayInferred = z.infer<typeof ArraySchema>;  // number[]

const TupleSchema = z.tuple([
  z.string(),
  z.number().transform((v) => v > 0)
]);
type TupleInferred = z.infer<typeof TupleSchema>;  // [string, boolean]
```

### Unions and Discriminated Unions

```typescript
const UnionSchema = z.union([
  z.object({ type: z.literal("a"), value: z.string() }),
  z.object({ type: z.literal("b"), value: z.number() })
]);

type UnionType = z.infer<typeof UnionSchema>;
// { type: "a"; value: string } | { type: "b"; value: number }

const DiscriminatedSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("user"), name: z.string() }),
  z.object({ kind: z.literal("admin"), name: z.string(), permissions: z.array(z.string()) })
]);

type DiscriminatedType = z.infer<typeof DiscriminatedSchema>;
// { kind: "user"; name: string } | 
// { kind: "admin"; name: string; permissions: string[] }
```

## Branded Types

Branded types add nominal typing to distinguish between types with identical structures. Available in Zod v4.2+.

```typescript
type UserId = z.infer<typeof UserIdSchema> & z.Brand<"UserId">;
const UserIdSchema = z.number().brand<"UserId">();

type AdminId = z.infer<typeof AdminIdSchema> & z.Brand<"AdminId">;
const AdminIdSchema = z.number().brand<"AdminId">();

// At compile time, UserId and AdminId are different types
const userId: UserId = UserIdSchema.parse(1);
const adminId: AdminId = AdminIdSchema.parse(1);

// TypeScript error: Type 'AdminId' is not assignable to type 'UserId'
// userId = adminId;

// Requires parsing to obtain branded type
const id: UserId = 1;  // TypeScript error: cannot assign unbranded value

// After parsing, the value is branded
const brandedId: UserId = UserIdSchema.parse(1);  // OK
```

**Branded Type Behavior**:
- Pure TypeScript compile-time distinction
- Zero runtime overhead (brands are stripped)
- Prevents accidental type mixing (e.g., UserId vs AdminId)
- Requires schema parsing to create branded values
- Useful for domain-driven type safety

### Advanced Branding

```typescript
// Brand only output (not input)
type SafeString = z.infer<typeof SafeStringSchema> & z.Brand<"safe", "out">;
const SafeStringSchema = z.string()
  .refine((v) => !hasMaliciousContent(v))
  .brand<"safe", "out">();

// Input: string (unbranded)
// Output: SafeString (branded)

// Brand only input (rare)
type AuthorizedRequest = z.Brand<"authorized", "in"> & Record<string, any>;

// Brand both input and output (default)
const BrandedSchema = z.string().brand<"MyBrand">();
// Equivalent to .brand<"MyBrand", "in" | "out">()
```

## Extracting Specific Field Types

Sometimes you need to extract the type of a single field:

```typescript
const UserSchema = z.object({
  name: z.string(),
  email: z.string().email(),
  age: z.number()
});

type UserType = z.infer<typeof UserSchema>;
type UserName = UserType["name"];      // string
type UserEmail = UserType["email"];    // string
type UserAge = UserType["age"];        // number

// Or using z.infer directly on field schema
const NameSchema = UserSchema.shape.name;
type Name = z.infer<typeof NameSchema>;  // string
```

## Using Schemas as Type Predicates

While Zod schemas aren't true type guards, they can be used to narrow types:

```typescript
const schema = z.object({ name: z.string(), age: z.number() });

function processData(data: unknown) {
  const result = schema.safeParse(data);
  
  if (result.success) {
    // TypeScript knows result.data is { name: string; age: number }
    console.log(result.data.name);  // no type error
    console.log(result.data.age);   // no type error
  }
}
```

## Type Safety with Async Transforms

Async transforms preserve types correctly:

```typescript
const schema = z.string()
  .email()
  .transform(async (email) => {
    const user = await db.getUserByEmail(email);
    return user;
  });

type Inferred = z.infer<typeof schema>;  // Promise<User> if user exists, throws if not

const result = await schema.parseAsync("user@example.com");
// result is User type
```

## Constraints on Inferred Types

Zod's type inference respects all schema constraints:

```typescript
// Enum constraints
const StatusSchema = z.enum(["active", "inactive", "pending"]);
type Status = z.infer<typeof StatusSchema>;  // "active" | "inactive" | "pending"

// Literal constraints
const RoleSchema = z.literal("admin").or(z.literal("user"));
type Role = z.infer<typeof RoleSchema>;  // "admin" | "user"

// Union of objects
const ResponseSchema = z.union([
  z.object({ success: z.literal(true), data: z.unknown() }),
  z.object({ success: z.literal(false), error: z.string() })
]);
type Response = z.infer<typeof ResponseSchema>;
// { success: true; data: unknown } | { success: false; error: string }
```

## Generic Schemas

Zod schemas can be generic over their inferred types:

```typescript
// Factory for paginated responses
function createPaginatedSchema<T extends z.ZodTypeAny>(itemSchema: T) {
  return z.object({
    items: z.array(itemSchema),
    page: z.number(),
    pageSize: z.number(),
    total: z.number()
  });
}

const UserItemSchema = z.object({ id: z.number(), name: z.string() });
const PaginatedUsers = createPaginatedSchema(UserItemSchema);

type PaginatedUsersType = z.infer<typeof PaginatedUsers>;
// {
//   items: { id: number; name: string }[];
//   page: number;
//   pageSize: number;
//   total: number;
// }
```

## Common Type Patterns

### Required vs Optional Fields

```typescript
// All required
const StrictSchema = z.object({
  name: z.string(),
  email: z.string()
});

// With optional
const FlexibleSchema = z.object({
  name: z.string(),
  email: z.string().optional(),     // undefined allowed
  phone: z.string().nullable(),     // null allowed
  bio: z.string().nullish()         // null or undefined allowed
});

type Flexible = z.infer<typeof FlexibleSchema>;
// { name: string; email?: string; phone: string | null; bio?: string | null }
```

### Partial Schemas

```typescript
const UserSchema = z.object({
  name: z.string(),
  email: z.string(),
  age: z.number()
});

const PartialUserSchema = UserSchema.partial();
type PartialUser = z.infer<typeof PartialUserSchema>;
// { name?: string; email?: string; age?: number }

const PickSchema = UserSchema.pick({ name: true, email: true });
type Pick = z.infer<typeof PickSchema>;
// { name: string; email: string }
```

### Readonly Types

```typescript
const ReadonlyUserSchema = z.object({
  name: z.string(),
  email: z.string()
}).readonly();

type ReadonlyUser = z.infer<typeof ReadonlyUserSchema>;
// { readonly name: string; readonly email: string }
```
