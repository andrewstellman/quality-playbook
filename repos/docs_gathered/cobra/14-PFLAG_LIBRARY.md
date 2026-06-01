# pflag Library Documentation

**Source**: https://pkg.go.dev/github.com/spf13/pflag
**Repository**: https://github.com/spf13/pflag

**Accessed**: 2026-04-04

---

## Overview

**pflag** is a drop-in replacement for Go's standard `flag` package that implements POSIX/GNU-style command-line flags.

### Key Information
- **Status**: Stable (v1 major version)
- **Current Version**: v1.0.10
- **License**: BSD-3-Clause
- **Compatibility**: Drop-in replacement for standard flag package

---

## Drop-in Replacement Semantics

### Import Pattern
```go
import flag "github.com/spf13/pflag"

// Now use as if it were standard flag package
flag.String("name", "default", "help text")
flag.Parse()
```

### Backward Compatibility
- Same interface as standard flag package
- All existing code continues to work
- Additional features available for GNU flags

### Exception
Direct instantiation of Flag struct requires setting the new `Shorthand` field (otherwise ignored).

---

## POSIX/GNU Compliance

pflag is compatible with GNU extensions to POSIX recommendations:
- Single-dash short flags: `-v`
- Double-dash long flags: `--verbose`
- Combined boolean shorthands: `-vvv`
- Flexible syntax: `-f value`, `-f=value`, `-fvalue`

---

## Command-Line Syntax

### Boolean Flags
```
--flag              # true
--flag=true         # explicit true
--flag=false        # explicit false
-f                  # true (shorthand)
```

### Flags with Values
```
--flag value        # space-separated
--flag=value        # equals-separated
-f value            # shorthand space-separated
-f=value            # shorthand with equals
-fvalue             # shorthand adjacent value
```

### Combined Shorthands
```
-vv                 # Multiple v's
-abc                # Multiple boolean flags
-abcn1234           # Booleans followed by numeric
```

---

## Flag Definition Methods

### Pointer-Based (Direct)
```go
var count = flag.Int("count", 0, "number of items")
// Access with: *count
```

### Variable-Based (Recommended)
```go
var verbose bool
flag.BoolVar(&verbose, "verbose", false, "verbose output")
// Access with: verbose
```

### Shorthand Support (P suffix)
```go
var debug bool
flag.BoolVarP(&debug, "debug", "d", false, "debug mode")
// Supports: -d or --debug
```

---

## Shorthand Flags

### Shorthand Functions
All flag types have `P` variant for shorthand:
- `BoolVarP`, `IntVarP`, `StringVarP`, etc.
- Single letter shorthand
- Both short and long forms available

### Usage
```go
flag.IntVarP(&port, "port", "p", 8080, "port number")

// Both work:
// app -p 9000
// app --port 9000
```

### Shorthand Rules
- Single letter only
- Can be grouped with other shorthands (booleans only)
- All but last in group must be boolean

---

## Advanced Features

### NoOptDefVal (Optional Option Arguments)
Allows flag to work with or without argument:

```go
ip := flag.IntP("flagname", "f", 1234, "help message")
flag.Lookup("flagname").NoOptDefVal = "4321"

// Results:
// --flagname=1357  → ip=1357 (explicit value)
// --flagname       → ip=4321 (uses NoOptDefVal)
// (nothing)        → ip=1234 (default)
```

### Flag Name Normalization
Customize how flag names are compared:

```go
func wordSepNormalizeFunc(f *pflag.FlagSet, name string) pflag.NormalizedName {
    from := []string{"-", "_"}
    to := "."
    for _, sep := range from {
        name = strings.Replace(name, sep, to, -1)
    }
    return pflag.NormalizedName(name)
}

myFlagSet.SetNormalizeFunc(wordSepNormalizeFunc)
// Now: --my-flag == --my_flag == --my.flag
```

### Deprecating Flags
```go
flags.MarkDeprecated("badflag", "please use --good-flag instead")
// Flag still works but shows deprecation message
```

### Deprecating Shorthands Only
```go
flags.MarkShorthandDeprecated("noshorthandflag", "please use --noshorthandflag only")
// --noshorthandflag works, but -n doesn't
```

### Hidden Flags
```go
flags.MarkHidden("secretFlag")
// Flag works normally but doesn't appear in help
```

---

## Supported Flag Types

### Basic Types
- Bool, Int, Int8, Int16, Int32, Int64
- Uint, Uint8, Uint16, Uint32, Uint64
- Float32, Float64
- String
- Duration

### Collection Types
- Slice: IntSlice, Int64Slice, StringSlice, UintSlice, Uint64Slice
- Array: StringArray
- Map: StringToInt, StringToString, StringToInt64

### Network Types
- IP, IPMask, IPNet (with slice variants)

### Binary Types
- BytesHex, BytesBase64

### Custom Types
Implement the `Value` interface:
```go
type Value interface {
    String() string
    Set(string) error
}
```

---

## Getting Flag Values

### After Parsing
```go
flag.Parse()

value, err := flagset.GetInt("flagname")
str, err := flagset.GetString("strflag")
bools, err := flagset.GetBoolSlice("boolslice")
```

### Checking if Flag Was Set
```go
if flagset.Changed("flagname") {
    // Flag was explicitly set on command line
}
```

### Direct Variable Access
```go
var port int
flag.IntVar(&port, "port", 8080, "port")
flag.Parse()
fmt.Println(port)  // Access directly
```

---

## Integration with Go's Flag Package

### Adding Go Flags to pflag
```go
import (
    goflag "flag"
    flag "github.com/spf13/pflag"
)

func main() {
    flag.CommandLine.AddGoFlagSet(goflag.CommandLine)
    flag.Parse()
}
```

### In Tests
```go
import (
    goflag "flag"
    flag "github.com/spf13/pflag"
)

func TestMain(m *testing.M) {
    flag.CommandLine.AddGoFlagSet(goflag.CommandLine)
    flag.ParseSkippedFlags(os.Args[1:], goflag.CommandLine)
    flag.Parse()
    os.Exit(m.Run())
}
```

---

## FlagSet for Subcommands

Create independent flag namespaces:

```go
fs := flag.NewFlagSet("subcommand", flag.ContinueOnError)
addr := fs.String("addr", ":8080", "address")
fs.Parse(args)
```

---

## Interspersed Flags

### Default Behavior
Flags can appear anywhere (interspersed with arguments):
```bash
app --flag value arg1 arg2
app arg1 --flag value arg2
```

### Disabling Interspersed
```go
flags.SetInterspersed(false)
// After first non-flag argument, rest are arguments
```

---

## Error Handling

### ErrorHandling Modes

```go
goflag.ContinueOnError      // Return error (default)
goflag.ExitOnError          // Call os.Exit on error
goflag.PanicOnError         // Call panic on error
```

---

## References

- **pflag on GitHub**: https://github.com/spf13/pflag
- **Go Packages**: https://pkg.go.dev/github.com/spf13/pflag
