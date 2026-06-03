# Validation and Coercion: Strict vs Lax Mode

**Source:** https://pydantic.dev/docs/validation/latest/concepts/strict_mode/  
**Source:** https://pydantic.dev/docs/validation/latest/concepts/conversion_table/

## Strict vs Lax Mode: Core Concepts

Pydantic has two validation modes that determine how aggressively the library attempts to coerce input data to the correct type.

### Lax Mode (Default)

By default, Pydantic operates in **lax mode**, where it attempts to coerce values to the correct type whenever possible. This is useful for real-world scenarios:
- Query parameters from URLs (always strings)
- Environment variables (always strings)
- HTTP headers (always strings)
- Form data (often strings)
- API responses (often close but not exact types)

In lax mode, `'123'` converts to `123` (int), `'true'` converts to `True` (bool), etc.

### Strict Mode

In **strict mode**, Pydantic is much less lenient. It will error if data is not of the correct type, with limited exceptions:
- JSON data receives slightly more permissive handling (e.g., datetime fields accept ISO strings)
- Numeric types can still coerce between int and float
- Otherwise, only exact types are accepted

## Enabling Strict Mode

Strict mode can be enabled at three levels:

### 1. Per-Validation-Call

Enable for a single validation call:

```python
from pydantic import BaseModel, ValidationError

class User(BaseModel):
    age: int

# Lax mode (default)
user = User(age='30')  # Works: '30' coerces to 30

# Strict mode
try:
    user = User.model_validate({'age': '30'}, strict=True)
except ValidationError:
    pass  # Error: '30' not accepted as int in strict mode
```

### 2. Per-Field

Enable for specific fields:

```python
from pydantic import BaseModel, Field

class Config(BaseModel):
    port: int = Field(strict=True)  # Always strict
    timeout: int = 30               # Uses model default (lax)

Config(port='8080')    # Error: strict mode on port
Config(timeout='30')   # Works: lax mode for timeout
```

### 3. Model-Level

Enable for all fields:

```python
from pydantic import BaseModel, ConfigDict

class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True)
    name: str
    age: int

StrictModel(name='John', age='30')  # Error: strict mode for both
```

**Priority:** Field-level strict=True overrides model-level strict=False.

## Type Coercion Table

The following table shows which conversions are allowed in strict vs lax modes:

### Numeric Types

| From | To | Lax | Strict | Notes |
|------|----|----|--------|-------|
| `str` '123' | `int` | ✓ | ✗ | String must match digits pattern |
| `str` '123.45' | `int` | ✗ | ✗ | Decimals don't convert to int |
| `float` 1.0 | `int` | ✓ | ✗ | Floats only coerce if `.0` |
| `int` 123 | `float` | ✓ | ✓ | Integer always coerces to float |
| `str` '1.23' | `float` | ✓ | ✗ | String must match number pattern |
| `bool` True | `int` | ✓ | ✗ | True→1, False→0 in lax mode |

### Boolean Type

| From | To | Lax | Strict | Conversion |
|------|----|----|--------|------------|
| `int` 1 | `bool` | ✓ | ✗ | 1→True, 0→False |
| `int` 2 | `bool` | ✓ | ✗ | Non-zero→True (lax mode) |
| `float` 1.0 | `bool` | ✓ | ✗ | Similar to int |
| `str` 'true' | `bool` | ✓ | ✗ | Case-insensitive variations accepted |
| `str` 'false' | `bool` | ✓ | ✗ | Case-insensitive variations accepted |
| `str` '1' | `bool` | ✓ | ✗ | '1'→True, '0'→False |
| `str` 'yes' | `bool` | ✓ | ✗ | Yes/No accepted (case-insensitive) |
| `str` 'on' | `bool` | ✓ | ✗ | On/Off accepted (case-insensitive) |
| `str` '' | `bool` | ✓ | ✗ | Empty string→False |

### String Type

| From | To | Lax | Strict | Notes |
|------|----|----|--------|-------|
| `int` 123 | `str` | ✓ | ✗ | Converts via str() |
| `float` 1.23 | `str` | ✓ | ✗ | Converts via str() |
| `bool` True | `str` | ✓ | ✗ | True→'True' |
| `bytes` b'text' | `str` | ✓ | ✗ | Decodes as UTF-8 |
| `list` [1,2] | `str` | ✓ | ✗ | Converts via str() |

### Collection Types

| From | To | Lax | Strict | Notes |
|------|----|----|--------|-------|
| `tuple` | `list` | ✓ | ✓ | Tuple always converts |
| `set` | `list` | ✓ | ✓ | Set→list (order undefined) |
| `frozenset` | `list` | ✓ | ✓ | Frozenset→list |
| `deque` | `list` | ✓ | ✓ | Deque→list (maintains order) |
| `str` | `list` | ✓ | ✗ | Chars→list, e.g., 'abc'→['a','b','c'] |
| `Mapping` | `dict` | ✓ | ✓ | Generic Mapping types coerce |
| `str` '{"a":1}' | `dict` | ✓ | ✗ | JSON string parses to dict (lax only) |

### Date and Time Types

| From | To | Lax | Strict | Format |
|------|----|----|--------|--------|
| `str` '2024-01-15' | `date` | ✓ | ✓ | ISO format in both modes |
| `str` '2024-01-15T10:30:00' | `datetime` | ✓ | ✓ | ISO format in both modes |
| `int` 1705334400 | `datetime` | ✓ | ✗ | Unix timestamp (lax only) |
| `float` 1705334400.5 | `datetime` | ✓ | ✗ | Unix timestamp (lax only) |

### Special Types

| Type | Lax Conversions | Strict Conversions |
|------|-----------------|-------------------|
| `UUID` | Accept string hex/hyphens | Accept UUID objects, ISO strings |
| `Path` | Accept string paths | Accept Path objects, ISO strings |
| `IPv4Address` | Accept string IPs | Accept IPv4Address objects, strings |
| `IPv6Address` | Accept string IPs | Accept IPv6Address objects, strings |
| `Decimal` | Accept str, int, float | Accept Decimal, numeric strings |
| `Enum` | Accept value or name | Accept enum instance only |

## JSON-Specific Validation Behavior

JSON input has special handling even in strict mode:

```python
from pydantic import BaseModel
from datetime import datetime

class Event(BaseModel):
    name: str
    timestamp: datetime

# This works even with strict=True, because JSON parsing is special
event = Event.model_validate_json(
    '{"name": "launch", "timestamp": "2024-01-15T10:30:00Z"}',
    strict=True
)
```

**JSON allows:**
- Datetime fields accept ISO format strings
- Date fields accept ISO date strings
- Time fields accept ISO time strings
- Even in strict mode

**JSON doesn't allow:**
- `callable` types (no function representation)
- `InstanceOf` checks (not meaningful in JSON)
- Python-specific types with no JSON representation

## Validation Error Structure

When validation fails, Pydantic raises a `ValidationError`:

```python
from pydantic import BaseModel, ValidationError

class User(BaseModel):
    age: int

try:
    User(age='not-a-number')
except ValidationError as e:
    print(e.errors())
    # [{'type': 'int_parsing', 'loc': ('age',), 'msg': 'Input should be a valid integer', ...}]
```

### Error Details

Each error includes:
- `type` - Error type ('int_parsing', 'int_type', 'greater_than', etc.)
- `loc` - Location in data structure (tuple of keys/indices)
- `msg` - Human-readable error message
- `input` - The actual input value that failed
- `ctx` - Context info (constraints that failed, etc.)

### Common Error Types

| Error Type | Meaning | Example |
|-----------|---------|---------|
| `int_parsing` | String couldn't parse as int | '123abc' → int |
| `int_type` | Value not int in strict mode | '123' → int (strict) |
| `float_type` | Value not float in strict mode | '1.5' → float (strict) |
| `str_type` | Value not str in strict mode | 123 → str (strict) |
| `bool_type` | Value not bool in strict mode | 1 → bool (strict) |
| `string_too_short` | String shorter than min_length | min_length=5, got 'hi' |
| `string_too_long` | String longer than max_length | max_length=5, got 'hello world' |
| `string_pattern_mismatch` | Doesn't match regex pattern | pattern='[0-9]+', got 'abc' |
| `greater_than` | Value not > constraint | gt=0, got 0 |
| `less_than` | Value not < constraint | lt=10, got 10 |
| `list_type` | Value not list | 'not a list' → list |
| `dict_type` | Value not dict | 'not a dict' → dict |
| `union_tag_invalid` | Discriminator value invalid | Union[Cat, Dog], bad tag |

## Validation Behavior with None

```python
from typing import Optional

class Model(BaseModel):
    required: int           # None rejected
    optional: Optional[int]  # None accepted
    with_default: int = 0   # None rejected (has default ≠ optional)
```

**Key behavior:**
- `Optional[T]` = `T | None` - Accepts None
- `T` (without Optional) - Rejects None
- Default values don't make field optional; use Optional for that

## Custom Validation with @field_validator

```python
from pydantic import field_validator, BaseModel

class User(BaseModel):
    username: str

    @field_validator('username')
    @classmethod
    def username_valid(cls, v):
        if not v.isalnum():
            raise ValueError('must be alphanumeric')
        return v
```

When a validator raises `ValueError`, `AssertionError`, or `PydanticCustomError`, it's caught and included in ValidationError.

## Validation Behavior with Aliases

When using field aliases, validation uses the alias name:

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    user_id: int = Field(alias='userId')

# Must use alias in input
user = User(userId=123)  # Works
User(user_id=123)        # ValidationError: extra field
```

**Validation alias vs serialization alias:**
```python
class API(BaseModel):
    internal_name: str = Field(validation_alias='name', serialization_alias='display_name')

# Input uses validation_alias
api = API(name='value')

# Output uses serialization_alias
api.model_dump(by_alias=True)  # {'display_name': 'value'}
```
