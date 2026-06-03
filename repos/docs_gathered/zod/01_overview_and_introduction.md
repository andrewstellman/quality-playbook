# Zod - Overview and Introduction

## What is Zod?

Zod is a **TypeScript-first schema validation library with static type inference**. It enables developers to define schemas for validating data structures while automatically generating strongly-typed TypeScript types from those schemas. The key innovation is that validation logic and type definitions are unified into a single source of truth.

## Key Characteristics

- **Zero External Dependencies**: Minimal, self-contained implementation
- **Tiny Bundle Size**: 2kb gzipped core (excluding TypeScript compilation)
- **100% TypeScript Support**: Full type inference with `z.infer<typeof schema>`
- **Immutable API**: All schema methods return new instances, no mutations
- **Cross-Platform**: Works in Node.js and modern browsers
- **Built-in JSON Schema Conversion**: Native support for converting schemas to JSON Schema (Zod v4+)
- **Async Support**: Full async validation with `.parseAsync()` and `.safeParseAsync()`
- **Extensive Ecosystem**: 40+ third-party integrations (tRPC, React Hook Form, OpenAPI tools, etc.)

## Design Philosophy

Zod emphasizes several core principles:

1. **Type Safety First** - TypeScript types are inferred automatically, eliminating manual type duplication
2. **Composability** - Schemas are built by combining smaller schemas into larger ones
3. **Clarity** - Validation logic is explicit and declarative, not scattered across code
4. **Developer Experience** - Concise syntax with minimal boilerplate
5. **Immutability** - Schemas are treated as immutable values that can be safely shared and extended

## Installation

```bash
npm install zod
# or
yarn add zod
# or
pnpm add zod
```

## TypeScript Configuration Requirements

Zod requires TypeScript v5.5 or later with strict mode enabled:

```json
{
  "compilerOptions": {
    "strict": true,
    "target": "ES2020"
  }
}
```

## Quick Start Example

```typescript
import { z } from 'zod';

// Define a schema
const UserSchema = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string().email(),
  age: z.number().int().min(0).max(150).optional(),
});

// Extract TypeScript type
type User = z.infer<typeof UserSchema>;

// Parse and validate data
const data = {
  id: 1,
  name: "Alice",
  email: "alice@example.com",
  age: 30
};

const user = UserSchema.parse(data); // throws if invalid
const result = UserSchema.safeParse(data); // returns { success: boolean; ... }
```

## Version History

- **v4.x** (Current) - Native JSON Schema support, streamlined API
- **v3.x** - Stable release, widely adopted in production
- **v2.x** - Earlier feature-complete version
- **v1.x** - Initial releases

## When to Use Zod

Zod is ideal for:
- API request/response validation
- Form data validation in web applications
- Configuration file parsing and validation
- Type-safe data transformations
- API documentation generation (via JSON Schema)
- Ensuring runtime data matches static types
- Building type-safe libraries and frameworks

## Zod vs Alternatives

Compared to other validation libraries:
- **vs Yup**: Zod is TypeScript-native and has better async support
- **vs Joi**: Zod is smaller, faster, and TypeScript-first
- **vs io-ts**: Zod is simpler and more straightforward for most use cases
- **vs Ajv**: Zod is more developer-friendly with better TypeScript integration

## Core Concepts Overview

**Schema**: A Zod schema is a type definition and validator combined. Every schema validates a specific type of data.

**Parsing**: The act of validating data against a schema and returning either the validated (possibly transformed) data or an error.

**Type Inference**: Automatic extraction of TypeScript types from schemas using `z.infer<typeof schema>`.

**Immutability**: Schema methods return new schema instances rather than modifying the original.

**Composability**: Complex schemas are built by combining simpler schemas (objects contain field schemas, arrays contain element schemas, etc.).
