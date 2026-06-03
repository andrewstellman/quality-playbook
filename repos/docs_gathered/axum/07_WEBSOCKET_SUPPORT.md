# Axum WebSocket Support

**Source:** https://docs.rs/axum/latest/axum/extract/ws/
**Source:** https://github.com/tokio-rs/axum/blob/main/examples/websockets/src/main.rs
**Version:** 0.8.8+ (feature: ws)
**Accessed:** April 2026

## Overview

Axum provides WebSocket support via the `axum::extract::ws` module (feature-gated with the `ws` feature). WebSocket handling follows Axum's standard patterns: it's implemented as an extractor (`WebSocketUpgrade`) that handlers use to upgrade HTTP connections.

## Enabling WebSocket Support

Add to Cargo.toml:

```toml
[dependencies]
axum = { version = "0.8", features = ["ws"] }
tokio-tungstenite = "0.21"  # Transitive but explicit
```

## Basic WebSocket Handler

The fundamental pattern uses WebSocketUpgrade as an extractor:

```rust
use axum::extract::ws::{WebSocket, WebSocketUpgrade};
use axum::response::IntoResponse;

async fn websocket_handler(ws: WebSocketUpgrade) -> impl IntoResponse {
    ws.on_upgrade(|websocket| async {
        // Handle the websocket connection
        websocket_handler_impl(websocket).await
    })
}

async fn websocket_handler_impl(websocket: WebSocket) {
    let (mut sender, mut receiver) = websocket.split();
    
    while let Some(Ok(msg)) = receiver.next().await {
        if sender.send(msg).await.is_err() {
            break;
        }
    }
}
```

Behavioral contract:
- WebSocketUpgrade is extracted from the HTTP request
- `on_upgrade()` takes an async closure that receives WebSocket
- Closure is executed in a background task
- HTTP response is sent before closure executes
- WebSocket connection runs independently of request

## WebSocketUpgrade Type

The extractor that enables WebSocket upgrades:

```rust
pub struct WebSocketUpgrade {
    // ...
}

impl WebSocketUpgrade {
    pub fn on_upgrade<C, F>(self, f: C) -> impl IntoResponse
    where
        C: FnOnce(WebSocket) -> F + Send + 'static,
        F: Future<Output = ()> + Send + 'static,
    {
        // Returns HTTP 101 Switching Protocols response
        // Executes f in background task
    }
}
```

Behavioral contract:
- Implements FromRequestParts (non-body extractor)
- Returns IntoResponse (can be returned directly)
- Automatically performs HTTP upgrade handshake
- Returns 101 Switching Protocols response
- Closure runs in Tokio task

## WebSocket Type

The handle to the upgraded connection:

```rust
pub struct WebSocket {
    // ...
}

impl WebSocket {
    pub async fn send(&mut self, msg: Message) -> Result<(), Error>;
    pub async fn recv(&mut self) -> Option<Result<Message, Error>>;
    pub fn split(self) -> (SplitSender<WebSocket>, SplitReceiver<WebSocket>);
}

impl futures::Stream for WebSocket {
    type Item = Result<Message, Error>;
}

impl futures::Sink for WebSocket {
    type Item = Message;
}
```

Behavioral contract:
- Implements Stream (can use `next()` from StreamExt)
- Implements Sink (can use `send()` directly)
- `split()` creates independent sender/receiver
- `send()` fails if connection closed
- `recv()` returns None when connection closes
- All operations are async

## Message Types

WebSocket messages from tungstenite:

```rust
pub enum Message {
    Text(String),
    Binary(Vec<u8>),
    Ping(Vec<u8>),
    Pong(Vec<u8>),
    Close(Option<CloseFrame<'static>>),
    Frame(Frame),
}

impl Message {
    pub fn text(s: impl Into<String>) -> Message;
    pub fn binary(d: impl Into<Vec<u8>>) -> Message;
    pub fn ping(d: impl Into<Vec<u8>>) -> Message;
    pub fn pong(d: impl Into<Vec<u8>>) -> Message;
    pub fn close() -> Message;
}
```

Behavioral contract:
- Text and Binary are application-level message types
- Ping/Pong are keep-alive mechanism (typically automatic)
- Close message terminates connection
- Frame is low-level WebSocket frame (rarely used)
- Can pattern match on message types

## Concurrent Message Handling

For concurrent reading and writing:

```rust
use tokio::sync::mpsc;

async fn websocket_handler(ws: WebSocketUpgrade) -> impl IntoResponse {
    ws.on_upgrade(|websocket| async {
        let (sender, receiver) = websocket.split();
        
        let (tx, rx) = mpsc::channel(32);
        
        // Spawn task to forward messages from broadcast to websocket
        tokio::spawn(async move {
            let mut rx = rx;
            let mut sender = sender;
            while let Some(msg) = rx.recv().await {
                if sender.send(msg).await.is_err() {
                    break;
                }
            }
        });
        
        // Spawn task to receive from websocket
        tokio::spawn(async move {
            let mut receiver = receiver;
            while let Some(Ok(msg)) = receiver.next().await {
                // Process message
                // Could forward to broadcast channel, etc.
            }
        });
    })
}
```

Behavioral contract:
- split() creates sender and receiver halves
- Sender can be sent to other tasks (clone tx)
- Receiver must be in reading task
- Can use mpsc or broadcast channels for message passing
- Tasks must be spawned before closure returns

## Protocol Negotiation

WebSocket subprotocol selection:

```rust
async fn websocket_handler(ws: WebSocketUpgrade) -> impl IntoResponse {
    let protocols = ["chat", "game"];
    
    ws.protocols(protocols)
        .on_upgrade(|websocket| async {
            websocket_handler_impl(websocket).await
        })
}
```

Behavioral contract:
- `protocols()` sets offered subprotocols
- Client selects protocol from offered list
- Selected protocol returned by on_upgrade callback
- Allows version or feature negotiation

With protocol selection:

```rust
async fn websocket_handler(ws: WebSocketUpgrade) -> impl IntoResponse {
    let protocols = ["chat/v1", "chat/v2"];
    
    ws.protocols(protocols)
        .on_upgrade(|websocket| async {
            // Check if client selected a protocol
            // websocket.get_ref().protocol() might provide this
            websocket_handler_impl(websocket).await
        })
}
```

## Error Handling

Handling upgrade failures:

```rust
async fn websocket_handler(ws: WebSocketUpgrade) -> impl IntoResponse {
    ws.on_failed_upgrade(|error| {
        eprintln!("WebSocket upgrade failed: {}", error);
    })
    .on_upgrade(|websocket| async {
        websocket_handler_impl(websocket).await
    })
}
```

Behavioral contract:
- `on_failed_upgrade()` is called if upgrade fails in background task
- Error is logged/handled but response already sent
- Used for cleanup or logging on connection failure
- Default behavior is to silently ignore errors

## Integration with Application State

Access state in WebSocket handlers:

```rust
struct AppState {
    channel: broadcast::Sender<String>,
}

async fn websocket_handler(
    State(state): State<Arc<AppState>>,
    ws: WebSocketUpgrade,
) -> impl IntoResponse {
    ws.on_upgrade(|websocket| async move {
        let mut rx = state.channel.subscribe();
        
        handle_socket(websocket, rx).await
    })
}

async fn handle_socket(
    mut ws: WebSocket,
    mut rx: broadcast::Receiver<String>,
) {
    loop {
        tokio::select! {
            msg = rx.recv() => {
                if let Ok(text) = msg {
                    let _ = ws.send(Message::text(text)).await;
                }
            }
            ws_msg = ws.recv() => {
                if let Some(Ok(msg)) = ws_msg {
                    // Handle websocket message
                }
            }
        }
    }
}
```

Behavioral contract:
- State is accessible like any other extractor
- State is Arc<T>, shareable across connections
- Move closure to capture state
- Can use tokio::select! for multiplexing

## Middleware in WebSocket Handlers

Middleware runs before WebSocket upgrade:

```rust
async fn websocket_handler(
    State(state): State<Arc<AppState>>,
    Extension(user): Extension<User>,  // From auth middleware
    ws: WebSocketUpgrade,
) -> impl IntoResponse {
    ws.on_upgrade(|websocket| async move {
        // user is available
        handle_authenticated_socket(websocket, user, state).await
    })
}
```

Behavioral contract:
- Auth middleware runs before WebSocket extraction
- Extensions available in handler
- Extractors run normally
- Middleware rejections prevent WebSocket upgrade
- User information available in upgrade closure

## Connection Lifecycle

```rust
async fn handle_socket(mut ws: WebSocket) {
    loop {
        match ws.recv().await {
            Some(Ok(msg)) => {
                match msg {
                    Message::Text(text) => {
                        // Process text
                        if ws.send(Message::text("response")).await.is_err() {
                            break;  // Connection closed
                        }
                    }
                    Message::Binary(data) => {
                        // Process binary
                    }
                    Message::Close(_) => {
                        break;  // Client closed
                    }
                    _ => {}
                }
            }
            Some(Err(e)) => {
                eprintln!("WebSocket error: {}", e);
                break;  // Connection error
            }
            None => {
                break;  // Connection closed
            }
        }
    }
}
```

Behavioral contract:
- recv() returns None when connection closes
- Close message indicates normal closure
- Error in recv() indicates protocol violation or connection loss
- send() fails when connection already closed
- Break/return to cleanly close handler

## Broadcasting to Multiple Clients

Common pattern using broadcast channel:

```rust
struct AppState {
    tx: broadcast::Sender<Message>,
}

async fn websocket_handler(
    State(state): State<Arc<AppState>>,
    ws: WebSocketUpgrade,
) -> impl IntoResponse {
    ws.on_upgrade(|ws| async move {
        let mut rx = state.tx.subscribe();
        
        handle_client(ws, rx, state.tx.clone()).await
    })
}

async fn handle_client(
    mut ws: WebSocket,
    mut rx: broadcast::Receiver<Message>,
    tx: broadcast::Sender<Message>,
) {
    loop {
        tokio::select! {
            msg = rx.recv() => {
                if let Ok(msg) = msg {
                    if ws.send(msg).await.is_err() {
                        break;
                    }
                }
            }
            msg = ws.recv() => {
                match msg {
                    Some(Ok(msg)) => {
                        let _ = tx.send(msg);
                    }
                    _ => break,
                }
            }
        }
    }
}
```

Behavioral contract:
- broadcast::Sender can be cloned and used by multiple clients
- Each client has independent Receiver
- Sends are fire-and-forget (slow receivers drop messages)
- Useful for chat, notifications, live updates

## Performance Considerations

1. **Message buffering** - Default limits apply
2. **Connection count** - Each WebSocket uses one task and connection
3. **Memory per connection** - Buffers, task overhead
4. **Backpressure** - WebSocket doesn't support explicit backpressure
5. **CPU usage** - Message handling is the main CPU consumer

## Important Behavioral Contracts

1. **Upgrade is background task** - Handler returns immediately, socket runs separately
2. **101 Switching Protocols** - Sent automatically before on_upgrade closure
3. **Single connection per upgrade** - One HTTP upgrade per handler call
4. **Concurrent access** - split() enables concurrent send/receive
5. **Message order** - Preserved within stream
6. **Closure lifetime** - Owns the WebSocket, lives until connection closes
7. **State sharing** - Arc<T> enables sharing across connections
8. **Error handling** - send/recv failures indicate closed connection

## Known Issues and Edge Cases

1. **Slow message processing** - Can accumulate backlog
2. **Memory leaks** - Forgotten close handlers or circular references
3. **Protocol violations** - Invalid frames cause connection loss
4. **Binary data encoding** - Must match application protocol
5. **Subprotocol negotiation** - Not all clients support or check protocols
6. **Ping/Pong handling** - Typically automatic but may need manual handling
7. **Graceful shutdown** - May need to wait for tasks

## Router Configuration

WebSocket route registration:

```rust
let router = Router::new()
    .route("/ws", get(websocket_handler))
    .route("/chat", get(chat_handler))
    .layer(middleware::auth)  // Auth before WebSocket
    .with_state(state);
```

Behavioral contract:
- Use `get()` for WebSocket routes (GET upgrade request)
- Other HTTP methods don't make sense for WebSocket
- Middleware applies before WebSocket upgrade
- Full routing and extraction available

## Streaming Bodies in WebSocket

Limited support for streaming response bodies (WebSockets don't use typical response bodies post-upgrade):

```rust
async fn handler(ws: WebSocketUpgrade) -> impl IntoResponse {
    ws.on_upgrade(|ws| async move {
        // Stream data via WebSocket messages, not response body
    })
}
```

Behavioral contract:
- WebSocket is full-duplex streaming
- Not the same as HTTP streaming responses
- Use Message frames for all data transfer

## Sources

- https://docs.rs/axum/latest/axum/extract/ws/
- https://docs.rs/tokio-tungstenite/latest/tokio_tungstenite/
- https://github.com/tokio-rs/axum/blob/main/examples/websockets/src/main.rs
- https://tools.ietf.org/html/rfc6455 (WebSocket Protocol)
