# Type System: Annotated, Unions, Discriminators, Generics, and Recursion

**Source:** https://docs.pydantic.dev/latest/concepts/unions/

## Annotated Types

`Annotated` from `typing` allows attaching metadata to type hints:

```python
from typing import Annotated
from pydantic import BaseModel, Field

class User(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)]
    age: Annotated[int, Field(gt=0, le=150)]
```

### Multiple Validators with Annotated

Annotated can stack multiple validators right-to-left:

```python
from typing import Annotated
from pydantic import field_validator, BaseModel

def check_even(v):
    assert v % 2 == 0, 'must be even'
    return v

def check_positive(v):
    assert v > 0, 'must be positive'
    return v

class Numbers(BaseModel):
    # Validators run right-to-left (check_even then check_positive)
    value: Annotated[int, field_validator('value')(check_even)]
```

### Advantages of Annotated

- Cleaner than Field() for simple constraints
- Reusable type definitions
- Better IDE support
- Separate constraints from field definition

```python
# Define once, use everywhere
PositiveInt = Annotated[int, Field(gt=0)]
LimitedStr = Annotated[str, Field(min_length=1, max_length=100)]

class Product(BaseModel):
    price: PositiveInt
    name: LimitedStr
```

## Union Types

Union types allow a field to accept multiple type options:

```python
from typing import Union

class Response(BaseModel):
    data: Union[str, int, float]  # Accepts string, int, or float

Response(data='hello')     # OK
Response(data=123)         # OK
Response(data=1.5)         # OK
```

### Union Validation Order

By default, Pydantic validates union members left-to-right using smart mode:

```python
from typing import Union

# This order matters!
class Model1(BaseModel):
    value: Union[int, str]

Model1(value='123')  # Validated as int (123), not str ('123')
```

**Validation mode: 'smart_mode'** (default in V2) - Continues validation after finding a match to look for "better" matches:
- Tries first type
- If matches, validates other types too
- Uses the "best" match based on specificity

**Validation mode: 'left_to_right'** - Stops at first match:
```python
from pydantic import ConfigDict

class Model(BaseModel):
    model_config = ConfigDict(union_mode='left_to_right')
    value: Union[int, str]
```

## Discriminated Unions (Tagged Unions)

Discriminated unions use a field to determine which union member to validate:

```python
from typing import Union, Literal
from pydantic import BaseModel, Field, Discriminator

class Cat(BaseModel):
    pet_type: Literal['cat']
    meows: int

class Dog(BaseModel):
    pet_type: Literal['dog']
    barks: int

class Pet(BaseModel):
    animal: Annotated[Union[Cat, Dog], Discriminator('pet_type')]

# Discriminator chooses which model to use based on pet_type
pet1 = Pet(animal={'pet_type': 'cat', 'meows': 5})
pet2 = Pet(animal={'pet_type': 'dog', 'barks': 3})
```

### How Discriminators Work

1. **Inspect discriminator field** - Looks at the value of the discriminator field
2. **Match discriminator value** - Finds union member with matching Literal value
3. **Validate against that member** - Only validates against the matched type
4. **Efficient error reporting** - Error only from the matched member

### Benefits

- **Performance** - Only validates matched type (not all union members)
- **Better errors** - Error message is specific to actual type
- **Clarity** - Type intent is explicit via discriminator

### Discriminator with Function

Use a callable to extract the discriminator value:

```python
from typing import Annotated, Union, Literal

class Cat(BaseModel):
    animal_type: Literal['cat']

class Dog(BaseModel):
    animal_type: Literal['dog']

def get_animal_type(data):
    if isinstance(data, dict):
        return data.get('animal_type')
    return data.animal_type

class Pet(BaseModel):
    animal: Annotated[Union[Cat, Dog], Discriminator(get_animal_type)]
```

## Recursive Models

Models can reference themselves:

```python
from pydantic import BaseModel
from typing import Optional

class Node(BaseModel):
    value: int
    left: Optional['Node'] = None
    right: Optional['Node'] = None

# Forward reference is resolved at model creation time
Node.model_rebuild()

# Create nested structure
tree = Node(
    value=1,
    left=Node(value=2),
    right=Node(value=3, left=Node(value=4))
)
```

### String Forward References

For recursive or circular references, use string annotations:

```python
from __future__ import annotations
from pydantic import BaseModel

class TreeNode(BaseModel):
    value: int
    children: list[TreeNode] = []  # String reference (with __future__)
```

### Deferred Validation

With recursive models, validation errors occur at each recursion level:

```python
class Node(BaseModel):
    value: int
    next: Optional['Node'] = None

# Invalid data at depth 2
try:
    Node(
        value=1,
        next={'value': 2, 'next': {'value': 'not-int'}}
    )
except ValidationError as e:
    # Error reports path to the invalid value
    pass
```

## Generic Models

Models can be generic over type parameters:

```python
from typing import TypeVar, Generic
from pydantic import BaseModel

T = TypeVar('T')

class Container(BaseModel, Generic[T]):
    value: T
    count: int

# Parameterize the generic
IntContainer = Container[int]
StrContainer = Container[str]

ic = IntContainer(value=42, count=1)      # value is int
sc = StrContainer(value='hello', count=1)  # value is str
```

### Generic Constraints

Add constraints to type variables:

```python
from typing import TypeVar

# Constrain T to be str or int
T = TypeVar('T', str, int)

class LimitedContainer(BaseModel, Generic[T]):
    value: T
```

### Generic with Bounds

```python
from typing import TypeVar

class Comparable:
    def __lt__(self, other): ...

T = TypeVar('T', bound=Comparable)

class Sorted(BaseModel, Generic[T]):
    items: list[T]
```

## Literal Types

Literal constrains a field to specific values:

```python
from typing import Literal
from pydantic import BaseModel

class Log(BaseModel):
    level: Literal['debug', 'info', 'warning', 'error']
    message: str

Log(level='info', message='test')  # OK
Log(level='critical', message='test')  # ValidationError
```

## Enum Types

Python enums are validated against enum members:

```python
from enum import Enum
from pydantic import BaseModel

class Color(str, Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'

class Item(BaseModel):
    color: Color

item = Item(color='red')          # OK: coerces to Color.RED
item = Item(color=Color.RED)      # OK: accepts enum directly
item = Item(color='yellow')       # ValidationError
```

### Enum Value vs Name

By default, Pydantic accepts both value and name:

```python
class Status(Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'

# Both work
Model(status='active')     # By value
Model(status='ACTIVE')     # By name (less common)
```

Control with serialization:

```python
class Config(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    status: Status

# Serializes to 'active' (value), not enum object
```

## Special Container Types

### List, Set, FrozenSet

```python
from pydantic import BaseModel

class Collection(BaseModel):
    tags: list[str]          # List of strings
    unique_ids: set[int]     # Set of integers
    fixed_roles: frozenset[str]  # Immutable set
```

### Dict with Typed Values

```python
from pydantic import BaseModel

class Config(BaseModel):
    settings: dict[str, int]  # String keys, int values
    metadata: dict[str, str]  # All string key-value pairs
```

### Tuple Types

```python
from pydantic import BaseModel

class Point(BaseModel):
    coordinates: tuple[int, int]        # Fixed-length tuple (x, y)
    values: tuple[int, ...]              # Variable-length tuple
```

## ClassVar and TypeVar Edge Cases

### ClassVar

ClassVar fields are not validated and not included in serialization:

```python
from typing import ClassVar
from pydantic import BaseModel

class Settings(BaseModel):
    debug: bool
    version: ClassVar[str] = '1.0.0'  # Not validated or serialized

s = Settings(debug=True)
# s.version is '1.0.0', but not in model_dump()
```

### TypeVar in Non-Generic Models

```python
from typing import TypeVar

T = TypeVar('T')

class NonGeneric(BaseModel):
    value: T  # TypeVar without Generic base - treated as generic type
```

This creates an implicit generic model.

## Union with Literal for Discriminators (Common Pattern)

```python
from typing import Union, Literal, Annotated
from pydantic import BaseModel, Discriminator

class SuccessResponse(BaseModel):
    status: Literal['success']
    data: str

class ErrorResponse(BaseModel):
    status: Literal['error']
    error_code: int

# Discriminate on 'status' field
APIResponse = Annotated[
    Union[SuccessResponse, ErrorResponse],
    Discriminator('status')
]

class API(BaseModel):
    response: APIResponse

api1 = API(response={'status': 'success', 'data': 'result'})
api2 = API(response={'status': 'error', 'error_code': 404})
```

This pattern is essential for polymorphic APIs and webhook handling.
