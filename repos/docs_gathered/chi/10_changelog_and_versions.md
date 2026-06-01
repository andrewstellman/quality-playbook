# Chi Router - Changelog and Version History

## Major Version Timeline

### V5 Series (Current - Module Support)

**v5.0.0 (2021-02-27)** - Go Semantic Import Versioning

Major architectural decision to adopt semantic import versioning with the import path changing to `github.com/go-chi/chi/v5`. This decision prioritized clean API aesthetics in the routing interface.

**Key Features in v5:**
- Full `go.mod` support
- Module-based versioning
- API stability and backward compatibility focus
- Requires Go 1.14+

**Recent v5 Releases:**
- **v5.0.12** (2024) - Added support for Go 1.22+ mux routing features
  - Support for `r.Handle("GET /users/{userID}", handler)`
  - Access to URL path parameters via `request.PathValue("xyz")`
  - Support for wildcard paths with `request.PathValue("*")`

### V4 Series (Previous Stable)

**v4.0.0 (2019-01-10)** - Go 1.10+ Requirement

- Required Go 1.10.3 or later
- Router behavior improvements with empty routes
- Wildcard validation enhancements
- Final v4 release: v4.1.2

### V3 Series (Flexible Routing Introduction)

**v3.0.0 (2017-06-21)** - Regex and Complex Patterns

- Introduced flexible routing with pattern syntax like `/articles/{month}-{day}-{year}`
- Added regexp support via `/{paramKey:regExp}`
- Enhanced route matching capabilities

### V2 Series (Context Package Integration)

**v2.0.0-rc1 (2016-07-26)** - Go 1.7+ Context Package Adoption

Major redesign for Go 1.7's standard library context package:
- Replaced chi's custom handler interface with `http.Handler`
- Full integration with Go's context package
- Request-scoped value passing through context

### V1 Series (Original Design)

**v1.0.0 (2016)** - Initial Release

- Lightweight, composable HTTP router
- Patricia Radix Trie-based routing
- Standard library compatibility

## Upgrade Paths

### V4 to V5 Upgrade

```go
// v4 import
import "github.com/go-chi/chi"

// v5 import - just change to
import "github.com/go-chi/chi/v5"

// Code otherwise compatible
r := chi.NewRouter()  // Still works the same
```

### Using Older Versions

```bash
# Install specific version
go get github.com/go-chi/chi/v5@v5.0.10

# Or older version
go get github.com/go-chi/chi@v4.1.2
```

## Known Issues and Resolutions

### Wildcard Routing

**Issue**: Wildcard routes must be last in pattern definition but not always enforced in edge cases

**Workaround**: Always place wildcard routes last
```go
r.Get("/api/*", apiHandler)
r.Get("/", homeHandler)  // Specific routes first
```

### Custom NotFound with FileServer

**Issue**: Custom NotFound handler doesn't trigger when using FileServer

**Resolution**: Order routes to avoid wildcard intercept
```go
// Correct order
r.Get("/api/*", apiHandler)
r.Mount("/static", http.FileServer(http.Dir("static")))
r.NotFound(custom404)
```

### Subrouter Parameter Conflicts

**Issue**: Stacked subrouters with same parameter names can cause issues

**Resolution**: Use unique parameter names or separate contexts
```go
r.Route("/{orgID}", func(r chi.Router) {
    r.Route("/teams/{teamID}", func(r chi.Router) {
        // No conflict: different parameter names
    })
})
```

## Support and Compatibility

### Go Version Support

Chi supports the **four most recent major versions of Go**:

- As of 2024: Go 1.21, 1.22, 1.23, 1.24 (v5)
- As of 2020: Go 1.13, 1.14, 1.15, 1.16 (v4)

### Long-term Stability

Chi emphasizes API stability:
- Breaking changes only in major versions
- Careful deprecation process
- Community feedback incorporated into design

## Migration Guides

### From v3 to v4

```go
// No code changes needed - API compatible
// Just update go.mod version
github.com/go-chi/chi v4.0.0
```

### From v2 to v3

```go
// Pattern syntax improvements
// v2 style
r.Get("/articles/{month:\\d{2}}-{day:\\d{2}}-{year:\\d{4}}", handler)

// v3 style (cleaner)
r.Get("/articles/{month}-{day}-{year}", handler)
// With validation
r.Get("/articles/{month:\\d{2}}-{day:\\d{2}}-{year:\\d{4}}", handler)
```

## Related Resources

For detailed changelog information, see:
- Official Changelog: https://github.com/go-chi/chi/blob/master/CHANGELOG.md
- Release Notes: https://github.com/go-chi/chi/releases
- Issues and Discussions: https://github.com/go-chi/chi/issues

## Version Selection Recommendation

**For new projects**: Use **v5.x** with latest Go version
- Full `go.mod` support
- Latest features (Go 1.22 compatibility)
- Active maintenance

**For existing projects**: Evaluate upgrade need
- v4 still works fine for stable projects
- v5 recommended when upgrading Go versions
- Consider maintenance burden vs benefit
