# Zod - Advanced Patterns

## Recursive Schemas

Recursive schemas reference themselves, enabling validation of tree-like and nested structures:

```typescript
import { z } from 'zod';

// Define a tree node that can have children (which are also tree nodes)
type TreeNode = {
  value: string;
  children?: TreeNode[];
};

const TreeNodeSchema: z.ZodType<TreeNode> = z.lazy(() =>
  z.object({
    value: z.string(),
    children: z.array(TreeNodeSchema).optional()
  })
);

const tree = {
  value: "root",
  children: [
    {
      value: "child1",
      children: [{ value: "grandchild1" }]
    },
    {
      value: "child2"
    }
  ]
};

TreeNodeSchema.parse(tree);  // validates recursive structure
```

**Recursive Schema Requirements**:
- Must use `z.lazy()` to wrap the schema definition
- Lazy function returns the schema, not the type
- Explicit type annotation often helps: `z.ZodType<TreeNode>`
- Circular references are resolved at runtime, not at type-checking time

### Mutual Recursion

Schemas can reference each other in circular patterns:

```typescript
type Category = {
  name: string;
  posts: Post[];
};

type Post = {
  title: string;
  category: Category;
};

const CategorySchema: z.ZodType<Category> = z.lazy(() =>
  z.object({
    name: z.string(),
    posts: z.array(PostSchema)
  })
);

const PostSchema: z.ZodType<Post> = z.lazy(() =>
  z.object({
    title: z.string(),
    category: CategorySchema
  })
);
```

## Using z.lazy()

`z.lazy()` delays schema evaluation until validation time:

```typescript
// Without lazy - circular reference error
const BadSchema = z.object({
  name: z.string(),
  self: BadSchema  // ReferenceError: BadSchema not defined yet
});

// With lazy - works fine
const GoodSchema: z.ZodType<any> = z.object({
  name: z.string(),
  self: z.lazy(() => GoodSchema).optional()
});

// Lazy also allows runtime schema selection
const DynamicSchema = z.lazy(() => {
  const env = process.env.VALIDATION_LEVEL;
  return env === 'strict' 
    ? z.object({ name: z.string().min(10) })
    : z.object({ name: z.string() });
});
```

**Lazy Behavior**:
- Schema is evaluated when first parsed, not when defined
- Circular references are resolved at parse time
- Can have runtime logic in lazy callbacks
- Useful for performance (deferred schema creation)

## ZodEffects and Effects

`ZodEffects` is a wrapper that contains preprocessing, refinements, and transforms. You can access it for advanced use cases:

```typescript
const schema = z.string()
  .transform((v) => v.toUpperCase())
  .refine((v) => v.length > 3);

// schema is actually a ZodEffects wrapping z.string()
console.log(schema instanceof z.ZodEffects);  // true

// Access the underlying schema
const inner = schema._def.schema;  // z.string()

// Effects contain array of "steps" 
const steps = schema._def.effects;  // transforms and refinements
```

**ZodEffects Use Cases**:
- Introspecting validation pipeline
- Building custom validation utilities
- Advanced debugging and logging
- Creating schema wrappers

## Conditional Validation

Validate based on other field values:

```typescript
const schema = z.object({
  country: z.enum(["US", "CA", "MX"]),
  state: z.string(),
  province: z.string()
}).superRefine((data, ctx) => {
  if (data.country === "US" && !data.state) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "State required for US",
      path: ["state"]
    });
  }
  
  if (data.country === "CA" && !data.province) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Province required for Canada",
      path: ["province"]
    });
  }
});

// Or using when parameter in refine (if available)
z.object({
  type: z.enum(["personal", "business"]),
  taxId: z.string().optional()
}).refine(
  (data) => data.type !== "business" || data.taxId,
  {
    message: "Tax ID required for business accounts",
    path: ["taxId"]
  }
);
```

## Union Dispatch Logic

Understand how Zod validates unions and discriminated unions:

### Regular Union Validation (O(n))

```typescript
const RegularUnion = z.union([
  z.object({ type: z.literal("user"), name: z.string() }),
  z.object({ type: z.literal("admin"), permissions: z.array(z.string()) })
]);

// Zod tries BOTH options:
// 1. Try first schema - check if input matches
// 2. Try second schema - check if input matches
// 3. If both fail, report errors from BOTH attempts

RegularUnion.safeParse({ type: "user", name: 123 }).error.issues
// Reports errors from BOTH options because neither succeeded
```

**Union Performance Characteristics**:
- Time complexity: O(n) where n = number of options
- All options are attempted
- Error messages include failures from all branches
- Useful when branches are significantly different

### Discriminated Union Validation (O(1))

```typescript
const DiscriminatedUnion = z.discriminatedUnion("type", [
  z.object({ type: z.literal("user"), name: z.string() }),
  z.object({ type: z.literal("admin"), permissions: z.array(z.string()) })
]);

// Zod dispatches based on discriminator:
// 1. Extract discriminator value: "user" or "admin"
// 2. Select matching schema
// 3. Validate ONLY against that schema
// 4. Report errors only from matching schema

DiscriminatedUnion.safeParse({ type: "user", name: 123 }).error.issues
// Reports only errors from the "user" option
// Does NOT report errors from "admin" option
```

**Discriminated Union Requirements**:
- All options must have a shared discriminator field
- Discriminator values must be literals or enums
- All options must be objects
- Order of options doesn't matter (dispatch is by value)

## Preprocess Patterns

### Type Coercion Before Validation

```typescript
// Parse string to number before validation
const AgeSchema = z.preprocess(
  (val) => {
    if (typeof val === 'string') return parseInt(val);
    return val;
  },
  z.number().int().min(0).max(150)
);

AgeSchema.parse("25")        // 25
AgeSchema.parse(25)          // 25
```

### Cleanup and Normalization

```typescript
const EmailSchema = z.preprocess(
  (val) => {
    if (typeof val === 'string') {
      return val.trim().toLowerCase();
    }
    return val;
  },
  z.string().email()
);

EmailSchema.parse("  USER@EXAMPLE.COM  ")  // "user@example.com"
```

### Default Transform in Preprocessing

```typescript
const ConfigSchema = z.preprocess(
  (val) => {
    if (typeof val === 'object' && val !== null && !('timeout' in val)) {
      return { ...val, timeout: 5000 };
    }
    return val;
  },
  z.object({
    endpoint: z.string().url(),
    timeout: z.number().positive()
  })
);

ConfigSchema.parse({ endpoint: "https://api.example.com" })
// { endpoint: "https://api.example.com", timeout: 5000 }
```

## Custom Validation Utilities

### Reusable Refinement Helpers

```typescript
// Factory for "at least one" validation
function atLeastOneOf<T extends Record<string, any>>(
  keys: (keyof T)[],
  message: string
) {
  return (obj: T) => keys.some(key => obj[key] !== undefined && obj[key] !== null);
}

const AccountSchema = z.object({
  email: z.string().email().optional(),
  phone: z.string().optional(),
  username: z.string().optional()
}).refine(
  (data) => atLeastOneOf(['email', 'phone', 'username'] as const, "Need one contact method")(data),
  { message: "Need one contact method" }
);

// Factory for cross-field comparison
function fieldsMatch<K extends string>(field1: K, field2: K, message: string) {
  return (obj: Record<K, any>) => obj[field1] === obj[field2];
}

const PasswordSchema = z.object({
  password: z.string(),
  confirmPassword: z.string()
}).refine(
  (data) => fieldsMatch('password', 'confirmPassword', "Passwords don't match")(data),
  { message: "Passwords don't match", path: ["confirmPassword"] }
);
```

### Domain-Specific Validators

```typescript
// Validation for credit card (Luhn algorithm)
const CreditCardSchema = z.string()
  .regex(/^\d{13,19}$/, "Invalid card number format")
  .refine((val) => {
    const digits = val.split('').map(Number);
    let sum = 0;
    let isEven = false;
    
    for (let i = digits.length - 1; i >= 0; i--) {
      let digit = digits[i];
      if (isEven) {
        digit *= 2;
        if (digit > 9) digit -= 9;
      }
      sum += digit;
      isEven = !isEven;
    }
    
    return sum % 10 === 0;
  }, { message: "Invalid credit card number" });

// Validation for slug format
const SlugSchema = z.string()
  .min(1)
  .max(100)
  .refine(
    (val) => /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(val),
    { message: "Invalid slug format" }
  );
```

## Extending Schemas

### Creating Schema Factories

```typescript
// ID schema factory
function createIdSchema<T extends string>(brand: T) {
  return z.number().int().positive().brand<T>();
}

const UserId = createIdSchema("UserId");
const AdminId = createIdSchema("AdminId");

type UserId = z.infer<typeof UserId>;
type AdminId = z.infer<typeof AdminId>;
```

### Composing Complex Schemas

```typescript
// Base schemas
const timestamps = z.object({
  createdAt: z.date(),
  updatedAt: z.date()
});

const metadata = z.object({
  tags: z.array(z.string()),
  priority: z.enum(["low", "medium", "high"])
});

// Compose into larger schema
const DocumentSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  content: z.string()
}).merge(timestamps).merge(metadata);

type Document = z.infer<typeof DocumentSchema>;
```

## Performance Optimization

### Schema Caching

```typescript
// Don't recreate schemas in hot paths
const userSchema = z.object({
  name: z.string(),
  email: z.string().email()
});

// Good - reuse same schema
function validateUser(data: unknown) {
  return userSchema.safeParse(data);
}

// Bad - creates new schema each time
function validateUserBad(data: unknown) {
  return z.object({  // avoid this
    name: z.string(),
    email: z.string().email()
  }).safeParse(data);
}
```

### Avoiding Unnecessary Transforms

```typescript
// Avoid transforms when type is already correct
const BadSchema = z.string()
  .transform((v) => v.toString())  // unnecessary - already string
  .transform((v) => v.trim());     // can use .trim() directly

const GoodSchema = z.string()
  .trim()
  .refine((v) => v.length > 0);
```

### Using Lazy for Large Union Sets

```typescript
// For large unions, use discriminated unions and lazy evaluation
const LargeUnion = z.discriminatedUnion("type", [
  z.lazy(() => z.object({ type: z.literal("a"), ...schemaA })),
  z.lazy(() => z.object({ type: z.literal("b"), ...schemaB })),
  z.lazy(() => z.object({ type: z.literal("c"), ...schemaC }))
  // ... many more options
]);
```
