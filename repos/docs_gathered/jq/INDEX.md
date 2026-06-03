# jq Documentation Index

Complete reference guide for the jq JSON processor — designed for AI code quality analysis and audit.

---

## Quick Navigation

### For Behavioral Contracts and Edge Cases
Start here: **[behavioral-contracts.md](behavioral-contracts.md)** — MUST/SHOULD requirements, known edge cases, type ordering, null propagation, number precision, error handling semantics.

### For Type System Details
**[type-system.md](type-system.md)** — Type categories, number representation, string encoding, array/object semantics, comparison rules, null handling, type coercion rules.

### For Operators and Filters
**[operators-and-filters.md](operators-and-filters.md)** — Identity, data access, pipe, comma, arithmetic, comparison, logical operators, conditionals, alternative operator, optional chaining, precedence.

### For Builtin Functions
**[builtin-functions.md](builtin-functions.md)** — Type introspection, array operations (sort, unique, flatten, min/max), object transformations (keys, to_entries, with_entries), string functions, path expressions, recursion (recurse, walk).

### For String Interpolation and Formatting
**[string-interpolation.md](string-interpolation.md)** — String interpolation syntax, tostring, format strings (@base64, @csv, @tsv, @html, @uri, @json, @text, @sh), tojson/fromjson.

### For Advanced Language Features
**[advanced-features.md](advanced-features.md)** — Function definitions (def), recursion with tail-call optimization, variable binding and scoping, reduce, foreach, label-break, $ENV, input/inputs, error handling, modules and imports.

### For Grammar and Syntax Details
**[filter-language.md](filter-language.md)** — Formal grammar (BNF), precedence and associativity, update operators (|=, +=, //=, etc.), try-catch, reduce/foreach expressions, object/array construction, pattern matching, recursion semantics.

### For Architecture and Implementation
**[architecture.md](architecture.md)** — Lexer (tokenization, string handling), parser (block IR, precedence), compiler (binding resolution, bytecode generation), VM (stack-based execution, generators), number literal preservation, TCO mechanics.

---

## Document Structure and Topics

### 1. architecture.md (280 lines)
- **Lexer**: Token classes, string handling, number token preservation
- **Parser**: Grammar structure, block representation, precedence rules
- **Compiler**: Binding resolution, bytecode generation, optimization techniques
- **VM**: Stack model, execution model, error propagation, generator protocol
- **Tail-Call Optimization**: Mechanics and limitations
- **Known Compiler/VM Behaviors**: Generator semantics, variable capture, recursion without TCO

### 2. type-system.md (320 lines)
- **Type Categories**: null, boolean, number, string, array, object, error
- **Number Representation**: IEEE754 double precision, literal form preservation, arithmetic coercion
- **String Encoding**: UTF-8, length semantics, escape sequences, string interpolation basics
- **Array Semantics**: Zero-based indexing, negative indices, out of bounds, null indexing
- **Object Semantics**: Hash table storage, key access, computed keys, merging
- **Comparison and Ordering**: Type ordering, equality semantics, relational operators, NaN handling
- **Type Coercion Rules**: No implicit coercion, explicit conversion functions
- **Null Semantics**: Null as value, propagation rules, null vs. empty distinction
- **Type Checking**: type function, type predicates (isnumber, isstring, etc.)
- **Edge Cases**: Infinity/NaN arithmetic, mixed-type collections, recursive comparison

### 3. operators-and-filters.md (300 lines)
- **Identity and Data Access**: . (identity), field access (.foo), array indexing/slicing, iterator (.[]`)
- **Pipe Operator (|)**: Chaining semantics, generator interaction, associativity
- **Comma Operator (,)**: Multiple output generation, comma vs. array construction
- **Arithmetic**: Addition (+), subtraction (-), multiplication (*), division (/), modulo (%)
- **Comparison**: Equality (==, !=), relational operators (<, >, <=, >=)
- **Logical**: and, or, not, truthiness rules
- **Alternative Operator (//)**: Default values, error handling limits
- **Conditional**: if-then-else syntax, truthiness in conditions, generators in branches
- **Optional Operator (?)**: Error suppression, empty conversion
- **Operator Precedence**: Complete precedence table with examples

### 4. builtin-functions.md (300 lines)
- **Type Introspection**: type, length, type predicates (isnumber, isstring, etc.)
- **Array Operations**: sort, sort_by, reverse, unique, unique_by, group_by, flatten, min/max, add
- **Array Search**: indices, contains, inside, index, rindex
- **String Functions**: split, join, ltrimstr, rtrimstr, ascii_upcase, ascii_downcase, startswith, endswith, explode, implode
- **Object/Array Transformation**: keys, keys_unsorted, values, to_entries, from_entries, with_entries
- **Filtering**: map, select
- **Path Expressions**: path, getpath, setpath, delpaths
- **Boolean Reduction**: any, all
- **Recursive Operations**: recurse, walk

### 5. string-interpolation.md (280 lines)
- **String Interpolation**: \(expr) syntax, nested parentheses, multiple interpolations
- **Expression Failures**: Error handling in interpolation
- **tostring**: Type-specific string conversion
- **Format Strings (@-syntax)**:
  - @text, @json, @html, @uri
  - @csv, @tsv (array-based)
  - @sh (shell escaping)
  - @base64, @base64d (encoding/decoding)
- **Format Functions**: Function equivalents and alternatives
- **String Building Patterns**: Array to string, conditional inclusion, iteration
- **Edge Cases**: Null in interpolation, empty generators, numeric precision, recursive interpolation, format errors
- **Performance**: String concatenation efficiency, interpolation overhead

### 6. advanced-features.md (300 lines)
- **Function Definitions**: def syntax, function scope, recursion (with/without arguments)
- **Recursion**: Mutual recursion using local definitions
- **Parameter Passing**: Value bindings ($x) vs. filter parameters
- **Variable Binding and Scoping**: as pattern, scope rules, lexical scoping, variable capture
- **reduce**: Accumulator semantics, variable scoping, examples (sum, count, grouping)
- **foreach**: Iterator with optional extraction, conditional emission
- **while and until**: Loop constructs, intermediate value generation
- **label and break**: Control flow, breaking out of loops
- **Environment Variables**: $ENV, env object
- **Input Functions**: input, inputs for reading multiple JSON values
- **Error Handling**: error function, debug function
- **Modules and Imports**: import, include, qualified names, module definition
- **Advanced Functions**: limit, first, recurse with conditions
- **Variable Capture**: Closure semantics in nested definitions
- **Known Behaviors**: TCO limitations, recursive definitions with arguments, module caching

### 7. filter-language.md (320 lines)
- **Grammar Overview**: Expression categories, precedence and associativity
- **Formal Grammar**: Simplified BNF notation for complete language
- **Update and Assignment Operators**: |=, //=, +=, -=, *=, /=, %=
- **Update Semantics**: Path modification, null propagation, multiple paths
- **try-catch**: Expression syntax, error message passing, optional shorthand
- **reduce**: GENERATOR as VAR pattern, accumulator updates, examples
- **foreach**: Stateful iteration with optional extraction
- **Object Construction**: Static keys, computed keys, shorthand notation
- **Array Construction**: Collection semantics, generator interaction
- **Variable Binding**: as pattern, scoping rules, pattern matching (if available)
- **Recursion**: Tail position, TCO limitations, function parameters
- **Pipe Operator**: Chaining, generator interaction, associativity
- **Comma Operator**: Multiple output generation, precedence

### 8. behavioral-contracts.md (420 lines)
- **Type System MUST Requirements**: Coercion rules, comparison semantics, sort stability
- **Null Handling**: Propagation rules, null as value, null in collections
- **Number Representation**: IEEE754 representation, literal form preservation, precision, overflow
- **String Handling**: UTF-8 encoding, operations, interpolation
- **Array Operations**: Indexing (including out-of-bounds), slicing, iteration
- **Object Operations**: Key access, key types, merging semantics
- **Error Handling**: try-catch semantics, optional operator, error propagation
- **Generator and Multiplicity**: Multiple outputs, array collection, lazy evaluation
- **Conditional and Boolean**: Truthiness, short-circuiting, not operator
- **Update Expressions**: Path modification, null propagation in updates
- **reduce and foreach**: Variable scope, emit behavior, accumulator semantics
- **Path Expressions**: path function, getpath/setpath/delpaths behavior
- **Recursion and TCO**: TCO optimization rules, recursion limits
- **Implementation Divergences**: Number division, sorting, error messages, module system
- **Edge Cases**: Object iteration order, recursive structures, unicode, empty values

---

## How to Use This Documentation

### For Debugging a Specific Behavior
1. Identify the operator/function involved
2. Look up the specific page (use index above)
3. Check **behavioral-contracts.md** for MUST/SHOULD requirements
4. Review examples and edge cases

### For Understanding a jq Filter
1. Parse filter into components (operators, functions, control flow)
2. Consult **operators-and-filters.md** for operator semantics
3. Consult **filter-language.md** for grammar and composition rules
4. Consult **advanced-features.md** if filter uses def, reduce, foreach, etc.

### For Code Quality Auditing
1. Start with **behavioral-contracts.md** — identifies what MUST be true
2. Check against **type-system.md** for precise type handling
3. Verify error handling against **behavioral-contracts.md** and **operators-and-filters.md**
4. Check null propagation rules in **behavioral-contracts.md** section 2

### For Implementation Details
1. **architecture.md** explains lexer, parser, compiler, VM pipeline
2. **advanced-features.md** explains function definitions, recursion, variable binding
3. **filter-language.md** provides formal grammar and operator precedence

---

## Cross-References by Topic

### Null Handling
- type-system.md: Section 8 (Null Semantics)
- operators-and-filters.md: Various operators handle null
- behavioral-contracts.md: Section 2 (Null Handling — MUST/SHOULD)

### Number Precision
- type-system.md: Section 2 (Number Representation)
- behavioral-contracts.md: Section 3 (Number Representation)
- architecture.md: Section 5 (Value Representation) and Section 8

### String Operations
- type-system.md: Section 3 (String Representation)
- builtin-functions.md: Section 3 (String Functions)
- string-interpolation.md: Complete guide

### Error Handling
- operators-and-filters.md: Section 8 (Optional Operator)
- advanced-features.md: Section 6 (Error Handling)
- behavioral-contracts.md: Section 7 (Error Handling)

### Function Definitions and Recursion
- advanced-features.md: Sections 1-4 (Definitions, Recursion, Variable Binding)
- architecture.md: Section 7 (Tail-Call Optimization)
- behavioral-contracts.md: Section 13 (Recursion and TCO)
- filter-language.md: Section 11 (Recursion and tail-call Optimization)

### Generators and Multiple Outputs
- operators-and-filters.md: Section 3 (Comma Operator)
- architecture.md: Section 6 (Generator Protocol in VM)
- behavioral-contracts.md: Section 8 (Generator and Multiplicity)
- filter-language.md: Various sections on comma, reduce, foreach

### Type Coercion and Comparison
- type-system.md: Sections 6-7 (Comparison, Type Coercion)
- operators-and-filters.md: Section 5 (Comparison Operators)
- behavioral-contracts.md: Sections 1, 3 (Type and Number)

---

## Version Coverage

All documents cover **jq 1.8** with notes on version-specific behaviors where they differ from earlier versions (1.5, 1.6, 1.7).

---

## External References

- **Official jq Manual**: https://jqlang.org/manual/
- **GitHub Repository**: https://github.com/jqlang/jq
- **GitHub Issues**: https://github.com/jqlang/jq/issues (for behavior clarifications)
- **GitHub Wiki (Advanced Topics)**: https://github.com/jqlang/jq/wiki
- **GitHub Wiki (Internals)**: https://github.com/jqlang/jq/wiki/Internals:-the-compiler

---

## Document Statistics

| Document | Lines | Focus |
|----------|-------|-------|
| README.md | 40 | Overview and purpose |
| INDEX.md | This file | Navigation and structure |
| architecture.md | 280 | Implementation: lexer, parser, compiler, VM |
| type-system.md | 320 | Type categories, representation, comparison |
| operators-and-filters.md | 300 | Operators and basic filters |
| builtin-functions.md | 300 | Builtin functions and operations |
| string-interpolation.md | 280 | String handling and formatting |
| advanced-features.md | 300 | def, recursion, reduce, modules |
| filter-language.md | 320 | Grammar, syntax, update expressions |
| behavioral-contracts.md | 420 | MUST/SHOULD behaviors, edge cases |
| **Total** | **2540** | Complete jq reference |

---

## Last Updated

2026-04-12 — Covers jq 1.8 from jqlang/jq main branch
