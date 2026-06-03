# Zod - Error Handling

## ZodError

`ZodError` is the exception thrown by `.parse()` when validation fails. It contains detailed information about all validation issues:

```typescript
import { z, ZodError } from 'zod';

const schema = z.object({
  name: z.string(),
  age: z.number().int().positive()
});

try {
  schema.parse({
    name: 123,
    age: -5
  });
} catch (error) {
  if (error instanceof ZodError) {
    console.log(error.issues);
    console.log(error.message);
    console.log(error.errors);  // alias for issues
  }
}
```

## ZodError Structure

### issues Array

The core property of ZodError is the `issues` array containing all validation failures:

```typescript
error.issues  // Array<ZodIssue>

// Each issue has:
[
  {
    code: "invalid_type",        // error code (string)
    expected: "string",          // what was expected
    received: "number",          // what was received
    path: ["name"],              // error location as array
    message: "Expected string, received number"
  },
  {
    code: "too_small",
    type: "number",              // context type
    minimum: 1,                  // constraint value
    inclusive: true,             // constraint is inclusive (>=)
    path: ["age"],
    message: "Number must be greater than 0"
  }
]
```

### message Property

```typescript
error.message  // concatenated string of all error messages

// Example output:
"[
  {
    \"code\": \"invalid_type\",
    \"expected\": \"string\",
    \"received\": \"number\",
    \"path\": [\"name\"],
    \"message\": \"Expected string, received number\"
  },
  {
    \"code\": \"too_small\",
    \"type\": \"number\",
    \"minimum\": 1,
    \"inclusive\": true,
    \"path\": [\"age\"],
    \"message\": \"Number must be greater than 0\"
  }
]"
```

## ZodIssue Codes

Zod defines specific error codes for different validation failures:

### Type Errors

```typescript
"invalid_type"      // value is wrong type (expected string, got number)
"invalid_literal"   // value doesn't match literal (expected "admin", got "user")
"invalid_enum"      // value not in enum options
"invalid_date"      // invalid date value
```

### String Validation

```typescript
"invalid_string"    // string format validation failed
                    // message includes: { validation: "email" | "url" | "uuid" | etc. }
"too_small"         // string too short
"too_big"           // string too long
```

### Number Validation

```typescript
"too_small"         // number less than minimum
                    // message includes: { type: "number", minimum, inclusive }
"too_big"           // number greater than maximum
"not_multiple"      // number not divisible by specified value
"not_finite"        // number is Infinity or NaN when not allowed
"not_int"           // float when integer required
```

### Collection Validation

```typescript
"invalid_union"     // value didn't match any union option
"invalid_union_discriminator"  // discriminated union dispatch failed
"too_small"         // array/set/tuple too few elements
"too_big"           // array/set/tuple too many elements
```

### Object Validation

```typescript
"unrecognized_keys"  // object has unexpected properties (strict mode)
"invalid_arguments"  // function parameters don't match
```

### Custom Errors

```typescript
"custom"            // custom refinement or superRefine issue
```

## Error Formatting Methods

### .flatten()

Converts nested error structure to a flat object keyed by field path:

```typescript
const error = ZodError([...]);
error.flatten()  // { fieldErrors: {...}, formErrors: [...] }

// Example:
{
  fieldErrors: {
    name: ["Expected string, received number"],
    "address.street": ["String must be at least 1 characters"],
    "tags.0": ["Expected string, received number"]
  },
  formErrors: []  // errors not tied to specific fields
}

// Useful for mapping errors to form fields
form.fields.name.errors = error.flatten().fieldErrors.name;
```

### .flatten(callback)

Custom formatting of flattened errors:

```typescript
error.flatten((issue) => ({
  code: issue.code,
  message: issue.message,
  received: issue.received
}))
```

### .format()

Recursively formats errors matching the input structure:

```typescript
const schema = z.object({
  name: z.string(),
  address: z.object({
    street: z.string(),
    zip: z.string().regex(/^\d{5}$/)
  })
});

try {
  schema.parse(data);
} catch (error) {
  const formatted = error.format();
  // {
  //   name?: { _errors: ["Expected string..."] },
  //   address?: {
  //     street?: { _errors: ["..."] },
  //     zip?: { _errors: ["..."] }
  //   },
  //   _errors: [...]
  // }
}
```

**Format Structure**: 
- `_errors` array contains errors for the current level
- Nested objects mirror the schema structure
- Undefined fields indicate no errors
- Useful for form validation error display

## Custom Error Messages

### refine() with message

```typescript
z.string()
  .refine((v) => v.length > 3, {
    message: "Must be longer than 3 characters"
  })
  .parse("ab")  // ZodError with custom message
```

### superRefine() with custom codes

```typescript
z.string().superRefine((val, ctx) => {
  if (val.includes("admin")) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Cannot contain 'admin'",
      path: [""]  // error on this field
    });
  }
  
  if (val.length < 5) {
    ctx.addIssue({
      code: z.ZodIssueCode.too_small,
      type: "string",
      minimum: 5,
      inclusive: true,
      message: "Must be at least 5 characters"
    });
  }
})
```

### Parameterized Messages

```typescript
// Zod's built-in messages use parameters
z.string().min(5)  
// Message: "String must contain at least 5 character(s)"

z.number().max(100)
// Message: "Number must be less than or equal to 100"

// Custom messages override defaults:
z.string().min(5, "Name must be at least 5 chars")
z.number().max(100, "Score cannot exceed 100")
```

## Error Handling Patterns

### Try-Catch Pattern

```typescript
try {
  const data = schema.parse(input);
  // use data
} catch (error) {
  if (error instanceof ZodError) {
    // handle validation error
    error.issues.forEach(issue => {
      console.log(issue.code, issue.path, issue.message);
    });
  } else {
    // unexpected error
    throw error;
  }
}
```

### SafeParse Pattern

```typescript
const result = schema.safeParse(input);

if (result.success) {
  // result.data is the validated value (type T)
  processData(result.data);
} else {
  // result.error is ZodError
  const fieldErrors = result.error.flatten().fieldErrors;
  displayErrors(fieldErrors);
}
```

### Async Error Handling

```typescript
try {
  const data = await schema.parseAsync(input);
  // use data
} catch (error) {
  if (error instanceof ZodError) {
    // handle validation error
  }
}

// Or with safeParseAsync
const result = await schema.safeParseAsync(input);
if (!result.success) {
  // handle error.error
}
```

## Error Message Internalization

Zod doesn't have built-in i18n, but error messages can be customized:

```typescript
// Custom messages per validation
const schema = z.string()
  .min(3, "Username must be at least 3 characters")
  .max(20, "Username cannot exceed 20 characters")
  .email("Please enter a valid email");

// Or using refine for complex messages
const schema = z.string().refine(
  (val) => val.length >= 3,
  { 
    message: i18n.t("validation.tooShort", { min: 3 })
  }
);

// Transform error messages
function translateErrors(error: ZodError, locale: string) {
  return error.issues.map(issue => ({
    ...issue,
    message: i18n.t(`validation.${issue.code}`, { locale })
  }));
}
```

## Edge Cases and Behavioral Contracts

### Multiple Issues in Single Field

A field can have multiple validation errors:

```typescript
const schema = z.object({
  password: z.string()
    .min(8, "At least 8 characters")
    .regex(/[A-Z]/, "At least one uppercase letter")
    .regex(/[0-9]/, "At least one number")
});

// Parsing with multiple failures reports all issues:
schema.safeParse({ password: "weak" }).error.issues
// [
//   { code: "too_small", ... message: "At least 8 characters" },
//   { code: "invalid_string", ... message: "At least one uppercase letter" },
//   { code: "invalid_string", ... message: "At least one number" }
// ]
```

### Union Errors

Regular unions report errors from all options:

```typescript
z.union([z.string().email(), z.number().int()])
  .safeParse(true).error.issues
// Reports errors from BOTH branches because neither succeeded
```

### Discriminated Union Errors

Discriminated unions report only from matching option:

```typescript
z.discriminatedUnion("type", [
  z.object({ type: z.literal("a"), value: z.string() }),
  z.object({ type: z.literal("b"), value: z.number() })
])
  .safeParse({ type: "a", value: 123 }).error.issues
// Reports error only from type "a" option (invalid value type)
// Does NOT report error from type "b" option
```

### Refinement Error Propagation

Refinements run after all base validations:

```typescript
z.string()
  .email()
  .refine((v) => !forbiddenEmails.includes(v))
  .safeParse("invalid-email").error.issues
// Reports: "invalid_string" (email format) only
// Does NOT reach refinement because base validation failed
```
