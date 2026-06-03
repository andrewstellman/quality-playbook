# Gson Date and DateTime Handling

## Overview

Date/time serialization and deserialization is a common source of issues due to different formats and time zones. Gson provides both built-in support and customization options.

## Default Date Handling

### Default Behavior

By default, Gson uses **ISO-8601 format** for Date objects:

```java
Date date = new Date();
String json = gson.toJson(date);
// Output: "2024-03-07T14:30:45.123Z"
```

### Deserialization

```java
String json = "\"2024-03-07T14:30:45.123Z\"";
Date date = gson.fromJson(json, Date.class);
```

## Custom Date Format with setDateFormat()

Use `GsonBuilder.setDateFormat()` to specify a custom pattern:

```java
Gson gson = new GsonBuilder()
    .setDateFormat("yyyy-MM-dd HH:mm:ss")
    .create();

Date date = new Date();
String json = gson.toJson(date);
// Output: "2024-03-07 14:30:45"

// Deserialization
String input = "\"2024-03-07 14:30:45\"";
Date parsed = gson.fromJson(input, Date.class);
```

### SimpleDateFormat Patterns

Common patterns for `setDateFormat()`:

```java
"yyyy-MM-dd"              // 2024-03-07
"yyyy-MM-dd HH:mm:ss"     // 2024-03-07 14:30:45
"yyyy-MM-dd'T'HH:mm:ss"   // 2024-03-07T14:30:45
"dd/MM/yyyy"              // 07/03/2024
"MMMM dd, yyyy"           // March 07, 2024
"EEE, MMMM dd yyyy"       // Thursday, March 07 2024
```

## Java 8 Date/Time Classes

For `LocalDate`, `LocalDateTime`, `Instant`, etc., custom deserializers are needed:

### LocalDate Deserialization

```java
class LocalDateDeserializer implements JsonDeserializer<LocalDate> {
    private static final DateTimeFormatter formatter =
        DateTimeFormatter.ISO_LOCAL_DATE;

    @Override
    public LocalDate deserialize(JsonElement json, Type typeOfT,
                                  JsonDeserializationContext context)
        throws JsonSyntaxException {
        try {
            return LocalDate.parse(json.getAsString(), formatter);
        } catch (DateTimeParseException e) {
            throw new JsonSyntaxException("Invalid date format", e);
        }
    }
}
```

### Registration

```java
Gson gson = new GsonBuilder()
    .registerTypeAdapter(LocalDate.class, new LocalDateDeserializer())
    .create();

String json = "\"2024-03-07\"";
LocalDate date = gson.fromJson(json, LocalDate.class);
```

### Complete Solution with Serialization and Deserialization

```java
class LocalDateAdapter
    implements JsonSerializer<LocalDate>, JsonDeserializer<LocalDate> {

    private static final DateTimeFormatter formatter =
        DateTimeFormatter.ISO_LOCAL_DATE;

    @Override
    public JsonElement serialize(LocalDate date, Type typeOfSrc,
                                  JsonSerializationContext context) {
        return new JsonPrimitive(formatter.format(date));
    }

    @Override
    public LocalDate deserialize(JsonElement json, Type typeOfT,
                                  JsonDeserializationContext context)
        throws JsonSyntaxException {
        try {
            return LocalDate.parse(json.getAsString(), formatter);
        } catch (DateTimeParseException e) {
            throw new JsonSyntaxException("Invalid date format", e);
        }
    }
}

Gson gson = new GsonBuilder()
    .registerTypeAdapter(LocalDate.class, new LocalDateAdapter())
    .create();
```

## Handling Split Date Fields

Common API pattern where date is split into day, month, year:

```java
class LocalDateDeserializer implements JsonDeserializer<LocalDate> {
    @Override
    public LocalDate deserialize(JsonElement json, Type typeOfT,
                                  JsonDeserializationContext context)
        throws JsonSyntaxException {
        JsonObject obj = json.getAsJsonObject();

        int day = obj.get("day").getAsInt();
        int month = obj.get("month").getAsInt();
        int year = obj.get("year").getAsInt();

        return LocalDate.of(year, month, day);
    }
}

// Input JSON
{
  "name": "John",
  "birthDate": {
    "day": 15,
    "month": 3,
    "year": 1990
  }
}
```

## Timestamp (Unix Epoch) Handling

For timestamps (milliseconds since epoch):

```java
class UnixTimestampDeserializer implements JsonDeserializer<Date> {
    @Override
    public Date deserialize(JsonElement json, Type typeOfT,
                            JsonDeserializationContext context)
        throws JsonSyntaxException {
        try {
            long timestamp = json.getAsLong();
            return new Date(timestamp);
        } catch (Exception e) {
            throw new JsonSyntaxException("Invalid timestamp", e);
        }
    }
}

Gson gson = new GsonBuilder()
    .registerTypeAdapter(Date.class, new UnixTimestampDeserializer())
    .create();

// Input: 1704067200000 (March 7, 2024)
Date date = gson.fromJson("1704067200000", Date.class);
```

## LocalDateTime with Timezone

```java
class LocalDateTimeAdapter
    implements JsonSerializer<LocalDateTime>, JsonDeserializer<LocalDateTime> {

    private static final DateTimeFormatter formatter =
        DateTimeFormatter.ISO_LOCAL_DATE_TIME;

    @Override
    public JsonElement serialize(LocalDateTime dateTime, Type typeOfSrc,
                                  JsonSerializationContext context) {
        return new JsonPrimitive(formatter.format(dateTime));
    }

    @Override
    public LocalDateTime deserialize(JsonElement json, Type typeOfT,
                                      JsonDeserializationContext context)
        throws JsonSyntaxException {
        try {
            return LocalDateTime.parse(json.getAsString(), formatter);
        } catch (DateTimeParseException e) {
            throw new JsonSyntaxException("Invalid datetime format", e);
        }
    }
}
```

## ZonedDateTime with Timezone

```java
class ZonedDateTimeAdapter
    implements JsonSerializer<ZonedDateTime>, JsonDeserializer<ZonedDateTime> {

    private static final DateTimeFormatter formatter =
        DateTimeFormatter.ISO_OFFSET_DATE_TIME;

    @Override
    public JsonElement serialize(ZonedDateTime dateTime, Type typeOfSrc,
                                  JsonSerializationContext context) {
        return new JsonPrimitive(formatter.format(dateTime));
    }

    @Override
    public ZonedDateTime deserialize(JsonElement json, Type typeOfT,
                                      JsonDeserializationContext context)
        throws JsonSyntaxException {
        try {
            return ZonedDateTime.parse(json.getAsString(), formatter);
        } catch (DateTimeParseException e) {
            throw new JsonSyntaxException("Invalid zoned datetime format", e);
        }
    }
}
```

## Common Issues and Solutions

### Issue: Date Deserialization Fails

**Cause:** Date format in JSON doesn't match format in code

**Solution:**
1. Check JSON date format
2. Use `@JsonAdapter` on field for specific format
3. Register custom deserializer with `GsonBuilder`

### Issue: Null Dates

```java
class NullableDateDeserializer implements JsonDeserializer<Date> {
    @Override
    public Date deserialize(JsonElement json, Type typeOfT,
                            JsonDeserializationContext context)
        throws JsonSyntaxException {
        if (json.isJsonNull()) {
            return null;
        }

        try {
            return new SimpleDateFormat("yyyy-MM-dd")
                .parse(json.getAsString());
        } catch (ParseException e) {
            throw new JsonSyntaxException("Invalid date", e);
        }
    }
}
```

### Issue: Flexible Format Support

```java
class FlexibleDateDeserializer implements JsonDeserializer<Date> {
    private static final String[] DATE_FORMATS = {
        "yyyy-MM-dd",
        "yyyy-MM-dd HH:mm:ss",
        "yyyy-MM-dd'T'HH:mm:ss",
        "dd/MM/yyyy"
    };

    @Override
    public Date deserialize(JsonElement json, Type typeOfT,
                            JsonDeserializationContext context)
        throws JsonSyntaxException {
        String dateStr = json.getAsString();

        for (String format : DATE_FORMATS) {
            try {
                return new SimpleDateFormat(format).parse(dateStr);
            } catch (ParseException e) {
                // Try next format
            }
        }

        throw new JsonSyntaxException("Unable to parse date: " + dateStr);
    }
}
```

## Best Practices

1. **Choose consistent format** - Use ISO-8601 when possible
2. **Document date format** - Make it clear in API docs
3. **Handle timezones** - Use ZonedDateTime for multi-region systems
4. **Support null** - Always handle null dates gracefully
5. **Cache DateTimeFormatter** - They're expensive to create
6. **Use custom adapters** - For API-specific formats

## Reference

- **Baeldung Date Handling:** https://www.baeldung.com/gson-serialization-guide
- **JavaGuides LocalDate:** https://www.javaguides.net/2019/11/gson-localdatetime-localdate.html
- **DateTimeFormatter Patterns:** https://docs.oracle.com/javase/8/docs/api/java/time/format/DateTimeFormatter.html
