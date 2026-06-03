# Pydantic V2 Documentation for AI Code Quality Tools

**Source:** https://pydantic.dev and https://github.com/pydantic/pydantic  
**Version:** Pydantic V2 (2.0+)  
**Last Updated:** April 2026

## Overview

This documentation collection provides reference material for understanding Pydantic V2's validation, serialization, and configuration behavior. It's designed for AI-driven code quality tools and bug detection systems that analyze Pydantic usage.

Rather than tutorial-style content, these files focus on **behavioral contracts**—the exact rules for:
- Type coercion in strict and lax modes
- Validator execution order and modes
- Serialization behavior and edge cases
- Model configuration and inheritance
- Error conditions and validation semantics

## Files in This Collection

1. **01_OVERVIEW_AND_ARCHITECTURE.md** - V2 architecture, pydantic-core, schema building
2. **02_MODEL_DEFINITION.md** - BaseModel, Field(), validators, model_config
3. **03_VALIDATION_AND_COERCION.md** - Strict vs lax mode, type coercion rules, validation errors
4. **04_SERIALIZATION.md** - model_dump, model_dump_json, custom serializers, computed fields
5. **05_TYPE_SYSTEM.md** - Annotated, discriminated unions, recursive models, generic models
6. **06_SETTINGS_MANAGEMENT.md** - BaseSettings, env vars, dotenv, secrets, custom sources
7. **07_JSON_SCHEMA.md** - Schema generation, customization, ref handling
8. **08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md** - Coercion tables, validator ordering, inheritance, private attributes, frozen models, equality, hashing

## Key Design Principles

Pydantic V2 separates concerns into two packages:
- **pydantic** (Python) - Model definition and configuration
- **pydantic-core** (Rust) - Validation and serialization logic

This architectural split provides 5-50x performance improvements over V1 at the cost of limited customization of internal validation logic.

## Using These Docs

For AI code quality analysis:
1. Refer to **03_VALIDATION_AND_COERCION.md** for expected type conversions
2. Check **02_MODEL_DEFINITION.md** for Field() and validator semantics
3. Use **08_BEHAVIORAL_CONTRACTS_AND_EDGE_CASES.md** for edge case behavior
4. Consult **04_SERIALIZATION.md** for serialization correctness
5. Review **05_TYPE_SYSTEM.md** for union and generic type handling

## Common Pitfalls

- Frozen models don't prevent mutation of contained mutable objects
- Private attributes are not copied in `__copy__` or `__deepcopy__`
- Validator execution order depends on mode ('before', 'after', 'wrap')
- Strict mode is more permissive with JSON input than Python input
- Model equality requires same type and private attribute values

## Official Resources

- **Main Documentation:** https://docs.pydantic.dev/
- **GitHub Repository:** https://github.com/pydantic/pydantic
- **Pydantic-Core:** https://github.com/pydantic/pydantic-core
