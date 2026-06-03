# Pydantic V2 Documentation Index

**Complete Reference for AI Code Quality Analysis**

This index provides quick navigation to all documentation on Pydantic V2's validation, serialization, type system, and behavioral contracts.

## File Listing

### 01_OVERVIEW_AND_ARCHITECTURE.md
**Core Concepts**
- What is Pydantic V2 and why it changed from V1
- Two-package architecture (pydantic + pydantic-core)
- Core schema as the bridge between Python and Rust
- Schema generation process
- Validation and serialization pipelines
- Performance characteristics
- Customization constraints
- Key design decisions

**For AI Analysis:** Start here to understand that Pydantic separates model definition (Python) from validation logic (Rust), which limits certain types of customization.

### 02_MODEL_DEFINITION.md
**Building Pydantic Models**
- BaseModel: The foundation class
- Field() function and parameters
- Annotated types for reusable constraints
- Field types and validation
- @field_validator decorator (before/after/wrap modes)
- @model_validator decorator
- model_config and ConfigDict options
- Model inheritance
- Default and computed values
- Private attributes

**For AI Analysis:** This covers the complete model definition API. Key behavioral items: field override in inheritance, private attribute non-validation, and validator mode semantics.

### 03_VALIDATION_AND_COERCION.md
**Validation Behavior and Type Coercion**
- Strict vs lax mode overview
- How to enable strict mode (per-call, per-field, model-level)
- Complete coercion table for all types
- Numeric type conversions (str→int, float→int, etc.)
- Boolean type conversions
- String conversions
- Collection type conversions
- Date/time type conversions
- Special type conversions (UUID, Path, IP addresses)
- JSON-specific validation rules
- ValidationError structure and error types
- None handling and Optional
- Custom validation with @field_validator
- Alias behavior during validation

**For AI Analysis:** This is the behavioral contract for type coercion. The coercion tables are essential for understanding what conversions will succeed in strict vs lax modes.

### 04_SERIALIZATION.md
**Converting Models to Dicts and JSON**
- model_dump() and parameters
- model_dump_json() and parameters
- Include/exclude with nested models
- by_alias parameter
- Custom serializers with @field_serializer
- Plain vs wrap serializer modes
- Model-level serializers with @model_serializer
- Computed fields
- Serialization context passing
- Python mode vs JSON mode
- Serialization errors
- round_trip parameter

**For AI Analysis:** Covers all serialization behavior. Important: private attributes are NOT serialized; frozen models still have mutable nested objects; computed fields are read-only.

### 05_TYPE_SYSTEM.md
**Advanced Type Handling**
- Annotated types and metadata
- Union types and validation order
- Discriminated (tagged) unions
- How discriminators optimize validation
- Recursive and self-referential models
- Generic models with type parameters
- Literal types
- Enum types
- Container types (List, Set, Dict, Tuple)
- ClassVar behavior
- Union with Literal patterns

**For AI Analysis:** Critical for understanding polymorphic APIs. Discriminated unions are special—they only validate against the matched member type, not all union members.

### 06_SETTINGS_MANAGEMENT.md
**Configuration Management with BaseSettings**
- BaseSettings overview
- Environment variables (case sensitivity, prefixes)
- Dotenv files and multiple file support
- Secrets directories
- File precedence (args > env > secrets > dotenv > defaults)
- Custom sources and settings_customise_sources
- Complex types in environment variables
- SettingsConfigDict options
- Validation with BaseSettings
- Reloading settings

**For AI Analysis:** Settings are immutable by default; environment variable names are uppercased by default; file precedence is important for configuration resolution.

### 07_JSON_SCHEMA.md
**Automatic Schema Generation**
- model_json_schema() for schema generation
- Field-level customization (title, description, examples)
- json_schema_extra with dict and callable
- Model-level customization
- WithJsonSchema and SkipJsonSchema annotations
- Reference ($ref) handling and customization
- Custom GenerateJsonSchema subclass
- Validation vs serialization schema modes
- Computed fields in schemas
- TypeAdapter for non-model types
- Union and discriminated union schemas
- Constraints in schema generation

**For AI Analysis:** Schema generation is deterministic and reflects all validation constraints. Discriminated unions generate optimized schemas.

### 08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md
**Critical Behavioral Rules and Edge Cases**
- Validator execution order (before/after/wrap modes)
- Execution order within single field
- Execution order across fields
- Annotated validator ordering (right-to-left)
- Type coercion determinism
- Private attribute behavior (non-validation, non-serialization, non-copying)
- Frozen model limitations (faux immutability, mutable nested objects)
- Frozen models and hashing
- Model equality semantics (same type, not equal to dicts)
- Model inheritance edge cases
- Validate default values behavior
- Validate assignment behavior
- Arbitrary types handling
- Union validation modes (smart_mode vs left_to_right)
- Circular/recursive model gotchas
- from_attributes behavior
- Extra fields handling
- Alias behavior in validation vs serialization
- JSON input special rules

**For AI Analysis:** This file contains the "gotchas" and edge cases that trip up both developers and AI systems. Critical items: private attributes aren't copied, frozen models aren't truly immutable, validator execution order depends on mode.

## Navigation by Use Case

### For Validation Bug Detection
1. Start: **03_VALIDATION_AND_COERCION.md** (coercion table and error types)
2. Then: **02_MODEL_DEFINITION.md** (validator behavior)
3. Finally: **08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md** (execution order edge cases)

### For Serialization Issues
1. Start: **04_SERIALIZATION.md** (serialization methods)
2. Then: **02_MODEL_DEFINITION.md** (computed fields)
3. Finally: **08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md** (private attribute non-serialization)

### For Type System Problems
1. Start: **05_TYPE_SYSTEM.md** (union, generic, discriminator)
2. Then: **03_VALIDATION_AND_COERCION.md** (type coercion)
3. Finally: **08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md** (union modes, recursive models)

### For Configuration/Settings Issues
1. Start: **06_SETTINGS_MANAGEMENT.md** (environment and file handling)
2. Then: **03_VALIDATION_AND_COERCION.md** (validation of settings)

### For Schema Generation Issues
1. Start: **07_JSON_SCHEMA.md** (schema generation)
2. Then: **02_MODEL_DEFINITION.md** (field constraints)
3. Finally: **01_OVERVIEW_AND_ARCHITECTURE.md** (schema building concept)

### For Model Design Issues
1. Start: **02_MODEL_DEFINITION.md** (model structure)
2. Then: **08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md** (inheritance, private attributes, equality)

## Key Concepts Quick Reference

### Strict vs Lax Mode
- **Lax (default):** Attempts type coercion (e.g., '123' → 123)
- **Strict:** Minimal coercion; mostly rejects wrong types
- **Enabled:** `model_validate(..., strict=True)`, `Field(strict=True)`, or `ConfigDict(strict=True)`
- **Full table:** See 03_VALIDATION_AND_COERCION.md

### Validator Modes
- **mode='before':** Runs before type coercion; handles raw input
- **mode='after':** Runs after type coercion; value type guaranteed
- **mode='wrap':** Wraps entire validation; can call handler
- **Execution:** Before/wrap right-to-left; After left-to-right

### Field Aliases
- **validation_alias:** Name used during input validation
- **serialization_alias:** Name used in model_dump output
- **alias:** Shorthand for both (deprecated in favor of separate)

### Extra Fields
- **allow:** Extra fields stored in __pydantic_extra__
- **forbid:** Extra fields raise ValidationError
- **ignore:** Extra fields silently discarded (default)

### Private Attributes (_field)
- NOT validated during initialization
- NOT included in serialization
- NOT copied in __copy__/__deepcopy__
- Set via model_post_init() or default_factory
- Access via normal attribute syntax (model._field)

### Frozen Models
- **NOT true immutability:** Mutable nested objects can still change
- **Can't reassign fields:** m.name = 'new' raises ValidationError
- **Can be deleted:** del m.name works despite frozen=True
- **Can be hashed:** If all fields are hashable

### Model Equality
- Models only equal to other BaseModel instances
- NOT equal to dicts with same data
- Type must match exactly
- Private attributes must match
- Inheritance doesn't create separate types

## Important Warnings

**Private Attributes:** Are lost in copy operations. This is a design limitation, not a bug.

**Frozen Models:** Don't prevent mutation of nested mutable objects (lists, dicts). Use a truly immutable approach if needed.

**Validator Order:** Depends on mode. 'before' mode executes in reverse declaration order; 'after' in forward order. This trips up many developers.

**Serialization Errors:** Certain types (callables) cannot be serialized to JSON and will raise PydanticSerializationError.

**Circular References:** Recursive models can serialize infinitely if there are cycles in the data. Need to break cycles before serialization.

**Union Validation:** By default uses smart_mode, which tries to find the best match. Order matters with left_to_right mode.

**JSON Input:** Has special rules for dates and times even in strict mode (ISO strings always accepted).

## File Statistics

- **01_OVERVIEW_AND_ARCHITECTURE.md** - ~280 lines
- **02_MODEL_DEFINITION.md** - ~320 lines
- **03_VALIDATION_AND_COERCION.md** - ~350 lines
- **04_SERIALIZATION.md** - ~280 lines
- **05_TYPE_SYSTEM.md** - ~310 lines
- **06_SETTINGS_MANAGEMENT.md** - ~310 lines
- **07_JSON_SCHEMA.md** - ~280 lines
- **08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md** - ~380 lines
- **Total:** ~2,500 lines of focused documentation

## Sources

All documentation is derived from:
- Official Pydantic documentation: https://docs.pydantic.dev/
- Pydantic GitHub repository: https://github.com/pydantic/pydantic
- Pydantic-core repository: https://github.com/pydantic/pydantic-core
- GitHub issues and discussions documenting edge cases
