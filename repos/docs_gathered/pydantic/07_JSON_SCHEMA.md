# JSON Schema Generation and Customization

**Source:** https://docs.pydantic.dev/latest/concepts/json_schema/

## JSON Schema Generation Overview

Pydantic automatically generates JSON Schema from models using:

```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

# Generate JSON Schema
schema = User.model_json_schema()
```

The generated schema includes:
- Type information
- Required fields
- Field descriptions
- Constraints (min/max, patterns, etc.)
- Field examples
- Nested model definitions

## BaseModel.model_json_schema()

Generate schema for a model:

```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

schema = User.model_json_schema()
# Returns a dict compatible with JSON Schema Draft 2020-12
```

### Parameters

```python
User.model_json_schema(
    by_alias=True,           # Use field aliases
    ref_template='{model}.json#/$defs/{model}',  # $ref template
    schema_generator=None,   # Custom schema generator class
    mode='validation',       # 'validation' or 'serialization'
)
```

| Parameter | Effect |
|-----------|--------|
| `by_alias` | Use alias names instead of field names |
| `ref_template` | Control how $ref paths are formatted |
| `schema_generator` | Custom GenerateJsonSchema subclass |
| `mode` | Use validation or serialization schema |

## Schema Customization at Field Level

### Field() Schema Options

```python
from pydantic import BaseModel, Field

class Product(BaseModel):
    name: str = Field(
        title='Product Name',
        description='The name of the product',
        examples=['Widget', 'Gadget']
    )
    price: float = Field(
        title='Price',
        description='Price in USD',
        gt=0,
        json_schema_extra={'currency': 'USD'}
    )
```

### Common Field Parameters

| Parameter | Effect |
|-----------|--------|
| `title` | Display title in schema |
| `description` | Detailed description |
| `examples` | List of example values |
| `json_schema_extra` | Additional schema properties (dict or callable) |
| `exclude` | Exclude from schema |

### json_schema_extra with Dict

Add custom properties to field schema:

```python
class Product(BaseModel):
    price: float = Field(
        json_schema_extra={
            'currency': 'USD',
            'format': 'currency'
        }
    )
```

### json_schema_extra with Callable

Dynamically modify field schema:

```python
def schema_extra(schema, model_type):
    schema['custom_field'] = 'custom_value'
    if 'title' not in schema:
        schema['title'] = 'Default Title'

class Product(BaseModel):
    name: str = Field(json_schema_extra=schema_extra)
```

## Schema Customization at Model Level

### Model-Level Configuration

```python
from pydantic import BaseModel, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(
        title='User Model',
        json_schema_extra={
            'examples': [
                {'name': 'John', 'age': 30},
                {'name': 'Jane', 'age': 25}
            ]
        }
    )
    name: str
    age: int
```

### json_schema_extra at Model Level

```python
def model_schema_extra(schema, model):
    schema['custom'] = 'model-level'

class Config(BaseModel):
    model_config = ConfigDict(
        json_schema_extra=model_schema_extra
    )
    setting1: str
```

## WithJsonSchema and SkipJsonSchema

### WithJsonSchema

Override generated schema without custom methods:

```python
from pydantic import BaseModel, WithJsonSchema
from typing import Annotated

class Model(BaseModel):
    # Use custom schema without implementing special methods
    value: Annotated[int, WithJsonSchema({'type': 'integer', 'minimum': 0})]
```

### SkipJsonSchema

Exclude fields from schema entirely:

```python
from pydantic import BaseModel, SkipJsonSchema
from typing import Annotated

class Model(BaseModel):
    public_field: str
    internal_field: Annotated[str, SkipJsonSchema()]

schema = Model.model_json_schema()
# internal_field not in schema
```

## Reference ($ref) Handling

### Default Reference Handling

Pydantic uses $ref for nested models:

```python
from pydantic import BaseModel

class Address(BaseModel):
    street: str
    city: str

class User(BaseModel):
    name: str
    address: Address

schema = User.model_json_schema()
# Schema includes $ref and $defs/$definitions
```

Generated schema structure:

```json
{
  "$defs": {
    "Address": {
      "type": "object",
      "properties": {
        "street": {"type": "string"},
        "city": {"type": "string"}
      }
    }
  },
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "address": {"$ref": "#/$defs/Address"}
  }
}
```

### Customizing ref_template

Control how $ref paths are formatted:

```python
# OpenAPI style refs
schema = User.model_json_schema(
    ref_template='#/components/schemas/{model}'
)

# Results in: {"$ref": "#/components/schemas/Address"}

# Different format
schema = User.model_json_schema(
    ref_template='{model}.schema.json'
)
```

## Custom GenerateJsonSchema

For advanced customization, subclass `GenerateJsonSchema`:

```python
from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from typing import Any

class CustomGenerateJsonSchema(GenerateJsonSchema):
    def generate(self, schema, mode='validation'):
        # Modify before generation
        return super().generate(schema, mode)
    
    def handler(self, core_schema):
        # Process specific schema types
        return super().handler(core_schema)

class Model(BaseModel):
    value: int

schema = Model.model_json_schema(
    schema_generator=CustomGenerateJsonSchema
)
```

## Schema Modes: Validation vs Serialization

Generate different schemas for validation vs serialization:

```python
from pydantic import BaseModel, field_serializer

class Model(BaseModel):
    internal_id: int
    name: str
    
    @field_serializer('internal_id')
    def serialize_id(self, value):
        return f'id_{value}'

# Validation schema (what can be input)
validation_schema = Model.model_json_schema(mode='validation')

# Serialization schema (what can be output)
serialization_schema = Model.model_json_schema(mode='serialization')
```

Differences:
- Validation schema shows input constraints
- Serialization schema shows computed fields and serializer output types

## Schema Generation for Computed Fields

Computed fields appear in schemas:

```python
from pydantic import BaseModel, computed_field

class Rectangle(BaseModel):
    width: float
    height: float
    
    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height

schema = Rectangle.model_json_schema()
# Schema includes 'area' field with type 'number'
```

## TypeAdapter for Non-Model Types

Generate schemas for types without models:

```python
from pydantic import TypeAdapter

adapter = TypeAdapter(list[int])
schema = adapter.json_schema()
# {'type': 'array', 'items': {'type': 'integer'}}
```

## Schema Generation for Unions

Unions generate oneOf schemas:

```python
from pydantic import BaseModel
from typing import Union

class Cat(BaseModel):
    pet_type: str = 'cat'
    meows: int

class Dog(BaseModel):
    pet_type: str = 'dog'
    barks: int

class Pet(BaseModel):
    animal: Union[Cat, Dog]

schema = Pet.model_json_schema()
# animal property uses oneOf with Cat and Dog schemas
```

## Schema Generation for Discriminated Unions

Discriminated unions generate optimized schemas:

```python
from pydantic import BaseModel, Discriminator
from typing import Union, Literal, Annotated

class Cat(BaseModel):
    pet_type: Literal['cat']
    meows: int

class Dog(BaseModel):
    pet_type: Literal['dog']
    barks: int

class Pet(BaseModel):
    animal: Annotated[Union[Cat, Dog], Discriminator('pet_type')]

schema = Pet.model_json_schema()
# Schema optimized for discriminated union
```

## Constraints in Schema

Field constraints appear in schema:

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(gt=0, le=150)
    email: str = Field(pattern=r'^[\w\.-]+@[\w\.-]+$')

schema = User.model_json_schema()
# name: {"type": "string", "minLength": 1, "maxLength": 100}
# age: {"type": "integer", "exclusiveMinimum": 0, "maximum": 150}
# email: {"type": "string", "pattern": "^[\\w\\.-]+@[\\w\\.-]+$"}
```

## Real-World Example

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Address(BaseModel):
    street: str = Field(description='Street name and number')
    city: str = Field(description='City name')
    postal_code: str = Field(pattern=r'^\d{5}$', description='5-digit ZIP code')

class User(BaseModel):
    model_config = ConfigDict(
        title='User',
        json_schema_extra={
            'examples': [
                {
                    'id': 1,
                    'name': 'John Doe',
                    'email': 'john@example.com',
                    'created_at': '2024-01-15T10:30:00Z',
                    'address': {
                        'street': '123 Main St',
                        'city': 'Springfield',
                        'postal_code': '12345'
                    }
                }
            ]
        }
    )
    
    id: int = Field(description='Unique user identifier')
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r'^[\w\.-]+@[\w\.-]+$')
    created_at: datetime = Field(description='Account creation timestamp')
    address: Optional[Address] = Field(default=None, description='User address')

schema = User.model_json_schema()
# Generates comprehensive schema with examples, constraints, descriptions
```

## Schema Output

The generated JSON Schema can be:
- Used for API documentation
- Passed to OpenAPI generators
- Used for client code generation
- Used for validation in other languages
- Served as endpoint documentation
