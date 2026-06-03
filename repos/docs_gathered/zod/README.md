# Zod Reference Documentation

A comprehensive specification-style reference for the Zod TypeScript validation library, designed for AI-assisted code quality analysis and bug identification.

## Purpose

This documentation set provides detailed specifications of Zod's API surface and behavioral contracts. Unlike tutorials, these docs emphasize:

- **Exact specifications** over explanations
- **Edge case semantics** over happy path examples
- **Behavioral contracts** over conceptual overviews
- **Coercion rules** and type transformations
- **Error reporting specifics** including codes and paths
- **Performance characteristics** (e.g., O(n) unions vs O(1) discriminated unions)

The documentation is structured to help AI tools identify bugs, verify expected behavior, and understand why specific validation decisions occur.

## When to Use This Documentation

### For AI Code Quality Tools
These docs are optimized for automated analysis:
- Look up expected behavior for specific Zod methods
- Find edge cases that might reveal bugs
- Understand performance implications of API choices
- Verify error messages match specifications
- Check type inference accuracy

### For Zod Library Development
- Validate that implementation matches specification
- Identify discrepancies between code and documented behavior
- Catch behavioral regressions
- Test edge case handling

### For Zod Users
- Find exact behavioral semantics for confusing APIs
- Understand why validation behaves a certain way
- Learn about subtle distinctions (optional vs nullable vs nullish)
- Discover performance-relevant API choices

## File Structure

```
01_overview_and_introduction.md        Core concepts and philosophy
02_schema_types_and_validation.md      All schema types, validators, and constraints
03_schema_methods_and_transforms.md    Parsing, refinements, transforms, utilities
04_error_handling.md                   ZodError structure, codes, formatting
05_type_inference_and_typescript.md    Type extraction and TypeScript integration
06_advanced_patterns.md                Recursive schemas, lazy eval, composition
07_ecosystem_and_extensions.md         Framework integration and extensions
08_behavioral_contracts_and_edge_cases.md  Exact semantics, coercion, edge cases
INDEX.md                               Navigation guide and file summaries
README.md                              This file
```

See **INDEX.md** for detailed descriptions of each file and suggested navigation paths.

## Documentation Format

Each file uses a consistent format:

### Headings
- `## Topic` - Major sections covering a semantic area
- `### Subtopic` - Specific methods, patterns, or edge cases

### Content Style
- **Specification format**: Describes what happens, not why
- **Code examples**: Show behavior with inputs and outputs
- **Behavioral contracts**: Explicit rules (e.g., "default only applies when input is undefined")
- **Edge cases**: Documented with examples showing unexpected behavior
- **Cross-references**: Links to related sections for context

### Examples
Code examples show:
```typescript
// Input and method call
schema.method(args)

// Expected output or behavior
// result or error
```

For validation results:
```typescript
schema.parse(input)          // returns value or throws ZodError
schema.safeParse(input)      // returns { success: boolean; ... }
```

## Key Concepts

### Behavioral Contracts
Explicit rules for when and how validation applies. Examples:
- `.default()` only applies when input is **undefined**, not null or falsy values
- `.optional()` allows undefined; `.nullable()` allows null; `.nullish()` allows both
- Refinements run **after** base validations, not before
- Discriminated unions dispatch O(1), regular unions try all options O(n)

### Coercion Rules
How Zod converts types before validation:
- Coercion uses JavaScript constructors: `String()`, `Number()`, `Boolean()`, `new Date()`
- `z.coerce.boolean()` converts truthy/falsy, not string literals
- `z.coerce.number().parse("invalid")` returns `NaN` (not an error)

### Type Inference
How TypeScript types are extracted from schemas:
- `z.infer<typeof schema>` gets output type (after transforms)
- `z.input<typeof schema>` gets input type (before transforms)
- Branded types distinguish types with identical structure at compile time only

### Error Reporting
How validation errors are collected and reported:
- All errors collected in `error.issues` array
- Errors include `code`, `message`, `path`, and context
- Regular unions report errors from all failed options
- Discriminated unions report only from matching option

## Using This Documentation with AI Tools

### Finding Expected Behavior
1. Look up the method in the relevant file
2. Check the "Behavioral Contract" section for edge cases
3. Cross-reference with file **08_behavioral_contracts_and_edge_cases.md** for semantics

### Verifying Type Inference
1. Check **05_type_inference_and_typescript.md** for the pattern
2. Verify that `z.infer<>`, `z.input<>`, and `z.output<>` are used correctly
3. Look for transform-related type discrepancies

### Checking Error Handling
1. Consult **04_error_handling.md** for error structure
2. Verify error codes match expected codes for the validation
3. Check that error paths are correct for nested structures

### Finding Performance Issues
1. Check **02_schema_types_and_validation.md** and **06_advanced_patterns.md**
2. Look for O(n) unions where O(1) discriminated unions could apply
3. Check for schema recreation in hot paths (should be cached)

## Version Information

- **Zod Versions Covered**: v3.x (stable) through v4.x (current)
- **TypeScript Requirement**: v5.5+ with `"strict": true`
- **Last Updated**: 2026-04-12

## Notable Changes and Deprecations

### Zod v4
- **New**: Native JSON Schema generation via `.toJSONSchema()`
- **Deprecated**: External `zod-to-json-schema` library (use native method)
- **New**: `.meta()` method for OpenAPI and documentation metadata
- **Improved**: Type inference and branded types

### Potential Future Changes
- Watch GitHub issues for API stability notes
- Behavioral contracts in this documentation should be considered authoritative

## Sources and References

Documentation compiled from:
- Official Zod documentation (https://zod.dev)
- GitHub repository (https://github.com/colinhacks/zod)
- API reference (https://zod.dev/api)
- Ecosystem documentation (https://zod.dev/ecosystem)
- Community tools and integrations

## Integration Examples

### With AI Code Analysis
```typescript
// AI tool can use docs to verify expected behavior
const expectedBehavior = lookupInDocs("z.coerce.number()", "parsing", "NaN");
// Returns: "NaN is valid and passes through (not an error)"

const actualBehavior = z.coerce.number().safeParse("invalid");
// Verify: actualBehavior.data === NaN and actualBehavior.success === true
```

### With Type Checking
```typescript
// AI tool can verify type inference accuracy
const schema = z.string().transform((v) => parseInt(v));
const inferred = z.infer<typeof schema>;  // should be number

// From docs: transforms change output type
// Expected: inferred === number
// Verify in test
```

### With Testing
```typescript
// Use edge case specifications to generate test cases
// From docs: "default only applies when input is undefined"
const testCases = [
  { input: "value", expected: "value" },
  { input: undefined, expected: "default" },
  { input: null, expected: "error" },  // important edge case
  { input: "", expected: "" },         // empty string, not default
];
```

## How to Report Issues Using This Documentation

When identifying a potential Zod bug:

1. **Locate the specification**: Find the method in the docs and note the expected behavior
2. **Document the discrepancy**: Show input, expected output, actual output
3. **Reference the section**: Include which documentation file and section describes expected behavior
4. **Provide test case**: Create minimal reproduction case matching the documentation

Example:
```
Issue: z.coerce.number().parse("invalid") should return NaN, but throws error

Documentation Reference: 02_schema_types_and_validation.md, "Coercion Types"
and 08_behavioral_contracts_and_edge_cases.md, "Primitive Coercion"

Expected: z.coerce.number().parse("invalid") === NaN
Actual: ZodError thrown

Test case: [provided]
```

## Support and Maintenance

This documentation is maintained alongside the Zod library. As Zod evolves:
- New files may be added for major feature areas
- Existing files updated to reflect behavior changes
- Edge cases documented as they're discovered
- Performance characteristics noted as they change

For Zod-specific questions, consult the official repository and discussions.
