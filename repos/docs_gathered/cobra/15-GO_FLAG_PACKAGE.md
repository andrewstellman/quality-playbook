# Go Standard Library Flag Package

**Source**: https://pkg.go.dev/flag
**Documentation**: Go 1.26+ standard library

**Accessed**: 2026-04-04

---

## Overview

The `flag` package implements command-line flag parsing in Go. Cobra extends this with POSIX/GNU compliance through pflag.

---

## Basic Usage

### Three Approaches to Define Flags

#### 1. Pointer-Based (Returns pointer)
```go
var nFlag = flag.Int("n", 1234, "help message for flag n")
// After Parse(): fmt.Println(*nFlag)
```

#### 2. Variable-Based (Binds to variable)
```go
var flagvar int
func init() {
    flag.IntVar(&flagvar, "flagname", 1234, "help message")
}
// After Parse(): fmt.Println(flagvar)
```

#### 3. Custom Value Types
```go
flag.Var(&customValue, "name", "help message")
// Implement Value interface
```

---

## Parsing and Access

### Parse Function
```go
flag.Parse()  // Must call after defining all flags
```

### Accessing Arguments
```go
flag.Args()     // []string of non-flag arguments
flag.Arg(i)     // i-th argument
flag.NArg()     // Count of arguments
```

---

## Command-Line Flag Syntax

### Permitted Forms
All these are valid:
```
-flag
-flag=x
-flag x         // Space-separated (non-boolean only)
--flag          // Double dash also works
--flag=x        // Long form with equals
```

### Boolean Flag Special Rule
Boolean flags cannot use space-separated form:
```
-flag false     # INVALID
-flag=false     # VALID
```

---

## Parsing Rules

### Parsing Stops When
- First non-flag argument encountered (by default)
- `--` marker is encountered
- Flag parsing error occurs (error handling mode dependent)

### Interspersed Flags
Standard flag package does NOT allow interspersed flags (unlike pflag).

```
app -flag1 value1 arg1 arg2
# After arg1, remaining aren't parsed as flags
```

---

## Supported Flag Types

| Type | Function | Var Function |
|------|----------|--------------|
| bool | `Bool()` | `BoolVar()` |
| int | `Int()` | `IntVar()` |
| int64 | `Int64()` | `Int64Var()` |
| uint | `Uint()` | `UintVar()` |
| uint64 | `Uint64()` | `Uint64Var()` |
| float64 | `Float64()` | `Float64Var()` |
| string | `String()` | `StringVar()` |
| time.Duration | `Duration()` | `DurationVar()` |

### Type Parsing Rules

#### Integer Formats
Accepted by integer flags:
- Decimal: `1234`
- Octal: `0664`
- Hexadecimal: `0x1234`
- Negative: `-42`
- Default interpretation: decimal unless prefix indicates otherwise

#### Boolean Formats
Accepted values (case-insensitive for first char):
- `1, 0, t, f, T, F, true, false, TRUE, FALSE, True, False`
- Note: `true` and `false` are common conventions

#### Duration Formats
Valid `time.ParseDuration` values:
```
300ms
1.5h
2h45m
1m30s
```

---

## Advanced Features

### Custom Flag Types (Go 1.16+)

#### Func Method (Go 1.16+)
```go
flag.Func("ip", "IP address to parse", func(s string) error {
    ip := net.ParseIP(s)
    if ip == nil {
        return errors.New("invalid IP")
    }
    return nil
})
```

#### BoolFunc Method (Go 1.16+)
```go
flag.BoolFunc("v", "verbose", func(s string) error {
    verbosity = strings.Count(s, "v")
    return nil
})
```

### Custom Value Interface
```go
type Value interface {
    String() string
    Set(string) error
}

// Optional: for boolean flags
func (v *MyValue) IsBoolFlag() bool { return true }
```

**Example**:
```go
type portFlag int

func (p *portFlag) String() string { return fmt.Sprintf("%d", *p) }
func (p *portFlag) Set(s string) error {
    port, err := strconv.Atoi(s)
    if err != nil || port < 1 || port > 65535 {
        return fmt.Errorf("invalid port: %s", s)
    }
    *p = portFlag(port)
    return nil
}

var port portFlag = 8080
flag.Var(&port, "port", "server port")
```

---

## FlagSet for Independent Flag Spaces

Create separate flag namespaces (useful for subcommands):

```go
fs := flag.NewFlagSet("subcommand", flag.ContinueOnError)
addr := fs.String("addr", ":8080", "address to listen on")
debug := fs.Bool("debug", false, "debug mode")
fs.Parse(args)
```

---

## Error Handling Modes

Three ErrorHandling modes available:

### ContinueOnError
```go
fs := flag.NewFlagSet("cmd", flag.ContinueOnError)
// Returns error instead of exiting
```

### ExitOnError
```go
fs := flag.NewFlagSet("cmd", flag.ExitOnError)
// Calls os.Exit(2) on error, os.Exit(0) for -h/-help
```

### PanicOnError
```go
fs := flag.NewFlagSet("cmd", flag.PanicOnError)
// Calls panic(err)
```

---

## Key Functions

### Flag Inspection
```go
flag.Lookup(name)       // Get flag by name
flag.VisitAll(fn)       // Visit all defined flags
flag.Visit(fn)          // Visit only set flags
flag.NFlag()            // Count of set flags
flag.Parsed()           // Check if Parse() was called
```

### Utility Functions
```go
flag.PrintDefaults()    // Print all flags and defaults
flag.Set(name, value)   // Programmatically set flag
```

---

## Important Variables

```go
flag.ErrHelp                // Error returned when -help invoked
flag.CommandLine            // Default flag set
flag.Usage                  // Function for custom usage message
```

---

## Default Behavior

### Help Flag
- `-h` and `-help` are automatically recognized
- Prints all flags and their defaults
- Exits with status 0

### Default Values
- Printed in parentheses in help text
- Used if flag not provided

---

## Go Flag vs pflag

| Feature | Go flag | pflag |
|---------|---------|-------|
| Short flags (-v) | No | Yes |
| Long flags (--verbose) | Limited | Yes |
| Interspersed flags | No | Yes |
| Flag grouping (-abc) | No | Yes |
| GNU compatibility | No | Yes |
| POSIX compliance | Partial | Full |

---

## References

- **Flag Package**: https://pkg.go.dev/flag
- **Documentation**: https://golang.org/pkg/flag/
- **Go 1.26+**: Current as of 2026-04-04
