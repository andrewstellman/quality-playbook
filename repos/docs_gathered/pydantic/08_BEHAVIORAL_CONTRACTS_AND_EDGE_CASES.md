# Behavioral Contracts and Edge Cases

**Source:** https://github.com/pydantic/pydantic/issues  
**Source:** https://docs.pydantic.dev/latest/concepts/models/

This file documents the exact behavioral guarantees and edge cases critical for understanding Pydantic V2's semantics.

## Validator Execution Order

The order of validator execution is deterministic but complex:

### Order of Operations (High Level)

```
1. model_validator(mode='before') - Executes on raw input
2. Field coercion and type validation (pydantic-core)
3. @field_validator(mode='before') - Field-level before validators
4. @field_validator(mode='after') - Field-level after validators
5. model_validator(mode='after') - Executes on validated model
```

### Detailed Execution Order for @field_validator

Within a single field's validators:

```python
class Model(BaseModel):
    value: int
    
    # These execute in this order:
    # 1. validator_1_before (mode='before')
    # 2. validator_2_before (mode='before')
    # 3. pydantic-core validation (type coercion)
    # 4. validator_1_after (mode='after')
    # 5. validator_2_after (mode='after')
    
    @field_validator('value', mode='before')
    @classmethod
    def validator_1_before(cls, v):
        return v
    
    @field_validator('value', mode='before')
    @classmethod
    def validator_2_before(cls, v):
        return v
    
    @field_validator('value', mode='after')
    @classmethod
    def validator_1_after(cls, v):
        return v
```

**Important:** When mode='before', validators are executed in **reverse declaration order**. When mode='after', they execute in **declaration order**.

### Across Multiple Fields

Fields are validated in **declaration order**:

```python
class Model(BaseModel):
    field_a: int   # Validated first
    field_b: str   # Validated second
    field_c: bool  # Validated third
```

If field_a validation fails, field_b and field_c are not validated.

### Annotated Validators

When using Annotated with validators, execution is right-to-left for before/wrap, then left-to-right for after:

```python
from typing import Annotated
from pydantic import field_validator

def check_even(v):
    return v

def check_positive(v):
    return v

# Execution order:
# 1. check_even (right-to-left for 'before' mode)
# 2. check_positive
# 3. pydantic-core validation
# Note: No explicit mode specified, so uses 'after' mode by default

Value: Annotated[int, field_validator('value')(check_even), field_validator('value')(check_positive)]
```

### Wrap Validators

Wrap validators can intercept before and after validation:

```python
@field_validator('value', mode='wrap')
@classmethod
def validate_wrap(cls, v, handler):
    # Run before standard validation
    v = do_something_before(v)
    # Call standard validation
    result = handler(v)
    # Run after standard validation
    result = do_something_after(result)
    return result
```

## Type Coercion Determinism

The exact type coercion behavior is deterministic based on mode and type:

### String to Int Conversion

```python
# Lax mode (default)
int_val = int('123')        # ✓ Works
int_val = int('123.45')     # ✗ Fails (decimal string)
int_val = int('')           # ✗ Fails (empty string)
int_val = int('+123')       # ✓ Works
int_val = int('-456')       # ✓ Works
int_val = int('0x10', 0)    # ✗ Fails (hex not auto-detected)

# Strict mode
# All of above fail; only int type accepted
```

### Float to Int Conversion

```python
# Lax mode
int(1.0)   # ✓ Works (exactly 1.0)
int(1.5)   # ✗ Fails (not whole number)

# Strict mode
int(1.0)   # ✗ Fails (not int type)
```

### Bool Conversions

In lax mode, these convert to bool:

```python
bool('true')     # ✓ True (case-insensitive)
bool('false')    # ✓ False (case-insensitive)
bool('yes')      # ✓ True (case-insensitive)
bool('no')       # ✓ False (case-insensitive)
bool('on')       # ✓ True (case-insensitive)
bool('off')      # ✓ False (case-insensitive)
bool('1')        # ✓ True
bool('0')        # ✓ False
bool('')         # ✓ False (empty string)
bool('any')      # ✗ Fails (unrecognized)
bool(1)          # ✓ True
bool(0)          # ✓ False
bool(1.0)        # ✓ True
bool(0.0)        # ✓ False
```

### List Coercions

```python
# Lax mode - these collections convert to list
list((1, 2, 3))           # ✓ Tuple → list
list({1, 2, 3})           # ✓ Set → list
list(frozenset([1, 2]))   # ✓ Frozenset → list
list('abc')               # ✓ String → ['a', 'b', 'c']
list({'a': 1, 'b': 2})    # ✓ Dict keys → list

# Strict mode
# Only list type accepted (except JSON input)
```

## Private Attributes Behavior

Private attributes (prefixed with `_`) have special semantics:

### Validation and Initialization

```python
from pydantic import BaseModel, PrivateAttr

class Model(BaseModel):
    public: str
    _private: str = PrivateAttr(default='')
    
    def model_post_init(self, __context):
        self._private = 'set_in_post_init'

# Private fields not in __init__
m = Model(public='value')  # OK

# Cannot pass private fields to __init__
Model(public='value', _private='x')  # Extra field error

# Private fields are NOT validated
m._private = 123  # OK, no type checking
```

### Copy Semantics

Private attributes are **NOT copied** in __copy__ or __deepcopy__:

```python
import copy

class Model(BaseModel):
    public: str
    _private: str = PrivateAttr(default='original')

m1 = Model(public='value')
m1._private = 'custom'

m2 = copy.copy(m1)
m2._private  # 'original' (not copied!)

m3 = copy.deepcopy(m1)
m3._private  # 'original' (not copied!)
```

This is a critical edge case: private attribute state is lost in copies.

### Serialization

Private attributes are **NOT serialized**:

```python
class Model(BaseModel):
    public: str
    _private: str = PrivateAttr(default='secret')

m = Model(public='value')
m._private = 'custom'

m.model_dump()       # {'public': 'value'}  (no _private)
m.model_dump_json()  # '{"public":"value"}'
```

## Frozen Models

Setting `frozen=True` creates **faux immutability**:

```python
from pydantic import BaseModel, ConfigDict

class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    items: list

m = FrozenModel(name='test', items=[1, 2, 3])

# Cannot reassign attributes
m.name = 'new'  # ✗ ValidationError (frozen_instance)

# But mutable objects can be mutated
m.items.append(4)  # ✓ Works! items is now [1, 2, 3, 4]
```

This is NOT true immutability. The model instance cannot be reassigned, but nested mutable objects are still mutable.

### Frozen Models and Hashing

Frozen models become hashable IF all fields are hashable:

```python
from pydantic import BaseModel, ConfigDict

class HashableModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    value: int

m = HashableModel(name='test', value=42)
hash(m)  # ✓ Works

# Can be used as dict key
d = {m: 'some_value'}

# But if any field is unhashable:
class UnhashableModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    items: list  # Unhashable

m2 = UnhashableModel(name='test', items=[1, 2])
hash(m2)  # ✗ TypeError (unhashable type: 'list')
```

### Deleting Attributes on Frozen Models

Despite being frozen, attributes can be deleted:

```python
m = FrozenModel(name='test', items=[1, 2, 3])
del m.name  # ✓ Works!
m.name  # ✗ AttributeError
```

This is a known quirk in Pydantic V2.

## Model Equality (__eq__)

Model equality has specific semantics:

### Same Type Requirement

Two models are equal ONLY if they are the same type:

```python
class User(BaseModel):
    name: str
    age: int

class Person(BaseModel):
    name: str
    age: int

u = User(name='John', age=30)
p = Person(name='John', age=30)

u == p  # ✗ False (different types)
u == u  # ✓ True
```

### Dict Comparison

In V2, models are NOT equal to dicts with the same data:

```python
u = User(name='John', age=30)
data = {'name': 'John', 'age': 30}

u == data  # ✗ False (must be model instance)
u.model_dump() == data  # ✓ True
```

### Private Attributes in Equality

Two model instances are equal ONLY if they have the same type AND same private attribute values:

```python
from pydantic import BaseModel, PrivateAttr

class Model(BaseModel):
    public: str
    _private: str = PrivateAttr(default='')

m1 = Model(public='value')
m1._private = 'secret1'

m2 = Model(public='value')
m2._private = 'secret1'

m1 == m2  # ✓ True (same public and private values)

m2._private = 'secret2'
m1 == m2  # ✗ False (different private values)
```

## Model Inheritance

Inheritance works as expected with important edge cases:

### Field Inheritance

```python
class Base(BaseModel):
    name: str
    age: int

class Derived(Base):
    email: str

d = Derived(name='John', age=30, email='john@example.com')
```

### Field Override

Subclasses can override parent fields:

```python
class Base(BaseModel):
    value: int

class Derived(Base):
    value: int = 0  # Add default

d = Derived()  # OK, uses default
```

### Validator Inheritance

Validators are inherited:

```python
class Base(BaseModel):
    value: int
    
    @field_validator('value')
    @classmethod
    def check_positive(cls, v):
        assert v > 0
        return v

class Derived(Base):
    extra: str

Derived(value=-1, extra='x')  # ✗ Fails (inherits validator)
```

### Configuration Inheritance

`model_config` values propagate to subclasses, with subclass overrides:

```python
class Base(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: int

class Derived(Base):
    model_config = ConfigDict(str_strip_whitespace=True)
    # Inherits extra='forbid', adds str_strip_whitespace
```

### Private Attribute Inheritance Edge Case

Private attributes can have unexpected behavior in inheritance:

```python
from pydantic import BaseModel, PrivateAttr

class Base(BaseModel):
    _private: str = PrivateAttr(default='base')

class Derived(Base):
    public: str

d = Derived(public='value')
d._private  # 'base' (inherited)

# But in model_post_init of Derived:
class Derived(Base):
    public: str
    
    def model_post_init(self, __context):
        self._private = 'derived'  # This works

d = Derived(public='value')
d._private  # 'derived'
```

## Validate Default Values

By default, default values are **not validated**:

```python
from pydantic import BaseModel, Field

class Model(BaseModel):
    value: int = Field(ge=0)

# This works despite -1 being invalid
m = Model()  # Doesn't validate the -1 against ge=0
```

Enable validation:

```python
from pydantic import BaseModel, ConfigDict, Field

class Model(BaseModel):
    model_config = ConfigDict(validate_default=True)
    value: int = Field(ge=0)  # Default not specified (would fail if it was -1)
```

## Validate Assignment

By default, assigning to fields after creation does NOT validate:

```python
class Model(BaseModel):
    value: int

m = Model(value=5)
m.value = 'not an int'  # ✓ Works (no validation!)
m.value  # 'not an int' (type is wrong!)
```

Enable validation on assignment:

```python
from pydantic import BaseModel, ConfigDict

class Model(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    value: int

m = Model(value=5)
m.value = 'not an int'  # ✗ ValidationError
```

## Arbitrary Types Handling

`arbitrary_types_allowed=True` allows non-Pydantic types but with caveats:

```python
from pydantic import BaseModel, ConfigDict

class CustomClass:
    pass

class Model(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    custom: CustomClass

obj = CustomClass()
m = Model(custom=obj)  # ✓ Works

# But these don't work:
m = Model(custom={'data': 'x'})  # ✗ Fails (dict not CustomClass)
m.model_dump()  # ✗ Cannot serialize arbitrary types
```

## Union Validation Modes

Unions have different validation strategies:

### smart_mode (Default in V2)

Validates all union members, picks the best match:

```python
from typing import Union
from pydantic import ConfigDict

class Model(BaseModel):
    model_config = ConfigDict(union_mode='smart_mode')
    value: Union[int, str]

Model(value='123')  # Converts to int 123 (best match)
```

### left_to_right

Stops at first match:

```python
class Model(BaseModel):
    model_config = ConfigDict(union_mode='left_to_right')
    value: Union[int, str]

Model(value='123')  # Keeps as string (int matches first)
```

## Circular/Recursive Models

Recursive models require special handling:

```python
from pydantic import BaseModel
from typing import Optional

class Node(BaseModel):
    value: int
    next: Optional['Node'] = None

# Must rebuild after definition
Node.model_rebuild()

# Can create circular references in data
n1 = Node(value=1)
n2 = Node(value=2, next=n1)
n1.next = n2  # Circular reference

# Serialization needs care with circular references
n1.model_dump()  # Will recurse infinitely!
```

## from_attributes Behavior

With `from_attributes=True`, models can be created from objects with attributes:

```python
from pydantic import BaseModel, ConfigDict

class DataClass:
    name: str = 'John'
    age: int = 30

class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    age: int

obj = DataClass()
m = Model.model_validate(obj)  # ✓ Reads from attributes
```

## Extra Fields Behavior

Extra field handling is controlled by `extra` in model_config:

### extra='allow'

```python
class Model(BaseModel):
    model_config = ConfigDict(extra='allow')
    name: str

m = Model(name='John', age=30)
m.__pydantic_extra__  # {'age': 30}
m.model_dump()        # {'name': 'John', 'age': 30}
```

### extra='forbid'

```python
class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str

Model(name='John', age=30)  # ✗ ValidationError (extra not allowed)
```

### extra='ignore'

```python
class Model(BaseModel):
    model_config = ConfigDict(extra='ignore')
    name: str

m = Model(name='John', age=30)
m.model_dump()  # {'name': 'John'} (age discarded)
```

## Alias Behavior

Aliases control how fields are named in validation and serialization:

```python
from pydantic import BaseModel, Field

class Model(BaseModel):
    internal_name: str = Field(
        validation_alias='externalName',
        serialization_alias='outputName'
    )

# Input uses validation_alias
m = Model(externalName='value')  # ✓ Works
Model(internal_name='value')      # ✗ Extra field error

# Output uses serialization_alias
m.model_dump(by_alias=True)  # {'outputName': 'value'}
m.model_dump(by_alias=False)  # {'internal_name': 'value'}
```

## JSON Input Handling

JSON input has special rules even in strict mode:

```python
class Model(BaseModel):
    timestamp: datetime

# This works even with strict=True
Model.model_validate_json('{"timestamp":"2024-01-15T10:30:00Z"}', strict=True)

# ISO format strings are always accepted for datetime, date, time in strict mode with JSON
```
