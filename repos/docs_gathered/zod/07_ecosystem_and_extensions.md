# Zod - Ecosystem and Extensions

## JSON Schema Integration

### Native JSON Schema Support (Zod v4+)

Zod v4 introduced native JSON Schema generation without requiring external libraries:

```typescript
import { z } from 'zod';

const UserSchema = z.object({
  id: z.number(),
  name: z.string().describe("User's full name"),
  email: z.string().email(),
  age: z.number().int().positive().optional()
});

// Generate JSON Schema
const jsonSchema = UserSchema.toJSONSchema();

// Result:
{
  "type": "object",
  "properties": {
    "id": { "type": "number" },
    "name": { 
      "type": "string",
      "description": "User's full name"
    },
    "email": { "type": "string", "format": "email" },
    "age": { "type": "number" }
  },
  "required": ["id", "name", "email"]
}
```

**JSON Schema Versions Supported**:
- JSON Schema Draft 7 (default)
- JSON Schema Draft 2020-12
- JSON Schema Draft 4
- OpenAPI 3.0

### Generating Different Schema Versions

```typescript
const schema = z.string().email();

const draft7 = schema.toJSONSchema({ version: "draft-7" });
const draft2020 = schema.toJSONSchema({ version: "draft-2020-12" });
const openapi3 = schema.toJSONSchema({ version: "openapi-3.0.0" });
```

## OpenAPI Integration

### zod-openapi Library

`zod-openapi` generates OpenAPI v3.x documentation from Zod schemas:

```typescript
import { z } from 'zod';
import { OpenApiBuilder } from 'openapi3-ts';

const UserSchema = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string().email()
}).describe("User account");

const ErrorSchema = z.object({
  code: z.string(),
  message: z.string()
}).describe("Error response");

// Generate OpenAPI components
const openapi = new OpenApiBuilder()
  .addTitle("My API")
  .addVersion("1.0.0")
  .addPath("/users/:id", {
    get: {
      responses: {
        "200": {
          description: "User found",
          content: {
            "application/json": {
              schema: UserSchema.toJSONSchema()
            }
          }
        },
        "404": {
          description: "User not found",
          content: {
            "application/json": {
              schema: ErrorSchema.toJSONSchema()
            }
          }
        }
      }
    }
  });
```

### Using .meta() for OpenAPI Extensions

```typescript
const UserSchema = z.object({
  id: z.number()
    .meta({ example: 123 }),
  email: z.string()
    .email()
    .meta({ 
      example: "user@example.com",
      description: "User's email address"
    })
}).meta({
  description: "User account information",
  example: { id: 1, email: "user@example.com" }
});

// Metadata is accessible during OpenAPI generation
const meta = UserSchema._meta;
```

## Framework Integrations

### React Hook Form Integration

```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email"),
  age: z.number().positive("Age must be positive")
});

type FormData = z.infer<typeof schema>;

function MyForm() {
  const {
    register,
    handleSubmit,
    formState: { errors }
  } = useForm<FormData>({
    resolver: zodResolver(schema)
  });

  return (
    <form onSubmit={handleSubmit((data) => console.log(data))}>
      <input {...register("name")} />
      {errors.name && <span>{errors.name.message}</span>}
      
      <input {...register("email")} />
      {errors.email && <span>{errors.email.message}</span>}
      
      <input type="number" {...register("age", { valueAsNumber: true })} />
      {errors.age && <span>{errors.age.message}</span>}
      
      <button type="submit">Submit</button>
    </form>
  );
}
```

### tRPC Integration

tRPC uses Zod for end-to-end type-safe API definitions:

```typescript
import { z } from 'zod';
import { router, publicProcedure } from './trpc';

const userRouter = router({
  create: publicProcedure
    .input(z.object({
      name: z.string(),
      email: z.string().email()
    }))
    .output(z.object({
      id: z.number(),
      name: z.string(),
      email: z.string()
    }))
    .mutation(async ({ input }) => {
      const user = await db.createUser(input);
      return user;
    }),

  getById: publicProcedure
    .input(z.object({
      id: z.number()
    }))
    .query(async ({ input }) => {
      return await db.getUserById(input.id);
    })
});
```

## Community Libraries and Extensions

### Form Validation Libraries

**Conform**: Lightweight form validation and submission
```typescript
const schema = z.object({
  name: z.string(),
  email: z.string().email()
});

const form = useForm({
  onValidate({ formData }) {
    return parse(formData, { schema });
  }
});
```

**Valibot**: Alternative validation library with Zod interop
- Similar API to Zod
- Smaller bundle size for some use cases
- Can convert between Zod and Valibot schemas

### Database and ORM Integration

**Prisma + Zod**: Generate Zod schemas from Prisma models
```typescript
// Generated from Prisma schema
const UserSchema = z.object({
  id: z.number().int(),
  email: z.string().email(),
  name: z.string().nullable()
});
```

**Drizzle ORM**: Native Zod validation support
```typescript
import { pgTable, serial, varchar } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  email: varchar('email').notNull(),
  name: varchar('name')
});

// Automatically generate Zod schemas
import { createSelectSchema } from 'drizzle-zod';
const selectUserSchema = createSelectSchema(users);
```

### Data Mocking and Testing

**MSW (Mock Service Worker)**: Use Zod schemas with MSW for API mocking
```typescript
import { http, HttpResponse } from 'msw';

const userSchema = z.object({ id: z.number(), name: z.string() });

export const handlers = [
  http.get('/api/users/:id', ({ params }) => {
    return HttpResponse.json(userSchema.parse({
      id: parseInt(params.id),
      name: "Mocked User"
    }));
  })
];
```

**Faker.js + Zod**: Generate realistic fake data matching schemas
```typescript
import { faker } from '@faker-js/faker';

const userSchema = z.object({
  id: z.number(),
  email: z.string().email(),
  name: z.string()
});

function generateFakeUser(): z.infer<typeof userSchema> {
  return {
    id: faker.number.int(),
    email: faker.internet.email(),
    name: faker.person.fullName()
  };
}
```

## GraphQL Integration

### GraphQL + Zod

Zod schemas can be used for input validation in GraphQL resolvers:

```typescript
import { GraphQLObjectType, GraphQLString, GraphQLInt } from 'graphql';

const userInputSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
  age: z.number().int().positive()
});

export const createUserResolver = {
  type: UserType,
  args: {
    input: { type: UserInputType }
  },
  resolve: (parent, args) => {
    const validatedInput = userInputSchema.parse(args.input);
    return createUser(validatedInput);
  }
};
```

## Configuration and Environment Validation

### Environment Variable Validation

```typescript
const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']),
  PORT: z.coerce.number().int().positive(),
  DATABASE_URL: z.string().url(),
  API_KEY: z.string().min(32)
});

type Environment = z.infer<typeof envSchema>;

const env = envSchema.parse(process.env);

export default env;
```

### Configuration File Parsing

```typescript
import { readFileSync } from 'fs';
import { parse as parseYaml } from 'yaml';

const configSchema = z.object({
  server: z.object({
    host: z.string().default('localhost'),
    port: z.coerce.number().default(3000)
  }),
  database: z.object({
    url: z.string().url(),
    maxConnections: z.coerce.number().int().positive()
  })
});

const configFile = readFileSync('config.yaml', 'utf-8');
const config = configSchema.parse(parseYaml(configFile));
```

## API Request/Response Validation

```typescript
const createUserRequestSchema = z.object({
  name: z.string().min(1, "Name required"),
  email: z.string().email("Invalid email"),
  role: z.enum(['user', 'admin']).default('user')
});

const userResponseSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  email: z.string().email(),
  role: z.enum(['user', 'admin']),
  createdAt: z.date(),
  updatedAt: z.date()
});

type CreateUserRequest = z.infer<typeof createUserRequestSchema>;
type UserResponse = z.infer<typeof userResponseSchema>;

// In API handler
app.post('/users', (req, res) => {
  const result = createUserRequestSchema.safeParse(req.body);
  
  if (!result.success) {
    return res.status(400).json(result.error.flatten());
  }

  const user = createUser(result.data);
  const response = userResponseSchema.parse(user);
  
  res.status(201).json(response);
});
```

## Testing with Zod

### Schema-Based Property Testing

```typescript
import { test } from 'vitest';

const userSchema = z.object({
  name: z.string().min(1).max(100),
  age: z.number().int().min(18).max(150)
});

test('schema validates correct user data', () => {
  const validUser = {
    name: "John Doe",
    age: 30
  };
  
  expect(() => userSchema.parse(validUser)).not.toThrow();
});

test('schema rejects invalid user data', () => {
  const invalidUser = {
    name: "",
    age: 10
  };
  
  const result = userSchema.safeParse(invalidUser);
  expect(result.success).toBe(false);
});
```

### Mock Data Generation from Schemas

```typescript
// Custom function to generate realistic data from schema
function generateTestData<T>(schema: z.ZodSchema<T>): T {
  // Implementation would introspect schema and generate valid data
  return schema.parse({...});
}

const testUser = generateTestData(userSchema);
```

## Maintenance Status

### Deprecated: zod-to-json-schema

As of Zod v4, the external `zod-to-json-schema` library is no longer recommended. Use the native `.toJSONSchema()` method instead:

```typescript
// Old (deprecated)
// import { jsonSchemaFromZodSchema } from 'zod-to-json-schema';

// New (Zod v4+)
const schema = z.object({ name: z.string() });
const jsonSchema = schema.toJSONSchema();
```

## Extensibility Points

Zod provides extension points for custom integrations:

### Custom Schema Types

```typescript
// Create custom schema type
class CustomSchema extends z.ZodType {
  parse(data) {
    // custom parsing logic
  }
  
  safeParse(data) {
    // custom safe parsing
  }
  
  _parse(input) {
    // internal parsing
  }
}
```

### Schema Introspection

```typescript
const schema = z.object({ name: z.string(), age: z.number() });

// Access schema definition
const shape = schema.shape;            // field schemas
const keys = Object.keys(shape);       // field names
const nameSchema = shape.name;         // specific field

// Iterate over all fields
for (const [key, fieldSchema] of Object.entries(shape)) {
  console.log(key, fieldSchema._type); // e.g., "name", "ZodString"
}
```
