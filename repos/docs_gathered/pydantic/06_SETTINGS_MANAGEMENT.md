# Settings Management with Pydantic

**Source:** https://docs.pydantic.dev/latest/concepts/pydantic_settings/

## BaseSettings Overview

`BaseSettings` extends `BaseModel` to read configuration from environment variables, dotenv files, and secrets files.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    debug: bool = False
    api_key: str
```

When instantiated, BaseSettings attempts to populate fields from:
1. Arguments passed to __init__
2. Environment variables
3. Dotenv files
4. Secrets files

## Environment Variables

### Basic Usage

Fields map to uppercase environment variable names:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str      # Reads DATABASE_URL env var
    api_key: str           # Reads API_KEY env var
    debug: bool = False    # Reads DEBUG env var (case-insensitive)

# If DATABASE_URL env var exists, it's used
settings = Settings()  # Reads from environment
```

### Custom Field Names with env

Control the environment variable name:

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    database_url: str = Field(alias='DB_URL')
    # Reads DB_URL env var instead of DATABASE_URL

settings = Settings()
```

### env_prefix

Add a prefix to all environment variables:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='APP_')
    
    database_url: str      # Reads APP_DATABASE_URL
    api_key: str           # Reads APP_API_KEY
    debug: bool = False    # Reads APP_DEBUG

settings = Settings()
```

### Nested Models with env_nested_delimiter

Environment variables can populate nested models:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel

class DatabaseSettings(BaseModel):
    host: str
    port: int

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter='__')
    
    database: DatabaseSettings

# Environment variables:
# DATABASE__HOST=localhost
# DATABASE__PORT=5432
settings = Settings()
```

### Case Sensitivity

Environment variables are case-insensitive by default:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False)
    
    api_key: str           # Matches API_KEY, Api_Key, api_key, etc.

# All of these work:
import os
os.environ['API_KEY'] = 'key123'
os.environ['api_key'] = 'key456'  # Overwrites (same key)
```

## Dotenv Files

Load settings from `.env` files:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8'
    )
    
    database_url: str
    api_key: str

# Reads from .env file
settings = Settings()
```

### Multiple Dotenv Files

Load from multiple files (later files override earlier):

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=('.env', '.env.local', '.env.prod')
    )
    
    database_url: str
```

File loading order:
1. `.env` - Base configuration
2. `.env.local` - Local overrides (usually not committed)
3. `.env.prod` - Production overrides

### Dotenv File Format

```
# .env file format
DATABASE_URL=postgresql://localhost/mydb
API_KEY=secret123
DEBUG=true
ALLOWED_HOSTS=["localhost", "127.0.0.1"]
```

### Precedence: Arguments > Env Vars > Dotenv

```python
import os

os.environ['API_KEY'] = 'from_env'

settings = Settings(api_key='from_init')
# Uses 'from_init' (argument has highest priority)

settings = Settings()
# Uses 'from_env' (env var overrides dotenv)
```

**Priority order:**
1. Arguments to Settings()
2. Environment variables
3. Dotenv files
4. Default values

## Secrets Files

Load sensitive data from files instead of environment variables:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        secrets_dir='/run/secrets'  # Docker Swarm secrets location
    )
    
    database_password: str
    api_key: str

# Reads from /run/secrets/database_password and /run/secrets/api_key
settings = Settings()
```

### Secrets Directory Structure

```
/run/secrets/
├── database_password    (contains: "secret123")
├── api_key             (contains: "key456")
└── db_host             (contains: "postgres.local")
```

Each file is a secret; the filename is the field name.

### Multiple Secrets Directories

Load from multiple locations (later overrides earlier):

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        secrets_dir=('/etc/secrets', '/run/secrets')
    )
```

### Precedence: Arguments > Env > Secrets > Dotenv > Defaults

```
1. Arguments passed to Settings()
2. Environment variables
3. Secrets files
4. Dotenv files
5. Default values
```

## Custom Sources

Define custom configuration sources with `settings_customise_sources`:

```python
from pydantic_settings import BaseSettings, EnvSettingsSource, SettingsConfigDict
from typing import Any

class CustomSettingsSource:
    def __init__(self, settings):
        self.settings = settings

    def __call__(self):
        # Return dict of settings
        return {'api_key': 'custom_value'}

    def __repr__(self):
        return 'CustomSettingsSource()'

class Settings(BaseSettings):
    api_key: str
    
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        # Control order and which sources are used
        return (
            init_settings,
            CustomSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

settings = Settings()  # Uses custom source
```

### Common Custom Source Pattern

Load from database, API, or other sources:

```python
from pydantic_settings import BaseSettings, EnvSettingsSource

class DatabaseSettingsSource(EnvSettingsSource):
    def __call__(self):
        # Fetch from database
        data = {'api_key': 'from_db'}
        return data

class Settings(BaseSettings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        return (
            init_settings,
            env_settings,
            DatabaseSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )
```

## Complex Types in Environment Variables

### Lists

Environment variables can define lists:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='APP_')
    
    allowed_hosts: list[str]

# Environment: APP_ALLOWED_HOSTS=localhost,127.0.0.1,example.com
# Automatically parses as list
settings = Settings()
# allowed_hosts = ['localhost', '127.0.0.1', 'example.com']
```

### JSON Objects

Complex objects can be passed as JSON strings:

```python
from pydantic_settings import BaseSettings
from pydantic import BaseModel

class DatabaseConfig(BaseModel):
    host: str
    port: int

class Settings(BaseSettings):
    database: DatabaseConfig

# Environment: DATABASE={"host":"localhost","port":5432}
settings = Settings()
```

## Model Config for Settings

### SettingsConfigDict Options

```python
from pydantic_settings import SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',                      # Dotenv file path
        env_file_encoding='utf-8',            # File encoding
        env_prefix='APP_',                    # Env var prefix
        env_nested_delimiter='__',            # Nested model delimiter
        case_sensitive=False,                 # Case sensitivity
        # Validation settings
        extra='forbid',                       # Handle extra fields
        validate_default=True,                # Validate defaults
        # Sources customization
        json_file=None,                       # Load from JSON
        json_file_encoding='utf-8',
        toml_file=None,                       # Load from TOML
        yaml_file=None,                       # Load from YAML
    )
```

## Real-World Example

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

class DatabaseSettings(BaseModel):
    host: str = 'localhost'
    port: int = 5432
    name: str = 'myapp'
    user: str
    password: str

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='APP_',
        env_nested_delimiter='__',
        secrets_dir='/run/secrets'
    )
    
    # Core settings
    debug: bool = False
    database: DatabaseSettings
    api_key: str = Field(validation_alias='SECRET_API_KEY')
    allowed_hosts: list[str] = ['localhost']
    
    # With defaults
    max_connections: int = 10
    log_level: str = 'info'

# Usage in code:
# settings = Settings()
# Access: settings.database.host, settings.api_key, etc.
```

## Validation with BaseSettings

BaseSettings inherits all validation from BaseModel:

```python
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator

class Settings(BaseSettings):
    port: int = Field(gt=0, le=65535)
    timeout: int = Field(ge=1)
    
    @field_validator('timeout', mode='before')
    @classmethod
    def parse_timeout(cls, v):
        if isinstance(v, str):
            return int(v)
        return v

# Validation runs on values from all sources
settings = Settings()
```

## Reloading Settings

Settings are immutable by default; to reload use a new instance:

```python
# Original settings
settings = Settings()

# Change environment
import os
os.environ['APP_DEBUG'] = 'true'

# Create new instance (old one unchanged)
new_settings = Settings()
# new_settings.debug == True
# settings.debug unchanged
```

To make settings mutable:

```python
class MutableSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=False)  # Allow mutation
    
    debug: bool = False
```
