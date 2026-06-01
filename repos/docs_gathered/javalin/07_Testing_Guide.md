# Javalin Testing Guide

## Testing Philosophy

Since Javalin is just a library, you're more or less free to test however you like. There is no "Javalin way" of testing. However, Javalin provides tools and patterns that work well for different test types.

## Three Testing Approaches

### 1. Unit Tests

Unit tests target isolated components implementing the `Handler` interface.

**Characteristics**:
- Very fast and cheap to run
- Require mocking of objects
- Test business logic in isolation
- No HTTP requests made

**Dependencies**:
- Mocking library: Mockito (Java) or MockK (Kotlin)
- Assertion library: AssertJ (recommended)
- JUnit 5 (or preferred test framework)

**Pattern**:
Mock the `Context` object since it's responsible for input and output in Javalin Handlers.

**Example - Unit Test with Mockito**:
```java
@Test
public void testUserCreationHandler() {
    // Arrange
    Context ctx = mock(Context.class);
    User inputUser = new User("John", "john@example.com");

    when(ctx.bodyAsClass(User.class)).thenReturn(inputUser);

    CreateUserHandler handler = new CreateUserHandler();

    // Act
    handler.handle(ctx);

    // Assert
    verify(ctx).status(201);
    ArgumentCaptor<String> captor = ArgumentCaptor.forClass(String.class);
    verify(ctx).json(captor.capture());

    // Verify user was created
    String jsonResponse = captor.getValue();
    assertThat(jsonResponse).contains("John");
}
```

**Example - Unit Test with Kotlin/MockK**:
```kotlin
@Test
fun testUserCreationHandler() {
    // Arrange
    val ctx = mockk<Context>()
    val inputUser = User("John", "john@example.com")

    every { ctx.bodyAsClass(User::class.java) } returns inputUser
    every { ctx.status(any()) } returns ctx
    every { ctx.json(any()) } just runs

    val handler = CreateUserHandler()

    // Act
    handler.handle(ctx)

    // Assert
    verify { ctx.status(201) }
    verify { ctx.json(any()) }
}
```

**Benefits**:
- Fast test execution (milliseconds)
- No external dependencies needed
- Good for testing business logic
- Easy to run in CI/CD

**Limitations**:
- Doesn't test actual HTTP handling
- Mock behavior may differ from real Context
- Requires deep mocking for complex handlers

### 2. Functional/Integration Tests

Functional tests employ "black box" testing, focusing only on business requirements and expected output.

**Characteristics**:
- Test complete HTTP flow
- Start actual Javalin server
- Make real HTTP requests
- Slower than unit tests but comprehensive

**Dependencies**:
- `javalin-testtools` (included in javalin-bundle)
- HTTP client library: RestAssured or Fuel
- JUnit 5

**Pattern**:
Use `javalin-testtools` which comes included in the javalin-bundle.

**Example - Integration Test with RestAssured**:
```java
class FunctionalTests {
    private Javalin app;

    @BeforeEach
    void setUp() {
        app = Javalin.create().start();
        setupRoutes(app);
    }

    @AfterEach
    void tearDown() {
        app.stop();
    }

    @Test
    public void testCreateUser() {
        User newUser = new User("Jane", "jane@example.com");

        given()
            .body(newUser)
            .contentType(ContentType.JSON)
        .when()
            .post("http://localhost:8080/users")
        .then()
            .statusCode(201)
            .body("id", notNullValue())
            .body("name", equalTo("Jane"));
    }

    @Test
    public void testGetUser() {
        given()
        .when()
            .get("http://localhost:8080/users/1")
        .then()
            .statusCode(200)
            .body("name", equalTo("John"));
    }

    @Test
    public void testDeleteUser() {
        given()
        .when()
            .delete("http://localhost:8080/users/1")
        .then()
            .statusCode(204);
    }

    @Test
    public void testUserNotFound() {
        given()
        .when()
            .get("http://localhost:8080/users/9999")
        .then()
            .statusCode(404);
    }
}
```

**Example - Using Javalin Test Tools**:
```java
class JavalinTestToolsExample {
    private Javalin app;

    @BeforeEach
    void setUp() {
        app = Javalin.create().start();
        setupTestRoutes(app);
    }

    @Test
    public void testWithTestClient() {
        TestClient client = new TestClient(app);

        TestResponse response = client.post("/users", "{\"name\": \"Bob\"}");

        assertThat(response.status()).isEqualTo(201);
        assertThat(response.body()).contains("Bob");
    }
}
```

**Test Performance**:
Javalin's test suite "starts and stops more than 500 Javalin instances, and running all the tests takes about ten seconds total."

**Benefits**:
- Tests actual HTTP behavior
- Validates complete request/response cycle
- Catches integration issues
- More realistic than unit tests

**Limitations**:
- Slower than unit tests
- May need to reset state between tests
- Database/external services may need mocking

### 3. End-to-End/UI Tests

These simulate user interactions using Selenium WebDriver.

**Characteristics**:
- Test complete user workflows
- Simulate browser interactions
- Slowest type of test
- Most comprehensive but brittle

**Dependencies**:
- Selenium WebDriver
- WebDriverManager (automatic driver management)
- Headless browser (Chrome/Firefox)

**Example - UI Test with Selenium**:
```java
class UITests {
    private WebDriver driver;
    private Javalin app;

    @BeforeEach
    void setUp() {
        // Start Javalin app
        app = Javalin.create().start();
        setupRoutes(app);

        // Setup headless Chrome
        WebDriverManager.chromedriver().setup();
        ChromeOptions options = new ChromeOptions();
        options.addArguments("--headless");
        driver = new ChromeDriver(options);
    }

    @AfterEach
    void tearDown() {
        driver.quit();
        app.stop();
    }

    @Test
    public void testUserCanCreateAccount() {
        // Navigate to sign up page
        driver.get("http://localhost:8080/signup");

        // Fill form
        driver.findElement(By.id("username")).sendKeys("newuser");
        driver.findElement(By.id("email")).sendKeys("user@example.com");
        driver.findElement(By.id("password")).sendKeys("password123");

        // Submit form
        driver.findElement(By.id("submit-btn")).click();

        // Verify redirect to dashboard
        wait(10).until(urlContains("/dashboard"));
        assertThat(driver.getCurrentUrl()).contains("/dashboard");
    }

    @Test
    public void testUserCanLogin() {
        driver.get("http://localhost:8080/login");

        driver.findElement(By.id("username")).sendKeys("testuser");
        driver.findElement(By.id("password")).sendKeys("testpass");
        driver.findElement(By.id("login-btn")).click();

        wait(10).until(presenceOfElementLocated(By.id("dashboard")));
        WebElement dashboard = driver.findElement(By.id("dashboard"));
        assertThat(dashboard.isDisplayed()).isTrue();
    }
}
```

**Benefits**:
- Tests real user flows
- Validates UI/UX
- Catches visual bugs
- Most realistic tests

**Limitations**:
- Very slow (seconds per test)
- Brittle (UI changes break tests)
- Hard to debug failures
- Expensive to maintain
- Flaky (timing issues)

## Testing Static Files and SPA Routes

```java
@Test
public void testStaticFiles() {
    given()
    .when()
        .get("http://localhost:8080/index.html")
    .then()
        .statusCode(200)
        .contentType("text/html");
}

@Test
public void testSPARouting() {
    // SPA falls back to index.html for unknown routes
    given()
    .when()
        .get("http://localhost:8080/unknown-route")
    .then()
        .statusCode(200)
        .body(containsString("SPA root"));
}
```

## Testing WebSockets

**Unit Testing WebSocket Handlers**:
```java
@Test
public void testWebSocketHandler() {
    WsContext ctx = mock(WsContext.class);
    when(ctx.message()).thenReturn("test message");

    WebSocketHandler handler = (ws) -> {
        String msg = ws.message();
        ws.send(msg.toUpperCase());
    };

    handler.handle(ctx);

    verify(ctx).send("TEST MESSAGE");
}
```

**Integration Testing WebSockets**:
```java
@Test
public void testWebSocketChat() throws Exception {
    // Start server
    Javalin app = Javalin.create().start();
    setupWebSocketRoute(app);

    // Connect WebSocket client
    WebSocketClient client = new WebSocketClient(
        new URI("ws://localhost:8080/chat")
    );
    client.connect();

    // Wait for connection
    client.getConnection().waitForState(OPEN);

    // Send message
    client.send("Hello");

    // Verify response
    String response = client.getResponse(1, TimeUnit.SECONDS);
    assertThat(response).contains("Hello");

    client.close();
    app.stop();
}
```

## Testing Async Handlers

```java
@Test
public void testAsyncHandler() {
    app.get("/async", ctx -> {
        CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
            try {
                Thread.sleep(100);
                return "Async Result";
            } catch (InterruptedException e) {
                throw new RuntimeException(e);
            }
        });
        ctx.future(future);
    });

    given()
    .when()
        .get("http://localhost:8080/async")
    .then()
        .statusCode(200)
        .body(equalTo("Async Result"));
}
```

## Testing Error Handlers

```java
@Test
public void testErrorHandler() {
    app.error(404, ctx -> {
        ctx.json(Map.of("error", "Not found", "status", 404));
    });

    given()
    .when()
        .get("http://localhost:8080/nonexistent")
    .then()
        .statusCode(404)
        .body("error", equalTo("Not found"));
}

@Test
public void testExceptionHandler() {
    app.exception(MyException.class, (e, ctx) -> {
        ctx.status(400).json(Map.of("error", e.getMessage()));
    });

    given()
    .when()
        .get("http://localhost:8080/trigger-error")
    .then()
        .statusCode(400);
}
```

## Testing Validation

```java
@Test
public void testValidationError() {
    app.post("/validate", ctx -> {
        int age = ctx.queryParamAsClass("age", Integer.class).required().get();
        ctx.result("Age: " + age);
    });

    // Valid
    given()
    .when()
        .post("http://localhost:8080/validate?age=25")
    .then()
        .statusCode(200);

    // Invalid - missing required param
    given()
    .when()
        .post("http://localhost:8080/validate")
    .then()
        .statusCode(400);
}
```

## Testing Authentication

```java
@Test
public void testProtectedEndpoint() {
    app.get("/protected", ctx -> {
        String token = ctx.header("Authorization");
        if (token != null && isValidToken(token)) {
            ctx.result("Protected content");
        } else {
            ctx.status(401).result("Unauthorized");
        }
    });

    // Without token
    given()
    .when()
        .get("http://localhost:8080/protected")
    .then()
        .statusCode(401);

    // With valid token
    given()
        .header("Authorization", "Bearer valid-token")
    .when()
        .get("http://localhost:8080/protected")
    .then()
        .statusCode(200);
}
```

## Best Practices

1. **Test Isolation**:
   - Each test should be independent
   - Clean up resources in @AfterEach
   - Don't rely on test execution order

2. **Clear Test Names**:
   ```java
   @Test
   public void shouldReturn404WhenUserNotFound() { }

   @Test
   public void shouldCreateUserWithValidData() { }
   ```

3. **Arrange-Act-Assert Pattern**:
   ```java
   @Test
   public void test() {
       // Arrange - setup
       User user = new User("Test");

       // Act - execute
       response = createUser(user);

       // Assert - verify
       assertThat(response.status()).isEqualTo(201);
   }
   ```

4. **Use Test Fixtures**:
   ```java
   @BeforeEach
   void setupTestData() {
       // Create common test data
   }
   ```

5. **Test Edge Cases**:
   - Null values
   - Empty inputs
   - Boundary conditions
   - Error scenarios

## Mocking Javalin Classes

For older versions (before Javalin 2.1.0), special mocking considerations apply. See official guide for version-specific advice.

## Recommended Testing Stack

- **Unit Tests**: JUnit 5 + Mockito/MockK + AssertJ
- **Integration Tests**: JUnit 5 + RestAssured + Javalin TestTools
- **UI Tests**: Selenium + WebDriverManager + Junit 5
- **Test Reporting**: JaCoCo (code coverage)
- **CI/CD**: GitHub Actions, GitLab CI, Jenkins

## References

- Official Testing Tutorial: https://javalin.io/tutorials/testing
- Javalin TestTools: Included in javalin-bundle
- Mockito Documentation: https://javadoc.io/doc/org.mockito/mockito-core
- RestAssured Guide: https://rest-assured.io/
- Selenium WebDriver: https://www.selenium.dev/
