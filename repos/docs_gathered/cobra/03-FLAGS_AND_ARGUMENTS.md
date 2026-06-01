# Flags and Arguments Documentation

**Sources**:
- https://cobra.dev/docs/how-to-guides/working-with-flags/
- https://pkg.go.dev/github.com/spf13/cobra
- https://pkg.go.dev/github.com/spf13/pflag
- https://pkg.go.dev/flag

**Accessed**: 2026-04-04

---

## Flag Fundamentals

Cobra is built on a structure of commands, arguments & flags, where:
- **Commands** represent actions
- **Arguments** are things (subjects being operated on)
- **Flags** are modifiers for those actions

The pattern follows: `APPNAME COMMAND ARG --FLAG`

---

## Flag Scoping

### Local Flags
Local flags apply to a single command and don't inherit to subcommands.

```go
serveCmd.Flags().Int("port", 8080, "port to listen on")
```

**Behavioral specs**:
- Only available on the specific command where defined
- Not inherited by subcommands
- Retrieved via `cmd.Flags()` and `cmd.LocalFlags()`

### Persistent Flags
Persistent flags live on a parent and are available to all descendants (unless shadowed).

```go
rootCmd.PersistentFlags().Bool("verbose", false, "enable verbose output")
```

**Behavioral specs**:
- Available on defining command and all descendants
- Can be shadowed by local flags with same name
- Retrieved via `cmd.PersistentFlags()` and `cmd.InheritedFlags()`

---

## Flag Declaration

### Pointer-Based Approach
```go
var port = serveCmd.Flags().Int("port", 8080, "port to listen on")
// Access with: *port
```

### Variable-Based Approach (Recommended)
```go
var port int
serveCmd.Flags().IntVar(&port, "port", 8080, "port to listen on")
// Access with: port
```

### Shorthand Flags
Use the `P` variant methods for single-letter shortcuts:

```go
serveCmd.Flags().IntP("port", "p", 8080, "port to listen on")
// Usage: serve -p 9000 or serve --port=9000
```

---

## Common Flag Types

Cobra supports extensive flag types through pflag/flag package:

| Type | Function | Shorthand |
|------|----------|-----------|
| bool | `BoolVar()` | `BoolVarP()` |
| int | `IntVar()` | `IntVarP()` |
| int64 | `Int64Var()` | `Int64VarP()` |
| uint | `UintVar()` | `UintVarP()` |
| uint64 | `Uint64Var()` | `Uint64VarP()` |
| float64 | `Float64Var()` | `Float64VarP()` |
| string | `StringVar()` | `StringVarP()` |
| duration | `DurationVar()` | `DurationVarP()` |
| StringSlice | `StringSliceVar()` | `StringSliceVarP()` |
| StringArray | `StringArrayVar()` | `StringArrayVarP()` |
| IntSlice | `IntSliceVar()` | `IntSliceVarP()` |
| Count | `CountVar()` | `CountVarP()` |

---

## Required Flags

### Marking Flags as Required
```go
loginCmd.MarkFlagRequired("username")
loginCmd.MarkFlagRequired("password")
```

**Cobra automatically displays an error when required flags are omitted.**

### Marking Persistent Flags as Required
```go
rootCmd.MarkPersistentFlagRequired("config")
```

### Important Limitation
**Known issue**: If there is a required persistent flag in root command, then Cobra's built-in commands "completion" and "help" will not work if the flag is not specified. This is because required flag checking happens before builtin command dispatch.

---

## Flag Groups

### MarkFlagsOneRequired
At least one flag from the group must be provided:
```go
cmd.MarkFlagsOneRequired("json", "yaml")
// User must provide --json or --yaml (or both)
```

### MarkFlagsMutuallyExclusive
At most one flag from the group allowed:
```go
cmd.MarkFlagsMutuallyExclusive("json", "yaml", "xml")
// User can provide only one of these, not multiple
```

### MarkFlagsRequiredTogether
All flags must be used together:
```go
cmd.MarkFlagsRequiredTogether("username", "password")
// If --username is provided, --password must be too
```

### Flag Group Semantics
- Flags can appear in multiple groups
- A flag may be part of multiple groups
- A group may contain any number of flags
- Validation happens at command execution time

---

## Special Flag Behaviors

### Count Flags (Verbosity)
Increment on repetition:
```go
var verbose int
rootCmd.PersistentFlags().CountVarP(&verbose, "verbose", "v", "verbosity level")
// Usage: app -v (verbose=1), app -vv (verbose=2), app -vvv (verbose=3)
```

### Array/Slice Flags

**StringArrayVarP** - Multiple invocations:
```go
var tags []string
cmd.Flags().StringArrayVarP(&tags, "tag", "t", []string{}, "tags")
// Usage: cmd --tag value1 --tag value2
// Result: ["value1", "value2"]
```

**StringSliceVarP** - Comma-separated values:
```go
var items []string
cmd.Flags().StringSliceVarP(&items, "items", "i", []string{}, "items")
// Usage: cmd --items value1,value2,value3
// Result: ["value1", "value2", "value3"]
```

### NoOptDefVal (Optional Option Arguments)
Flag can be used without a value, using a default:
```go
flags.Lookup("flagname").NoOptDefVal = "4321"
// --flagname=1357  → 1357
// --flagname       → 4321 (default)
// (nothing)        → 1234 (flag default)
```

---

## Flag Value Binding

### Read on Demand
```go
val, _ := cmd.Flags().GetInt("port")
```

### Bind to Variables
```go
var port int
cmd.Flags().IntVarP(&port, "port", "p", 8080, "port")
// Access directly: port
```

### Viper Integration
Bind Cobra flags to Viper configuration:
```go
viper.BindPFlag("port", rootCmd.PersistentFlags().Lookup("port"))
```

---

## Flag Validation

### Using PreRunE for Validation
```go
PreRunE: func(cmd *cobra.Command, args []string) error {
    if stdout && outPath != "" {
        return fmt.Errorf("--stdout and --output are mutually exclusive")
    }
    return nil
}
```

---

## Flag Deprecation and Hiding

### Hide a Flag
```go
rootCmd.PersistentFlags().MarkHidden("config")
// Flag still works but doesn't appear in help
```

### Deprecate a Flag
```go
rootCmd.PersistentFlags().MarkDeprecated("colour", "use --color instead")
// Flag still works, shows deprecation message
```

---

## Flag Access Methods

```go
cmd.Flags()              // Local + persistent flags for this command
cmd.LocalFlags()         // Local flags only
cmd.PersistentFlags()    // Persistent flags defined on this command
cmd.InheritedFlags()     // Flags from parent commands
cmd.Flag("name")         // Get specific flag by name

cmd.HasFlags()           // Has any flags
cmd.HasLocalFlags()      // Has local flags
cmd.HasAvailableFlags()  // Has non-hidden, non-deprecated flags
```

---

## Flag Parsing Behavior

### Default Parsing
Cobra uses **pflag** library (POSIX/GNU compliant):
- Single dash `-f` for short flags
- Double dash `--flag` for long flags
- Combined short flags: `-vvv` (three v's)
- Space or equals for values: `--flag value` or `--flag=value`

### Interspersed Flag Parsing
By default, pflag allows flags interspersed with arguments. To disable:
```go
flags.SetInterspersed(false)
// After first non-flag argument, remaining are arguments, not flags
```

### Double Dash (`--`) Handling
The `--` marker terminates flag parsing:
```
app command --flag value -- --not-a-flag
// "--not-a-flag" is treated as an argument, not a flag
```

---

## References

- **Working with Flags**: https://cobra.dev/docs/how-to-guides/working-with-flags/
- **pflag Documentation**: https://pkg.go.dev/github.com/spf13/pflag
- **Go Flag Package**: https://pkg.go.dev/flag
