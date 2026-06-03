# Javalin Database Integration with Hibernate ORM

## Overview

Integrating Hibernate ORM with Javalin provides object-relational mapping and database transaction management. The combination offers a powerful, efficient tech stack for building modern web applications.

**Stack**: Java 21 + Javalin 6.3.0+ + Hibernate 7.0.0+ offers excellent performance and modern Java features.

## Project Setup

### Maven Dependencies

```xml
<dependencies>
    <!-- Javalin Web Framework -->
    <dependency>
        <groupId>io.javalin</groupId>
        <artifactId>javalin</artifactId>
        <version>7.x.x</version>
    </dependency>

    <!-- Hibernate ORM -->
    <dependency>
        <groupId>org.hibernate.orm</groupId>
        <artifactId>hibernate-core</artifactId>
        <version>7.0.0.Final</version>
    </dependency>

    <!-- Database Driver (Example: PostgreSQL) -->
    <dependency>
        <groupId>org.postgresql</groupId>
        <artifactId>postgresql</artifactId>
        <version>42.7.3</version>
    </dependency>

    <!-- JPA API -->
    <dependency>
        <groupId>jakarta.persistence</groupId>
        <artifactId>jakarta.persistence-api</artifactId>
        <version>3.1.0</version>
    </dependency>

    <!-- Testing -->
    <dependency>
        <groupId>org.junit.jupiter</groupId>
        <artifactId>junit-jupiter</artifactId>
        <version>5.9.x</version>
        <scope>test</scope>
    </dependency>
</dependencies>
```

### Gradle Setup

```gradle
dependencies {
    implementation 'io.javalin:javalin:7.x.x'
    implementation 'org.hibernate.orm:hibernate-core:7.0.0.Final'
    implementation 'org.postgresql:postgresql:42.7.3'
    implementation 'jakarta.persistence:jakarta.persistence-api:3.1.0'
    testImplementation 'org.junit.jupiter:junit-jupiter:5.9.x'
}
```

## Core Architecture

### 1. Entity Class with JPA Annotations

Define database entities using JPA annotations:

```java
import jakarta.persistence.*;

@Entity
@Table(name = "courses")
public class Course {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 255)
    private String title;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(name = "instructor_name", nullable = false)
    private String instructor;

    @Column(name = "duration_hours")
    private Integer durationHours;

    @Column(name = "created_at", columnDefinition = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    private LocalDateTime createdAt;

    // Constructors
    public Course() {
    }

    public Course(String title, String description, String instructor) {
        this.title = title;
        this.description = description;
        this.instructor = instructor;
        this.createdAt = LocalDateTime.now();
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getInstructor() { return instructor; }
    public void setInstructor(String instructor) { this.instructor = instructor; }

    public Integer getDurationHours() { return durationHours; }
    public void setDurationHours(Integer durationHours) { this.durationHours = durationHours; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
```

### 2. Hibernate Configuration (persistence.xml)

Create `META-INF/persistence.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<persistence xmlns="https://jakarta.ee/xml/ns/persistence"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             xsi:schemaLocation="https://jakarta.ee/xml/ns/persistence
                                 https://jakarta.ee/xml/ns/persistence/persistence_3_0.xsd"
             version="3.0">

    <persistence-unit name="primary">
        <provider>org.hibernate.jpa.HibernateJpaProvider</provider>

        <!-- Entity classes -->
        <class>com.example.Course</class>

        <properties>
            <!-- Database connection -->
            <property name="jakarta.persistence.jdbc.driver" value="org.postgresql.Driver"/>
            <property name="jakarta.persistence.jdbc.url" value="jdbc:postgresql://localhost:5432/myapp"/>
            <property name="jakarta.persistence.jdbc.user" value="postgres"/>
            <property name="jakarta.persistence.jdbc.password" value="password"/>

            <!-- Hibernate configuration -->
            <property name="hibernate.dialect" value="org.hibernate.dialect.PostgreSQLDialect"/>
            <property name="hibernate.hbm2ddl.auto" value="update"/>
            <property name="hibernate.show_sql" value="false"/>
            <property name="hibernate.format_sql" value="true"/>
            <property name="hibernate.use_sql_comments" value="true"/>

            <!-- Connection pooling (HikariCP recommended for production) -->
            <property name="hibernate.hikari.maximum_pool_size" value="20"/>
            <property name="hibernate.hikari.minimum_idle" value="5"/>
            <property name="hibernate.hikari.connection_timeout" value="30000"/>
        </properties>
    </persistence-unit>

</persistence>
```

**Key Properties**:
- `hbm2ddl.auto`:
  - `update` - Update schema on startup
  - `create` - Drop and recreate
  - `validate` - Validate schema (production)
- `show_sql` - Log SQL statements
- `format_sql` - Pretty-print SQL
- `dialect` - Database-specific dialect (PostgreSQL, MySQL, H2, etc.)

### 3. Lightweight Hibernate Wrapper

Create an `AppHibernate` wrapper class to manage transactions:

```java
import org.hibernate.SessionFactory;
import org.hibernate.cfg.Configuration;

public class AppHibernate {
    private static final SessionFactory sessionFactory;

    static {
        try {
            // Build SessionFactory from persistence.xml
            sessionFactory = new Configuration()
                .configure()
                .buildSessionFactory();
        } catch (Exception e) {
            throw new RuntimeException("Failed to initialize Hibernate", e);
        }
    }

    /**
     * Execute a transaction with void result
     */
    public static void inTransaction(Consumer<StatelessSession> action) {
        try (StatelessSession session = sessionFactory.openStatelessSession()) {
            var transaction = session.beginTransaction();
            try {
                action.accept(session);
                transaction.commit();
            } catch (Exception e) {
                transaction.rollback();
                throw e;
            }
        }
    }

    /**
     * Execute a transaction with return value
     */
    public static <T> T fromTransaction(Function<StatelessSession, T> action) {
        try (StatelessSession session = sessionFactory.openStatelessSession()) {
            var transaction = session.beginTransaction();
            try {
                T result = action.apply(session);
                transaction.commit();
                return result;
            } catch (Exception e) {
                transaction.rollback();
                throw e;
            }
        }
    }

    public static void shutdown() {
        sessionFactory.close();
    }
}
```

**Why StatelessSession?**
- Command-oriented, bare-metal approach
- No first-level cache
- No persistent objects
- Simpler for REST APIs
- Good performance for discrete operations

### 4. Request Handlers

Create handlers that use the Hibernate wrapper:

```java
public class CourseHandler {

    public static void listCourses(Context ctx) {
        List<Course> courses = AppHibernate.fromTransaction(session -> {
            return session.createSelectionQuery(
                "FROM Course ORDER BY createdAt DESC",
                Course.class
            ).getResultList();
        });

        ctx.json(courses);
    }

    public static void getCourse(Context ctx) {
        Long id = ctx.pathParamAsClass("id", Long.class).get();

        Course course = AppHibernate.fromTransaction(session -> {
            return session.get(Course.class, id);
        });

        if (course != null) {
            ctx.json(course);
        } else {
            ctx.status(404).json(Map.of("error", "Course not found"));
        }
    }

    public static void createCourse(Context ctx) {
        Course newCourse = ctx.bodyAsClass(Course.class);

        Course saved = AppHibernate.fromTransaction(session -> {
            session.insert(newCourse);
            return newCourse;
        });

        ctx.status(201).json(saved);
    }

    public static void updateCourse(Context ctx) {
        Long id = ctx.pathParamAsClass("id", Long.class).get();
        Course updates = ctx.bodyAsClass(Course.class);

        AppHibernate.inTransaction(session -> {
            Course existing = session.get(Course.class, id);
            if (existing != null) {
                existing.setTitle(updates.getTitle());
                existing.setDescription(updates.getDescription());
                existing.setInstructor(updates.getInstructor());
                existing.setDurationHours(updates.getDurationHours());
                session.update(existing);
            }
        });

        ctx.json(Map.of("id", id));
    }

    public static void deleteCourse(Context ctx) {
        Long id = ctx.pathParamAsClass("id", Long.class).get();

        AppHibernate.inTransaction(session -> {
            Course course = session.get(Course.class, id);
            if (course != null) {
                session.delete(course);
            }
        });

        ctx.status(204);
    }
}
```

### 5. Javalin Application Setup

```java
public class App {
    public static void main(String[] args) {
        var app = Javalin.create(config -> {
            // Middleware setup
            config.routes(() -> {
                get("/courses", CourseHandler::listCourses);
                get("/courses/{id}", CourseHandler::getCourse);
                post("/courses", CourseHandler::createCourse);
                put("/courses/{id}", CourseHandler::updateCourse);
                delete("/courses/{id}", CourseHandler::deleteCourse);
            });
        }).start(8080);

        // Graceful shutdown
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            AppHibernate.shutdown();
            app.stop();
        }));
    }
}
```

## Advanced Patterns

### Query API (HQL)

```java
public static List<Course> searchByInstructor(String instructor) {
    return AppHibernate.fromTransaction(session -> {
        return session.createSelectionQuery(
            "FROM Course WHERE instructor = :instructor ORDER BY title",
            Course.class
        )
        .setParameter("instructor", instructor)
        .getResultList();
    });
}

public static List<Course> findLongCourses() {
    return AppHibernate.fromTransaction(session -> {
        return session.createSelectionQuery(
            "FROM Course WHERE durationHours > 40 ORDER BY durationHours DESC",
            Course.class
        )
        .getResultList();
    });
}
```

### Pagination

```java
public static List<Course> paginated(int page, int pageSize) {
    return AppHibernate.fromTransaction(session -> {
        return session.createSelectionQuery(
            "FROM Course ORDER BY createdAt DESC",
            Course.class
        )
        .setFirstResult(page * pageSize)
        .setMaxResults(pageSize)
        .getResultList();
    });
}
```

### Native SQL Queries

```java
public static List<Map<String, Object>> customQuery(String sql) {
    return AppHibernate.fromTransaction(session -> {
        return session.createNativeQuery(sql)
            .getResultList();
    });
}
```

## Connection Pooling

### HikariCP Configuration (Recommended for Production)

Add dependency:
```xml
<dependency>
    <groupId>com.zaxxer</groupId>
    <artifactId>HikariCP</artifactId>
    <version>5.1.0</version>
</dependency>
```

In persistence.xml:
```xml
<property name="hibernate.connection.provider_class"
          value="com.zaxxer.hikari.HikariConfig"/>
<property name="hibernate.hikari.maximum_pool_size" value="20"/>
<property name="hibernate.hikari.minimum_idle" value="5"/>
<property name="hibernate.hikari.connection_timeout" value="30000"/>
<property name="hibernate.hikari.idle_timeout" value="600000"/>
```

### Agroal (Alternative)

```xml
<dependency>
    <groupId>io.agroal</groupId>
    <artifactId>agroal-pool</artifactId>
    <version>2.3</version>
</dependency>
```

## Testing with Database

### Test Database Setup

Use H2 in-memory database for testing:

```xml
<persistence-unit name="test">
    <provider>org.hibernate.jpa.HibernateJpaProvider</provider>

    <class>com.example.Course</class>

    <properties>
        <property name="jakarta.persistence.jdbc.driver" value="org.h2.Driver"/>
        <property name="jakarta.persistence.jdbc.url" value="jdbc:h2:mem:test"/>
        <property name="jakarta.persistence.jdbc.user" value="sa"/>
        <property name="jakarta.persistence.jdbc.password" value=""/>

        <property name="hibernate.dialect" value="org.hibernate.dialect.H2Dialect"/>
        <property name="hibernate.hbm2ddl.auto" value="create"/>
    </properties>
</persistence-unit>
```

### Integration Test Example

```java
class CourseTests {
    private Javalin app;

    @BeforeEach
    void setUp() {
        // Use test persistence unit
        app = Javalin.create().start();
        setupTestRoutes(app);
    }

    @Test
    void testCreateAndRetrieveCourse() {
        Course course = new Course(
            "Java Basics",
            "Learn Java fundamentals",
            "John Doe"
        );

        AppHibernate.inTransaction(session -> {
            session.insert(course);
        });

        Course retrieved = AppHibernate.fromTransaction(session -> {
            return session.get(Course.class, course.getId());
        });

        assertThat(retrieved).isNotNull();
        assertThat(retrieved.getTitle()).isEqualTo("Java Basics");
    }

    @Test
    void testListCourses() {
        // Create test data
        AppHibernate.inTransaction(session -> {
            session.insert(new Course("Course 1", "Desc 1", "Instructor 1"));
            session.insert(new Course("Course 2", "Desc 2", "Instructor 2"));
        });

        // Retrieve
        List<Course> courses = AppHibernate.fromTransaction(session -> {
            return session.createSelectionQuery(
                "FROM Course",
                Course.class
            ).getResultList();
        });

        assertThat(courses).hasSize(2);
    }
}
```

## Best Practices

1. **Transaction Management**:
   - Keep transactions short
   - Commit as soon as possible
   - Handle rollbacks appropriately

2. **Entity Design**:
   - Use proper ID generation
   - Add timestamps for auditing
   - Define constraints in annotations

3. **Performance**:
   - Use StatelessSession for REST endpoints
   - Avoid lazy loading in detached sessions
   - Use pagination for large result sets
   - Index frequently searched fields

4. **Error Handling**:
   ```java
   try {
       AppHibernate.inTransaction(session -> {
           // database operations
       });
   } catch (PersistenceException e) {
       ctx.status(400).json(Map.of("error", "Database error"));
   }
   ```

5. **Migrations**:
   - Use Flyway or Liquibase for schema management
   - Never rely on hbm2ddl.auto in production
   - Version database schema like code

## Docker Compose Setup

For local development:

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Start with:
```bash
docker-compose up -d
```

## References

- Javalin + Hibernate Tutorial: https://javalin.io/tutorials/javalin-hibernate
- Hibernate Documentation: https://hibernate.org/orm/documentation/
- Jakarta Persistence: https://jakarta.ee/specifications/persistence/
- HikariCP: https://github.com/brettwooldridge/HikariCP
