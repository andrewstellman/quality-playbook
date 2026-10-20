# Behavioral Contract Extraction
Generated: 2026-04-04T03:52:43Z
Source files analyzed: 81
Total contracts extracted: 826

## Summary by category
- METHOD: 411
- NULL: 59
- CONFIG: 58
- ERROR: 134
- INVARIANT: 53
- COMPAT: 49
- ORDER: 9
- LIFECYCLE: 33
- THREAD: 20

### gson/src/main/java/com/google/gson/ExclusionStrategy.java (2 contracts)

1. [METHOD] ExclusionStrategy.shouldSkipField(FieldAttributes): returning `true` causes Gson to ignore that field for whichever direction the strategy is registered for; returning `false` leaves the field eligible for normal handling.
2. [METHOD] ExclusionStrategy.shouldSkipClass(Class<?>): returning `true` causes Gson to treat values of that type as excluded rather than processed normally; when wired through `GsonBuilder`, exclusion can apply to serialization only, deserialization only, or both.
### gson/src/main/java/com/google/gson/FieldAttributes.java (8 contracts)

1. [NULL] FieldAttributes(Field): requires a non-null `Field`; passing `null` throws `NullPointerException` via `Objects.requireNonNull`.
2. [THREAD] FieldAttributes is immutable and therefore safe to share across threads.
3. [METHOD] FieldAttributes.getDeclaringClass(): returns the exact declaring class of the wrapped field.
4. [METHOD] FieldAttributes.getName(): returns the Java field name unchanged.
5. [METHOD] FieldAttributes.getDeclaredType(): returns the field’s declared generic `Type`, preserving parameterization instead of erasing to raw class.
6. [METHOD] FieldAttributes.getDeclaredClass(): returns the field’s raw declared `Class<?>`.
7. [METHOD] FieldAttributes.getAnnotation(Class<T>): returns the requested annotation instance when present, otherwise `null`.
8. [METHOD] FieldAttributes.getAnnotations()/hasModifier(int)/toString(): expose the field’s runtime annotations, modifier membership, and `Field.toString()` representation without additional transformation.
### gson/src/main/java/com/google/gson/FieldNamingPolicy.java (9 contracts)

1. [METHOD] FieldNamingPolicy.IDENTITY.translateName(Field): returns the Java field name unchanged.
2. [METHOD] FieldNamingPolicy.UPPER_CAMEL_CASE.translateName(Field): capitalizes the first letter character in the field name while preserving any leading non-letter prefix such as `_`.
3. [METHOD] FieldNamingPolicy.UPPER_CAMEL_CASE_WITH_SPACES.translateName(Field): splits camel-case boundaries with spaces, then capitalizes the first letter character.
4. [METHOD] FieldNamingPolicy.UPPER_CASE_WITH_UNDERSCORES.translateName(Field): inserts `_` before uppercase transitions and uppercases with `Locale.ENGLISH`.
5. [METHOD] FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES.translateName(Field): inserts `_` before uppercase transitions and lowercases with `Locale.ENGLISH`.
6. [METHOD] FieldNamingPolicy.LOWER_CASE_WITH_DASHES.translateName(Field): inserts `-` before uppercase transitions and lowercases with `Locale.ENGLISH`.
7. [METHOD] FieldNamingPolicy.LOWER_CASE_WITH_DOTS.translateName(Field): inserts `.` before uppercase transitions and lowercases with `Locale.ENGLISH`.
8. [METHOD] FieldNamingPolicy.separateCamelCase(String,char): splits at every uppercase character after the first emitted character, so acronyms like `aURL` become `a_U_R_L`-style segments rather than preserving acronym groups.
9. [METHOD] FieldNamingPolicy.upperCaseFirstLetter(String): uppercases the first letter character it finds and leaves strings with no letters, or already-uppercase first letters, unchanged.
### gson/src/main/java/com/google/gson/FieldNamingStrategy.java (2 contracts)

1. [METHOD] FieldNamingStrategy.translateName(Field): must map a Java field to the JSON member name Gson should use for both serialization and primary-name deserialization.
2. [METHOD] FieldNamingStrategy.alternateNames(Field): defaults to an empty list, meaning custom alternate deserialization names are opt-in rather than implied.
### gson/src/main/java/com/google/gson/FormattingStyle.java (8 contracts)

1. [INVARIANT] FormattingStyle.COMPACT means no newline, no indent, and no separator spaces.
2. [INVARIANT] FormattingStyle.PRETTY means `"\n"` newline, two-space indent, and a space after `:`.
3. [NULL] FormattingStyle construction via `withNewline`/`withIndent` rejects `null` newline or indent values with `NullPointerException`.
4. [ERROR] FormattingStyle construction rejects newline strings containing anything other than `\r` and `\n` with `IllegalArgumentException`.
5. [ERROR] FormattingStyle construction rejects indent strings containing anything other than spaces and tabs with `IllegalArgumentException`.
6. [METHOD] FormattingStyle.withNewline(String), withIndent(String), and withSpaceAfterSeparators(boolean): return new immutable `FormattingStyle` instances instead of mutating the current one.
7. [CONFIG] FormattingStyle.withSpaceAfterSeparators(boolean): only controls spaces after separators; if newline is non-empty, commas still emit newline rather than comma-space.
8. [METHOD] FormattingStyle.getNewline()/getIndent()/usesSpaceAfterSeparators(): expose the exact stored formatting settings.
### gson/src/main/java/com/google/gson/Gson.java (29 contracts)

1. [THREAD] Gson instances are thread-safe and intended for reuse across threads.
2. [METHOD] Gson.newBuilder(): returns a new `GsonBuilder` initialized with this instance’s current configuration, custom factories, and hierarchy factories.
3. [COMPAT] Gson.excluder(): exposes the internal `Excluder` only for backward compatibility and is explicitly deprecated as accidental API leakage.
4. [METHOD] Gson.fieldNamingStrategy()/serializeNulls()/htmlSafe(): report the active field naming, null-serialization, and HTML-escaping configuration of the instance.
5. [NULL] Gson.getAdapter(TypeToken<T>): rejects a null type token with `NullPointerException`.
6. [METHOD] Gson.getAdapter(TypeToken<T>): returns the adapter for the requested type, using per-thread placeholders to break adapter-construction cycles and global caching for resolved adapters.
7. [ERROR] Gson.getAdapter(TypeToken<T>): throws `IllegalArgumentException` when no registered or built-in factory can handle the type.
8. [THREAD] Gson.getAdapter(TypeToken<T>): concurrent requests for the same type may receive different adapter instances, so adapter implementations are expected to be stateless.
9. [METHOD] Gson.getDelegateAdapter(TypeAdapterFactory,TypeToken<T>): searches only factories after `skipPast`; if `skipPast` is not actually part of the effective factory chain, it falls back to `getAdapter(type)`.
10. [ERROR] Gson.getDelegateAdapter(TypeAdapterFactory,TypeToken<T>): rejects null `skipPast` or `type` and throws `IllegalArgumentException` if a real `skipPast` is found but no later factory can handle the type.
11. [METHOD] Gson.toJsonTree(Object): serializes non-null objects using runtime class and returns `JsonNull.INSTANCE` for null input.
12. [METHOD] Gson.toJsonTree(Object,Type): serializes to an in-memory `JsonElement` tree using the supplied generic type.
13. [METHOD] Gson.toJson(Object): returns a JSON string and serializes null input as JSON `null`.
14. [METHOD] Gson.toJson(Object,Type): serializes using the supplied generic type rather than runtime erasure.
15. [METHOD] Gson.toJson(Object,Appendable)/toJson(Object,Type,Appendable): write JSON through a configured `JsonWriter`; appendable write failures are surfaced as `JsonIOException`.
16. [METHOD] Gson.toJson(Object,Type,JsonWriter): applies Gson’s strictness, HTML-safety, and serialize-nulls settings to the provided writer for the duration of the call and restores the writer’s original settings afterward.
17. [COMPAT] Gson.toJson(Object,Type,JsonWriter) and Gson.toJson(JsonElement,JsonWriter): if Gson has no explicit strictness and the writer is `LEGACY_STRICT`, Gson temporarily downgrades it to `LENIENT` for backward compatibility unless the writer is already `STRICT`.
18. [ERROR] Gson.toJson(...): wraps `IOException` as `JsonIOException` and rewrites `AssertionError` messages to include the Gson version.
19. [METHOD] Gson.toJson(JsonElement): converts a JSON tree to its JSON string form.
20. [METHOD] Gson.toJson(JsonElement,Appendable)/toJson(JsonElement,JsonWriter): write a `JsonElement` tree using the same temporary-writer-setting semantics as object serialization.
21. [METHOD] Gson.newJsonWriter(Writer): creates a fresh `JsonWriter`, optionally prefixes non-executable JSON, applies formatting style, HTML-safety, strictness, and serialize-nulls settings, and defaults strictness to `LEGACY_STRICT` when Gson has none explicitly set.
22. [METHOD] Gson.newJsonReader(Reader): creates a fresh `JsonReader` whose strictness is Gson’s explicit strictness or `LEGACY_STRICT` by default.
23. [NULL] Gson.fromJson(String,...): returns `null` when the input string itself is `null`.
24. [COMPAT] Gson.fromJson(String,...)/fromJson(Reader,...): for the String and Reader overloads, Gson requires full document consumption and throws if there are multiple top-level values or trailing data.
25. [METHOD] Gson.fromJson(Reader,TypeToken<T>): uses a configured `JsonReader`, then calls `assertFullConsumption`; EOF before any token yields `null` for compatibility with older Gson.
26. [METHOD] Gson.fromJson(JsonReader,TypeToken<T>): reads exactly the next JSON value only, intentionally allowing additional top-level values or trailing data afterward.
27. [COMPAT] Gson.fromJson(JsonReader,TypeToken<T>): if Gson has no explicit strictness and the reader is `LEGACY_STRICT`, Gson temporarily changes it to `LENIENT` and restores the original strictness on return.
28. [ERROR] Gson.fromJson(JsonReader,TypeToken<T>): wraps malformed structure or I/O as `JsonSyntaxException`, returns `null` only for empty input, and throws `ClassCastException` if a type adapter returns an instance not assignable to the requested raw type.
29. [COMPAT] Gson intentionally has no `fromJson(JsonReader, Class<T>)` overload because adding it would break source compatibility in some call sites.
### gson/src/main/java/com/google/gson/GsonBuilder.java (33 contracts)

1. [METHOD] GsonBuilder() starts with default Gson behavior: no explicit strictness, compact formatting, HTML escaping enabled, null object fields omitted, simple map keys, and JDK `Unsafe` enabled.
2. [METHOD] GsonBuilder.setVersion(double): enables `@Since`/`@Until` filtering for the configured version.
3. [ERROR] GsonBuilder.setVersion(double): rejects `NaN` and negative versions with `IllegalArgumentException`.
4. [NULL] GsonBuilder.excludeFieldsWithModifiers(int...): rejects a null modifiers array; otherwise replaces the default modifier set with the supplied one.
5. [METHOD] GsonBuilder.generateNonExecutableJson(): causes created Gson writers to prefix output with the non-executable JSON prefix.
6. [METHOD] GsonBuilder.excludeFieldsWithoutExposeAnnotation(): causes only `@Expose`-annotated fields to participate in serialization/deserialization.
7. [METHOD] GsonBuilder.serializeNulls(): makes created Gson instances include null object fields instead of omitting them.
8. [CONFIG] GsonBuilder.enableComplexMapKeySerialization(): only changes map output when a key’s serialized JSON form is non-primitive; such maps serialize as entry arrays instead of JSON objects.
9. [CONFIG] GsonBuilder.disableInnerClassSerialization(): excludes non-static inner classes from serialization and deserialization, causing excluded values to serialize as JSON `null` and deserialize as Java `null`.
10. [NULL] GsonBuilder.setLongSerializationPolicy(LongSerializationPolicy), setFieldNamingStrategy(FieldNamingStrategy), setObjectToNumberStrategy(ToNumberStrategy), setNumberToNumberStrategy(ToNumberStrategy), setFormattingStyle(FormattingStyle), setStrictness(Strictness), and addReflectionAccessFilter(ReflectionAccessFilter): reject null arguments.
11. [METHOD] GsonBuilder.setFieldNamingPolicy(FieldNamingPolicy): is just a convenience wrapper around `setFieldNamingStrategy`.
12. [COMPAT] GsonBuilder.setFieldNamingStrategy(FieldNamingStrategy): created Gson instances may cache translated names, so strategies are not guaranteed to be invoked every time a field is processed.
13. [METHOD] GsonBuilder.setExclusionStrategies(ExclusionStrategy...): adds each strategy as a disjunctive rule for both serialization and deserialization instead of replacing prior strategies.
14. [METHOD] GsonBuilder.addSerializationExclusionStrategy(ExclusionStrategy) and addDeserializationExclusionStrategy(ExclusionStrategy): add one-way exclusion rules only for the selected direction.
15. [CONFIG] Exclusion strategies on fields/classes make Gson behave as if excluded fields do not exist; excluded object values serialize as JSON `null`, and excluded values are skipped and read back as Java `null`.
16. [METHOD] GsonBuilder.setPrettyPrinting(): is exactly `setFormattingStyle(FormattingStyle.PRETTY)`.
17. [COMPAT] GsonBuilder.setLenient(): is the deprecated alias for `setStrictness(Strictness.LENIENT)`.
18. [METHOD] GsonBuilder.disableHtmlEscaping(): turns off escaping of HTML characters such as `<` and `>`.
19. [METHOD] GsonBuilder.setDateFormat(String): sets the pattern used for `Date` and supported SQL date/time types; `null` resets the explicit pattern.
20. [ERROR] GsonBuilder.setDateFormat(String): validates the pattern eagerly with `SimpleDateFormat` and throws `IllegalArgumentException` for invalid patterns.
21. [METHOD] GsonBuilder.setDateFormat(int): sets only the date style, leaves the current time style unchanged, and clears any explicit pattern.
22. [METHOD] GsonBuilder.setDateFormat(int,int): sets both date and time styles and clears any explicit pattern.
23. [ERROR] GsonBuilder.setDateFormat(int) / setDateFormat(int,int): only accept style values `0..3`; invalid styles throw `IllegalArgumentException`.
24. [NULL] GsonBuilder.registerTypeAdapter(Type,Object): rejects null type or adapter.
25. [ERROR] GsonBuilder.registerTypeAdapter(Type,Object): requires the adapter object to implement at least one of `TypeAdapter`, `InstanceCreator`, `JsonSerializer`, or `JsonDeserializer`, otherwise throws `IllegalArgumentException`.
26. [ERROR] GsonBuilder.registerTypeAdapter(Type,Object): forbids overriding the built-in adapter for `Object.class` and throws `IllegalArgumentException` when attempted.
27. [CONFIG] GsonBuilder.registerTypeAdapter(Type,Object): registers exact-type handling only; related primitive/wrapper or subclass types are not automatically covered.
28. [NULL] GsonBuilder.registerTypeAdapterFactory(TypeAdapterFactory) and registerTypeHierarchyAdapter(Class<?>,Object): reject null arguments.
29. [METHOD] GsonBuilder.registerTypeAdapterFactory(TypeAdapterFactory): appends a factory whose adapter results may later be cached per type by Gson.
30. [METHOD] GsonBuilder.registerTypeHierarchyAdapter(Class<?>,Object): applies to a base class/interface hierarchy, but an exact-type adapter still takes precedence over a hierarchy adapter.
31. [METHOD] GsonBuilder.serializeSpecialFloatingPointValues(): allows Gson to emit `NaN` and infinities instead of throwing on serialization.
32. [METHOD] GsonBuilder.disableJdkUnsafe(): prevents created Gson instances from using JDK `Unsafe` for constructor-less instantiation.
33. [ORDER] GsonBuilder.addReflectionAccessFilter(ReflectionAccessFilter): inserts filters at the front so the most recently added filter runs first; GsonBuilder.create() is side-effect free and can be called repeatedly to build independent `Gson` instances from the current configuration.
### gson/src/main/java/com/google/gson/InstanceCreator.java (2 contracts)

1. [METHOD] InstanceCreator.createInstance(Type): is called during deserialization to supply a new instance whose fields Gson will then overwrite from JSON data.
2. [INVARIANT] InstanceCreator.createInstance(Type): must return a fresh object, not a shared/common instance, because Gson destroys any prior state in the returned object during field population.
### gson/src/main/java/com/google/gson/JsonArray.java (18 contracts)

1. [INVARIANT] JsonArray preserves insertion order and its iterator/equality semantics are order-sensitive.
2. [NULL] JsonArray does not store Java `null` elements; every `add(...)` and `set(...)` overload converts null input to `JsonNull.INSTANCE`.
3. [ERROR] JsonArray(int): negative capacity is rejected by the underlying `ArrayList` constructor.
4. [METHOD] JsonArray.deepCopy(): returns a deep copy of all child elements and returns a new empty array for an empty source.
5. [METHOD] JsonArray.add(Boolean/Character/Number/String/JsonElement): appends one element to the end of the array.
6. [METHOD] JsonArray.addAll(JsonArray): appends all elements from the other array in their current order.
7. [METHOD] JsonArray.set(int,JsonElement): replaces and returns the previous element at that index.
8. [ERROR] JsonArray.set(int,JsonElement), remove(int), and get(int): throw `IndexOutOfBoundsException` when the index is outside `[0,size)`.
9. [METHOD] JsonArray.remove(JsonElement): removes the first matching element if present and returns whether removal happened.
10. [METHOD] JsonArray.remove(int): removes and returns the indexed element and shifts subsequent elements left.
11. [METHOD] JsonArray.contains(JsonElement)/size()/isEmpty(): expose membership and cardinality without copying.
12. [METHOD] JsonArray.getAsNumber()/getAsString()/getAsDouble()/getAsBigDecimal()/getAsBigInteger()/getAsFloat()/getAsLong()/getAsInt()/getAsByte()/getAsCharacter()/getAsShort()/getAsBoolean(): delegate to the sole contained element.
13. [ERROR] JsonArray.getAs*(): require the array to contain exactly one element; empty or multi-element arrays throw `IllegalStateException` with the actual size in the message.
14. [METHOD] JsonArray.asList(): returns a live mutable `List<JsonElement>` view backed by the array.
15. [NULL] JsonArray.asList(): unlike `JsonArray.add`, the list view rejects Java `null` with `NullPointerException`; callers must use `JsonNull`.
16. [METHOD] JsonArray.equals(Object): arrays are equal only when the other object is a `JsonArray` with equal elements in the same order.
17. [METHOD] JsonArray.hashCode(): is based on element sequence.
18. [INVARIANT] JsonArray places no explicit nesting-depth or size guard on tree construction, so very deep or huge arrays still rely on downstream parser/writer limits rather than `JsonArray` enforcing one.
### gson/src/main/java/com/google/gson/JsonDeserializationContext.java (2 contracts)

1. [METHOD] JsonDeserializationContext.deserialize(JsonElement,Type): invokes Gson’s default tree-based deserialization for the requested target type.
2. [ERROR] JsonDeserializationContext.deserialize(JsonElement,Type): may throw `JsonParseException` when the tree does not match the requested type, and calling it recursively on the same `(json,type)` a custom deserializer is already handling will loop back into that deserializer.
### gson/src/main/java/com/google/gson/JsonDeserializer.java (3 contracts)

1. [METHOD] JsonDeserializer.deserialize(JsonElement,Type,JsonDeserializationContext): is the callback Gson invokes when a registered custom deserializer handles a matching type.
2. [ERROR] JsonDeserializer.deserialize(...): should throw `JsonParseException` when the JSON tree is not in the expected format for `typeOfT`.
3. [THREAD] JsonDeserializer implementations are expected to be stateless and thread-safe because Gson may reuse them across threads.
### gson/src/main/java/com/google/gson/JsonElement.java (18 contracts)

1. [COMPAT] JsonElement() exists only for backward compatibility; creating custom `JsonElement` subclasses is discouraged and may lead to undefined behavior.
2. [METHOD] JsonElement.deepCopy(): must return a deep copy for mutable subclasses, while immutable subclasses may return themselves.
3. [METHOD] JsonElement.isJsonArray()/isJsonObject()/isJsonPrimitive()/isJsonNull(): report the runtime JSON kind by `instanceof`.
4. [METHOD] JsonElement.getAsJsonObject()/getAsJsonArray()/getAsJsonPrimitive()/getAsJsonNull(): return `this` cast to the requested subtype when the runtime type matches.
5. [ERROR] JsonElement.getAsJsonObject()/getAsJsonArray()/getAsJsonPrimitive()/getAsJsonNull(): throw `IllegalStateException` containing the actual value when called on the wrong JSON kind.
6. [METHOD] Base JsonElement.getAsBoolean()/getAsNumber()/getAsString()/getAsDouble()/getAsFloat()/getAsLong()/getAsInt()/getAsByte()/getAsCharacter()/getAsBigDecimal()/getAsBigInteger()/getAsShort(): do not implement conversion themselves.
7. [ERROR] Base JsonElement.getAs*(): throw `UnsupportedOperationException` naming the subclass unless overridden by a subtype.
8. [COMPAT] JsonArray overrides the scalar `getAs*` methods so single-element arrays act like their sole element; multi-element arrays throw `IllegalStateException` instead of `UnsupportedOperationException`.
9. [METHOD] JsonElement.toString(): renders this element as JSON text.
10. [COMPAT] JsonElement.toString(): forces a lenient `JsonWriter` so rendering does not fail merely because contained numbers include `NaN` or infinities.
11. [METHOD] JsonElement.toString(): uses standard JSON escaping/quoting; callers wanting raw string contents must use `getAsString()` instead.
12. [ERROR] JsonElement.toString(): converts unexpected `IOException` into `AssertionError`, since writing to the in-memory `StringBuilder` should not fail.
13. [NULL] JsonElement tree APIs model JSON null with `JsonNull`, not Java `null`; tree containers are expected to use `JsonNull.INSTANCE` for present JSON nulls.
14. [INVARIANT] JsonElement imposes no intrinsic validation that a tree is RFC-compliant; callers can construct or stringify trees containing non-standard values and rely on higher-level strictness checks elsewhere.
15. [METHOD] JsonElement is the common base for object, array, primitive, and null tree nodes and guarantees those conversions are accessible through the unified `getAs...` surface.
16. [ERROR] JsonElement.getAsCharacter(): is deprecated because it returns the first character of a string value rather than a true JSON char type.
17. [THREAD] The base class itself provides no synchronization; thread-safety depends on the mutability of the concrete subtype.
18. [INVARIANT] Every concrete `JsonElement` must be representable both as tree data and as JSON text via `toString()`.
### gson/src/main/java/com/google/gson/JsonIOException.java (2 contracts)

1. [ERROR] JsonIOException is the dedicated runtime exception Gson uses to signal read/write I/O failures rather than syntax mismatches.
2. [METHOD] JsonIOException(String), JsonIOException(String,Throwable), and JsonIOException(Throwable): preserve message/cause information without adding extra behavior.
### gson/src/main/java/com/google/gson/JsonNull.java (4 contracts)

1. [INVARIANT] JsonNull.INSTANCE is the canonical singleton for JSON null values.
2. [COMPAT] JsonNull() remains public but deprecated; callers are expected to use `INSTANCE` instead.
3. [METHOD] JsonNull.deepCopy(): returns `INSTANCE` because `JsonNull` is immutable.
4. [METHOD] JsonNull.equals(Object)/hashCode(): all `JsonNull` instances compare equal and share the same hash code.
### gson/src/main/java/com/google/gson/JsonObject.java (15 contracts)

1. [INVARIANT] JsonObject stores members in insertion order.
2. [INVARIANT] JsonObject does not store Java `null` values; member values passed as `null` are converted to `JsonNull.INSTANCE`.
3. [METHOD] JsonObject.deepCopy(): recursively deep-copies every member value into a new object while preserving member order.
4. [METHOD] JsonObject.add(String,JsonElement): adds or replaces the member with that name.
5. [METHOD] JsonObject.remove(String): removes and returns the current member value or returns `null` if the name is absent.
6. [METHOD] JsonObject.addProperty(String,String/Number/Boolean/Character): wraps non-null primitives in `JsonPrimitive` and converts nulls to `JsonNull.INSTANCE`.
7. [METHOD] JsonObject.entrySet()/keySet(): return live ordered views of members and member names.
8. [METHOD] JsonObject.size()/isEmpty()/has(String)/get(String): expose object membership and size directly against the backing map.
9. [METHOD] JsonObject.getAsJsonPrimitive(String)/getAsJsonArray(String)/getAsJsonObject(String): return the named member cast to the requested subtype or `null` if absent.
10. [ERROR] JsonObject.getAsJsonPrimitive(String)/getAsJsonArray(String)/getAsJsonObject(String): throw `ClassCastException` if the present member is not of the requested subtype.
11. [METHOD] JsonObject.asMap(): returns a live mutable `Map<String,JsonElement>` view backed by the object.
12. [NULL] JsonObject.asMap(): unlike `JsonObject.add`, the map view rejects Java null keys and values with `NullPointerException`; callers must use `JsonNull` for JSON nulls.
13. [METHOD] JsonObject.equals(Object): compares member mappings ignoring insertion order.
14. [METHOD] JsonObject.hashCode(): is based on members ignoring insertion order.
15. [INVARIANT] JsonObject itself does not reject duplicate logical JSON names beyond normal map replacement semantics; adding the same property name replaces the old value rather than preserving both.
### gson/src/main/java/com/google/gson/JsonParseException.java (2 contracts)

1. [ERROR] JsonParseException is Gson’s public unchecked base exception for parse/format failures that callers may handle without being forced into checked-exception flows.
2. [METHOD] JsonParseException(String), JsonParseException(String,Throwable), and JsonParseException(Throwable): preserve message/cause only and add no subtype-specific behavior.
### gson/src/main/java/com/google/gson/JsonParser.java (8 contracts)

1. [COMPAT] JsonParser’s static parse methods parse in lenient mode by default rather than strict RFC mode.
2. [METHOD] JsonParser.parseString(String): parses a complete JSON string and delegates to `parseReader(new StringReader(json))`.
3. [METHOD] JsonParser.parseReader(Reader): parses one complete JSON document and rejects trailing data or multiple top-level elements unless the parsed value is JSON null at EOF.
4. [METHOD] JsonParser.parseReader(JsonReader): parses only the next JSON value from the stream and intentionally permits additional top-level values or trailing data afterward.
5. [COMPAT] JsonParser.parseReader(JsonReader): preserves `STRICT` readers, but temporarily changes `LEGACY_STRICT` readers to `LENIENT` and restores the original strictness before returning.
6. [ERROR] JsonParser.parseReader(Reader): wraps malformed JSON and numeric format failures as `JsonSyntaxException`, and I/O failures as `JsonIOException`.
7. [ERROR] JsonParser.parseReader(JsonReader) and JsonStreamParser-style parsing: wrap `StackOverflowError` and `OutOfMemoryError` as `JsonParseException` with source context rather than letting raw VM errors escape.
8. [COMPAT] The instance `parse(...)` methods are deprecated pass-through wrappers over the static methods and exist only for backward compatibility.
### gson/src/main/java/com/google/gson/JsonPrimitive.java (15 contracts)

1. [NULL] All public JsonPrimitive constructors reject null input with `NullPointerException`.
2. [METHOD] JsonPrimitive(Character): stores characters as one-character JSON strings, because JSON has no separate char type.
3. [METHOD] JsonPrimitive.deepCopy(): returns `this` because primitives are immutable.
4. [METHOD] JsonPrimitive.isBoolean()/isNumber()/isString(): report which primitive representation is stored.
5. [METHOD] JsonPrimitive.getAsBoolean(): returns the stored boolean directly, or else parses the string form with `Boolean.parseBoolean`, so only case-insensitive `"true"` becomes `true`.
6. [METHOD] JsonPrimitive.getAsNumber(): returns the stored `Number`, or lazily parses a stored string with `LazilyParsedNumber`.
7. [ERROR] JsonPrimitive.getAsNumber(): throws `UnsupportedOperationException` when the stored value is neither a number nor a string.
8. [METHOD] JsonPrimitive.getAsString(): returns the stored string, numeric string form, or boolean string form depending on the stored primitive kind.
9. [METHOD] JsonPrimitive.getAsDouble()/getAsFloat()/getAsLong()/getAsInt()/getAsShort()/getAsByte(): use the stored number directly when numeric, otherwise parse the string form.
10. [METHOD] JsonPrimitive.getAsBigDecimal()/getAsBigInteger(): preserve existing `BigDecimal`/`BigInteger` instances when already stored and otherwise parse from string, using integral-number fast paths for some `BigInteger` cases.
11. [ERROR] Numeric conversion methods throw `NumberFormatException` when the stored string is not a valid number for the requested target type.
12. [METHOD] JsonPrimitive.getAsCharacter(): returns the first character of the string form.
13. [ERROR] JsonPrimitive.getAsCharacter(): throws `UnsupportedOperationException` if the string form is empty.
14. [METHOD] JsonPrimitive.equals(Object): treats integral numeric types by numeric value, treats `BigDecimal` values equal when `compareTo(...) == 0`, and treats `NaN` values as equal to each other while also considering `-0.0` and `+0.0` equal.
15. [METHOD] JsonPrimitive.hashCode(): follows the same numeric-normalization rules as equality so equal integral/double values hash consistently.
### gson/src/main/java/com/google/gson/JsonSerializationContext.java (2 contracts)

1. [METHOD] JsonSerializationContext.serialize(Object): invokes Gson’s default serialization and returns the resulting `JsonElement` tree.
2. [ERROR] JsonSerializationContext.serialize(Object,Type): supports explicit generic type information, but calling it on the same source object/type a custom serializer is currently handling recurses back into that serializer and causes an infinite loop.
### gson/src/main/java/com/google/gson/JsonSerializer.java (3 contracts)

1. [METHOD] JsonSerializer.serialize(T,Type,JsonSerializationContext): is the callback Gson invokes when a registered custom serializer handles a matching type.
2. [ERROR] JsonSerializer.serialize(...): must not call `context.serialize(src, typeOfSrc)` on the same source object it is already serializing, or Gson will recurse indefinitely.
3. [THREAD] JsonSerializer implementations are expected to be stateless and thread-safe because Gson may reuse them across threads.
### gson/src/main/java/com/google/gson/JsonStreamParser.java (7 contracts)

1. [METHOD] JsonStreamParser(String) and JsonStreamParser(Reader): create a streaming parser that reads concatenated JSON values and configures the underlying `JsonReader` to `Strictness.LENIENT`.
2. [THREAD] JsonStreamParser is only conditionally thread-safe; callers must externally synchronize compound `hasNext()`/`next()` sequences.
3. [METHOD] JsonStreamParser.hasNext(): checks whether another top-level JSON value remains by peeking for `END_DOCUMENT`.
4. [METHOD] JsonStreamParser.next(): returns the next parsed `JsonElement`.
5. [ERROR] JsonStreamParser.next(): throws `NoSuchElementException` when no more values are available.
6. [ERROR] JsonStreamParser.hasNext()/next(): convert malformed JSON to `JsonSyntaxException`, I/O failures to `JsonIOException`, and stack/heap exhaustion during parse to `JsonParseException`.
7. [METHOD] JsonStreamParser.remove(): is unsupported and always throws `UnsupportedOperationException`.
### gson/src/main/java/com/google/gson/JsonSyntaxException.java (2 contracts)

1. [ERROR] JsonSyntaxException is Gson’s dedicated unchecked subtype for malformed JSON read/write problems rather than low-level I/O problems.
2. [METHOD] JsonSyntaxException(String), JsonSyntaxException(String,Throwable), and JsonSyntaxException(Throwable): preserve message/cause only and add no extra behavior.
### gson/src/main/java/com/google/gson/LongSerializationPolicy.java (4 contracts)

1. [METHOD] LongSerializationPolicy.DEFAULT.serialize(Long): emits non-null longs as JSON numbers and nulls as `JsonNull.INSTANCE`.
2. [METHOD] LongSerializationPolicy.STRING.serialize(Long): emits non-null longs as JSON strings and nulls as `JsonNull.INSTANCE`.
3. [METHOD] LongSerializationPolicy.typeAdapter(): returns the matching built-in `TypeAdapter<Number>` used internally by `GsonBuilder`.
4. [CONFIG] Choosing a `LongSerializationPolicy` affects serialization only; it changes how `long`/`Long` values are written, not how they are read.
### gson/src/main/java/com/google/gson/ReflectionAccessFilter.java (8 contracts)

1. [METHOD] ReflectionAccessFilter.check(Class<?>): returns `ALLOW`, `INDECISIVE`, `BLOCK_INACCESSIBLE`, or `BLOCK_ALL` to tell Gson whether reflection-based handling is permitted for that class.
2. [INVARIANT] FilterResult.INDECISIVE means “consult the next registered filter”; if none remain, it behaves like `ALLOW`.
3. [INVARIANT] FilterResult.BLOCK_INACCESSIBLE forbids Gson from relying on members that would need `setAccessible`/illegal-access style escalation, but still permits reflection for already-accessible members.
4. [COMPAT] FilterResult.BLOCK_INACCESSIBLE is only fully effective on Java 9+ and may effectively degrade toward `ALLOW` on older runtimes.
5. [INVARIANT] ReflectionAccessFilter.BLOCK_INACCESSIBLE_JAVA returns `BLOCK_INACCESSIBLE` for detected `java.*`/`javax.*` classes and `INDECISIVE` otherwise.
6. [INVARIANT] ReflectionAccessFilter.BLOCK_ALL_JAVA`, `BLOCK_ALL_ANDROID`, and `BLOCK_ALL_PLATFORM` each return `BLOCK_ALL` for their respective detected platform classes and `INDECISIVE` for others.
7. [ORDER] Filters are applied in reverse registration order; the most recently added filter gets first decision.
8. [CONFIG] Reflection access filters cause Gson to fail rather than silently skip fields/classes, unlike `ExclusionStrategy`.
### gson/src/main/java/com/google/gson/Strictness.java (3 contracts)

1. [CONFIG] Strictness.LENIENT permits large deviations from RFC 8259 syntax.
2. [CONFIG] Strictness.LEGACY_STRICT permits a smaller compatibility subset of deviations and is the default strictness Gson assigns to newly created readers/writers when no explicit strictness is configured.
3. [CONFIG] Strictness.STRICT requires strict JSON-spec compliance.
### gson/src/main/java/com/google/gson/ToNumberPolicy.java (6 contracts)

1. [METHOD] ToNumberPolicy.DOUBLE.readNumber(JsonReader): consumes one JSON number and returns it as `Double`.
2. [METHOD] ToNumberPolicy.LAZILY_PARSED_NUMBER.readNumber(JsonReader): consumes one JSON number string and returns a `LazilyParsedNumber`.
3. [METHOD] ToNumberPolicy.LONG_OR_DOUBLE.readNumber(JsonReader): prefers `Long` when the token text parses as a long without a decimal point; otherwise falls back to `Double`.
4. [ERROR] ToNumberPolicy.LONG_OR_DOUBLE.readNumber(JsonReader): rejects parsed `NaN`/infinite doubles on non-lenient readers with `MalformedJsonException` that includes the JSON path.
5. [ERROR] ToNumberPolicy.LONG_OR_DOUBLE.readNumber(JsonReader): throws `JsonParseException` with path context when the token text cannot be parsed as either long or double.
6. [METHOD] ToNumberPolicy.BIG_DECIMAL.readNumber(JsonReader): returns arbitrary-precision `BigDecimal` and throws `JsonParseException` with path context on invalid numeric text.
### gson/src/main/java/com/google/gson/ToNumberStrategy.java (2 contracts)

1. [METHOD] ToNumberStrategy.readNumber(JsonReader): must consume exactly one numeric JSON value from the reader and return a `Number`.
2. [NULL] ToNumberStrategy.readNumber(JsonReader): is guaranteed not to be called for JSON `null`; implementations may assume the returned `Number` itself is non-null.
### gson/src/main/java/com/google/gson/TypeAdapter.java (11 contracts)

1. [METHOD] TypeAdapter.write(JsonWriter,T): must write exactly one JSON value for the supplied Java value.
2. [METHOD] TypeAdapter.read(JsonReader): must read exactly one JSON value and return the converted Java value.
3. [NULL] TypeAdapter implementations are expected to handle Java nulls and JSON nulls themselves unless wrapped with `nullSafe()`.
4. [THREAD] TypeAdapter implementations are expected to be stateless and thread-safe so Gson’s thread-safety holds.
5. [METHOD] TypeAdapter.toJson(Writer,T): uses a default-configured `JsonWriter` and delegates to `write`.
6. [METHOD] TypeAdapter.toJson(T): returns the JSON string form and wraps unexpected `IOException` as `JsonIOException`.
7. [METHOD] TypeAdapter.toJsonTree(T): serializes into a `JsonElement` tree and wraps unexpected `IOException` as `JsonIOException`.
8. [METHOD] TypeAdapter.fromJson(Reader)/fromJson(String): use a default-configured `JsonReader` with `LEGACY_STRICT` strictness and intentionally do not enforce full-document consumption.
9. [METHOD] TypeAdapter.fromJsonTree(JsonElement): deserializes from a `JsonTreeReader` and wraps unexpected `IOException` as `JsonIOException`.
10. [METHOD] TypeAdapter.nullSafe(): returns a wrapper that intercepts Java null serialization and JSON null deserialization without invoking the wrapped adapter.
11. [COMPAT] TypeAdapter.nullSafe(): is idempotent for already-null-safe wrappers and returns `this` instead of double-wrapping.
### gson/src/main/java/com/google/gson/TypeAdapterFactory.java (3 contracts)

1. [METHOD] TypeAdapterFactory.create(Gson,TypeToken<T>): must return a `TypeAdapter<T>` for supported types or `null` for unsupported types.
2. [COMPAT] TypeAdapterFactory.create(...): may be called for many unrelated types, so factories are expected to reject most requests cheaply by returning `null`.
3. [LIFECYCLE] Expensive reflection/setup work should happen in `create(...)`, because the returned adapter may be reused many times after Gson caches it.
### gson/src/main/java/com/google/gson/annotations/Expose.java (3 contracts)

1. [CONFIG] `@Expose` has no effect unless Gson is built with `GsonBuilder.excludeFieldsWithoutExposeAnnotation()`.
2. [CONFIG] `@Expose.serialize()` defaults to `true`; when set to `false`, the field is skipped during serialization.
3. [CONFIG] `@Expose.deserialize()` defaults to `true`; when set to `false`, the field is skipped during deserialization.
### gson/src/main/java/com/google/gson/annotations/JsonAdapter.java (5 contracts)

1. [CONFIG] `@JsonAdapter.value()` must name a class that is a `TypeAdapter`, `TypeAdapterFactory`, or implements `JsonSerializer` and/or `JsonDeserializer`.
2. [ORDER] Field-level `@JsonAdapter` takes precedence over `GsonBuilder` registrations, which in turn take precedence over type-level `@JsonAdapter`.
3. [CONFIG] `@JsonAdapter.nullSafe()` defaults to `true`, so Gson handles Java null / JSON null without calling the adapter unless explicitly set to `false`.
4. [LIFECYCLE] Gson creates the annotated adapter using the same instantiation rules as custom-class deserialization: registered `InstanceCreator` first, then no-args constructor, then `Unsafe` as last resort.
5. [COMPAT] Gson may cache adapter instances created for `@JsonAdapter`; callers must not rely on a fresh adapter instance for every serialization/deserialization.
### gson/src/main/java/com/google/gson/annotations/SerializedName.java (3 contracts)

1. [CONFIG] `@SerializedName.value()` defines the primary JSON field name for both serialization and deserialization and overrides any active field naming policy.
2. [CONFIG] `@SerializedName.alternate()` defines additional names accepted only during deserialization.
3. [CONFIG] The declared names should be valid JSON field names; Gson will attempt to deserialize any of the declared primary/alternate names into the same field.
### gson/src/main/java/com/google/gson/annotations/Since.java (2 contracts)

1. [CONFIG] `@Since` has no effect unless Gson is built with `GsonBuilder.setVersion(double)`.
2. [CONFIG] `@Since.value()` is inclusive: annotated fields/types are included only when `gsonVersion >= value`.
### gson/src/main/java/com/google/gson/annotations/Until.java (2 contracts)

1. [CONFIG] `@Until` has no effect unless Gson is built with `GsonBuilder.setVersion(double)`.
2. [CONFIG] `@Until.value()` is exclusive: annotated fields/types are included only when `gsonVersion < value`.
### gson/src/main/java/com/google/gson/internal/$Gson$Types.java (18 contracts)

1. [LIFECYCLE] `$Gson$Types()` is a non-instantiable utility class and always throws `UnsupportedOperationException`.
2. [METHOD] `$Gson$Types.newParameterizedTypeWithOwner(...)` returns a serializable `ParameterizedType` wrapper that canonicalizes owner/raw/argument types.
3. [ERROR] `$Gson$Types.newParameterizedTypeWithOwner(...)` rejects `null` raw types, rejects primitive type arguments, and throws `IllegalArgumentException` if an owner type is required for a non-static member class but omitted.
4. [INVARIANT] `$Gson$Types.ParameterizedTypeImpl` defensively clones type arguments on construction and again from `getActualTypeArguments()`, so callers cannot mutate internal state through returned arrays.
5. [METHOD] `$Gson$Types.arrayOf(...)` returns a serializable `GenericArrayType` whose component type is canonicalized.
6. [NULL] `$Gson$Types.arrayOf(...)` rejects a `null` component type via `requireNonNull`.
7. [METHOD] `$Gson$Types.subtypeOf(...)` and `supertypeOf(...)` normalize wildcard bounds, reusing existing wildcard upper or lower bounds when passed a `WildcardType`.
8. [ERROR] `$Gson$Types.WildcardTypeImpl` permits exactly one upper bound and at most one lower bound; it rejects primitive bounds and rejects any lower-bounded wildcard whose upper bound is not `Object.class`.
9. [METHOD] `$Gson$Types.canonicalize(...)` converts arrays, parameterized types, generic arrays, and wildcards into Gson’s serializable internal implementations, but leaves unsupported `Type` implementations unchanged.
10. [METHOD] `$Gson$Types.getRawType(...)` maps `Class`, `ParameterizedType`, `GenericArrayType`, `TypeVariable`, and `WildcardType` to a raw `Class`, using `Object.class` for type variables.
11. [ERROR] `$Gson$Types.getRawType(...)` throws `IllegalArgumentException` for `null` or unsupported types, and also throws `IllegalArgumentException` if a malformed `ParameterizedType` reports a raw type that is not a `Class`.
12. [METHOD] `$Gson$Types.equals(...)` defines structural equality for supported `Type` forms; unsupported `Type` implementations compare as unequal unless they are the same reference.
13. [METHOD] `$Gson$Types.typeToString(...)` uses `Class.getName()` for classes and `Type.toString()` for all other types.
14. [METHOD] `$Gson$Types.getCollectionElementType(...)` resolves a collection supertype and returns its first actual type argument, defaulting to `Object.class` for raw collections.
15. [METHOD] `$Gson$Types.getMapKeyAndValueTypes(...)` returns key/value types for map supertypes, but special-cases only `Properties.class` itself as `String`/`String`; raw or unresolved maps default to `Object`/`Object`.
16. [METHOD] `$Gson$Types.resolve(...)` recursively resolves type variables, arrays, parameterized types, and wildcards against a context type, preserving the original object when nothing changes.
17. [INVARIANT] `$Gson$Types.resolve(...)` tracks visited type variables with a placeholder to break infinite-recursion cycles during self-referential generic resolution.
18. [COMPAT] `$Gson$Types.ParameterizedTypeImpl` accepts any non-null `Type` as `rawType` even though a parameterized raw type should effectively be a `Class`; stricter validation is absent and malformed constructions can still be created.
### gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java (14 contracts)

1. [METHOD] `ConstructorConstructor.get(TypeToken)` delegates to `get(TypeToken, true)`, so the default lookup path allows Unsafe allocation when globally enabled.
2. [METHOD] `ConstructorConstructor.get(TypeToken, boolean)` resolves constructors in strict priority order: exact-type `InstanceCreator`, raw-type `InstanceCreator`, special collection constructor, accessible no-args constructor, default collection/map implementation, instantiability failure, unsafe-disabled failure, access-filter failure, then Unsafe allocation.
3. [ERROR] `ConstructorConstructor.checkInstantiable(...)` reports interfaces and abstract classes as non-instantiable and returns user-facing remediation text instead of throwing directly.
4. [COMPAT] `ConstructorConstructor.checkInstantiable(...)` includes R8-specific guidance and a troubleshooting URL for abstract classes because code shrinking can remove constructors and mark classes abstract.
5. [METHOD] `newSpecialCollectionConstructor(...)` constructs `EnumSet` only from a parameterized type whose element type is a concrete `Class`, and constructs `EnumMap` only for the exact raw type `EnumMap.class`.
6. [ERROR] `newSpecialCollectionConstructor(...)` throws `JsonIOException` for invalid `EnumSet` or `EnumMap` type metadata instead of silently guessing an element type.
7. [METHOD] `newDefaultConstructor(...)` returns `null` for abstract classes or classes without a no-args constructor; otherwise it returns an `ObjectConstructor` that invokes that constructor reflectively.
8. [ERROR] `newDefaultConstructor(...)` returns a throwing constructor when reflection filters forbid access or when making the constructor accessible fails; invocation failures are wrapped in `RuntimeException`, and unexpected `IllegalAccessException` is converted through `ReflectionHelper`.
9. [METHOD] `newDefaultImplementationConstructor(...)` supplies concrete defaults only for recognized `Collection` and `Map` shapes; unsupported interfaces fall through to later construction strategies.
10. [METHOD] `newCollectionConstructor(...)` maps compatible collection supertypes to `ArrayList`, `LinkedHashSet`, `TreeSet`, or `ArrayDeque`, preferring the first assignable match.
11. [METHOD] `newMapConstructor(...)` maps compatible map supertypes to `LinkedTreeMap`, `LinkedHashMap`, `TreeMap`, `ConcurrentHashMap`, or `ConcurrentSkipListMap`; unrecognized map types get no default implementation.
12. [COMPAT] `newMapConstructor(...)` prefers `LinkedTreeMap` for maps with string keys, including raw maps assumed to possibly have string keys, to preserve Gson’s legacy hash-collision DoS defense.
13. [METHOD] `newUnsafeAllocator(...)` uses `UnsafeAllocator.INSTANCE` only when `useJdkUnsafe` is enabled and the caller allows Unsafe; otherwise it returns a constructor that always throws `JsonIOException`.
14. [COMPAT] `ThrowingObjectConstructor.construct()` creates and throws a fresh `JsonIOException` on every call so failures remain deferred until deserialization time and no long-lived exception object leaks memory.
### gson/src/main/java/com/google/gson/internal/Excluder.java (12 contracts)

1. [CONFIG] `Excluder.DEFAULT` excludes `transient` and `static` fields, ignores version annotations, allows inner-class serialization, does not require `@Expose`, and starts with no custom strategies.
2. [METHOD] `withVersion(...)`, `withModifiers(...)`, `disableInnerClassSerialization()`, `excludeFieldsWithoutExposeAnnotation()`, and `withExclusionStrategy(...)` all return cloned `Excluder` instances and do not mutate the original.
3. [CONFIG] `withModifiers(...)` replaces the modifier mask rather than appending to the existing default mask.
4. [METHOD] `create(...)` returns `null` when neither serialization nor deserialization is excluded for the type, allowing other factories to handle it.
5. [METHOD] `create(...)` returns a wrapper adapter when either direction is excluded; reads skip the JSON value and return `null` when deserialization is excluded, and writes emit JSON `null` when serialization is excluded.
6. [THREAD] The exclusion adapter caches its delegate in a `volatile` field so concurrent Gson use is safe even if multiple threads race to initialize the delegate.
7. [METHOD] `excludeField(...)` excludes fields matching configured modifiers, invalid `@Since`/`@Until` windows, synthetic fields, missing or disallowed `@Expose`, excluded field types, or any registered strategy that skips the field.
8. [METHOD] `excludeClass(...)` excludes classes outside the configured version window, non-static inner classes when inner-class serialization is disabled, and any class skipped by the applicable exclusion strategies.
9. [COMPAT] `excludeClass(...)` excludes anonymous and non-static local classes only for deserialization, not serialization, so custom serializers can still write them even though reflective deserialization is considered unsafe.
10. [CONFIG] Version handling is inclusive for `@Since` (`version >= annotation`) and exclusive for `@Until` (`version < annotation`).
11. [INVARIANT] `isInnerClass(...)` treats only member classes that are not static as inner classes for exclusion purposes.
12. [ERROR] `clone()` converts the impossible `CloneNotSupportedException` into `AssertionError`, making cloning failure a hard internal error.
### gson/src/main/java/com/google/gson/internal/GsonTypes.java (18 contracts)

1. [LIFECYCLE] `GsonTypes()` is a non-instantiable utility class and always throws `UnsupportedOperationException`.
2. [METHOD] `GsonTypes.newParameterizedTypeWithOwner(...)` returns a serializable `ParameterizedType` backed by canonicalized owner/raw/argument types.
3. [ERROR] `GsonTypes.newParameterizedTypeWithOwner(...)` rejects a `null` raw class, rejects primitive type arguments, and throws `IllegalArgumentException` if an owner type is required for a non-static member class but missing.
4. [INVARIANT] `GsonTypes.ParameterizedTypeImpl` clones type-argument arrays on input and output, preserving immutability of the stored generic signature.
5. [METHOD] `GsonTypes.arrayOf(...)` returns a serializable `GenericArrayType` whose component type is canonicalized.
6. [NULL] `GsonTypes.arrayOf(...)` rejects a `null` component type via `requireNonNull`.
7. [METHOD] `GsonTypes.subtypeOf(...)` and `supertypeOf(...)` normalize wildcard bounds and preserve existing wildcard upper or lower bounds when possible.
8. [ERROR] `GsonTypes.WildcardTypeImpl` throws descriptive `IllegalArgumentException`s unless there is exactly one upper bound, at most one lower bound, no primitive bounds, and any lower-bounded wildcard uses `Object.class` as its upper bound.
9. [METHOD] `GsonTypes.canonicalize(...)` rewrites arrays, parameterized types, generic arrays, and wildcards into Gson’s serializable implementations, leaving unsupported `Type` implementations unchanged.
10. [METHOD] `GsonTypes.getRawType(...)` resolves raw classes from `Class`, `ParameterizedType`, `GenericArrayType`, `TypeVariable`, and `WildcardType`, returning `Object.class` for type variables.
11. [ERROR] `GsonTypes.getRawType(...)` throws `IllegalArgumentException` for `null` or unsupported types, but a malformed `ParameterizedType` whose raw type is not a `Class` fails with `ClassCastException` because the raw type is cast directly.
12. [METHOD] `GsonTypes.equals(...)` defines structural equality for supported `Type` variants; unsupported `Type` implementations compare unequal unless they are the same reference.
13. [METHOD] `GsonTypes.typeToString(...)` uses `Class.getName()` for classes and `Type.toString()` otherwise.
14. [ERROR] `GsonTypes.getSupertype(...)` throws `IllegalArgumentException` with context if the requested supertype is not assignable from the provided raw type.
15. [METHOD] `GsonTypes.getCollectionElementType(...)` resolves the collection supertype and returns its first actual type argument, defaulting to `Object.class` for raw collections.
16. [METHOD] `GsonTypes.getMapKeyAndValueTypes(...)` special-cases `Properties` and all of its subclasses as `String`/`String`; otherwise it returns resolved map arguments or `Object`/`Object` for raw maps.
17. [METHOD] `GsonTypes.resolve(...)` recursively resolves type variables, arrays, parameterized types, and wildcards against a context type, reusing the original type object when no substitution occurs.
18. [INVARIANT] `GsonTypes.resolve(...)` records visited type variables with a placeholder so self-referential generic resolution terminates instead of recursing forever.
### gson/src/main/java/com/google/gson/internal/JavaVersion.java (6 contracts)

1. [LIFECYCLE] `JavaVersion` computes `majorJavaVersion` once at class initialization from `System.getProperty("java.version")` and thereafter serves the cached value.
2. [METHOD] `parseMajorJavaVersion(...)` first tries dotted parsing, then leading-digit extraction, and falls back to `6` if neither works.
3. [METHOD] `parseDotted(...)` supports both legacy `1.x` version strings and newer dotted/underscored formats, returning `-1` on parse failure.
4. [METHOD] `extractBeginningInt(...)` parses only the leading digit run of the version string and stops at the first non-digit.
5. [METHOD] `getMajorJavaVersion()` returns the cached major version, not a live reread of the system property.
6. [METHOD] `isJava9OrLater()` returns `true` iff the cached major version is at least 9.
### gson/src/main/java/com/google/gson/internal/JsonReaderInternalAccess.java (3 contracts)

1. [LIFECYCLE] `JsonReaderInternalAccess.INSTANCE` is a `volatile` singleton hook meant to be installed by `JsonReader` during class loading before Gson internals use it.
2. [METHOD] `promoteNameToValue(JsonReader)` is the internal contract for converting the current property-name token into a string value token.
3. [ERROR] `promoteNameToValue(JsonReader)` may throw `IOException`; no default implementation or fallback exists, so an unset `INSTANCE` would fail with a `NullPointerException` at call time.
### gson/src/main/java/com/google/gson/internal/LazilyParsedNumber.java (9 contracts)

1. [METHOD] `LazilyParsedNumber` stores the original numeric string and defers numeric conversion until a `Number` method is called.
2. [NULL] `LazilyParsedNumber(String)` documents that `value` must be non-null but does not enforce it; passing `null` succeeds initially and causes later failures such as `NullPointerException`.
3. [METHOD] `intValue()` tries `Integer.parseInt`, then `Long.parseLong` cast to `int`, then `BigDecimal.intValue()`, preserving truncation semantics of the final conversion path.
4. [METHOD] `longValue()` tries `Long.parseLong` first and falls back to `BigDecimal.longValue()`.
5. [METHOD] `floatValue()` and `doubleValue()` parse directly from the stored string with Java’s standard floating-point parsers.
6. [ERROR] Big-decimal fallback goes through `NumberLimits.parseBigDecimal(...)`, so excessively long numbers or unsupported scales fail with `NumberFormatException`.
7. [METHOD] `toString()` returns the original source string exactly, not a normalized numeric rendering.
8. [COMPAT] `writeReplace()` serializes the number as a `BigDecimal` so Java serialization does not require Gson-specific classes on the receiving side.
9. [LIFECYCLE] `readObject(...)` always throws `InvalidObjectException`, making direct Java deserialization of `LazilyParsedNumber` unsupported.
### gson/src/main/java/com/google/gson/internal/LinkedTreeMap.java (19 contracts)

1. [ORDER] `LinkedTreeMap` preserves insertion order for iteration even though it uses key comparison order internally for lookup and balancing.
2. [METHOD] `LinkedTreeMap()` creates a naturally ordered map with non-null comparable keys and allows `null` values.
3. [CONFIG] `LinkedTreeMap(boolean allowNullValues)` keeps natural key ordering and configures whether stored values may be `null`.
4. [CONFIG] `LinkedTreeMap(Comparator, boolean)` substitutes natural ordering when the comparator is `null`; the public API still rejects `null` keys regardless of comparator behavior.
5. [METHOD] `size()`, `get(...)`, `containsKey(...)`, `remove(...)`, and `clear()` implement normal map semantics, with `get`/`remove` returning `null` when no mapping exists.
6. [ERROR] `put(...)` always throws `NullPointerException("key == null")` for a `null` key and throws `NullPointerException("value == null")` when `allowNullValues` is `false` and a `null` value is inserted.
7. [METHOD] `put(...)` inserts or replaces the mapping and returns the previous value associated with the key.
8. [ERROR] `find(K, boolean)` throws `ClassCastException` when natural ordering is used with a non-`Comparable` key or when keys are otherwise not mutually comparable.
9. [COMPAT] `findByObject(...)` catches `ClassCastException` and treats incompatible keys as absent, so `get`, `containsKey`, and `remove` return “not found” instead of throwing for wrong key types.
10. [INVARIANT] The tree remains AVL-balanced after insertions and removals, and every structural mutation updates both the tree links and the insertion-order linked list.
11. [INVARIANT] `header` is a sentinel node whose `next`/`prev` links always anchor iteration order; `clear()` resets those links back to the sentinel itself.
12. [METHOD] `findByEntry(...)` matches entries by comparator-based key lookup plus value equality, not by raw `Map.Entry.equals` key lookup alone.
13. [COMPAT] If the comparator is inconsistent with `equals`, `entrySet().contains(...)` and `entrySet().remove(...)` can violate normal collections expectations because key equality follows comparator order.
14. [METHOD] `entrySet()` and `keySet()` lazily allocate and cache live view objects, returning the same view instance on subsequent calls.
15. [METHOD] `Node.setValue(...)` enforces the map’s null-value policy, returns the old value, and updates only that entry.
16. [METHOD] `Node.equals(...)`, `hashCode()`, and `toString()` implement standard `Map.Entry` semantics using key/value equality and `"key=value"` formatting.
17. [ERROR] Iterators are fail-fast: `next()` throws `NoSuchElementException` at the end and throws `ConcurrentModificationException` if the map was structurally modified outside the iterator.
18. [ERROR] Iterator `remove()` throws `IllegalStateException` unless a successful `next()` has occurred since the last removal.
19. [LIFECYCLE] `writeReplace()` serializes the map as a `LinkedHashMap`, and `readObject(...)` always throws `InvalidObjectException`, so direct Java deserialization of `LinkedTreeMap` is unsupported.
### gson/src/main/java/com/google/gson/internal/NonNullElementWrapperList.java (7 contracts)

1. [METHOD] `NonNullElementWrapperList` is a `RandomAccess` list wrapper over an `ArrayList` delegate and forwards read-only and bulk operations to that delegate.
2. [NULL] `NonNullElementWrapperList(ArrayList)` rejects a `null` delegate via `Objects.requireNonNull`.
3. [ERROR] `set(...)` and `add(int, E)` reject `null` elements with `NullPointerException("Element must be non-null")`.
4. [NULL] Query-style methods such as `contains`, `indexOf`, `lastIndexOf`, and `remove(Object)` do not reject `null` arguments and simply delegate to the wrapped list.
5. [METHOD] `clear`, `remove`, `removeAll`, `retainAll`, `toArray`, `equals`, and `hashCode` mirror the delegate’s behavior and complexity.
6. [INVARIANT] The wrapper prevents `null` insertion only for mutations performed through the wrapper itself.
7. [COMPAT] If the wrapped `ArrayList` already contains `null` or is mutated externally, the wrapper does not repair or prevent those `null`s, so “non-null elements” is not an absolute global invariant.
### gson/src/main/java/com/google/gson/internal/NumberLimits.java (5 contracts)

1. [CONFIG] `NumberLimits` caps accepted numeric string length at 10,000 characters.
2. [ERROR] `checkNumberStringLength(...)` throws `NumberFormatException` for oversized inputs and includes only the first 30 characters plus `...` in the message.
3. [METHOD] `parseBigDecimal(...)` enforces the length limit, parses with `BigDecimal`, and then rejects values whose absolute scale is 10,000 or greater.
4. [METHOD] `parseBigInteger(...)` enforces the length limit and then parses with `BigInteger`, with no additional scale check.
5. [NULL] Both parsing methods assume a non-null string; passing `null` fails with `NullPointerException` rather than `NumberFormatException`.
### gson/src/main/java/com/google/gson/internal/ObjectConstructor.java (3 contracts)

1. [METHOD] `ObjectConstructor.construct()` is the internal factory contract for producing an object instance used during deserialization.
2. [COMPAT] The interface itself is intentionally minimal and does not require implementations to use constructors, return fresh instances, or avoid throwing.
3. [NULL] The interface does not forbid returning `null`; any non-null/fresh-instance guarantee must come from the specific implementation.
### gson/src/main/java/com/google/gson/internal/PreJava9DateFormatProvider.java (4 contracts)

1. [METHOD] `getUsDateTimeFormat(...)` returns a new `SimpleDateFormat` using the US-locale date/time patterns that matched Java 8 and earlier defaults.
2. [CONFIG] Date styles map to fixed patterns: `SHORT`=`M/d/yy`, `MEDIUM`=`MMM d, yyyy`, `LONG`=`MMMM d, yyyy`, `FULL`=`EEEE, MMMM d, yyyy`.
3. [CONFIG] Time styles map to fixed patterns: `SHORT`=`h:mm a`, `MEDIUM`=`h:mm:ss a`, and both `LONG` and `FULL`=`h:mm:ss a z`.
4. [ERROR] Unknown date or time style integers throw `IllegalArgumentException` naming the unsupported style value.
### gson/src/main/java/com/google/gson/internal/Primitives.java (5 contracts)

1. [METHOD] `isPrimitive(Type)` returns `true` only when the argument is a `Class` representing a primitive type; all other `Type` implementations return `false`.
2. [METHOD] `isWrapperType(Type)` recognizes exactly the nine Java wrapper/reference counterparts: `Integer`, `Float`, `Byte`, `Double`, `Long`, `Character`, `Boolean`, `Short`, and `Void`.
3. [METHOD] `wrap(Class)` maps primitive classes to wrapper classes and otherwise returns the input unchanged, making it idempotent.
4. [METHOD] `unwrap(Class)` maps wrapper classes to primitive classes and otherwise returns the input unchanged, making it idempotent.
5. [NULL] `wrap(null)` and `unwrap(null)` return `null` because neither method performs a null check.
### gson/src/main/java/com/google/gson/internal/ReflectionAccessFilterHelper.java (7 contracts)

1. [METHOD] `isJavaType(...)` treats any class name starting with `java.` or `javax.` as a Java platform type.
2. [METHOD] `isAndroidType(...)` treats `android.*`, `androidx.*`, and all Java platform types as Android/platform types.
3. [METHOD] `isAnyPlatformType(...)` extends platform detection to Android/Java plus `kotlin.*`, `kotlinx.*`, and `scala.*`.
4. [METHOD] `getFilterResult(...)` applies reflection filters in list order and returns the first decisive result; if all filters are indecisive, it defaults to `FilterResult.ALLOW`.
5. [CONFIG] Filter ordering is behaviorally significant because later filters are ignored once an earlier filter returns anything other than `INDECISIVE`.
6. [METHOD] `canAccess(...)` delegates to a version-specific `AccessChecker` that uses `AccessibleObject.canAccess` reflectively on Java 9+ when available.
7. [COMPAT] If `canAccess` reflection is unavailable, `ReflectionAccessFilterHelper` assumes access is allowed; if reflective invocation itself fails, it throws `RuntimeException("Failed invoking canAccess", cause)`.
### gson/src/main/java/com/google/gson/internal/Streams.java (10 contracts)

1. [LIFECYCLE] `Streams()` is a non-instantiable utility class and always throws `UnsupportedOperationException`.
2. [METHOD] `Streams.parse(JsonReader)` reads the next JSON value from the reader’s current state and returns it as a `JsonElement`.
3. [COMPAT] `Streams.parse(...)` returns `JsonNull.INSTANCE` for an empty document instead of throwing, preserving pre-1.6 Gson behavior.
4. [ERROR] `Streams.parse(...)` converts premature EOF after parsing has started, malformed JSON, and number-format failures into `JsonSyntaxException`.
5. [ERROR] `Streams.parse(...)` converts other `IOException`s into `JsonIOException`.
6. [METHOD] `Streams.write(...)` serializes a `JsonElement` recursively through `JsonElementTypeAdapter.ADAPTER`.
7. [METHOD] `writerForAppendable(...)` returns the input unchanged when it is already a `Writer`; otherwise it wraps the `Appendable` in an internal `Writer` adapter.
8. [METHOD] `AppendableWriter.flush()` and `close()` are conditional no-ops unless the wrapped appendable also implements `Flushable` or `Closeable`.
9. [NULL] `AppendableWriter.write(String, int, int)` rejects `null` strings with `NullPointerException` instead of letting `Appendable.append` convert `null` into the literal text `"null"`.
10. [INVARIANT] `CurrentWrite.toString()` caches and returns the string representation of the current char array, while `setChars(...)` invalidates that cache before reuse.
### gson/src/main/java/com/google/gson/internal/TroubleshootingGuide.java (3 contracts)

1. [LIFECYCLE] `TroubleshootingGuide()` is a non-instantiable utility class.
2. [METHOD] `createUrl(String id)` always returns `https://github.com/google/gson/blob/main/Troubleshooting.md#` plus the provided fragment id.
3. [NULL] `createUrl(null)` does not reject `null`; it returns a URL ending in `#null`, so fragment validation/escaping is the caller’s responsibility.
### gson/src/main/java/com/google/gson/internal/UnsafeAllocator.java (6 contracts)

1. [METHOD] `UnsafeAllocator` is an abstraction for allocating instances without invoking constructors.
2. [LIFECYCLE] `UnsafeAllocator.INSTANCE` is chosen once at class initialization by trying multiple allocation backends in order and keeping the first one that works.
3. [METHOD] `create()` tries `sun.misc.Unsafe.allocateInstance`, then `ObjectStreamClass.newInstance(Class,int)`, then `ObjectInputStream.newInstance(Class,Class)`, and falls back only if all fail.
4. [ERROR] Every successful backend calls `assertInstantiable(...)`, which throws `AssertionError` if asked to allocate an interface or abstract class as a safeguard against JVM crashes.
5. [ERROR] Backend `newInstance(...)` methods may propagate reflective failures from the underlying allocation mechanism.
6. [ERROR] If no backend is usable, the fallback allocator always throws `UnsupportedOperationException` explaining that Unsafe use was enabled but unavailable at runtime.
### gson/src/main/java/com/google/gson/internal/bind/ArrayTypeAdapter.java (9 contracts)

1. [METHOD] FACTORY.create(): returns null for any type that is neither a `GenericArrayType` nor an array `Class`; only array types receive this adapter
2. [METHOD] ArrayTypeAdapter constructor: wraps the component adapter in `TypeAdapterRuntimeTypeWrapper` so that runtime subtype adapters are preferred during serialization
3. [NULL] read(): if the next JSON token is `NULL`, consumes it and returns Java `null`
4. [METHOD] read(): deserializes a JSON array into a Java array whose component type matches the type token; for primitive component types copies elements one-by-one via `Array.set` (not `toArray`) to avoid boxing failures
5. [METHOD] read(): for non-primitive component types uses `ArrayList.toArray(E[])` to produce a typed array
6. [NULL] write(): if the array value is Java `null`, writes a JSON null
7. [METHOD] write(): iterates elements via `Array.getLength`/`Array.get`, so it works on both primitive and object arrays without casting to `Object[]`
8. [ORDER] write(): array element order in JSON exactly matches the order of elements in the source Java array
9. [INVARIANT] The component type adapter used for every element is always the same `TypeAdapterRuntimeTypeWrapper`-wrapped adapter; individual elements cannot select different adapters per-element during deserialization (read uses the adapter directly)
### gson/src/main/java/com/google/gson/internal/bind/CollectionTypeAdapterFactory.java (8 contracts)

1. [METHOD] create(): returns null for any type whose raw class is not assignable to `Collection`
2. [CONFIG] allowUnsafe=false: `ConstructorConstructor` is never asked to use Unsafe to instantiate the collection, preventing partially-initialised instances from having `Collection` methods called on them
3. [METHOD] Adapter.read(): wraps the element adapter in `TypeAdapterRuntimeTypeWrapper` so runtime subtypes are respected during element serialization
4. [NULL] Adapter.read(): if the next JSON token is `NULL`, consumes it and returns Java `null`
5. [METHOD] Adapter.read(): expects a JSON array; reads each element with the element adapter and adds it to a freshly-constructed collection
6. [NULL] Adapter.write(): if the collection is Java `null`, writes a JSON null
7. [METHOD] Adapter.write(): iterates the collection using its own iterator; element order in JSON mirrors the collection's iteration order
8. [ORDER] Output order is stable and determined by the collection's own iteration order (undefined for `HashSet`, stable for `LinkedHashSet`/`List`, etc.)
### gson/src/main/java/com/google/gson/internal/bind/DefaultDateTypeAdapter.java (13 contracts)

1. [METHOD] DEFAULT_STYLE_FACTORY.create(): matches only `Date.class` exactly (not subclasses); always creates a new `DefaultDateTypeAdapter` instance per call so that `SimpleDateFormat` captures the current default `TimeZone` at that moment
2. [LIFECYCLE] Constructor with pattern string: adds a Locale.US `SimpleDateFormat`; if the JVM default locale differs from `Locale.US`, also adds a default-locale `SimpleDateFormat` as a fallback deserialisation format
3. [LIFECYCLE] Constructor with int/int styles: adds Locale.US + default-locale `DateFormat.getDateTimeInstance`; on Java 9+, additionally adds a `PreJava9DateFormatProvider` format for round-trip compatibility
4. [NULL] write(): if the `Date` value is `null`, writes a JSON null
5. [METHOD] write(): serializes using `dateFormats.get(0)` (the Locale.US format) regardless of how many formats are in the list
6. [THREAD] write(): synchronises on `dateFormats` before calling `DateFormat.format()` because `DateFormat` is not thread-safe
7. [NULL] read(): if the next JSON token is `NULL`, consumes it and returns `null`
8. [METHOD] read(): attempts each format in `dateFormats` in order; if all fail, falls back to `ISO8601Utils.parse()`
9. [ERROR] read(): if ISO8601 parsing also fails, throws `JsonSyntaxException` containing the raw input string and the current reader path
10. [LIFECYCLE] deserializeToDate(): restores each `DateFormat`'s original `TimeZone` in a `finally` block after each parse attempt, preventing timezone leakage between calls
11. [THREAD] read(): synchronises on `dateFormats` for the whole multi-format try loop
12. [METHOD] DateType.DATE.deserialize(): returns the `java.util.Date` instance unchanged (identity)
13. [METHOD] toString(): returns `"DefaultDateTypeAdapter(pattern)"` for `SimpleDateFormat`, or `"DefaultDateTypeAdapter(ClassName)"` for other `DateFormat` subclasses
### gson/src/main/java/com/google/gson/internal/bind/EnumTypeAdapter.java (11 contracts)

1. [METHOD] FACTORY.create(): returns null for `Enum.class` itself; for an anonymous subclass of an enum, climbs to the declaring enum class via `getSuperclass()`
2. [METHOD] Constructor: discovers constants via `getDeclaredFields` + `isEnumConstant()` (not `Enum.values()`) to work with obfuscated class names
3. [METHOD] Constructor: if a field has `@SerializedName`, its `value()` becomes the primary serialized name and each `alternate()` is registered in `nameToConstant` as an additional deserialization alias
4. [INVARIANT] `constantToName` always maps to the primary serialized name (the single name used for serialization)
5. [METHOD] Constructor: `stringToConstant` maps each constant's `toString()` value; this provides a fallback lookup during deserialization
6. [COMPAT] `HashMap` is used instead of `EnumMap` to preserve behaviour under ProGuard/R8 obfuscation
7. [NULL] read(): if the next JSON token is `NULL`, consumes it and returns `null`
8. [METHOD] read(): first checks `nameToConstant`; if not found, falls back to `stringToConstant`; if still not found, returns `null` (no exception)
9. [NULL] write(): if the enum value is `null`, calls `out.value((String) null)` which writes a JSON null
10. [INVARIANT] No duplicate-name detection between `@SerializedName.value()` and `alternate()` values; a later `put` will silently overwrite an earlier entry in `nameToConstant`
11. [THREAD] `nameToConstant`, `stringToConstant`, and `constantToName` are built once in the constructor and never mutated afterwards; the adapter is effectively immutable and safe for concurrent reads
### gson/src/main/java/com/google/gson/internal/bind/IgnoreJRERequirement.java (0 contracts)

Trivial — a marker annotation used internally to suppress Animal Sniffer JRE requirement checks. It has no runtime behaviour or behavioral contracts.
### gson/src/main/java/com/google/gson/internal/bind/JavaTimeTypeAdapters.java (21 contracts)

1. [METHOD] JAVA_TIME_FACTORY.create(): returns `null` immediately if the raw class name does not start with `"java.time."`, avoiding eager classloading of all `java.time` classes
2. [COMPAT] All serialized formats deliberately freeze the reflective JDK 21 field layout (e.g., `seconds`/`nanos`, `year`/`month`/`day`) to avoid using reflection on private JDK fields and `--add-opens` requirements
3. [METHOD] Duration: serialized as `{"seconds": long, "nanos": long}`
4. [METHOD] Instant: serialized as `{"seconds": long, "nanos": long}`
5. [METHOD] LocalDate: serialized as `{"year": int, "month": int, "day": int}`
6. [METHOD] LocalTime: serialized as `{"hour": int, "minute": int, "second": int, "nano": int}`
7. [METHOD] LocalDateTime: serialized as `{"date": <LocalDate>, "time": <LocalTime>}`; wrapped with `nullSafe()`
8. [ERROR] LocalDateTime.read(): if `"date"` or `"time"` field is absent from the JSON object, throws `JsonSyntaxException("Missing <fieldName> field; at path ...")`
9. [METHOD] MonthDay: serialized as `{"month": int, "day": int}`
10. [METHOD] OffsetDateTime: serialized as `{"dateTime": <LocalDateTime>, "offset": <ZoneOffset>}`; null-safe; throws `JsonSyntaxException` if `"dateTime"` or `"offset"` missing
11. [METHOD] OffsetTime: serialized as `{"time": <LocalTime>, "offset": <ZoneOffset>}`; null-safe; throws `JsonSyntaxException` if `"time"` or `"offset"` missing
12. [METHOD] Period: serialized as `{"years": int, "months": int, "days": int}`
13. [METHOD] Year: serialized as `{"year": int}`
14. [METHOD] YearMonth: serialized as `{"year": int, "month": int}`
15. [METHOD] ZoneId (ZoneRegion subtype): serialized as `{"id": string}` using `ZoneId.getId()`
16. [METHOD] ZoneOffset: serialized as `{"totalSeconds": int}` using `ZoneOffset.getTotalSeconds()`
17. [ERROR] ZoneId.read(): if JSON object contains neither `"id"` nor `"totalSeconds"`, throws `JsonSyntaxException("Missing id or totalSeconds field; at path ...")`
18. [METHOD] ZonedDateTime: serialized as `{"dateTime": <LocalDateTime>, "offset": <ZoneOffset>, "zone": <ZoneId>}`; null-safe; throws `JsonSyntaxException` if any of the three fields is absent
19. [METHOD] FACTORY matches `ZoneId.class` and `ZoneOffset.class` by exact identity (not `isAssignableFrom`) to prevent matching the non-public `ZoneRegion` at runtime, preserving user-registered `ZoneId` adapter precedence
20. [METHOD] Extra JSON fields during deserialization of any `java.time` type are silently skipped via `in.skipValue()`
21. [ERROR] `toIntExact()` calls throw `ArithmeticException` (not a Gson exception) if a long value exceeds `int` range during deserialization of types with `int`-ranged fields
### gson/src/main/java/com/google/gson/internal/bind/JsonAdapterAnnotationTypeAdapterFactory.java (13 contracts)

1. [METHOD] create(): returns `null` if the raw type bears no `@JsonAdapter` annotation
2. [ERROR] getTypeAdapter(): if the `@JsonAdapter.value()` class is not a `TypeAdapter`, `TypeAdapterFactory`, `JsonSerializer`, or `JsonDeserializer`, throws `IllegalArgumentException` naming the offending class
3. [METHOD] getTypeAdapter(): for `TypeAdapterFactory` values on a class annotation, caches the factory instance in a `ConcurrentHashMap` keyed by raw type using `putIfAbsent` to ensure a single shared instance per type
4. [THREAD] `adapterFactoryMap` is a `ConcurrentHashMap`; concurrent requests for the same type may race to create a factory but `putIfAbsent` guarantees all threads observe the same instance thereafter
5. [CONFIG] `@JsonAdapter.nullSafe() = true` (the default): the produced adapter is wrapped with `nullSafe()` unless the adapter is a `TreeTypeAdapter` (which manages null handling internally)
6. [CONFIG] `@JsonAdapter.nullSafe() = false`: the produced adapter is used as-is without a `nullSafe()` wrapper
7. [METHOD] For `JsonSerializer`/`JsonDeserializer` values, wraps in a `TreeTypeAdapter` with a `DummyTypeAdapterFactory` as `skipPast`, using `TREE_TYPE_CLASS_DUMMY_FACTORY` for class-level annotations and `TREE_TYPE_FIELD_DUMMY_FACTORY` for field-level annotations
8. [METHOD] isClassJsonAdapterFactory(): `TREE_TYPE_CLASS_DUMMY_FACTORY` is always recognized as a class-level annotation factory regardless of type
9. [METHOD] isClassJsonAdapterFactory(): for factory values, uses reference equality (not `.equals()`) to compare with the cached factory
10. [METHOD] isClassJsonAdapterFactory(): if the factory has not yet been cached for the type, creates one by inspecting the `@JsonAdapter` annotation to ensure consistent results regardless of call order
11. [NULL] isClassJsonAdapterFactory(): both `type` and `factory` arguments are required non-null; `Objects.requireNonNull` throws `NullPointerException` otherwise
12. [LIFECYCLE] createAdapter(): uses `ConstructorConstructor` with `allowUnsafe=true`, so adapter classes may be instantiated even without a no-arg constructor
13. [INVARIANT] Field-level `@JsonAdapter` annotations are never cached (only class-level ones are); a new adapter instance may be created per field use
### gson/src/main/java/com/google/gson/internal/bind/JsonElementTypeAdapter.java (17 contracts)

1. [INVARIANT] `ADAPTER` is a singleton (`public static final`); the class has a private constructor
2. [METHOD] read(): if the reader is a `JsonTreeReader`, delegates directly to `nextJsonElement()` for zero-copy extraction
3. [METHOD] read(): `STRING` token → `new JsonPrimitive(String)` (exact string value)
4. [METHOD] read(): `NUMBER` token → `new JsonPrimitive(new LazilyParsedNumber(rawString))` — preserves the raw JSON number string without eager parsing
5. [METHOD] read(): `BOOLEAN` token → `new JsonPrimitive(boolean)`
6. [METHOD] read(): `NULL` token → `JsonNull.INSTANCE`
7. [METHOD] read(): `BEGIN_ARRAY` → recursively builds a `JsonArray` containing all nested elements
8. [METHOD] read(): `BEGIN_OBJECT` → recursively builds a `JsonObject` containing all nested name/value pairs
9. [ERROR] read(): any other token (e.g., `NAME`, `END_ARRAY`, `END_OBJECT`) throws `IllegalStateException("Unexpected token: " + peeked)`
10. [NULL] write(): Java `null` reference or `JsonNull` → `out.nullValue()`
11. [METHOD] write(): `JsonPrimitive` number → `out.value(Number)`
12. [METHOD] write(): `JsonPrimitive` boolean → `out.value(boolean)`
13. [METHOD] write(): `JsonPrimitive` string → `out.value(String)`
14. [METHOD] write(): `JsonArray` → recursively writes each element as a JSON array
15. [METHOD] write(): `JsonObject` → writes each key-value pair; key order is determined by `JsonObject.entrySet()` iteration order
16. [ERROR] write(): an unknown `JsonElement` subclass (not Primitive, Array, Object, or Null) throws `IllegalArgumentException("Couldn't write " + value.getClass())`
17. [INVARIANT] Numbers deserialized via read() are always `LazilyParsedNumber` instances; their string representation is the verbatim JSON number token
### gson/src/main/java/com/google/gson/internal/bind/JsonTreeReader.java (23 contracts)

1. [LIFECYCLE] Constructor: takes a `JsonElement` and pushes it as the single root on an internal stack backed by a 32-element array; uses an `UNREADABLE_READER` sentinel to prevent accidental stream reads
2. [METHOD] peek(): returns `END_DOCUMENT` if the stack is empty; throws `IllegalStateException("JsonReader is closed")` if `SENTINEL_CLOSED` is on top; throws `MalformedJsonException` for any unrecognised (`custom`) `JsonElement` subclass
3. [METHOD] beginArray(): requires `BEGIN_ARRAY` token; pushes an `Iterator` over the array and resets path index to `0`
4. [METHOD] endArray(): requires `END_ARRAY` token; pops iterator then array; increments parent path index
5. [METHOD] beginObject(): requires `BEGIN_OBJECT` token; pushes `entrySet().iterator()`
6. [METHOD] endObject(): requires `END_OBJECT` token; nulls the current path name to permit GC; pops iterator then object; increments parent path index
7. [METHOD] nextString(): accepts both `STRING` and `NUMBER` tokens (coerces numbers to string); throws `IllegalStateException` for any other token
8. [METHOD] nextDouble(): accepts `NUMBER` or `STRING`; when not lenient, throws `MalformedJsonException` for `NaN` or `Infinity`
9. [METHOD] nextLong(): accepts `NUMBER` or `STRING`
10. [METHOD] nextInt(): accepts `NUMBER` or `STRING`
11. [METHOD] nextBoolean(): requires `BOOLEAN` token
12. [METHOD] nextNull(): requires `NULL` token; increments parent path index
13. [METHOD] nextJsonElement(): throws `IllegalStateException` for `NAME`, `END_ARRAY`, `END_OBJECT`, `END_DOCUMENT`; returns the current `JsonElement` and advances via `skipValue()`
14. [METHOD] skipValue(): treats `NAME` as a name-skip (records `"<skipped>"` in path); handles `END_ARRAY`/`END_OBJECT` by calling the corresponding `end*()` method; does nothing for `END_DOCUMENT`; pops stack and increments path index for all other tokens
15. [LIFECYCLE] close(): replaces the entire stack with `new Object[]{SENTINEL_CLOSED}` and sets `stackSize=1`; all subsequent `peek()` calls throw `IllegalStateException`
16. [METHOD] getPath(): builds a `$`-prefixed JSONPath string reflecting the current reader position; array indices point to the next element to be read
17. [METHOD] getPreviousPath(): same as `getPath()` but decrements the last array index by 1 when it is the top of stack, to refer to the last-consumed element
18. [METHOD] promoteNameToValue(): consumes the next object entry's key and pushes both its value and a `JsonPrimitive` of the key name onto the stack
19. [LIFECYCLE] push(): dynamically doubles all three arrays (`stack`, `pathIndices`, `pathNames`) when capacity is reached
20. [ORDER] Object member iteration follows `JsonObject.entrySet()` iteration order (insertion order)
21. [INVARIANT] The stack always contains either a `JsonElement`, an `Iterator`, or `SENTINEL_CLOSED`; encountering any other object type is a programming error that throws `MalformedJsonException`
22. [METHOD] hasNext(): returns `false` for `END_OBJECT`, `END_ARRAY`, or `END_DOCUMENT`; `true` for any other token
23. [METHOD] toString(): returns `"JsonTreeReader at path " + getPath()`
### gson/src/main/java/com/google/gson/internal/bind/JsonTreeWriter.java (18 contracts)

1. [LIFECYCLE] Constructor: uses an `UNWRITABLE_WRITER` sentinel; any direct write to the underlying `Writer` throws `AssertionError`
2. [METHOD] get(): throws `IllegalStateException` if the internal stack is not empty (document is still being built); returns `JsonNull.INSTANCE` if nothing was written
3. [CONFIG] serializeNulls: when `false`, `put()` skips null values written as object field values (`pendingName != null && value.isJsonNull()`)
4. [METHOD] beginArray(): creates a `JsonArray`, adds it to the current context, and pushes it on the stack
5. [METHOD] endArray(): throws `IllegalStateException` if the stack is empty, a pending name exists, or the top of the stack is not a `JsonArray`
6. [METHOD] beginObject(): creates a `JsonObject`, adds it to the current context, and pushes it on the stack
7. [METHOD] endObject(): throws `IllegalStateException` if the stack is empty, a pending name exists, or the top of the stack is not a `JsonObject`
8. [NULL] name(): throws `NullPointerException` if the name argument is `null` (via `Objects.requireNonNull`)
9. [ERROR] name(): throws `IllegalStateException` if stack is empty, a `pendingName` already exists, or the top element is not a `JsonObject`
10. [NULL] value(String): delegates `null` to `nullValue()` rather than writing a `JsonPrimitive`
11. [NULL] value(Boolean boxed): delegates `null` to `nullValue()`
12. [ERROR] value(float): throws `IllegalArgumentException` for `NaN` or `Infinity` when not lenient
13. [ERROR] value(double): throws `IllegalArgumentException` for `NaN` or `Infinity` when not lenient
14. [ERROR] value(Number): throws `IllegalArgumentException` when not lenient if `doubleValue()` is `NaN` or `Infinity`; delegates `null` to `nullValue()`
15. [METHOD] jsonValue(String): always throws `UnsupportedOperationException`
16. [METHOD] flush(): no-op; does nothing
17. [LIFECYCLE] close(): throws `IOException("Incomplete document")` if the stack is not empty; otherwise pushes `SENTINEL_CLOSED` so that subsequent operations on the internal stack cause `IndexOutOfBoundsException`
18. [INVARIANT] After `close()`, the `SENTINEL_CLOSED` sentinel on the stack causes `peek()` to crash on the next operation, preventing continued use of the writer
### gson/src/main/java/com/google/gson/internal/bind/MapTypeAdapterFactory.java (15 contracts)

1. [METHOD] create(): returns `null` for any type not assignable to `Map`
2. [CONFIG] allowUnsafe=false: `ConstructorConstructor` is never asked to use Unsafe to instantiate `Map` instances, preventing broken map state
3. [METHOD] getKeyAdapter(): `boolean`/`Boolean` keys always use `TypeAdapters.BOOLEAN_AS_STRING` (writes `"true"`/`"false"` as JSON strings); all other key types use their normal adapter
4. [METHOD] Key and value adapters are each wrapped in `TypeAdapterRuntimeTypeWrapper` to respect runtime subtypes
5. [NULL] Adapter.read(): if the next JSON token is `NULL`, consumes it and returns `null`
6. [METHOD] Adapter.read(): if JSON is a `BEGIN_ARRAY`, parses as an array of two-element `[key, value]` arrays
7. [METHOD] Adapter.read(): if JSON is a `BEGIN_OBJECT`, uses `JsonReaderInternalAccess.promoteNameToValue` to feed the member name through the key adapter
8. [ERROR] Adapter.read(): duplicate keys in either JSON array or JSON object form throw `JsonSyntaxException("duplicate key: " + key)`
9. [NULL] Adapter.write(): if the map is `null`, writes a JSON null
10. [CONFIG] complexMapKeySerialization=false: always serializes as a JSON object using `String.valueOf(key)` as the field name, regardless of key type
11. [CONFIG] complexMapKeySerialization=true: first converts each key to its JSON tree; if any key is a JSON array or JSON object, the entire map is serialized as a JSON array of `[key, value]` pairs
12. [CONFIG] complexMapKeySerialization=true, all keys primitive: even with complex-key serialization enabled, the map is serialized as a JSON object if no key resolves to a complex JSON value
13. [METHOD] keyToString(): converts `JsonNull` to the literal string `"null"`; handles number, boolean, and string primitives; throws `AssertionError` for complex key elements (should be unreachable in object-form path)
14. [ORDER] Output entry order exactly follows the map's `entrySet()` iteration order
15. [COMPAT] When `complexMapKeySerialization=false`, non-string keys are serialized via `String.valueOf(key)`, which cannot be round-tripped through the key adapter on deserialization for non-string key types
16. [SHOULD-EXIST] There is no validation that keys read during object-form deserialization are unique before insertion; the check is post-`put` (returns non-null replaced value), so the last-write wins is not possible — the exception fires immediately on any duplicate
### gson/src/main/java/com/google/gson/internal/bind/NumberTypeAdapter.java (6 contracts)

1. [METHOD] getFactory(): returns the shared `LAZILY_PARSED_NUMBER_FACTORY` singleton when `toNumberStrategy == ToNumberPolicy.LAZILY_PARSED_NUMBER`; creates a new factory for all other strategies
2. [METHOD] FACTORY.create(): matches only exactly `Number.class` (not subclasses)
3. [NULL] read(): if the next JSON token is `NULL`, consumes it and returns `null`
4. [METHOD] read(): accepts `NUMBER` or `STRING` tokens and delegates to `toNumberStrategy.readNumber()`
5. [ERROR] read(): any token other than `NULL`, `NUMBER`, or `STRING` throws `JsonSyntaxException("Expecting number, got: <token>; at path <path>")`
6. [METHOD] write(): delegates directly to `out.value(Number)` with no null guard
7. [SHOULD-EXIST] write() has no null check; passing `null` directly (bypassing a `nullSafe()` wrapper) will result in a `NullPointerException` or implementation-defined behavior from `JsonWriter`
### gson/src/main/java/com/google/gson/internal/bind/ObjectTypeAdapter.java (14 contracts)

1. [METHOD] getFactory(): returns the shared `DOUBLE_FACTORY` singleton when `toNumberStrategy == ToNumberPolicy.DOUBLE`; creates a new factory otherwise
2. [METHOD] FACTORY.create(): matches only exactly `Object.class`; returns `null` for all other types
3. [METHOD] read(): JSON object → `LinkedTreeMap<String, Object>`
4. [METHOD] read(): JSON array → `ArrayList<Object>`
5. [METHOD] read(): `STRING` token → `String`
6. [METHOD] read(): `NUMBER` token → result of `toNumberStrategy.readNumber()` (strategy-dependent numeric type)
7. [METHOD] read(): `BOOLEAN` token → `Boolean`
8. [NULL] read(): `NULL` token → Java `null`
9. [ERROR] read(): any other token throws `IllegalStateException("Unexpected token: " + peeked)`
10. [NULL] write(): `null` value → `out.nullValue()`
11. [METHOD] write(): uses `gson.getAdapter(value.getClass())` (runtime type) for serialization
12. [COMPAT] write(): if the runtime adapter is an `ObjectTypeAdapter` itself (to avoid infinite recursion), writes `{}` (empty JSON object) instead of delegating
13. [METHOD] write(): for all other runtime adapters, delegates to the actual adapter, effectively providing polymorphic serialization
14. [INVARIANT] Objects of unknown type that map back to `ObjectTypeAdapter` always serialize as `{}`, which is a silent data loss — there is no warning or exception
### gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java (25 contracts)

1. [METHOD] create(): returns `null` for primitive types (those not assignable to `Object`)
2. [COMPAT] create(): anonymous classes and non-static local classes produce a special adapter that always reads null/writes null, for backward compatibility (synthetic captured-value fields make reflection unreliable)
3. [ERROR] create(): `FilterResult.BLOCK_ALL` from any `ReflectionAccessFilter` throws `JsonIOException` naming the blocked type
4. [CONFIG] FilterResult.BLOCK_INACCESSIBLE: access checks for fields and constructors are deferred to the point of use; `setAccessible` is not called at adapter creation time
5. [METHOD] create(): Java records use `RecordAdapter`; all other types use `FieldReflectionAdapter`
6. [METHOD] getBoundFields(): returns `FieldsData.EMPTY` for interface types (no fields)
7. [METHOD] getBoundFields(): traverses the class hierarchy up to (but not including) `Object.class`; re-evaluates the `ReflectionAccessFilter` result for each superclass
8. [ERROR] getBoundFields(): two fields (or a field and its alternate `@SerializedName`) that map to the same JSON name throw `IllegalArgumentException` at adapter-creation time, naming both conflicting fields
9. [METHOD] getFieldNames(): `@SerializedName.value()` is the primary serialized name and the first deserialization name; `alternate()` entries are additional deserialization-only names
10. [ERROR] @SerializedName on a record accessor method (when the field lacks the annotation) throws `JsonIOException`
11. [METHOD] Static fields of records are excluded from deserialization (no accessor exists); they are still serialized if they pass the excluder check
12. [ERROR] Writing to a `static final` field throws `JsonIOException("Cannot set value of 'static final' ...")` rather than attempting reflection
13. [NULL] Adapter.write(): `null` value → `out.nullValue()`
14. [METHOD] Adapter.write(): if a field's value is the same object reference as the containing object (`fieldValue == source`), the field is silently skipped to prevent direct self-referential recursion
15. [NULL] Adapter.read(): `NULL` token → returns `null`
16. [METHOD] Adapter.read(): unknown JSON field names are silently skipped via `in.skipValue()`
17. [ERROR] Adapter.read(): `IllegalStateException` (e.g., malformed JSON structure) is wrapped in `JsonSyntaxException`
18. [METHOD] RecordAdapter: primitive record components default to `0`/`false`/`'\0'` when absent from the JSON input
19. [ERROR] RecordAdapter.readIntoArray(): a JSON `null` for a primitive record component throws `JsonParseException("null is not allowed as value for record component '<name>' of primitive type; at path ...")`
20. [METHOD] RecordAdapter: the canonical constructor is located via `ReflectionHelper.getCanonicalRecordConstructor()` and made accessible; argument order follows `RecordComponent` declaration order
21. [ERROR] RecordAdapter.finalize(): if the canonical constructor throws `InvocationTargetException`, wraps the cause in a `RuntimeException` with constructor description and argument array
22. [METHOD] FieldReflectionAdapter: constructs the target object first (via `ObjectConstructor`), then reflectively sets each deserialized field
23. [ERROR] If an accessor method (record) throws during serialization, a `JsonIOException("Accessor <desc> threw exception")` is raised wrapping the cause
24. [INVARIANT] `FieldsData.deserializedFields` is a `LinkedHashMap` preserving field-discovery order; `serializedFields` is a `List` in discovery order
25. [CONFIG] `allowUnsafe=true` for `ConstructorConstructor` in non-record field-reflection path; Unsafe-constructed instances may be in broken state when constructors have preconditions
### gson/src/main/java/com/google/gson/internal/bind/SerializationDelegatingTypeAdapter.java (2 contracts)

1. [METHOD] getSerializationDelegate(): must return the `TypeAdapter` actually used to serialize values; may return `this` (no delegation) or another adapter
2. [INVARIANT] The returned delegate may itself be a `SerializationDelegatingTypeAdapter`; callers must traverse the chain to find the terminal adapter (as `TypeAdapterRuntimeTypeWrapper.isReflective()` does)
3. [SHOULD-EXIST] There is no contract preventing an infinite delegation cycle; a subclass that returns a delegate that eventually delegates back to itself would cause infinite recursion in chain-traversal code
### gson/src/main/java/com/google/gson/internal/bind/TreeTypeAdapter.java (19 contracts)

1. [LIFECYCLE] Constructor (5-arg): sets `nullSafe = true` by default
2. [LIFECYCLE] Constructor (6-arg): accepts explicit `nullSafe` flag
3. [NULL] read(): if `nullSafe=true` and the parsed JSON value `isJsonNull()`, returns `null` without invoking the deserializer
4. [METHOD] read(): if `deserializer == null`, delegates entirely to the lazily-initialised `delegate` adapter
5. [METHOD] read(): otherwise parses the entire JSON value into a `JsonElement` tree and calls `deserializer.deserialize(tree, type, context)`
6. [NULL] write(): if `nullSafe=true` and `value == null`, writes a JSON null without invoking the serializer
7. [METHOD] write(): if `serializer == null`, delegates entirely to the lazily-initialised `delegate` adapter
8. [METHOD] write(): otherwise calls `serializer.serialize(value, type, context)` then writes the resulting `JsonElement` tree
9. [LIFECYCLE] delegate: lazily initialised on first use via `gson.getDelegateAdapter(skipPastForGetDelegateAdapter, typeToken)`; field is `volatile` so concurrent initialisation is safe (last-write-wins without lock)
10. [METHOD] getSerializationDelegate(): returns `this` if a serializer is present; returns the delegate if not
11. [METHOD] GsonContextImpl.serialize(Object): delegates to `gson.toJsonTree(src)`
12. [METHOD] GsonContextImpl.serialize(Object, Type): delegates to `gson.toJsonTree(src, typeOfSrc)`
13. [METHOD] GsonContextImpl.deserialize(JsonElement, Type): delegates to `gson.fromJson(json, typeOfT)`
14. [ERROR] SingleTypeFactory constructor: if `typeAdapter` implements neither `JsonSerializer` nor `JsonDeserializer`, throws `IllegalArgumentException` (after verifying it is non-null via `requireNonNull`)
15. [METHOD] newFactory(): factory matches by `TypeToken.equals()` (structural equality)
16. [METHOD] newFactoryWithMatchRawType(): additionally matches when `exactType` is a raw type and the requested type's raw class is identical
17. [METHOD] newTypeHierarchyFactory(): matches any type whose raw class is assignable from `hierarchyType`
18. [THREAD] The `volatile` delegate field ensures safe publication to concurrent threads with no explicit lock
19. [INVARIANT] `skipPastForGetDelegateAdapter` is a sentinel factory passed solely to `Gson.getDelegateAdapter`; it must never be used as a real factory (`DummyTypeAdapterFactory.create()` throws `AssertionError`)
### gson/src/main/java/com/google/gson/internal/bind/TypeAdapterRuntimeTypeWrapper.java (6 contracts)

1. [METHOD] read(): always delegates to the declared-type adapter with no runtime type dispatch; runtime type is irrelevant for deserialization
2. [METHOD] write(): applies a four-level preference for selecting the serialization adapter: (1) non-reflective user-registered adapter for the runtime type; (2) non-reflective declared-type adapter; (3) reflective adapter for the runtime type if it is more specific; (4) declared-type adapter as fallback
3. [METHOD] getRuntimeTypeIfMoreSpecific(): promotes to runtime type only if the value is non-null AND the declared type is a `Class<?>` or `TypeVariable<?>` — parameterized types and wildcard types are never promoted
4. [METHOD] isReflective(): traverses the `SerializationDelegatingTypeAdapter` chain to find the terminal serialization adapter and returns `true` iff it is a `ReflectiveTypeAdapterFactory.Adapter`
5. [COMPAT] isReflective(): only checks the final `ReflectiveTypeAdapterFactory.Adapter` instance in the chain; intermediate wrapping adapters do not affect the reflective determination (documented trade-off for backward compatibility)
6. [INVARIANT] A non-reflective user-registered adapter for the runtime type always takes precedence over any reflective adapter, ensuring that custom serializers for subtypes are honored even when the declared type differs
### gson/src/main/java/com/google/gson/internal/bind/TypeAdapters.java (40 contracts)

1. [ERROR] CLASS adapter: both `write()` and `read()` always throw `UnsupportedOperationException` with a troubleshooting URL; wrapped with `nullSafe()` so `null` is handled before reaching the throw
2. [METHOD] BIT_SET: deserializes from a JSON array of `0`/`1` integers or `true`/`false` booleans; element `i` in the array sets bit `i`; wrapped `nullSafe()`
3. [ERROR] BIT_SET.read(): values other than `0` or `1` for integer elements throw `JsonSyntaxException`; wrong token type (not NUMBER, STRING, BOOLEAN) also throws `JsonSyntaxException`
4. [COMPAT] BOOLEAN.read(): accepts `STRING` token and parses with `Boolean.parseBoolean` for Gson 1.7 compatibility; NOT wrapped with `nullSafe()` (handles `NULL` inline)
5. [METHOD] BOOLEAN_AS_STRING.write(): writes `null` as the string literal `"null"` (not a JSON null), making null values indistinguishable from the string `"null"` on round-trip
6. [ERROR] BYTE.read(): allows values in `[-128, 255]` (permits unsigned bytes); values outside that range throw `JsonSyntaxException("Lossy conversion from <n> to byte; at path ...")`
7. [ERROR] SHORT.read(): allows values in `[-32768, 65535]`; values outside that range throw `JsonSyntaxException("Lossy conversion from <n> to short; at path ...")`
8. [ERROR] INTEGER.read(): `NumberFormatException` from `nextInt()` is re-thrown as `JsonSyntaxException`
9. [METHOD] ATOMIC_INTEGER: not null-safe; `null` input causes NPE on `nextInt()`
10. [METHOD] atomicLongAdapter(): factory method requiring non-null `longAdapter`; result is null-safe
11. [METHOD] ATOMIC_BOOLEAN: not null-safe; expects a boolean token directly
12. [METHOD] ATOMIC_INTEGER_ARRAY: not null-safe; reads a JSON array of ints; `NumberFormatException` → `JsonSyntaxException`
13. [METHOD] atomicLongArrayAdapter(): factory method requiring non-null `longAdapter`; result is null-safe
14. [ERROR] LONG.read(): `NumberFormatException` from `nextLong()` is re-thrown as `JsonSyntaxException`
15. [METHOD] LONG_AS_STRING.write(): serializes long values as JSON strings (not numbers); reads using `nextLong()` (not `nextString()`), so the JSON input must still be parseable as a long
16. [CONFIG] FLOAT (strict=false): NaN/Infinity are permitted in output; for backward compatibility, calls `out.value(Number)` rather than `out.value(float)` to avoid breaking custom `JsonWriter` subclasses
17. [CONFIG] FLOAT_STRICT (strict=true): NaN/Infinity throw `IllegalArgumentException` on write
18. [CONFIG] DOUBLE (strict=false): NaN/Infinity permitted
19. [CONFIG] DOUBLE_STRICT (strict=true): NaN/Infinity throw `IllegalArgumentException` on write
20. [ERROR] CHARACTER.read(): string of length ≠ 1 throws `JsonSyntaxException("Expecting character, got: <s>; at <path>")`
21. [COMPAT] STRING.read(): coerces a `BOOLEAN` token to its string representation for Gson 1.7 backward compatibility
22. [ERROR] BIG_DECIMAL.read(): delegates to `NumberLimits.parseBigDecimal()`; malformed input throws `JsonSyntaxException` with path
23. [ERROR] BIG_INTEGER.read(): delegates to `NumberLimits.parseBigInteger()`; malformed input throws `JsonSyntaxException` with path
24. [METHOD] URL.read(): the literal string `"null"` is treated as a null Java reference (not a URL whose text is "null")
25. [METHOD] URI.read(): same as URL — literal `"null"` → null Java reference
26. [ERROR] URI.read(): malformed URI throws `JsonIOException` (wraps `URISyntaxException`), not `JsonSyntaxException` — inconsistent with other adapters
27. [COMPAT] INET_ADDRESS.read(): uses `InetAddress.getByName()` (resolves by hostname); INET_ADDRESS.write() uses `getHostAddress()` (IP address), so serialization loses the hostname and cannot round-trip to the same `InetAddress` by name
28. [ERROR] UUID.read(): malformed UUID string throws `JsonSyntaxException("Failed parsing '<s>' as UUID; at path ...")`
29. [METHOD] CURRENCY: not null-safe; `read()` calls `nextString()` without null check; `write()` calls `value.getCurrencyCode()` without null check — null input causes NPE
30. [METHOD] IntegerFieldsTypeAdapter.read(): missing fields default to `0L` (the default `long` value in the pre-allocated array); extra fields are silently skipped
31. [METHOD] CALENDAR: serializes/deserializes 6 integer fields: `year`, `month`, `dayOfMonth`, `hourOfDay`, `minute`, `second` using `GregorianCalendar`; registered for both `Calendar.class` and `GregorianCalendar.class`
32. [METHOD] LOCALE.read(): parses underscore-delimited string into language, country, variant components; extra tokens beyond the third are silently ignored
33. [METHOD] JSON_ELEMENT: delegates to `JsonElementTypeAdapter.ADAPTER` singleton
34. [METHOD] ENUM_FACTORY: delegates to `EnumTypeAdapter.FACTORY`
35. [METHOD] javaTimeTypeAdapterFactory(): loads `JavaTimeTypeAdapters` via reflection; returns `null` if the class is not found or linkage fails — `java.time` support is optional
36. [METHOD] newFactory(TypeToken, TypeAdapter): factory matches by `TypeToken.equals()` (structural equality including type arguments)
37. [METHOD] newFactory(Class, TypeAdapter): factory matches by raw-type identity (`==`), not `instanceof`
38. [METHOD] newFactory(Class unboxed, Class boxed, TypeAdapter): factory matches either the primitive or boxed class by identity
39. [METHOD] newFactoryForMultipleTypes(): factory matches either `base` or `sub` by identity
40. [METHOD] newTypeHierarchyFactory(): factory matches by `isAssignableFrom`; after deserialization, performs a runtime type check on the result and throws `JsonSyntaxException` if the deserialized object is not an instance of the requested type
### gson/src/main/java/com/google/gson/internal/bind/util/ISO8601Utils.java (14 contracts)

1. [METHOD] format(Date): formats to `"yyyy-MM-ddThh:mm:ssZ"` in UTC with no milliseconds
2. [METHOD] format(Date, boolean): formats in UTC; `millis=true` appends `.sss`
3. [METHOD] format(Date, boolean, TimeZone): for UTC offset=0 appends `Z`; for any other timezone appends `+hh:mm` or `-hh:mm`
4. [METHOD] parse(): accepts both compact (`yyyyMMdd`) and dashed (`yyyy-MM-dd`) date formats
5. [METHOD] parse(): time component (`T...`) is optional; a date-only string with no remaining characters is valid and returns midnight in the local/default timezone
6. [ERROR] parse(): when a time component is present, a timezone indicator is mandatory; absence of `Z`, `+`, or `-` after the time throws `IllegalArgumentException("No time zone indicator")` wrapped in `ParseException`
7. [METHOD] parse(): leap seconds 60–62 are silently truncated to 59
8. [METHOD] parse(): fractional seconds — only up to 3 digits are parsed; 1-digit fractions are multiplied by 100, 2-digit by 10, ≥3-digit use the first 3 digits
9. [METHOD] parse(): timezone `"+0000"` and `"+00:00"` are treated as UTC; other offsets are looked up as `"GMT<offset>"` (not `"UTC<offset>"`)
10. [ERROR] parse(): invalid timezone offset (JVM does not recognize the `GMT<offset>` string) throws `IndexOutOfBoundsException("Mismatching time zone indicator: ...")` wrapped in `ParseException`
11. [ERROR] parse(): invalid date/time field values (e.g., month 13) are caught by `GregorianCalendar.setLenient(false)` and wrapped in `ParseException`
12. [METHOD] parse(): `ParsePosition.index` is updated to the index immediately after the last parsed character
13. [ERROR] parse(): all `IndexOutOfBoundsException` and `IllegalArgumentException` errors are caught and re-thrown as `ParseException` with the input string quoted in the message and the original position as the error offset
14. [INVARIANT] `TIMEZONE_UTC` is a static constant pre-fetched at class load time; it is not looked up per invocation
15. [SHOULD-EXIST] There is no validation that the date string is fully consumed (extra trailing characters after the parsed portion are silently ignored because `ParsePosition.index` just stops at the end of what was recognised)
### gson/src/main/java/com/google/gson/internal/reflect/ReflectionHelper.java (16 contracts)

1. [ERROR] makeAccessible(): calls `setAccessible(true)`; on any failure throws `JsonIOException` whose message names the field/method/constructor and appends a troubleshooting guide URL for `InaccessibleObjectException`
2. [METHOD] getAccessibleObjectDescription(): returns `"field 'ClassName#name'"`, `"method 'ClassName#name(ParamTypes)'"`, or `"constructor 'ClassName(ParamTypes)'"` using simple names for parameter types; unknown `AccessibleObject` types produce `"<unknown AccessibleObject> toString()"`
3. [METHOD] getAccessibleObjectDescription(): if `uppercaseFirstLetter=true` and the first character is lowercase, capitalises it
4. [METHOD] fieldToString(): produces `"ClassName#fieldName"`
5. [METHOD] constructorToString(): produces `"ClassName(SimpleParamType1, SimpleParamType2, ...)"`
6. [METHOD] isStatic(Class): returns `Modifier.isStatic(clazz.getModifiers())`
7. [METHOD] isAnonymousOrNonStaticLocal(Class): returns `true` iff the class is not static AND (anonymous OR local)
8. [METHOD] tryMakeAccessible(Constructor): returns `null` on success; returns a descriptive error message string (never throws); message includes troubleshooting URL for `InaccessibleObjectException`
9. [METHOD] isRecord(): delegates to `RECORD_HELPER.isRecord()`; always returns `false` on JVMs without record support
10. [ERROR] getRecordComponentNames(): throws `UnsupportedOperationException` on JVMs without record support
11. [METHOD] getAccessor(Class, Field): returns the public method with the same name as the field (record accessor contract from JLS §8.10.3)
12. [ERROR] getAccessor(): `ReflectiveOperationException` is wrapped in a `RuntimeException` with a message stating the exception is unexpected
13. [METHOD] getCanonicalRecordConstructor(): uses `getDeclaredConstructor` (not `getConstructor`) because the canonical constructor has the same visibility as the record itself and may not be public
14. [ERROR] createExceptionForUnexpectedIllegalAccess(): always throws `RuntimeException` (never returns); message includes Gson version and hints about `ReflectionAccessFilter` requirements
15. [LIFECYCLE] RECORD_HELPER: initialised at class load time; if `RecordSupportedHelper` construction fails (any `ReflectiveOperationException`), falls back to `RecordNotSupportedHelper`
16. [INVARIANT] `RecordNotSupportedHelper.isRecord()` always returns `false`; all other methods throw `UnsupportedOperationException`
### gson/src/main/java/com/google/gson/internal/sql/SqlDateTypeAdapter.java (9 contracts)

1. [METHOD] FACTORY.create(): matches only exactly `java.sql.Date.class`; a new adapter instance is created per Gson instance (not a singleton)
2. [METHOD] read(): uses the format `"MMM d, yyyy"` (e.g., `"Jan 1, 2020"`)
3. [NULL] read(): `NULL` token → consumes and returns `null`
4. [ERROR] read(): `ParseException` is re-thrown as `JsonSyntaxException("Failed parsing '<s>' as SQL Date; at path ...")` containing the raw input string and path
5. [LIFECYCLE] read(): restores the `DateFormat`'s original `TimeZone` in a `finally` block after parsing
6. [THREAD] read(): synchronises on `this` around the `format.parse()` call
7. [NULL] write(): `null` value → `out.nullValue()`
8. [THREAD] write(): synchronises on `this` around the `format.format()` call
9. [INVARIANT] The internal `DateFormat` captures the JVM default `TimeZone` and `Locale` when the adapter is constructed; changing the default timezone/locale afterwards does not affect an existing adapter instance
### gson/src/main/java/com/google/gson/internal/sql/SqlTimeTypeAdapter.java (9 contracts)

1. [METHOD] FACTORY.create(): matches only exactly `java.sql.Time.class`; a new adapter instance is created per Gson instance
2. [METHOD] read(): uses the format `"hh:mm:ss a"` (12-hour with AM/PM, e.g., `"09:30:00 AM"`)
3. [NULL] read(): `NULL` token → consumes and returns `null`
4. [ERROR] read(): `ParseException` is re-thrown as `JsonSyntaxException("Failed parsing '<s>' as SQL Time; at path ...")`
5. [LIFECYCLE] read(): restores the `DateFormat`'s original `TimeZone` in a `finally` block after parsing
6. [THREAD] read(): synchronises on `this` around the `format.parse()` call
7. [NULL] write(): `null` value → `out.nullValue()`
8. [THREAD] write(): synchronises on `this` around the `format.format()` call
9. [INVARIANT] The internal `DateFormat` captures the default `TimeZone`/`Locale` at construction; later changes to JVM defaults do not affect this adapter
### gson/src/main/java/com/google/gson/internal/sql/SqlTimestampTypeAdapter.java (4 contracts)

1. [METHOD] FACTORY.create(): matches only exactly `Timestamp.class`; delegates to the Gson-registered `Date` adapter for all actual serialization logic
2. [METHOD] read(): delegates to `dateTypeAdapter.read(in)`; if the result is non-null, wraps it with `new Timestamp(date.getTime())` preserving only millisecond precision
3. [NULL] read(): if `dateTypeAdapter.read()` returns `null`, returns `null`
4. [METHOD] write(): passes the `Timestamp` directly to `dateTypeAdapter.write()` (since `Timestamp` extends `Date`); format and null handling are determined entirely by the `Date` adapter
5. [SHOULD-EXIST] Nanosecond precision of `java.sql.Timestamp` is silently lost during serialization and deserialization (only `getTime()` milliseconds are used); there is no warning or documented precision constraint
### gson/src/main/java/com/google/gson/internal/sql/SqlTypesSupport.java (8 contracts)

1. [INVARIANT] `SUPPORTS_SQL_TYPES` is `true` iff `java.sql.Date` can be loaded via `Class.forName()`; determined once at class load time and never changes
2. [INVARIANT] When `SUPPORTS_SQL_TYPES=true`: `DATE_DATE_TYPE`, `TIMESTAMP_DATE_TYPE`, `DATE_FACTORY`, `TIME_FACTORY`, `TIMESTAMP_FACTORY` are all non-null; `SQL_TYPE_FACTORIES` contains all three factories
3. [INVARIANT] When `SUPPORTS_SQL_TYPES=false`: all five field constants are `null`; `SQL_TYPE_FACTORIES` is `Collections.emptyList()`
4. [METHOD] `SQL_TYPE_FACTORIES` is always an unmodifiable list (backed by `Collections.unmodifiableList`); mutation attempts throw `UnsupportedOperationException`
5. [ORDER] `SQL_TYPE_FACTORIES` order is always `[TIME_FACTORY, DATE_FACTORY, TIMESTAMP_FACTORY]`; this order determines which factory is consulted first when Gson iterates adapter factories
6. [METHOD] `DATE_DATE_TYPE.deserialize(Date)`: returns `new java.sql.Date(date.getTime())`, truncating to millisecond precision
7. [METHOD] `TIMESTAMP_DATE_TYPE.deserialize(Date)`: returns `new Timestamp(date.getTime())`, truncating to millisecond precision
8. [LIFECYCLE] All constants are initialised in a `static` block; `ClassNotFoundException` from `java.sql.Date` class loading is caught and handled; no exception escapes static initialisation
### gson/src/main/java/com/google/gson/reflect/TypeToken.java (18 contracts)

1. [METHOD] TypeToken.TypeToken(): a direct anonymous subclass captures its single generic type argument in canonicalized form and derives a stable raw type and cached hash code from it.
2. [ERROR] TypeToken.TypeToken(): using a raw `TypeToken` superclass with no type argument throws `IllegalStateException` with shrinker-signature troubleshooting guidance.
3. [ERROR] TypeToken.TypeToken(): creating a subclass of a subclass of `TypeToken` throws `IllegalStateException`; only direct subclasses are accepted.
4. [CONFIG] TypeToken: capturing type variables is forbidden unless system property `gson.allowCapturingTypeVariables` is exactly `"true"`.
5. [ERROR] TypeToken.verifyNoTypeVariable(...): any captured `TypeVariable`, including inside parameterized types, arrays, owners, or wildcards, causes `IllegalArgumentException`.
6. [ERROR] TypeToken.verifyNoTypeVariable(...): a captured `null` type argument is treated as an error and causes `IllegalArgumentException`.
7. [METHOD] TypeToken.getRawType(): returns the raw non-generic `Class` corresponding to the represented type.
8. [METHOD] TypeToken.getType(): returns the canonical underlying `Type` represented by this token.
9. [COMPAT] TypeToken.isAssignableFrom(Class/Type/TypeToken): these deprecated methods implement Gson’s own assignability rules and may disagree with `javac` for wildcard types.
10. [NULL] TypeToken.isAssignableFrom(Type): passing `null` returns `false` rather than throwing.
11. [ERROR] TypeToken.isAssignableFrom(Type): if this token represents something other than a `Class`, `ParameterizedType`, or `GenericArrayType`, assignability checks fail with `IllegalArgumentException`.
12. [INVARIANT] TypeToken.equals/hashCode/toString: equality, hash code, and string form are all based on the canonical represented type; hash code is computed once and reused.
13. [NULL] TypeToken.get(Type) / TypeToken.get(Class): passing `null` is rejected via `NullPointerException`.
14. [ERROR] TypeToken.getParameterized(...): `rawType` must be a `Class`; any other `Type` causes `IllegalArgumentException`.
15. [ERROR] TypeToken.getParameterized(...): the number of supplied type arguments must exactly match the raw class’s type parameters or it throws `IllegalArgumentException`.
16. [COMPAT] TypeToken.getParameterized(...): for a non-generic class with zero type arguments, Gson returns `TypeToken.get(rawClass)` instead of synthesizing a parameterized type.
17. [ERROR] TypeToken.getParameterized(...): raw types that require an owner type are rejected, and each type argument must be non-null and satisfy its declared bounds.
18. [METHOD] TypeToken.getArray(...): returns a token representing an array whose component type is the supplied type.
### gson/src/main/java/com/google/gson/stream/JsonReader.java (54 contracts)

1. [LIFECYCLE] JsonReader.JsonReader(Reader): requires a non-null `Reader` and binds the instance to a single JSON stream.
2. [THREAD] JsonReader: instances are explicitly not thread-safe.
3. [CONFIG] JsonReader: default strictness is `Strictness.LEGACY_STRICT`.
4. [CONFIG] JsonReader.setLenient(boolean): `true` maps to `Strictness.LENIENT`; `false` maps to `Strictness.LEGACY_STRICT`.
5. [METHOD] JsonReader.isLenient(): returns `true` only when current strictness is exactly `LENIENT`.
6. [NULL] JsonReader.setStrictness(Strictness): rejects `null`; `getStrictness()` returns the current strictness mode.
7. [CONFIG] JsonReader.setStrictness(STRICT): strict mode accepts only RFC 8259 JSON.
8. [COMPAT] JsonReader.setStrictness(LEGACY_STRICT): legacy-strict mode also accepts mixed-case `true`/`false`/`null`, `\'`, backslash-newline escapes, and unescaped control characters.
9. [COMPAT] JsonReader.setStrictness(LENIENT): lenient mode additionally accepts the non-execute prefix, multiple top-level values, `NaN`/`Infinity`, comments, single-quoted or unquoted names/strings, `;` separators, omitted array elements as `null`, and `=`/`=>` name separators.
10. [CONFIG] JsonReader: default nesting limit is 255 open arrays/objects.
11. [ERROR] JsonReader.setNestingLimit(int): negative limits throw `IllegalArgumentException`.
12. [CONFIG] JsonReader.setNestingLimit(int): a limit of 0 forbids opening any array or object; the limit counts concurrently open arrays/objects.
13. [ERROR] JsonReader.push(...): exceeding the nesting limit throws `MalformedJsonException` with current location information.
14. [METHOD] JsonReader.beginArray(): consumes the next token only if it is `BEGIN_ARRAY`, pushes array scope, and initializes the current array index to 0.
15. [ERROR] JsonReader.beginArray(): any non-array next token causes `IllegalStateException`.
16. [METHOD] JsonReader.endArray(): consumes `END_ARRAY`, pops array scope, and advances the parent path index.
17. [ERROR] JsonReader.endArray(): any non-array-end next token causes `IllegalStateException`.
18. [METHOD] JsonReader.beginObject(): consumes the next token only if it is `BEGIN_OBJECT` and pushes object scope.
19. [ERROR] JsonReader.beginObject(): any non-object next token causes `IllegalStateException`.
20. [METHOD] JsonReader.endObject(): consumes `END_OBJECT`, pops object scope, clears the last path name, and advances the parent path index.
21. [ERROR] JsonReader.endObject(): any non-object-end next token causes `IllegalStateException`.
22. [METHOD] JsonReader.hasNext(): returns `false` only for `END_OBJECT`, `END_ARRAY`, or end-of-document; otherwise `true`.
23. [METHOD] JsonReader.peek(): reports the next `JsonToken` without consuming it, including `END_DOCUMENT` when input is exhausted.
24. [METHOD] JsonReader.nextName(): consumes the next property name from double-quoted, single-quoted, or unquoted syntax as allowed by mode, and records it in the current path.
25. [ERROR] JsonReader.nextName(): any non-name token causes `IllegalStateException`.
26. [METHOD] JsonReader.nextString(): consumes a JSON string or number and returns its textual form, so numbers can be read as strings.
27. [ERROR] JsonReader.nextString(): any token that is neither string-like nor number-like causes `IllegalStateException`.
28. [METHOD] JsonReader.nextBoolean(): consumes only `true` or `false` and advances the path index.
29. [ERROR] JsonReader.nextBoolean(): any non-boolean token causes `IllegalStateException`.
30. [METHOD] JsonReader.nextNull(): consumes only a JSON `null` literal and advances the path index.
31. [ERROR] JsonReader.nextNull(): any non-null token causes `IllegalStateException`.
32. [METHOD] JsonReader.nextDouble(): accepts numeric tokens and numeric strings, parsing them with `Double.parseDouble`.
33. [ERROR] JsonReader.nextDouble(): unparsable input throws `NumberFormatException`, and non-lenient `NaN` or infinities throw `MalformedJsonException`.
34. [METHOD] JsonReader.nextLong(): accepts numeric tokens and numeric strings and returns a `long` only when the value is exactly representable.
35. [ERROR] JsonReader.nextLong(): unparsable input or precision loss throws `NumberFormatException`.
36. [METHOD] JsonReader.nextInt(): accepts numeric tokens and numeric strings and returns an `int` only when the value is exactly representable.
37. [ERROR] JsonReader.nextInt(): unparsable input or precision loss throws `NumberFormatException`.
38. [METHOD] JsonReader.skipValue(): recursively skips arrays, objects, and primitive values; if called on a property name it skips only the name, not the value; if called at `END_DOCUMENT` it is a no-op.
39. [INVARIANT] JsonReader.skipValue() and consuming methods keep path tracking updated, and explicitly skipped top-level names become `"<skipped>"` in the path state.
40. [LIFECYCLE] JsonReader.close(): closes the underlying `Reader`, marks the reader closed, and later operations generally fail with `IllegalStateException`.
41. [COMPAT] JsonReader.fillBuffer(...): a leading UTF-8 BOM is consumed only on the first read.
42. [COMPAT] JsonReader.nextNonWhitespace(...): always skips JSON whitespace, and in lenient mode also skips `//`, `#`, and `/* ... */` comments.
43. [ERROR] JsonReader.nextNonWhitespace(...): unterminated block comments produce `MalformedJsonException`, and EOF either returns `-1` or throws `EOFException` depending on caller request.
44. [ERROR] JsonReader.peekKeyword(): `true`, `false`, and `null` are recognized only when not followed by another literal character, so inputs like `falsey` are rejected as keywords.
45. [ERROR] JsonReader.nextQuotedValue(...): strict mode rejects unescaped control characters inside quoted strings.
46. [COMPAT] JsonReader.readEscapeCharacter(): supports `\uXXXX` and standard JSON escapes, and in non-`STRICT` modes also accepts `\'` and backslash-newline escapes.
47. [ERROR] JsonReader.readEscapeCharacter(): malformed or unterminated escape sequences throw `MalformedJsonException`.
48. [METHOD] JsonReader.getPath(): returns a dot-notation JSONPath to the next/current location; array segments point at the next index.
49. [METHOD] JsonReader.getPreviousPath(): returns a dot-notation JSONPath to the previous/current location; the last array segment points at the previous index when possible.
50. [METHOD] JsonReader.toString(): includes the reader’s current line, column, and path.
51. [ERROR] JsonReader.syntaxError(...) / unexpectedTokenError(...): parser failures include line, column, path, and a troubleshooting URL; unexpected `NULL` uses a null-safety troubleshooting id.
52. [COMPAT] JsonReader.consumeNonExecutePrefix(): the `")]}'\n"` non-execute prefix is consumed only in lenient mode and only after leading whitespace.
53. [COMPAT] JsonReader.doPeek(): in lenient arrays, leading separators like `,]` or `;]` are interpreted as omitted `null` elements instead of immediate syntax errors.
54. [METHOD] JsonReader internal access hook `promoteNameToValue(...)`: internal adapters can convert the next `NAME` token into a string-valued token, but only when the next token is actually a name.
### gson/src/main/java/com/google/gson/stream/JsonScope.java (4 contracts)

1. [INVARIANT] JsonScope.EMPTY_ARRAY and JsonScope.NONEMPTY_ARRAY distinguish whether an array is still before its first element or now requires a separator before the next element.
2. [INVARIANT] JsonScope.EMPTY_OBJECT, JsonScope.DANGLING_NAME, and JsonScope.NONEMPTY_OBJECT distinguish whether an object is waiting for its first name, waiting for the value of a just-written/read name, or requires a separator before the next name.
3. [INVARIANT] JsonScope.EMPTY_DOCUMENT and JsonScope.NONEMPTY_DOCUMENT distinguish whether a top-level value has started, enabling reader/writer enforcement of single-document semantics.
4. [LIFECYCLE] JsonScope.CLOSED is the terminal state for a closed reader or writer; the file is otherwise a trivial non-instantiable constant holder.
### gson/src/main/java/com/google/gson/stream/JsonToken.java (4 contracts)

1. [INVARIANT] JsonToken defines the complete public token vocabulary of Gson’s streaming reader/writer API; the file is otherwise a trivial enum.
2. [METHOD] JsonToken.BEGIN_ARRAY/END_ARRAY and BEGIN_OBJECT/END_OBJECT are the structural delimiters consumed by `JsonReader` and emitted by `JsonWriter`.
3. [INVARIANT] JsonToken.NAME represents object property names, and object streams conceptually alternate between `NAME` and a value until `END_OBJECT`.
4. [METHOD] JsonToken.END_DOCUMENT is a sentinel returned by `JsonReader.peek()` when no tokens remain in the stream.
### gson/src/main/java/com/google/gson/stream/JsonWriter.java (27 contracts)

1. [LIFECYCLE] JsonWriter.JsonWriter(Writer): requires a non-null `Writer`, starts in empty-document state, and defaults to `FormattingStyle.COMPACT`.
2. [THREAD] JsonWriter: each instance writes a single JSON stream and is explicitly not thread-safe.
3. [CONFIG] JsonWriter.setIndent(String): `""` switches to compact output; any non-empty indent replaces the current formatting style with pretty-printing using that indent.
4. [NULL] JsonWriter.setFormattingStyle(FormattingStyle): rejects `null`; `getFormattingStyle()` returns the current style.
5. [CONFIG] JsonWriter.setFormattingStyle(...): formatting style controls colon spacing, comma spacing, newline text, and indentation behavior.
6. [CONFIG] JsonWriter: default strictness is `Strictness.LEGACY_STRICT`.
7. [CONFIG] JsonWriter.setLenient(boolean): `true` maps to `Strictness.LENIENT`; `false` maps to `Strictness.LEGACY_STRICT`; `isLenient()` reports only exact `LENIENT`.
8. [NULL] JsonWriter.setStrictness(Strictness): rejects `null`; `getStrictness()` returns the current mode.
9. [CONFIG] JsonWriter.setStrictness(...): `STRICT` and `LEGACY_STRICT` currently emit only RFC 8259 JSON, while `LENIENT` also allows `NaN`/infinities and multiple top-level values.
10. [CONFIG] JsonWriter.setHtmlSafe(boolean): when enabled, strings additionally escape `<`, `>`, `&`, `=`, and `'`; default is off.
11. [CONFIG] JsonWriter.setSerializeNulls(boolean): controls whether object members whose value is `null` are written; array `null` elements are unaffected; default is `true`.
12. [METHOD] JsonWriter.beginArray() / beginObject(): write any deferred name, open a new array/object scope, and return `this`.
13. [METHOD] JsonWriter.endArray() / endObject(): close only the matching current scope and return `this`.
14. [ERROR] JsonWriter.endArray() / endObject(): mismatched nesting throws `IllegalStateException("Nesting problem.")`, and closing with a deferred name throws `IllegalStateException("Dangling name: ...")`.
15. [NULL] JsonWriter.name(String): rejects `null`, requires current context to be an object, and forbids writing two names in a row without a value.
16. [METHOD] JsonWriter.name(String): defers actual output of the property name until the following value/begin/null/jsonValue call.
17. [NULL] JsonWriter.value(String), value(Boolean), value(Number), and jsonValue(String): a `null` argument is treated as `nullValue()`.
18. [METHOD] JsonWriter.value(boolean/Boolean), value(long), and value(String): emit the corresponding JSON literal or quoted string and return `this`.
19. [ERROR] JsonWriter.value(float) / value(double): non-finite values are rejected with `IllegalArgumentException` unless strictness is `LENIENT`.
20. [ERROR] JsonWriter.value(Number): writes `Number.toString()` directly, but rejects non-finite values unless lenient and rejects invalid JSON-number text for untrusted `Number` subclasses.
21. [METHOD] JsonWriter.nullValue(): writes literal `null`, except that with a deferred object name and `serializeNulls == false` it suppresses both the name and the value.
22. [METHOD] JsonWriter.jsonValue(String): this implementation supports raw JSON output by writing the supplied text without quoting or escaping.
23. [ERROR] JsonWriter.beforeValue(): enforces exactly one top-level value unless strictness is `LENIENT`, and rejects malformed nesting with `IllegalStateException`.
24. [INVARIANT] JsonWriter.string(...): always escapes control characters, quotes, backslashes, and `U+2028`/`U+2029`; html-safe mode escapes additional HTML-sensitive characters.
25. [LIFECYCLE] JsonWriter.flush(): flushes the underlying writer but throws `IllegalStateException` if the writer is already closed.
26. [LIFECYCLE] JsonWriter.close(): closes the underlying writer, then throws `IOException("Incomplete document")` unless the JSON document is complete, and finally marks the writer closed.
27. [INVARIANT] JsonWriter’s mutating value/name/scope methods return `this`, enabling fluent chaining.
### gson/src/main/java/com/google/gson/stream/MalformedJsonException.java (4 contracts)

1. [METHOD] MalformedJsonException: this is a final `IOException` subtype used to signal malformed JSON; the file is otherwise a trivial exception wrapper.
2. [COMPAT] MalformedJsonException: the class documents that some malformed-input cases can be tolerated when `JsonReader` is configured as `Strictness.LENIENT`.
3. [METHOD] MalformedJsonException(String) / MalformedJsonException(String, Throwable): these constructors preserve the supplied message, and optionally the supplied cause.
4. [METHOD] MalformedJsonException(Throwable): this constructor preserves the supplied cause as the exception payload.
