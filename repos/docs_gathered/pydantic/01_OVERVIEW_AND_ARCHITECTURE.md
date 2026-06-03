# Pydantic V2 Overview and Architecture

**Source:** https://docs.pydantic.dev/latest/internals/architecture/  
**Source:** https://github.com/pydantic/pydantic-core

## What is Pydantic V2?

Pydantic is a data validation and settings management library for Python using type annotations. It enforces type hints at runtime and provides user-friendly error messages.

### Major Shift from V1

The biggest change in Pydantic V2 is the architectural split:
- **pydantic** package (Python) - Model definition, configuration, and Python-level APIs
- **pydantic-core** package (Rust) - All validation and serialization logic compiled to native code

This architectural change provides 5-50x performance improvements over Pydantic V1.

## Two-Package Architecture

### The pydantic Package (Python)

Handles:
- Model class definition (BaseModel, BaseSettings)
- Field configuration and metadata (Field, Annotated)
- Validator decorators (@field_validator, @model_validator)
- User-facing APIs (model_validate, model_dump, etc.)
- JSON Schema generation
- Settings and configuration management

### The pydantic-core Package (Rust)

Implements:
- Core validation logic - processes Python objects, JSON, and strings
- Type coercion rules (strict vs lax mode)
- Serialization and deserialization
- Schema interpretation
- Error reporting

The Rust implementation is wrapped with Python bindings, making it seamless to use from Python code.

## Core Concept: Schema Building

Pydantic uses a **core schema** to communicate between packages:

```
BaseModel definition
    ↓
GenerateSchema class (Python)
    ↓
Core schema (Python dict)
    ↓
pydantic-core (Rust)
    ↓
Validation/Serialization result
```

A **core schema** is a structured Python dictionary describing specific validation and serialization logic. This is the fundamental data structure that bridges pydantic and pydantic-core.

### Schema Types

Only a fixed number of core schema types are supported by pydantic-core. Custom core schemas cannot be defined—they must be interpretable by the Rust implementation.

Supported schema types include:
- `model` - For BaseModel instances
- `typed-dict` - For TypedDict
- `dataclass` - For dataclass models
- `union` - For Union types
- `list` - For list types
- `dict` - For dict types
- `str`, `int`, `float`, `bool` - For basic types
- `is-instance` - For custom types with isinstance checks
- `callable` - For callable types
- `tuple` - For tuple types
- Custom validators applied via `general-before`, `general-after`, `general-wrap`

## Schema Generation

The `GenerateSchema` class is responsible for converting a model's type annotations into a core schema. It processes:

1. **Field types** - Analyzes each field's type annotation
2. **Validators** - Incorporates @field_validator and @model_validator decorators
3. **Constraints** - Applies Field() constraints (min_length, max_length, etc.)
4. **Serialization** - Configures serializers and computed fields
5. **Configuration** - Applies model_config settings

### Generation Location

All schema generation happens in a single place, with a single entry point. This centralization means:
- Consistent behavior across all model types
- Single source of truth for validation behavior
- Limited customization possibilities (by design)

## Validation Pipeline

When data is validated against a Pydantic model:

1. **Intake** - pydantic receives Python object, JSON string, or Python dict
2. **Schema Lookup** - Retrieves the precompiled core schema for the model
3. **Validation** - pydantic-core processes data through schema rules
4. **Coercion** - Type coercion applied based on strict/lax mode
5. **Custom Logic** - Field validators and model validators executed
6. **Serialization** - Result is prepared according to serialization rules
7. **Output** - Returns validated model instance or raises ValidationError

## Serialization Pipeline

When a model is serialized:

1. **Mode Selection** - Determines 'python' mode (default) or 'json' mode
2. **Schema Application** - Uses serialization schema from core schema
3. **Field Serializers** - Custom serializers applied per field
4. **Computed Fields** - Calculated values added to output
5. **Type Conversion** - Python types converted to JSON types (if json mode)
6. **Output Format** - Returns dict or JSON string

## Performance Characteristics

**Speed:** Pydantic V2 is significantly faster due to Rust implementation:
- Simple validations: 5-10x faster
- Complex nested structures: 20-50x faster
- JSON parsing: 10-30x faster

**Trade-off:** The Rust implementation limits customization. Custom core schemas are not possible; only the predefined schema types can be used.

## Constraints on Customization

Due to the pydantic-core architecture:

1. **Core Schemas** - Cannot create custom core schemas; only predefined types work
2. **Internal Logic** - Cannot override internal validation logic without resorting to wrapping validators
3. **Error Types** - Validation errors have fixed structure (cannot customize error format)

However, customization is still possible through:
- Field validators (mode='before', 'after', 'wrap')
- Model validators
- Field serializers
- Custom types with __get_pydantic_core_schema__

## Comparison with V1

| Aspect | V1 | V2 |
|--------|----|----|
| Architecture | Pure Python | Python + Rust (pydantic-core) |
| Performance | Baseline | 5-50x faster |
| Customization | Highly flexible | Limited (by design) |
| Error messages | String-based | Structured ValidationError |
| JSON Schema | Separate logic | Integrated with core schema |
| Validators | Multiple decorator styles | Standardized @field_validator, @model_validator |
| Type system | Partial typing | Full type annotations throughout |

## Key Design Decisions

**Separation of Concerns:** Model definition (pydantic) is distinct from validation logic (pydantic-core), allowing:
- Python-focused APIs for model creation
- Rust-focused performance for validation
- Clear responsibility boundaries

**Schema as Bridge:** Core schemas act as the contract between packages:
- Stable interface for two-language implementation
- Enables schema inspection and reflection
- Allows custom validators to hook into validation pipeline

**No Custom Core Schemas:** This limitation ensures:
- Bounded complexity in Rust implementation
- Guaranteed compatibility and predictability
- Clear performance characteristics
