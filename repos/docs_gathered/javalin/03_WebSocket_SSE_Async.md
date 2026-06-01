# Javalin WebSocket, SSE, and Async Handling

## WebSocket Support

Javalin provides an intuitive way to declare WebSocket endpoints with a path and configure different event handlers in a lambda.

### WebSocket Configuration

```
config.routes.ws("/chat", wsConfig -> {
    wsConfig.onConnect(ws -> {
        // Handle new connection
    });
    wsConfig.onMessage(ws -> {
        // Handle incoming message
        String message = ws.message();
        // Process and broadcast
    });
    wsConfig.onBinaryMessage(ws -> {
        // Handle binary data
        byte[] binaryData = ws.messageAsBytes();
    });
    wsConfig.onClose(ws -> {
        // Handle disconnection
    });
    wsConfig.onError(ws -> {
        // Handle errors
        Throwable error = ws.error();
    });
    wsConfig.onUpgrade(ws -> {
        // Pre-upgrade handling
    });
});
```

### WebSocket Event Handlers

Available handlers:
- **onConnect**: New client connects
- **onMessage**: Text message received
- **onBinaryMessage**: Binary message received
- **onClose**: Client disconnects
- **onError**: Error occurs
- **onUpgrade**: Pre-upgrade handling

## WebSocket Concurrency & Ordering

### Message Ordering Guarantees
- WebSocket operates over TCP
- Messages arrive at server in order sent by client
- Javalin handles messages from a given connection sequentially
- **Order guarantee**: Messages handled in same order client sent them
- **Exception**: Different connections handled in parallel on multiple threads

### Thread Safety Requirements
- WebSocket event handlers must be **thread-safe**
- Different connections execute concurrently on different threads
- Shared resources between handlers require synchronization
- Use thread-safe collections or proper locking mechanisms

## Server-Sent Events (SSE)

Javalin SSE is very simple to implement:

### Basic SSE Configuration

```
config.routes.sse("/events", sseClient -> {
    // Connected SseClient available
    sseClient.sendEvent("hello", "data");
});
```

### Broadcasting to Multiple Clients

```
Set<SseClient> clients = ConcurrentHashMap.newKeySet();

config.routes.sse("/subscribe", client -> {
    clients.add(client);
});

config.routes.post("/broadcast", ctx -> {
    String message = ctx.body();
    clients.forEach(client -> {
        client.sendEvent("update", message);
    });
});
```

### SSE Client Methods
- `sendEvent()` - Send data to client
- `sendComment()` - Send comment
- Standard SSE event format support

## Asynchronous Request Handling

### CompletableFuture Support

You can set future results in endpoint handlers (get/post/put/etc) and after-handlers:

```
get("/async", ctx -> {
    CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
        // Simulate long-running operation
        return "Result";
    });
    ctx.future(future);
});
```

### Handler Execution After Async

- **Exception-handlers**: Run as expected after future resolved/rejected
- **Error-handlers**: Execute after async completion
- **Exceptions in ctx.future()**: Now handled by exception mapper

### Async Best Practices

1. **Use async only when necessary**:
   - If uncertain whether your application requires asynchronous requests, it likely doesn't
   - Synchronous request handling is often sufficient

2. **Virtual Threads Consideration**:
   - Using Loom's virtual threads as default thread-pool might not be best
   - Single synchronized block can drastically downgrade performance
   - Consider traditional thread pools for many concurrent connections

3. **Thread Pool Configuration**:
   - Configure via Jetty settings
   - Virtual threads enabled by default in some versions (disabled in Javalin 6+)
   - Monitor performance impact of thread pool choice

## Future Resolution

When you set a Future as result:
```
ctx.future(myFuture);
```

Javalin switches into asynchronous mode:
- Framework waits for future completion
- Handlers execute in order: before → async completion → after
- Exception handlers catch exceptions from future

## WebSocket vs HTTP

| Aspect | WebSocket | SSE |
|--------|-----------|-----|
| **Connection** | Persistent bidirectional | Long-lived one-way (server to client) |
| **Use Cases** | Real-time chat, gaming, collaboration | Live feeds, notifications, data streams |
| **Message Format** | Binary or text | Text events with IDs |
| **Implementation** | Lambda-based handler routing | Direct client-based approach |
| **Multiple Handlers** | Yes (onConnect, onMessage, etc.) | Single client object |
| **Ordering Guarantees** | Per-connection sequential | Linear delivery |

## WebSocket Chat Example

```
Set<WsContext> clients = ConcurrentHashMap.newKeySet();

config.routes.ws("/chat/{room}", wsConfig -> {
    wsConfig.onConnect(ws -> {
        String room = ws.pathParam("room");
        clients.add(ws);
        broadcast(room, ws.sessionId() + " joined");
    });

    wsConfig.onMessage(ws -> {
        String room = ws.pathParam("room");
        String message = ws.message();
        broadcast(room, ws.sessionId() + ": " + message);
    });

    wsConfig.onClose(ws -> {
        String room = ws.pathParam("room");
        clients.remove(ws);
        broadcast(room, ws.sessionId() + " left");
    });
});

private void broadcast(String room, String message) {
    clients.stream()
        .filter(ws -> room.equals(ws.pathParam("room")))
        .forEach(ws -> ws.send(message));
}
```

## SSE vs Traditional Polling

**Advantages of SSE**:
- Single HTTP connection (less overhead)
- Server controls message delivery
- Automatic reconnection handling
- Browser API support
- Reduced latency vs polling

## Testing SSE Endpoints

**Note**: Testing SSE endpoints with JavalinTest has been a known consideration area (Issue #1546).

Approaches:
1. Integration tests with actual HTTP client
2. Mock the SseClient object
3. Use test utilities from javalin-testtools

## Performance Considerations

- **WebSocket**: Choose for truly bidirectional, low-latency communication
- **SSE**: Choose for simpler one-way server-to-client messaging
- **HTTP Async**: Use CompletableFuture only when truly needed
- **Connection limits**: Monitor concurrent connection counts
- **Memory**: Each open connection consumes memory (especially WebSocket)

## Error Handling in Async

```
config.routes.exception(TimeoutException.class, (e, ctx) -> {
    ctx.status(504).json(Map.of("error", "Request timeout"));
});

get("/timeout-demo", ctx -> {
    CompletableFuture<String> future = new CompletableFuture<>();
    scheduledExecutor.schedule(() -> {
        future.completeExceptionally(new TimeoutException());
    }, 5, TimeUnit.SECONDS);
    ctx.future(future);
});
```

## WebSocket Upgrade Configuration

Pre-upgrade handling allows authentication and validation before WebSocket handshake completes:

```
wsConfig.onUpgrade(ws -> {
    // Validate headers, auth tokens, etc.
    // Return false to reject upgrade
});
```
