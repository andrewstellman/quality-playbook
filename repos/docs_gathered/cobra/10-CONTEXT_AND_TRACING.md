# Context and Tracing Support

**Sources**:
- https://cobra.dev/docs/how-to-guides/context-and-tracing/
- OpenTelemetry documentation
- https://www.jvt.me/posts/2024/11/17/cobra-otel-lessons/

**Accessed**: 2026-04-04

---

## Context Propagation

### Accessing Context
Every Cobra command provides access to a context:

```go
cmd.RunE = func(cmd *cobra.Command, args []string) error {
    ctx := cmd.Context()
    // Use context for cancellation, deadlines, tracing
    return doWorkWithContext(ctx)
}
```

**Context carries**:
- Cancellation signals
- Deadlines
- Trace information
- Custom values

### Context Inheritance
Context propagates from:
- Root command through all child commands
- Parent hooks to child execution
- Available in all lifecycle phases

---

## OpenTelemetry Integration

### Observable from Day One
Cobra applications can be transformed into observable systems with comprehensive context propagation and distributed tracing.

### SDK Initialization
```go
// Initialize in main() before Execute()
exporter, _ := otlptracehttp.New(context.Background())
provider := tracesdk.NewTracerProvider(
    tracesdk.WithBatcher(exporter),
)
otel.SetTracerProvider(provider)
```

### Service Configuration
Define service metadata:
```go
resource := resource.NewWithAttributes(
    semconv.SchemaURL,
    semconv.ServiceName("myapp"),
    semconv.DeploymentEnvironment("prod"),
)
```

---

## Instrumentation Patterns

### Command-Level Spans
Create spans for individual commands:

```go
cmd.RunE = func(cmd *cobra.Command, args []string) error {
    ctx, span := tracer.Start(cmd.Context(), cmd.CommandPath())
    defer span.End()

    span.SetAttributes(
        attribute.String("environment", os.Getenv("ENV")),
        attribute.Int("file_size", fileSize),
    )

    return doWork(ctx)
}
```

### Span Attributes
Track meaningful data:
- Operation type
- Environment designation
- File sizes and counts
- User information
- Request IDs

### Span Status Management
Record outcomes:

```go
if err != nil {
    span.RecordError(err)
    span.SetStatus(codes.Error, err.Error())
} else {
    span.SetStatus(codes.Ok, "")
}
```

---

## Distributed Tracing

### Hierarchical Tracing
Parent commands propagate context to child commands:

```go
rootCmd.PersistentPreRunE = func(cmd *cobra.Command, args []string) error {
    ctx, span := tracer.Start(cmd.Context(), "root-setup")
    defer span.End()
    // Context passed to children
    return nil
}
```

### Backend Integration

**Jaeger** (local development):
```bash
docker run -p 6831:6831/udp -p 16686:16686 jaegertracing/all-in-one
```

Configuration:
```go
exporter, _ := otlptracehttp.New(
    context.Background(),
    otlptracehttp.WithEndpoint("localhost:4317"),
)
```

**Cloud Providers**:
- AWS X-Ray via custom propagators
- Google Cloud Trace via dedicated exporters
- Honeycomb and similar SaaS platforms

---

## Environment Configuration

### OTEL Environment Variables

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.example.com:4317
OTEL_SERVICE_NAME=myapp
OTEL_DEPLOYMENT_ENVIRONMENT=production
OTEL_SAMPLE_RATE=0.1
```

### Sampling Strategy

**Sampling in production**:
- Ratio-based sampling: Only trace 10% of requests
- Parent-based sampling: Propagate parent's decision
- Reduces overhead in high-volume environments

```go
sampler := sdktrace.TraceIDRatioBased(0.1)  // 10% sampling
```

---

## Production Best Practices

### Bounded Attributes
Limit span attributes to meaningful, bounded values:

```go
// GOOD
span.SetAttributes(
    attribute.String("status", result),  // Fixed set of values
    attribute.Int("count", n),           // Numeric
)

// BAD
span.SetAttributes(
    attribute.String("user_input", rawInput),  // Unbounded cardinality
)
```

### Resource Configuration
Automatic detection of:
- Process metadata
- OS information
- Container/Kubernetes metadata
- Host information

```go
resource.NewWithAttributes(
    semconv.SchemaURL,
    semconv.ServiceNameKey.String("myapp"),
    semconv.ProcessPID(os.Getpid()),
)
```

### Graceful Shutdown
Properly flush traces:

```go
defer func() {
    if err := provider.ForceFlush(context.Background()); err != nil {
        log.Printf("Error flushing traces: %v", err)
    }
}()
```

---

## Context for Cancellation

### Timeout Handling
Use context for timeouts:

```go
ctx, cancel := context.WithTimeout(cmd.Context(), 30*time.Second)
defer cancel()

return doWorkWithTimeout(ctx)
```

### Graceful Cancellation
Handle context cancellation:

```go
select {
case <-ctx.Done():
    return ctx.Err()  // Context cancelled or deadline exceeded
case result := <-workChan:
    return processResult(result)
}
```

---

## Troubleshooting

### Trace Visibility Issues
- Verify endpoint connectivity
- Check backend logs for reception
- Confirm service name in traces

### Memory Growth
- Apply stricter sampling ratios
- Configure batch processor queue limits
- Monitor trace volume

### Context Loss
- Ensure context propagation through hierarchies
- Use context values for cross-cutting concerns
- Implement span linking for async operations

---

## References

- **Context & Tracing**: https://cobra.dev/docs/how-to-guides/context-and-tracing/
- **OpenTelemetry**: https://opentelemetry.io/
- **Lessons Learned**: https://www.jvt.me/posts/2024/11/17/cobra-otel-lessons/
