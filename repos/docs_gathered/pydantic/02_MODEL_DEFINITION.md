# Pydantic Model Definition

**Source:** https://docs.pydantic.dev/latest/concepts/models/  
**Source:** https://docs.pydantic.dev/latest/concepts/validators/

## BaseModel: Foundation of All Models

`BaseModel` is the core class for all Pydantic models. When you inherit from BaseModel:

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    id: int
    name: str
    email: str = "user@example.com"
```

Inheriting from BaseModel automatically provides:
- **Validation** - Type checking and coercion at instantiation
- **Serialization** - Methods to convert to dict/JSON
- **Schema Generation** - Automatic JSON schema creation
- **Introspection** - Reflection on model structure

## Field Definition and Constraints

### Basic Type Annotations

Fields are defined via class annotations. Type hints control validation behavior:

```python
class Product(BaseModel):
    name: str          # Required field, string type
    price: float       # Required field, float type
    quantity: int = 0  # Optional with default value
```

### Field() Function

The `Field()` function customizes individual field behavior:

```python
from pydantic import Field

class Item(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(gt=0, description="Price must be positive")
    quantity: int = Field(default=0, ge=0)
```

#### Common Field() Parameters

| Parameter | Type | Effect |
|-----------|------|--------|
| `default` | Any | Default value if not provided |
| `default_factory` | Callable | Function to create default value |
| `alias` | str | Alternative name for validation |
| `validation_alias` | str | Name used during validation only |
| `serialization_alias` | str | Name used during serialization only |
| `title` | str | Display title for documentation |
| `description` | str | Field description for JSON schema |
| `examples` | list | Example values for documentation |
| `min_length` | int | Minimum length for strings/collections |
| `max_length` | int | Maximum length for strings/collections |
| `pattern` | str | Regex pattern for strings |
| `gt` | number | Greater than constraint |
| `ge` | number | Greater than or equal constraint |
| `lt` | number | Less than constraint |
| `le` | number | Less than or equal constraint |
| `strict` | bool | Enable strict mode for this field only |
| `json_schema_extra` | dict/callable | Extra schema properties |

### Annotated Types

The `Annotated` pattern provides an alternative way to apply constraints:

```python
from typing import Annotated
from pydantic import Field

class Order(BaseModel):
    id: Annotated[int, Field(gt=0)]
    name: Annotated[str, Field(min_length=1)]
```

With Annotated, validators read right-to-left during execution.

## Field Types and Validation

### Standard Python Types

```python
class StandardTypes(BaseModel):
    flag: bool           # Boolean validation
    count: int           # Integer validation
    ratio: float         # Float validation
    name: str            # String validation
    items: list          # List validation
    mapping: dict        # Dict validation
    pair: tuple          # Tuple validation
```

### Optional and Union Types

```python
from typing import Optional, Union

class OptionalFields(BaseModel):
    middle_name: Optional[str] = None  # str or None
    id: str | None = None              # Python 3.10+ syntax
    value: Union[int, str]             # Can be int or str
```

### Pydantic Types

```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class SpecialTypes(BaseModel):
    user_id: UUID       # UUID validation and coercion
    created: datetime   # ISO format datetime
    data: bytes         # Byte string validation
```

## Validators: @field_validator and @model_validator

### @field_validator

Validates individual fields with custom logic:

```python
from pydantic import field_validator, BaseModel

class User(BaseModel):
    username: str
    age: int

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v):
        assert v.isalnum(), 'must be alphanumeric'
        return v

    @field_validator('age')
    @classmethod
    def age_positive(cls, v):
        assert v >= 0, 'must be positive'
        return v
```

#### @field_validator Modes

**mode='after'** (default) - Runs AFTER Pydantic's internal validation:
```python
@field_validator('age', mode='after')
@classmethod
def validate_age(cls, v):
    # v is guaranteed to be int (already validated)
    assert v >= 0, 'must be positive'
    return v
```

**mode='before'** - Runs BEFORE Pydantic's validation:
```python
@field_validator('age', mode='before')
@classmethod
def coerce_age(cls, v):
    # v could be any type
    if isinstance(v, str):
        return int(v)
    return v
```

**mode='wrap'** - Wraps Pydantic's validation:
```python
@field_validator('age', mode='wrap')
@classmethod
def validate_age(cls, v, handler):
    # Run custom logic before
    if isinstance(v, str):
        v = int(v)
    # Call standard validation
    result = handler(v)
    # Run custom logic after
    assert result >= 0
    return result
```

#### @field_validator Options

```python
@field_validator('name', mode='after', check_fields=False)
@classmethod
def validate_name(cls, v):
    return v.strip()
```

| Option | Effect |
|--------|--------|
| `mode` | 'before', 'after', or 'wrap' |
| `check_fields` | If False, skip validation if field missing |

### @model_validator

Validates entire model after or before all fields are processed:

```python
from pydantic import model_validator

class Coordinates(BaseModel):
    x: float
    y: float

    @model_validator(mode='after')
    def check_valid_position(self):
        # Runs after all field validators complete
        assert self.x != 0 or self.y != 0, 'cannot be at origin'
        return self
```

#### @model_validator Modes

**mode='after'** - Runs after all field validation:
```python
@model_validator(mode='after')
def multi_field_check(self):
    # All fields are already validated
    return self
```

**mode='before'** - Runs before field validation:
```python
@model_validator(mode='before')
@classmethod
def normalize_input(cls, data):
    # data is raw input dict
    if isinstance(data, dict):
        data['name'] = data.get('name', '').strip()
    return data
```

**mode='wrap'** - Wraps entire validation pipeline:
```python
@model_validator(mode='wrap')
@classmethod
def check_and_validate(cls, data, handler):
    # Custom logic before validation
    result = handler(data)
    # Custom logic after validation
    return result
```

## model_config: Global Configuration

The `model_config` dictionary controls model-wide behavior:

```python
from pydantic import BaseModel, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,      # Strip whitespace from strings
        str_to_lower=True,              # Convert strings to lowercase
        validate_default=True,          # Validate default values
        validate_assignment=True,       # Validate on attribute assignment
        extra='forbid',                 # Forbid extra fields
        frozen=True,                    # Make model immutable
        use_enum_values=True,           # Use enum values in serialization
    )
    name: str
```

### Configuration Options

| Option | Values | Effect |
|--------|--------|--------|
| `strict` | bool | Enable strict mode for all fields |
| `str_strip_whitespace` | bool | Strip leading/trailing whitespace from strings |
| `str_to_lower` | bool | Convert strings to lowercase |
| `str_to_upper` | bool | Convert strings to uppercase |
| `validate_default` | bool | Run validators on default values |
| `validate_assignment` | bool | Run validators when setting attributes |
| `extra` | 'allow', 'forbid', 'ignore' | How to handle extra fields |
| `frozen` | bool | Make model immutable (faux immutability) |
| `use_enum_values` | bool | Serialize enums as values (not names) |
| `arbitrary_types_allowed` | bool | Allow non-standard Python types |
| `from_attributes` | bool | Allow populating from object attributes |

### extra Field Handling

**extra='allow'** - Accept and store extra fields:
```python
class Model(BaseModel):
    model_config = ConfigDict(extra='allow')
    name: str

m = Model(name='John', age=30)
# m.__pydantic_extra__ == {'age': 30}
```

**extra='forbid'** - Raise ValidationError on extra fields:
```python
class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str

Model(name='John', age=30)  # ValidationError
```

**extra='ignore'** (default) - Silently ignore extra fields:
```python
class Model(BaseModel):
    model_config = ConfigDict(extra='ignore')
    name: str

m = Model(name='John', age=30)
# age is not stored anywhere
```

## Model Inheritance

Models inherit configuration and fields from parent classes:

```python
class Person(BaseModel):
    name: str
    age: int

class Employee(Person):
    employee_id: str
    salary: float

emp = Employee(name='John', age=30, employee_id='E001', salary=50000)
```

**Field Override:** Subclasses can override parent fields:
```python
class Base(BaseModel):
    name: str = Field(min_length=1)

class Derived(Base):
    name: str = Field(min_length=3)  # More restrictive
```

**Configuration Inheritance:** `model_config` values propagate to subclasses, with subclass values overriding parent values.

## Default and Computed Values

### Simple Defaults

```python
class Config(BaseModel):
    debug: bool = False
    timeout: int = 30
    retries: int = 3
```

### Default Factory

For mutable defaults, use `default_factory`:

```python
from pydantic import Field

class Data(BaseModel):
    items: list = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
```

### validate_default

By default, default values are not validated. Enable with:

```python
class Config(BaseModel):
    model_config = ConfigDict(validate_default=True)
    count: int = Field(ge=0)  # Default won't be validated without validate_default=True
```

## Private Attributes

Fields prefixed with underscore are not Pydantic fields:

```python
from pydantic import BaseModel, PrivateAttr

class Model(BaseModel):
    public_field: str
    _private_field: str  # Not validated, not in __init__

class ConfigWithPrivate(BaseModel):
    name: str
    _secret: str = PrivateAttr(default='')
    
    def model_post_init(self, __context):
        self._secret = 'initialized'
```

**Key behaviors:**
- Private attributes are not validated
- Not included in __init__ parameters
- Not serialized by default
- Cannot be used with Field()
- Set via `model_post_init()` or default_factory
- Accessed normally: `model._private`
