# Javalin Deployment Guides

## Overview

Javalin applications are compiled to standalone JARs with embedded Jetty servers, requiring no external application server. This section covers deployment to various platforms.

## Building a Javalin Application

### Creating a Runnable JAR

**Maven Assembly Plugin**:
```xml
<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-assembly-plugin</artifactId>
            <version>3.6.0</version>
            <executions>
                <execution>
                    <phase>package</phase>
                    <goals>
                        <goal>single</goal>
                    </goals>
                    <configuration>
                        <archive>
                            <manifest>
                                <mainClass>com.example.App</mainClass>
                            </manifest>
                        </archive>
                        <descriptorRefs>
                            <descriptorRef>jar-with-dependencies</descriptorRef>
                        </descriptorRefs>
                    </configuration>
                </execution>
            </executions>
        </plugin>
    </plugins>
</build>
```

Build with:
```bash
mvn clean package assembly:single
```

**Gradle Shadow Plugin**:
```gradle
plugins {
    id 'com.github.johnrengelman.shadow' version '8.1.1'
}

shadowJar {
    archiveBaseName = 'app'
    archiveVersion = '1.0'
    manifest {
        attributes 'Main-Class': 'com.example.App'
    }
}
```

Build with:
```bash
gradle shadowJar
```

### Running Locally

```bash
java -jar app.jar
# Or with JVM tuning
java -Xmx1024m -Xms512m -jar app.jar
```

## Docker Deployment

### Dockerfile

```dockerfile
# Build stage
FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /build
COPY . .
RUN mvn clean package -DskipTests

# Runtime stage
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=builder /build/target/app.jar ./app.jar

# Expose port
EXPOSE 8080

# Run application
CMD ["java", "-Xmx512m", "-jar", "app.jar"]
```

### Docker Compose

```yaml
version: '3.8'
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      JAVA_OPTS: "-Xmx512m -Xms256m"
    networks:
      - javalin-network
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - javalin-network

networks:
  javalin-network:

volumes:
  postgres_data:
```

Deploy with:
```bash
docker-compose up -d
docker-compose logs -f app
docker-compose down
```

### Multi-Stage Docker Build

Optimized Dockerfile with smaller final image:

```dockerfile
FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /build
COPY pom.xml .
RUN mvn dependency:go-offline
COPY src ./src
RUN mvn clean package -DskipTests

FROM eclipse-temurin:21-jre-alpine
RUN addgroup -S javalin && adduser -S app -G javalin
WORKDIR /app
COPY --from=builder --chown=app:javalin /build/target/app.jar ./
USER app
EXPOSE 8080
CMD ["java", "-Xmx512m", "-jar", "app.jar"]
```

## Heroku Deployment

### Procfile

Create `Procfile` in project root:

```
web: java -Xmx512m -Xms256m -jar target/app.jar
```

### app.json

Create `app.json` for one-click deployment:

```json
{
  "name": "My Javalin App",
  "description": "A simple Javalin REST API",
  "buildpacks": [
    {
      "url": "heroku/maven"
    }
  ],
  "env": {
    "SERVER_PORT": {
      "description": "Port for server",
      "value": "8080"
    }
  }
}
```

### Deploy

```bash
# Using Heroku CLI
heroku login
heroku create my-javalin-app
git push heroku main

# View logs
heroku logs --tail

# Scale
heroku ps:scale web=2
```

## AWS Lambda with GraalVM Native Image

### Native Image Build

Add GraalVM Maven plugin:

```xml
<plugin>
    <groupId>org.graalvm.buildtools</groupId>
    <artifactId>native-maven-plugin</artifactId>
    <version>0.9.28</version>
</plugin>
```

Build native image:
```bash
mvn -Pnative package
```

### Lambda Handler

```java
import com.amazonaws.serverless.proxy.model.AwsProxyRequest;
import com.amazonaws.serverless.proxy.model.AwsProxyResponse;
import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;

public class LambdaHandler implements RequestHandler<AwsProxyRequest, AwsProxyResponse> {
    private static Javalin app;

    static {
        app = Javalin.create(config -> {
            config.routes(() -> {
                get("/", ctx -> ctx.result("Hello from Lambda"));
            });
        }).start();
    }

    @Override
    public AwsProxyResponse handleRequest(AwsProxyRequest request, Context context) {
        // Handle request through Javalin
        return handleWithJavalin(request);
    }

    private AwsProxyResponse handleWithJavalin(AwsProxyRequest request) {
        // Implementation for routing Lambda request to Javalin
        // Requires serverless-java-container integration
        return null;
    }
}
```

### Deployment to AWS Lambda

```bash
# Build native image
mvn -Pnative package

# Create Lambda function
aws lambda create-function \
    --function-name javalin-app \
    --runtime provided.al2 \
    --role arn:aws:iam::ACCOUNT:role/lambda-role \
    --handler app.handler \
    --zip-file fileb://target/app

# Or update existing
aws lambda update-function-code \
    --function-name javalin-app \
    --zip-file fileb://target/app
```

**Benefits of GraalVM Native Image**:
- ~100x faster startup
- Much smaller memory footprint
- Suitable for Lambda's cost model
- Reduced cold start times

## Kubernetes Deployment

### Deployment YAML

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: javalin-app
  labels:
    app: javalin-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: javalin-app
  template:
    metadata:
      labels:
        app: javalin-app
    spec:
      containers:
      - name: javalin-app
        image: myregistry.azurecr.io/javalin-app:latest
        ports:
        - containerPort: 8080
        env:
        - name: JAVA_OPTS
          value: "-Xmx512m -Xms256m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 20
          periodSeconds: 5
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1024Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: javalin-app-service
spec:
  selector:
    app: javalin-app
  type: LoadBalancer
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
```

Deploy to Kubernetes:
```bash
kubectl apply -f deployment.yaml
kubectl get deployments
kubectl logs -f deployment/javalin-app
```

### Health Checks

Add health check endpoints:

```java
get("/health", ctx -> ctx.json(Map.of("status", "UP")));
get("/ready", ctx -> {
    if (dbConnected()) {
        ctx.json(Map.of("status", "READY"));
    } else {
        ctx.status(503).json(Map.of("status", "NOT_READY"));
    }
});
```

## GraalVM Native Image Compilation

### Setup

Requires GraalVM 21+ with Native Image component:

```bash
# Using SDKMAN
sdk install java 21.0.0-graalvm
sdk use java 21.0.0-graalvm
gu install native-image
```

### Configuration

Create `src/main/resources/META-INF/native-image/reflect-config.json`:

```json
[
  {
    "name": "com.example.App",
    "methods": [{ "name": "<init>" }]
  },
  {
    "name": "com.example.User",
    "allDeclaredConstructors": true,
    "allPublicMethods": true,
    "allPublicFields": true
  }
]
```

### Build Native Image

```bash
# Maven
mvn -Pnative clean package

# Gradle
gradle nativeCompile

# Result: executable binary (22MB typical size)
./target/app
```

**Performance**:
- Startup: ~50ms (vs 2-5s for JVM)
- Memory: ~50MB (vs 300-500MB for JVM)
- Perfect for serverless/containers

## Environment Configuration

### Environment Variables

```java
public class Config {
    public static final String DB_URL = System.getenv("DB_URL");
    public static final String DB_USER = System.getenv("DB_USER");
    public static final String DB_PASSWORD = System.getenv("DB_PASSWORD");
    public static final String PORT = System.getenv("PORT");
    public static final String ENVIRONMENT = System.getenv("ENVIRONMENT");
}
```

### .env File (Development)

Use a library like dotenv-java:

```gradle
implementation 'io.github.cdimascio:java-dotenv:6.4.1'
```

```java
import io.github.cdimascio.dotenv.Dotenv;

var dotenv = Dotenv.load();
String dbUrl = dotenv.get("DB_URL");
```

### Application Properties

```properties
# application.properties
server.port=8080
database.url=jdbc:postgresql://localhost:5432/myapp
database.user=postgres
database.password=password
environment=development
```

```java
import java.util.Properties;
import java.io.InputStream;

Properties props = new Properties();
try (InputStream input = App.class.getClassLoader().getResourceAsStream("application.properties")) {
    props.load(input);
}
String dbUrl = props.getProperty("database.url");
```

## Performance Tuning for Production

### JVM Arguments

```bash
java \
    -Xmx2g \                          # Max heap
    -Xms1g \                          # Initial heap
    -XX:+UseG1GC \                    # Garbage collector
    -XX:MaxGCPauseMillis=200 \        # GC pause target
    -XX:+ParallelRefProcEnabled \     # Parallel reference processing
    -XX:+UnlockExperimentalVMOptions \ # For experimental flags
    -XX:G1NewCollectionHeapPercent=30 \ # G1 tuning
    -Djava.net.preferIPv4Stack=true \
    -jar app.jar
```

### Monitoring

Add metrics collection:

```xml
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-core</artifactId>
    <version>1.12.x</version>
</dependency>

<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
    <version>1.12.x</version>
</dependency>
```

```java
config.registerPlugin(new MicrometerPlugin(micrometer -> {
    micrometer.registry = new PrometheusMeterRegistry(
        PrometheusConfig.DEFAULT
    );
}));

get("/metrics", ctx -> {
    ctx.result(micrometer.registry.scrape());
});
```

### Logging in Production

Use structured logging:

```xml
<dependency>
    <groupId>ch.qos.logback</groupId>
    <artifactId>logback-classic</artifactId>
    <version>1.4.x</version>
</dependency>

<dependency>
    <groupId>net.logstash.logback</groupId>
    <artifactId>logstash-logback-encoder</artifactId>
    <version>7.4</version>
</dependency>
```

## Troubleshooting Deployment

### Issue: Port Already in Use

```bash
# Check what's using the port
lsof -i :8080

# Use different port
java -Dserver.port=8081 -jar app.jar
```

### Issue: Database Connection Timeout

```bash
# Test database connection
psql -h localhost -U postgres -d myapp

# Check network connectivity
nc -zv localhost 5432
```

### Issue: Memory Errors

```bash
# Monitor JVM memory
jps -l
jmap -heap <pid>

# Adjust heap size
java -Xmx2g -jar app.jar
```

### Issue: Slow Startup

Use startup time profiler:
```bash
java -XX:+TraceClassLoading -jar app.jar 2>&1 | head -100
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy Javalin App

on:
  push:
    branches: [ main ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up JDK 21
        uses: actions/setup-java@v3
        with:
          java-version: '21'
          distribution: 'temurin'

      - name: Build JAR
        run: mvn clean package -DskipTests

      - name: Build Docker image
        run: docker build -t myapp:latest .

      - name: Push to Docker Registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker tag myapp:latest myrepo/myapp:latest
          docker push myrepo/myapp:latest

      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/javalin-app javalin-app=myrepo/myapp:latest
```

## References

- Docker Best Practices: https://docs.docker.com/develop/dev-best-practices/
- Heroku Deployment: https://devcenter.heroku.com/
- AWS Lambda: https://docs.aws.amazon.com/lambda/
- Kubernetes: https://kubernetes.io/docs/
- GraalVM Native Image: https://www.graalvm.org/latest/reference-manual/native-image/
