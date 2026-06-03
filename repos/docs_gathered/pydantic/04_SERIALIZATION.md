# Serialization: Dumping, Serializers, and Computed Fields

**Source:** https://docs.pydantic.dev/latest/concepts/serialization/

## Serialization Overview

Serialization converts Pydantic models to Python dicts or JSON strings. Pydantic distinguishes between:

- **Python mode** - Converts to dicts preserving Python types (datetime objects, UUID objects, etc.)
- **JSON mode** - Converts to JSON-compatible dicts/strings (datetimes as ISO strings, UUIDs as strings)

## model_dump(): Convert to Dictionary

`model_dump()` converts a model instance to a Python dictionary:

```python
from pydantic import BaseModel
from datetime import datetime

class Event(BaseModel):
    name: str
    timestamp: datetime

event = Event(name='launch', timestamp=datetime(2024, 1, 15, 10, 30))
result = event.model_dump()
# {'name': 'launch', 'timestamp': datetime.datetime(2024, 1, 15, 10, 30)}
```

### model_dump() Parameters

```python
model.model_dump(
    mode='python',           # 'python' or 'json'
    include=None,            # Fields to include (set, dict, or callable)
    exclude=None,            # Fields to exclude (set, dict, or callable)
    context=None,            # Context dict passed to serializers
    by_alias=False,          # Use field aliases from Field(alias=...)
    exclude_unset=False,     # Exclude fields not explicitly set
    exclude_defaults=False,  # Exclude fields with default values
    exclude_none=False,      # Exclude None values
    round_trip=False,        # Ensure data can be re-parsed
    warnings='none',         # Control serialization warnings
)
```

#### Practical Examples

```python
class User(BaseModel):
    name: str
    email: str = "default@example.com"
    admin: bool = False

user = User(name='John')

# Include only certain fields
user.model_dump(include={'name'})
# {'name': 'John'}

# Exclude fields
user.model_dump(exclude={'email'})
# {'name': 'John', 'admin': False}

# Exclude unset fields (email not explicitly set)
user.model_dump(exclude_unset=True)
# {'name': 'John'}

# Exclude defaults
user.model_dump(exclude_defaults=True)
# {'name': 'John'}

# Exclude None values
user.model_dump(exclude_none=True)
```

### include/exclude with Nested Models

For nested structures, use dict to control nesting:

```python
from pydantic import BaseModel

class Address(BaseModel):
    street: str
    city: str

class User(BaseModel):
    name: str
    address: Address

user = User(name='John', address=Address(street='Main St', city='NYC'))

# Include nested field
user.model_dump(include={'name': True, 'address': {'city'}})
# {'name': 'John', 'address': {'city': 'NYC'}}

# Include with callable
user.model_dump(include=lambda f: f.startswith('a'))
```

### by_alias Parameter

Use field aliases in output:

```python
from pydantic import BaseModel, Field

class API(BaseModel):
    user_id: int = Field(alias='userId')
    user_name: str = Field(alias='userName')

api = API(userId=123, userName='John')
api.model_dump()           # {'user_id': 123, 'user_name': 'John'}
api.model_dump(by_alias=True)  # {'userId': 123, 'userName': 'John'}
```

## model_dump_json(): Convert to JSON String

`model_dump_json()` serializes directly to JSON string:

```python
from pydantic import BaseModel
from datetime import datetime

class Event(BaseModel):
    name: str
    timestamp: datetime

event = Event(name='launch', timestamp=datetime(2024, 1, 15, 10, 30))
json_str = event.model_dump_json()
# '{"name":"launch","timestamp":"2024-01-15T10:30:00"}'
```

### model_dump_json() Parameters

```python
model.model_dump_json(
    indent=None,             # Indentation level (None for compact)
    include=None,            # Same as model_dump()
    exclude=None,            # Same as model_dump()
    context=None,            # Context dict passed to serializers
    by_alias=False,          # Use field aliases
    exclude_unset=False,     # Same as model_dump()
    exclude_defaults=False,  # Same as model_dump()
    exclude_none=False,      # Same as model_dump()
    round_trip=False,        # Ensure data can be re-parsed
    warnings='none',         # Control serialization warnings
)
```

### Examples

```python
model.model_dump_json()                    # Compact JSON
model.model_dump_json(indent=2)            # Pretty-printed JSON
model.model_dump_json(by_alias=True)       # Use field aliases
model.model_dump_json(exclude={'password'})  # Exclude sensitive fields
```

## Custom Serializers: @field_serializer

`@field_serializer` customizes how individual fields are serialized:

```python
from pydantic import BaseModel, field_serializer
from datetime import datetime

class Event(BaseModel):
    name: str
    timestamp: datetime

    @field_serializer('timestamp')
    def serialize_timestamp(self, value: datetime):
        return value.isoformat() + 'Z'

event = Event(name='launch', timestamp=datetime(2024, 1, 15, 10, 30))
event.model_dump()
# {'name': 'launch', 'timestamp': '2024-01-15T10:30:00Z'}
```

### Serializer Modes

**Plain Serializer** (default) - Bypasses Pydantic's default logic:

```python
@field_serializer('price', mode='plain')
def serialize_price(self, value):
    # value is the raw field value
    return f'${value:.2f}'
```

**Wrap Serializer** - Wraps Pydantic's logic:

```python
@field_serializer('price', mode='wrap')
def serialize_price(self, value, handler, info):
    # Get Pydantic's default serialization
    serialized = handler(value)
    # Post-process
    return f'${serialized:.2f}'
```

### Serializer Parameters

```python
@field_serializer(
    'field1', 'field2',      # Target fields
    mode='plain',             # 'plain' or 'wrap'
    when_used='json',         # 'json' or 'unless-none' or 'always'
)
def serialize_field(self, value):
    return value
```

| when_used | Meaning |
|-----------|---------|
| 'always' | Always apply serializer |
| 'json' | Only when mode='json' in model_dump |
| 'unless-none' | Apply unless value is None |

### Wrap Serializer Signature

Wrap serializers receive three parameters:

```python
@field_serializer('field', mode='wrap')
def serialize_field(self, value, handler, info):
    # value: the field value
    # handler: callable that runs standard serialization
    # info: SerializationInfo with context
    return handler(value)
```

**SerializationInfo attributes:**
- `context` - The context dict passed to model_dump()
- `field_name` - Name of the field being serialized
- `mode` - 'python' or 'json'

## Model-Level Serializers: @model_serializer

Apply custom serialization logic to the entire model:

```python
from pydantic import BaseModel, model_serializer

class User(BaseModel):
    name: str
    email: str

    @model_serializer(mode='wrap')
    def serialize_model(self, handler, info):
        data = handler(self)
        # Modify entire output
        data['full_data'] = True
        return data
```

**mode='wrap'** vs **mode='plain':**
- **mode='wrap'**: Get Pydantic's serialization, then modify
- **mode='plain'**: Complete custom serialization (must return dict)

## Computed Fields

Computed fields are calculated properties included in serialization:

```python
from pydantic import BaseModel, computed_field

class Rectangle(BaseModel):
    width: float
    height: float

    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height

rect = Rectangle(width=3, height=4)
rect.model_dump()
# {'width': 3, 'height': 4, 'area': 12.0}
```

### Computed Field Control

```python
from pydantic import computed_field

class Model(BaseModel):
    value: int

    @computed_field
    @property
    def double(self) -> int:
        return self.value * 2
```

**Computed fields:**
- Are included in serialization
- Are NOT included in validation (read-only)
- Can use @property or regular methods
- Can access other fields
- Support custom serialization via mode parameter

### Computed Field with Serialization Control

```python
@computed_field(mode='plain')
@property
def formatted(self) -> str:
    # mode='plain' bypasses Pydantic's serialization
    return f'Value: {self.value}'
```

## Serialization Context

Pass context to serializers:

```python
from pydantic import BaseModel, field_serializer

class User(BaseModel):
    name: str
    password: str

    @field_serializer('password')
    def serialize_password(self, value, _info):
        if _info.context.get('include_secrets'):
            return value
        return '***'

user = User(name='John', password='secret')
user.model_dump()  # {'name': 'John', 'password': '***'}
user.model_dump(context={'include_secrets': True})
# {'name': 'John', 'password': 'secret'}
```

## Serialization Mode: JSON vs Python

### Python Mode (Default)

Preserves Python types:

```python
from datetime import datetime
from uuid import UUID

class Data(BaseModel):
    timestamp: datetime
    id: UUID

data = Data(timestamp=datetime.now(), id=UUID('12345678-1234-5678-1234-567812345678'))

# Python mode
data.model_dump(mode='python')
# Returns with datetime and UUID objects intact

# JSON mode
data.model_dump(mode='json')
# {'timestamp': '2024-01-15T10:30:00.123456', 'id': '12345678-1234-5678-1234-567812345678'}
```

## Serialization Errors

If a field cannot be serialized to JSON, `PydanticSerializationError` is raised:

```python
from pydantic import BaseModel

class BadModel(BaseModel):
    func: callable  # Functions can't be serialized to JSON

model = BadModel(func=lambda x: x)
try:
    model.model_dump_json()
except PydanticSerializationError:
    pass  # Callable cannot be serialized
```

## round_trip Parameter

Use `round_trip=True` to ensure serialized data can be re-parsed:

```python
model = MyModel(...)
serialized = model.model_dump(round_trip=True)
re_parsed = MyModel(**serialized)  # Should work
```

This ensures:
- All information needed for re-validation is preserved
- Dataclass models use dataclass serialization format
- Custom types use formats compatible with validation
