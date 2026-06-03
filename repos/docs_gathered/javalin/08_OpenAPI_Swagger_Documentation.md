# Javalin OpenAPI and Swagger Documentation

## Overview

The Javalin OpenAPI plugin creates an OpenAPI spec (previously known as a "Swagger spec"), which is an API description format for REST APIs readable for both humans and machines. The spec enables:
- Interactive web-based documentation
- Automatic API client generation
- API validation and testing
- Clear API contracts

## OpenAPI/Swagger in Javalin

OpenAPI specification version 3 is the current standard. A spec can be used to:
1. Generate web-based documentation (Swagger UI, ReDoc)
2. Generate API clients for all major languages (OpenAPI Generator)
3. Validate API implementations
4. Create API contracts for testing

## Setup and Configuration

### Dependencies

Maven setup with essential plugins:

```xml
<dependencies>
    <!-- Core Javalin -->
    <dependency>
        <groupId>io.javalin</groupId>
        <artifactId>javalin-bundle</artifactId>
        <version>7.x.x</version>
    </dependency>

    <!-- OpenAPI Documentation Plugin -->
    <dependency>
        <groupId>io.javalin.community.openapi</groupId>
        <artifactId>javalin-openapi-plugin</artifactId>
        <version>6.1.x</version>
    </dependency>

    <!-- Swagger UI for interactive docs -->
    <dependency>
        <groupId>io.javalin.community.openapi</groupId>
        <artifactId>javalin-swagger-plugin</artifactId>
        <version>6.1.x</version>
    </dependency>

    <!-- ReDoc for alternative documentation -->
    <dependency>
        <groupId>io.javalin.community.openapi</groupId>
        <artifactId>javalin-redoc-plugin</artifactId>
        <version>6.1.x</version>
    </dependency>
</dependencies>
```

### Plugin Registration

```java
var app = Javalin.create(config -> {
    // Register OpenAPI plugin
    config.registerPlugin(new OpenApiPlugin(openApi -> {
        openApi.setDocumentationPath("/swagger-ui");
        openApi.setDefinitionPath("/openapi.json");
        openApi.title = "My REST API";
        openApi.version = "1.0.0";
        openApi.description = "API for managing users and posts";
    }));

    // Register Swagger UI
    config.registerPlugin(new SwaggerPlugin(swagger -> {
        swagger.setDocumentationPath("/swagger-ui");
        swagger.setDefinitionPath("/openapi.json");
    }));

    // Optional: Register ReDoc
    config.registerPlugin(new ReDocPlugin(redoc -> {
        redoc.setDocumentationPath("/redoc");
        redoc.setDefinitionPath("/openapi.json");
    }));

    // Define routes with documentation
    config.routes(() -> {
        get("/users", getUsersHandler());
        post("/users", createUserHandler());
        get("/users/{id}", getUserHandler());
        put("/users/{id}", updateUserHandler());
        delete("/users/{id}", deleteUserHandler());
    });
}).start();
```

## Documenting Endpoints with Annotations

### @OpenApi Annotation

Use `@OpenApi` annotation on handler methods to document endpoints:

```java
public static Handler getUsersHandler() {
    return new OpenApi(
        new OpenApiDocumentation()
            .operation(op -> {
                op.summary("List all users");
                op.description("Retrieve a paginated list of all users");
                op.operationId("listUsers");
                op.addTagsItem("Users");
            })
            .queryParameter("page", Integer.class, p -> {
                p.description("Page number (starting from 0)");
                p.required(false);
            })
            .queryParameter("limit", Integer.class, p -> {
                p.description("Results per page (max 100)");
                p.required(false);
            })
            .response(200, response -> {
                response.description("Successful response");
                response.addContent("application/json", mediaType -> {
                    mediaType.schema = new Schema()
                        .type("array")
                        .items(new Schema().$ref("#/components/schemas/User"));
                });
            })
            .response(401, response -> {
                response.description("Unauthorized");
            })
    ).handler(ctx -> {
        // Handler implementation
        ctx.json(getAllUsers());
    });
}
```

### Documentation Properties

Common properties for endpoint documentation:

- **summary**: Short description of what the endpoint does
- **operationId**: Unique ID for client generation
- **tags**: Categorize related endpoints
- **description**: Detailed explanation
- **pathParams**: Path parameters like `/users/{id}`
- **queryParams**: Query string parameters
- **formParams**: Form data parameters
- **requestBody**: Expected input structures with schema
- **responses**: Status codes and response bodies

## Complete User CRUD Example

```java
public class UserAPI {

    // Schema definition
    static class User {
        public int id;
        public String name;
        public String email;
        public String createdAt;
    }

    public static void main(String[] args) {
        var app = Javalin.create(config -> {
            config.registerPlugin(new OpenApiPlugin(openApi -> {
                openApi.title = "User Management API";
                openApi.version = "1.0.0";
            }));

            config.registerPlugin(new SwaggerPlugin());

            config.routes(() -> {
                // Get all users
                get("/users", openApi(
                    new OpenApiDocumentation()
                        .operation(op -> {
                            op.summary("List users");
                            op.operationId("listUsers");
                            op.addTagsItem("Users");
                        })
                        .response(200, response -> {
                            response.description("List of users");
                        }),
                    ctx -> {
                        ctx.json(getAllUsers());
                    }
                ));

                // Create user
                post("/users", openApi(
                    new OpenApiDocumentation()
                        .operation(op -> {
                            op.summary("Create user");
                            op.operationId("createUser");
                            op.addTagsItem("Users");
                        })
                        .requestBody(new RequestBody()
                            .required(true)
                            .description("User to create")
                            .addContent("application/json", mediaType -> {
                                mediaType.schema = userSchema();
                            })
                        )
                        .response(201, response -> {
                            response.description("User created");
                            response.addContent("application/json", mediaType -> {
                                mediaType.schema = userSchema();
                            });
                        })
                        .response(400, response -> {
                            response.description("Invalid input");
                        }),
                    ctx -> {
                        User user = ctx.bodyAsClass(User.class);
                        User created = createUser(user);
                        ctx.status(201).json(created);
                    }
                ));

                // Get single user
                get("/users/{id}", openApi(
                    new OpenApiDocumentation()
                        .operation(op -> {
                            op.summary("Get user");
                            op.operationId("getUser");
                            op.addTagsItem("Users");
                        })
                        .pathParameter("id", Integer.class, p -> {
                            p.description("User ID");
                        })
                        .response(200, response -> {
                            response.description("User details");
                            response.addContent("application/json", mediaType -> {
                                mediaType.schema = userSchema();
                            });
                        })
                        .response(404, response -> {
                            response.description("User not found");
                        }),
                    ctx -> {
                        int id = ctx.pathParamAsClass("id", Integer.class).get();
                        User user = getUserById(id);
                        if (user != null) {
                            ctx.json(user);
                        } else {
                            ctx.status(404);
                        }
                    }
                ));

                // Update user
                put("/users/{id}", openApi(
                    new OpenApiDocumentation()
                        .operation(op -> {
                            op.summary("Update user");
                            op.operationId("updateUser");
                            op.addTagsItem("Users");
                        })
                        .pathParameter("id", Integer.class)
                        .requestBody(new RequestBody()
                            .required(true)
                            .addContent("application/json", mediaType -> {
                                mediaType.schema = userSchema();
                            })
                        )
                        .response(200, response -> {
                            response.description("User updated");
                        })
                        .response(404, response -> {
                            response.description("User not found");
                        }),
                    ctx -> {
                        int id = ctx.pathParamAsClass("id", Integer.class).get();
                        User user = ctx.bodyAsClass(User.class);
                        User updated = updateUser(id, user);
                        if (updated != null) {
                            ctx.json(updated);
                        } else {
                            ctx.status(404);
                        }
                    }
                ));

                // Delete user
                delete("/users/{id}", openApi(
                    new OpenApiDocumentation()
                        .operation(op -> {
                            op.summary("Delete user");
                            op.operationId("deleteUser");
                            op.addTagsItem("Users");
                        })
                        .pathParameter("id", Integer.class)
                        .response(204, response -> {
                            response.description("User deleted");
                        })
                        .response(404, response -> {
                            response.description("User not found");
                        }),
                    ctx -> {
                        int id = ctx.pathParamAsClass("id", Integer.class).get();
                        if (deleteUser(id)) {
                            ctx.status(204);
                        } else {
                            ctx.status(404);
                        }
                    }
                ));
            });
        }).start();
    }

    static Schema userSchema() {
        return new Schema()
            .type("object")
            .addProperty("id", new IntegerSchema())
            .addProperty("name", new StringSchema())
            .addProperty("email", new StringSchema()
                .format("email"))
            .addProperty("createdAt", new StringSchema()
                .format("date-time"));
    }

    // Handler implementations
    static List<User> getAllUsers() {
        // Implementation
        return new ArrayList<>();
    }

    static User createUser(User user) {
        // Implementation
        return user;
    }

    static User getUserById(int id) {
        // Implementation
        return null;
    }

    static User updateUser(int id, User user) {
        // Implementation
        return user;
    }

    static boolean deleteUser(int id) {
        // Implementation
        return true;
    }
}
```

## Accessing Documentation

Once configured, documentation is available at:
- **Swagger UI**: http://localhost:8080/swagger-ui
- **OpenAPI JSON**: http://localhost:8080/openapi.json
- **ReDoc** (if enabled): http://localhost:8080/redoc

## OpenAPI Generator

Generate client libraries from OpenAPI specification:

```bash
# Generate Java client
openapi-generator-cli generate \
    -i http://localhost:8080/openapi.json \
    -g java \
    -o ./generated-client

# Generate Python client
openapi-generator-cli generate \
    -i http://localhost:8080/openapi.json \
    -g python \
    -o ./generated-python-client

# Generate TypeScript client
openapi-generator-cli generate \
    -i http://localhost:8080/openapi.json \
    -g typescript-fetch \
    -o ./generated-ts-client
```

## Advanced Documentation Features

### Error Response Documentation

```java
.response(400, response -> {
    response.description("Bad Request");
    response.addContent("application/json", mediaType -> {
        mediaType.schema = new Schema()
            .type("object")
            .addProperty("error", new StringSchema())
            .addProperty("code", new IntegerSchema());
    });
})
```

### Security Documentation

```java
openApi.addSecurityScheme("bearerAuth", new SecurityScheme()
    .type("http")
    .scheme("bearer")
    .bearerFormat("JWT")
);

// Apply to endpoint
.security(new SecurityRequirement()
    .addList("bearerAuth")
)
```

### Content Negotiation

```java
.response(200, response -> {
    response.description("Success");
    response.addContent("application/json", jsonMediaType);
    response.addContent("application/xml", xmlMediaType);
})
```

### Deprecated Endpoints

```java
.operation(op -> {
    op.summary("Old endpoint");
    op.deprecated(true);
})
```

## Best Practices for Documentation

1. **Keep Descriptions Clear and Concise**
   - Summarize in first sentence
   - Provide examples if needed

2. **Document All Status Codes**
   - 200/201 for success
   - 400 for client errors
   - 401 for auth failures
   - 404 for not found
   - 500 for server errors

3. **Define Request/Response Schemas**
   - Use consistent schema definitions
   - Include all fields
   - Document constraints

4. **Use Tags for Organization**
   - Group related endpoints
   - Keep tags consistent
   - Use clear naming

5. **Versioning**
   - Include version in spec
   - Document API changes
   - Support multiple versions if needed

6. **Examples**
   - Provide request examples
   - Include response examples
   - Show error responses

## Javalin-OpenAPI Annotation Processor

For compile-time OpenAPI documentation without reflection:

```xml
<dependency>
    <groupId>io.javalin.community.openapi</groupId>
    <artifactId>javalin-openapi-annotation-processor</artifactId>
    <version>6.1.x</version>
    <scope>provided</scope>
</dependency>
```

This generates OpenAPI documentation at compile time for better performance.

## Testing OpenAPI Endpoints

```java
@Test
public void testSwaggerUIAvailable() {
    given()
    .when()
        .get("http://localhost:8080/swagger-ui")
    .then()
        .statusCode(200)
        .contentType(ContentType.HTML);
}

@Test
public void testOpenAPISpec() {
    given()
    .when()
        .get("http://localhost:8080/openapi.json")
    .then()
        .statusCode(200)
        .contentType(ContentType.JSON)
        .body("info.title", equalTo("My REST API"));
}
```

## References

- Official Tutorial: https://javalin.io/tutorials/openapi-example
- Javalin OpenAPI Plugin: https://github.com/javalin/javalin-openapi
- OpenAPI Specification: https://spec.openapis.org/oas/v3.0.3
- OpenAPI Generator: https://openapi-generator.tech/
