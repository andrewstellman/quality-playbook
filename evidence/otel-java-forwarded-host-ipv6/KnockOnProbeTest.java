/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

package io.opentelemetry.instrumentation.api.semconv.http;

import static io.opentelemetry.semconv.ServerAttributes.SERVER_ADDRESS;
import static io.opentelemetry.semconv.ServerAttributes.SERVER_PORT;
import static java.nio.charset.StandardCharsets.UTF_8;

import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.common.AttributesBuilder;
import io.opentelemetry.context.Context;
import io.opentelemetry.instrumentation.api.instrumenter.AttributesExtractor;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;

// Temporary before/after probe. Not part of the patch.
class KnockOnProbeTest {

  private static final String[][] CASES = {
    {"host", "example.com"},
    {"host", "example.com:8080"},
    {"host", "example.com:"},
    {"host", "example.com:port"},
    {"host", "1.2.3.4:80"},
    {"host", ":8080"},
    {"host", "[::1]"},
    {"host", "[::1]:8080"},
    {"host", "[2001:db8::1]:8080"},
    {"host", "[fe80::1%25eth0]:80"},
    {"host", "[::1]:port"},
    {"host", "[::1]:"},
    {"host", "[::1]x"},
    {"host", "[]"},
    {"host", "[]:80"},
    {"host", "[::1"},
    {"host", "\"[::1]:8080\""},
    {"x-forwarded-host", "[::1]:8080"},
    {"x-forwarded-host", "example.com:8080"},
    {":authority", "[::1]:8443"},
    {"forwarded", "host=\"[2001:db8::1]:42\""},
    {"forwarded", "host=[::1]:42"},
    {"forwarded", "for=1.2.3.4;host=example.com:42"},
    {"forwarded", "host=\"[::1\""},
    {"x-forwarded-host", "[::1", "host", "example.com:80"},
    {"forwarded", "host=\"[::1\"", "host", "[2001:db8::2]:81"},
  };

  @Test
  void probe() throws Exception {
    try (PrintWriter out = new PrintWriter(Files.newBufferedWriter(Paths.get(System.getenv("PROBE_OUT")), UTF_8))) {
      for (String[] c : CASES) {
        Map<String, String> request = new LinkedHashMap<>();
        StringBuilder label = new StringBuilder();
        for (int i = 0; i < c.length; i += 2) {
          request.put("header." + c[i], c[i + 1]);
          label.append(i > 0 ? " + " : "").append(c[i]).append(": ").append(c[i + 1]);
        }
        AttributesExtractor<Map<String, String>, Map<String, String>> extractor =
            HttpServerAttributesExtractor.create(
                new HttpServerAttributesExtractorTest.TestHttpServerAttributesGetter());
        AttributesBuilder builder = Attributes.builder();
        extractor.onStart(builder, Context.root(), request);
        Attributes attrs = builder.build();
        String address = attrs.get(SERVER_ADDRESS);
        Long port = attrs.get(SERVER_PORT);
        out.println(
            label
                + "\t"
                + (address == null ? "(none)" : "\"" + address + "\"")
                + "\t"
                + (port == null ? "(none)" : port.toString()));
      }
    }
  }
}
