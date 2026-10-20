---
source: https://github.com/google/gson/issues/913
retrieved: 2026-04-03
type: github_issue
description: Apply serialize nulls for specific classes only
---

# Issue #913: Apply serialize nulls for specific classes only

## Status
**Open** — labeled as enhancement

## Description

The `serializeNulls()` option in Gson is all-or-nothing: once enabled, it applies globally to all object serialization. There is no built-in mechanism to enable null serialization for specific classes while keeping it disabled everywhere else.

This limitation forces developers into a choice: either serialize nulls for the entire object graph (cluttering output with nulls that aren't semantically important) or disable null serialization globally and lose the ability to distinguish null values for specific types that need this distinction.

## User Attempt and Failure

One developer attempted a workaround by registering a custom `JsonSerializer<MyClass>` that uses a separate Gson instance with `serializeNulls()` enabled:

```java
new GsonBuilder()
    .registerJsonSerializer(MyClass.class, (src, typeOfSrc, context) -> {
        Gson gsonWithNulls = new GsonBuilder().serializeNulls().create();
        return gsonWithNulls.toJsonTree(src);
    })
    .create()
```

However, this approach fails because:
1. The inner Gson instance correctly serializes nulls to a JsonElement
2. The outer Gson instance then re-serializes this JsonElement to the final output
3. During this re-serialization step, the outer Gson instance (which has serializeNulls disabled) strips the explicit null values

The explicit nulls in the returned JsonElement are ignored by the main Gson instance's configuration.

## Why This Matters

Different classes in an object model may have different null semantics:
- **Required fields** — null should always be present in JSON for API consistency
- **Optional fields** — null should be omitted to reduce payload size
- **Domain objects** — null may have specific meaning (uninitialized vs. explicitly cleared)

## Working Workaround

The current workaround that actually functions is to use a `TypeAdapterFactory` that temporarily modifies the writer's null-serialization setting:

```java
new GsonBuilder()
    .registerTypeAdapterFactory(new TypeAdapterFactory() {
        @Override
        public <T> TypeAdapter<T> create(Gson gson, TypeToken<T> type) {
            if (!MyClass.class.isAssignableFrom(type.getRawType())) {
                return null;
            }

            TypeAdapter<T> delegate = gson.getDelegateAdapter(this, type);

            return new TypeAdapter<T>() {
                @Override
                public void write(JsonWriter out, T value) throws IOException {
                    boolean previousSerializeNulls = out.getSerializeNulls();
                    try {
                        out.setSerializeNulls(true);
                        delegate.write(out, value);
                    } finally {
                        out.setSerializeNulls(previousSerializeNulls);
                    }
                }

                @Override
                public T read(JsonReader in) throws IOException {
                    return delegate.read(in);
                }
            };
        }
    })
    .create()
```

This works because:
1. The factory wraps the delegate adapter for the specific class
2. It temporarily enables null serialization just for that class
3. The try-finally ensures the setting is restored afterward

However, this pattern is verbose and requires understanding low-level Gson internals.

## Impact

The lack of per-class null serialization control creates friction when:
- Building REST APIs where different entity types have different null semantics
- Integrating multiple systems with different JSON conventions
- Creating domain-driven designs where nullness has semantic significance for specific types

## Potential Solutions

1. **@SerializeNulls annotation** — Allow marking specific classes or fields to enable null serialization for just those elements, while respecting the global setting otherwise.

2. **TypeAdapterFactory helper** — Provide a built-in utility that makes the try-finally pattern automatic and easier to use.

3. **Per-class GsonBuilder option** — Extend GsonBuilder to support `.serializeNullsFor(MyClass.class)` in addition to the global `serializeNulls()`.

4. **Context-aware adapter registration** — Allow adapters to query and temporarily modify writer configuration in a way that's respected by parent adapters.

## Relationship to Other Issues

This issue is related to:
- **Issue #676** — RuntimeTypeAdapterFactory losing serializeNulls settings
- **Issue #1558** — Distinguishing between optional and required/nullable fields
