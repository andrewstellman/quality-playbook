# Zod Documentation Index

## Complete File Listing

### 01_overview_and_introduction.md
Introduction to Zod and its core philosophy. Covers what Zod is, key characteristics (zero dependencies, TypeScript-first, immutable API), design principles, installation, version history, and when to use Zod. Includes quick start example comparing Zod to alternatives.

**Key Topics**: 
- Zero external dependencies, 2kb gzipped
- Immutable API design
- TypeScript v5.5+ requirement with strict mode
- Core concepts: schemas, parsing, type inference, composability
- Quick start example with `z.object()`, `z.infer`, `.parse()`

### 02_schema_types_and_validation.md
Complete reference for all primitive types, collection types, and schema composition patterns. Detailed coverage of string formats (email, URL, UUID, IP, datetime), numeric types, objects, arrays, tuples, sets, maps, records, unions, and discriminated unions.

**Key Topics**:
- Primitive types: string, number, boolean, bigint, date, literal, enum
- String formats: email, URL, UUID, IP address, datetime, date, time, regex, patterns
- Numeric constraints: min, max, int, finite, safe, positive, multipleOf
- Object modes: strict, loose, catchall, pick, omit, extend, merge, partial, required
- Array and tuple validation with length constraints
- Union types (O(n) complexity) vs discriminated unions (O(1) dispatch)
- Optional/nullable/nullish distinctions
- Coercion types with behavior rules

### 03_schema_methods_and_transforms.md
Reference for parsing methods, refinement APIs, and transformation patterns. Covers `.parse()`, `.safeParse()`, `.refine()`, `.superRefine()`, `.transform()`, `.pipe()`, `.preprocess()`, defaults, and utility methods like `.readonly()` and `.brand()`.

**Key Topics**:
- Parse methods: `.parse()` (throws), `.safeParse()` (discriminated union result)
- Async variants: `.parseAsync()`, `.safeParseAsync()`
- Refinements: `.refine()` (basic), `.superRefine()` (fine-grained control)
- Refinement function contract: must never throw, return boolean
- Transforms: `.transform()` (unidirectional), `.pipe()` (schema chaining)
- Preprocessing: `.preprocess()` for type conversion before validation
- Defaults: `.default()` (undefined only), `.prefault()`, `.catch()` (on error)
- Utilities: `.readonly()`, `.brand()`, `.describe()`, `.meta()`

### 04_error_handling.md
Comprehensive error handling reference covering ZodError structure, error codes, formatting methods, custom messages, and error handling patterns. Details how errors are collected and reported.

**Key Topics**:
- ZodError structure: `issues` array with detailed error objects
- Error codes: invalid_type, invalid_literal, too_small, too_big, custom, etc.
- Error information: code, message, path (nested error location), context
- Formatting methods: `.flatten()` (flat object), `.format()` (structured)
- Custom messages in refinements and superRefine
- Error handling patterns: try-catch, safeParse, async variants
- Edge cases: multiple issues per field, union vs discriminated union errors
- Refinement error propagation (runs after base validations)

### 05_type_inference_and_typescript.md
Type inference mechanisms and TypeScript integration. Covers `z.infer<>`, `z.input<>`, `z.output<>`, branded types, extracting field types, and type safety guarantees for complex scenarios including transforms, async, and discriminated unions.

**Key Topics**:
- Type inference: `z.infer<typeof schema>` extracts TypeScript types
- Input vs output types for schemas with transforms
- `z.input<>` for input types, `z.output<>` for output types
- Branded types for nominal typing (UserId vs AdminId distinction)
- Brand behavioral contract: compile-time only, zero runtime overhead
- Complex type inference for objects, arrays, unions, tuples, generics
- Type safety with async transforms
- Generic schema factories
- Pattern: readonly properties, partial schemas, optional fields

### 06_advanced_patterns.md
Advanced validation patterns including recursive schemas, lazy evaluation, conditional validation, union dispatch logic, preprocessing utilities, custom validators, schema composition, and performance optimization.

**Key Topics**:
- Recursive schemas with `z.lazy()` for tree-like structures
- Mutual recursion between schemas
- ZodEffects introspection for pipeline inspection
- Conditional validation with `superRefine()` context
- Union dispatch: O(n) complexity for regular unions
- Discriminated union dispatch: O(1) complexity with discriminator
- Custom validators for domain-specific logic (credit cards, slugs, etc.)
- Schema factories and composition patterns
- Performance: schema caching, avoiding unnecessary transforms
- Lazy evaluation for large union sets

### 07_ecosystem_and_extensions.md
Integration with the Zod ecosystem, framework integrations, and community libraries. Covers native JSON Schema generation (Zod v4+), OpenAPI support, React Hook Form, tRPC, database ORMs, testing utilities, and configuration validation patterns.

**Key Topics**:
- Native JSON Schema: `.toJSONSchema()` (Zod v4+) replacing zod-to-json-schema
- JSON Schema versions: draft-7, draft-2020-12, draft-4, openapi-3.0
- OpenAPI integration with `.meta()` for extensions
- React Hook Form integration with zodResolver
- tRPC end-to-end type-safe APIs
- Database integration: Prisma, Drizzle ORM
- Form libraries: Conform, Valibot
- Testing: MSW mocking, Faker.js integration
- Environment and configuration validation patterns
- GraphQL resolver validation

### 08_behavioral_contracts_and_edge_cases.md
Detailed specification of Zod's validation behavior, coercion rules, and edge cases. Essential for understanding exact validation semantics and preventing subtle bugs.

**Key Topics**:
- Coercion rules: String(), Number(), Boolean(), Date() behavior
- Coercion edge cases: arrays, objects, NaN, empty strings
- Nullable vs optional vs nullish: semantic differences
- Default value contract: only undefined triggers default, not null or falsy
- Prefault vs default: input-level vs output-level defaults
- Union resolution order and dispatch behavior
- Discriminated union dispatch requirements and edge cases
- Object extra property handling: strict vs loose vs catchall
- Type narrowing and refinement execution order
- Transformation side effects and execution order
- Async validation in sync vs async contexts
- Array/tuple validation order (length vs elements)
- Set and Map validation semantics
- Record key validation with enums
- Readonly semantics with Object.freeze()
- String trim behavior before validation
- Empty string handling rules
- Literal and enum equality (case sensitive, strict equality)

### README.md
Overview document explaining the purpose of this documentation set and how to use it for AI-assisted code quality analysis.

## Navigation by Topic

### Getting Started
- **01_overview_and_introduction.md** - Start here for Zod fundamentals
- **02_schema_types_and_validation.md** - All schema types and validators

### Practical Development
- **03_schema_methods_and_transforms.md** - How to use schema methods
- **04_error_handling.md** - Error handling and validation failures
- **05_type_inference_and_typescript.md** - TypeScript integration
- **07_ecosystem_and_extensions.md** - Framework and library integration

### Advanced Usage
- **06_advanced_patterns.md** - Complex validation scenarios
- **08_behavioral_contracts_and_edge_cases.md** - Exact semantics and edge cases

### For Bug Hunting in Zod Codebase
Start with **08_behavioral_contracts_and_edge_cases.md** to understand expected behavior, then cross-reference with other files for specific method behavior. Key areas:
- Coercion rules (02, 08)
- Union and discriminated union dispatch (02, 06, 08)
- Refinement execution order (03, 04, 08)
- Default value semantics (03, 08)
- Transform and pipe behavior (03, 06)
- Type inference accuracy (05)
- Error reporting completeness (04, 08)

## Statistics

- **Total Files**: 10 (8 content files + INDEX.md + README.md)
- **Total Lines**: ~3,500+ lines of detailed reference material
- **Coverage**: All major Zod APIs, patterns, behavioral contracts, and edge cases
- **Focus**: Specification-style documentation for AI code quality analysis

## Version

- **Zod Version Covered**: v3.x through v4.x (current)
- **Last Updated**: 2026-04-12
- **TypeScript Requirement**: v5.5+ with strict mode

## Key References

All documentation files contain executable TypeScript examples showing expected behavior. When debugging Zod issues, cross-reference the actual code against examples in these files to identify discrepancies between specification and implementation.
