///usr/bin/env java --class-path gson/target/classes "$0" "$@"; exit $?

import com.google.gson.Gson;
import com.google.gson.JsonSyntaxException;
import com.google.gson.reflect.TypeToken;
import java.lang.reflect.Type;
import java.util.Map;

/**
 * Reproducer for Gson duplicate-key bug with null first value.
 *
 * MapTypeAdapterFactory detects duplicate keys using:
 *     V replaced = map.put(key, value);
 *     if (replaced != null) { throw ... }
 *
 * When the first value is null, map.put() returns null (the previous value),
 * and the check silently passes. The duplicate key is accepted.
 *
 * Build first:  mvn compile -pl gson -am -DskipTests
 * Then run:     java --class-path gson/target/classes GsonDuplicateKeyBug.java
 */
public class GsonDuplicateKeyBug {
    public static void main(String[] args) {
        Gson gson = new Gson();
        Type mapType = new TypeToken<Map<String, Integer>>() {}.getType();

        System.out.println("=== Gson Duplicate Key Bug Reproducer ===\n");

        // Test 1: Non-null first value (correctly throws)
        System.out.print("Test 1: {\"a\":1, \"a\":2}  (non-null first value) ... ");
        try {
            gson.fromJson("{\"a\":1,\"a\":2}", mapType);
            System.out.println("BUG - no exception thrown");
        } catch (JsonSyntaxException e) {
            System.out.println("OK - threw: " + e.getMessage());
        }

        // Test 2: Null first value (THE BUG — should throw but doesn't)
        System.out.print("Test 2: {\"a\":null, \"a\":1}  (null first value)   ... ");
        try {
            Map<String, Integer> result = gson.fromJson("{\"a\":null,\"a\":1}", mapType);
            System.out.println("BUG - no exception, silently returned: " + result);
        } catch (JsonSyntaxException e) {
            System.out.println("OK - threw: " + e.getMessage());
        }

        // Test 3: Both values null (should throw but doesn't)
        System.out.print("Test 3: {\"a\":null, \"a\":null} (both null)        ... ");
        try {
            Map<String, Integer> result = gson.fromJson("{\"a\":null,\"a\":null}", mapType);
            System.out.println("BUG - no exception, silently returned: " + result);
        } catch (JsonSyntaxException e) {
            System.out.println("OK - threw: " + e.getMessage());
        }

        // Test 4: String values with null first
        System.out.print("Test 4: {\"a\":null, \"a\":\"x\"} (String values)    ... ");
        Type stringMapType = new TypeToken<Map<String, String>>() {}.getType();
        try {
            Map<String, String> result = gson.fromJson("{\"a\":null,\"a\":\"x\"}", stringMapType);
            System.out.println("BUG - no exception, silently returned: " + result);
        } catch (JsonSyntaxException e) {
            System.out.println("OK - threw: " + e.getMessage());
        }

        System.out.println("\nGson version: " + com.google.gson.internal.GsonBuildConfig.VERSION);
        System.out.println("\nRoot cause: MapTypeAdapterFactory.java uses 'if (replaced != null)'");
        System.out.println("Fix: change to 'if (replaced != null || map.containsKey(key))'");
    }
}
