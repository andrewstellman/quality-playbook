# Error Handling and Lifecycle

**Sources**:
- https://pkg.go.dev/github.com/spf13/cobra
- GitHub Issues: #464, #914, #1967
- Blog: https://www.jvt.me/posts/2024/11/29/gotcha-cobra-persistentpostrune/

**Accessed**: 2026-04-04

---

## Error Handling Architecture

### The RunE Variants
Cobra provides error-returning variants of hook functions:
- `PersistentPreRunE`
- `PreRunE`
- `RunE`
- `PostRunE`
- `PersistentPostRunE`

These allow errors to bubble up to the top for centralized handling instead of calling `os.Exit()` directly.

### Why RunE Matters
"The RunE variants return errors instead of calling os.Exit directly, which enables testing without process termination and allows parent commands to handle child errors."

**Behavioral spec**: If RunE returns an error, Cobra will:
1. Print the error to stderr
2. Print usage (unless SilenceUsage=true)
3. Print the error message (unless SilenceErrors=true)
4. Exit with non-zero status

---

## Error Propagation Order

### Execution Order
The Run functions are executed in this order:
1. `PersistentPreRun/PersistentPreRunE`
2. `PreRun/PreRunE`
3. `Run/RunE`
4. `PostRun/PostRunE`
5. `PersistentPostRun/PersistentPostRunE`

**Key point**: Error occurs in one of these phases, execution stops and bubbles up.

---

## Error Output Control

### SilenceErrors Flag
When `SilenceErrors = true`, Cobra suppresses automatic error printing.

```go
cmd.SilenceErrors = true
// If RunE returns an error, it's not automatically printed
// Useful for custom error formatting
```

### SilenceUsage Flag
When `SilenceUsage = true`, Cobra doesn't print usage on runtime errors.

```go
cmd.SilenceUsage = true
// Error still prints, but not the usage message
```

**Note**: Usage is always printed for flag/argument parsing errors, regardless of SilenceUsage.

### Default Error Behavior
If `SilenceErrors = false` (default), error is prefixed with "Error:" when printed.

---

## Advanced Error Handling

### FParseErrWhitelist
Allows specific flag parsing errors to be ignored:

```go
cmd.FParseErrWhitelist = cobra.FParseErrWhitelist{
    UnknownFlags: true,
}
// Unknown flags won't cause command to fail
```

### FlagErrorFunc
Sets custom handler for flag parsing errors:

```go
cmd.SetFlagErrorFunc(func(cmd *cobra.Command, err error) error {
    // Custom error formatting
    return fmt.Errorf("custom: %v", err)
})
```

---

## The PersistentPostRunE Gotcha

### Critical Behavior
**GOTCHA**: When `RunE` returns an error, `PersistentPostRunE` does NOT execute.

"When using the RunE function, PersistentPostRunE doesn't execute if RunE returns an error. This means cleanup code in `PersistentPostRunE` won't run when an error occurs."

### Why This Matters
Cleanup code in `PersistentPostRunE` won't run when:
- RunE returns an error
- PreRunE returns an error
- Any intermediate error occurs

### Solution: OnFinalize
Use the `OnFinalize` callback, which runs regardless of command success or failure:

```go
cmd.OnFinalize(func() {
    // This runs even if RunE returns an error
    cleanup()
})
```

---

## Pre-Run Error Handling

### PersistentPreRunE Behavior
Errors in `PersistentPreRunE` prevent subsequent hooks and command execution:

```go
cmd.PersistentPreRunE = func(cmd *cobra.Command, args []string) error {
    if err := validateConfig(); err != nil {
        return err  // Stops execution here
    }
    return nil
}
```

If this returns an error:
- `PreRunE` doesn't run
- `RunE` doesn't run
- `PostRunE` doesn't run
- `PersistentPostRunE` doesn't run

### Help Command Bypass (Issue #1967)
There's a known issue: Invoking `--help` bypasses `PersistentPreRunE` functions.

**Implication**: You can't enforce required configuration through `PersistentPreRunE` before help is displayed.

---

## Error Handling Best Practices

### Use PreRunE for Validation
```go
PreRunE: func(cmd *cobra.Command, args []string) error {
    if stdout && outPath != "" {
        return fmt.Errorf("--stdout and --output are mutually exclusive")
    }
    return nil
}
```

### Centralize Error Handling
```go
rootCmd.Execute()
// Returns error that caller can handle
// Or exits with appropriate status code
```

### Custom Error Messages
```go
cmd.SilenceErrors = true
cmd.RunE = func(cmd *cobra.Command, args []string) error {
    if err := doWork(); err != nil {
        fmt.Fprintf(os.Stderr, "CUSTOM ERROR: %v\n", err)
        return err  // Still return for exit code
    }
    return nil
}
```

---

## Error Reporting in Hooks

### Print to Stderr
```go
cmd.RunE = func(cmd *cobra.Command, args []string) error {
    cmd.PrintErr("Error message to stderr")
    return fmt.Errorf("description")
}
```

### Access cmd Methods
```go
cmd.PrintErr(i...)           // Print to stderr
cmd.Println(i...)            // Print to stdout
cmd.Printf(format, i...)     // Formatted output
```

---

## Error Context

### cmd.Context()
Every command has access to a context:

```go
RunE: func(cmd *cobra.Command, args []string) error {
    ctx := cmd.Context()
    // Can use for cancellation, deadlines, tracing
    return doWorkWithContext(ctx)
}
```

---

## Testing with Errors

### Why RunE Matters for Testing
By using RunE instead of Run + os.Exit:
- Tests can verify returned errors
- No process termination during tests
- Parent commands can handle child errors

```go
// Testing
cmd := NewCommand()
err := cmd.ExecuteContext(context.Background())
if err != nil {
    // Verify error was as expected
}
```

---

## References

- **Error Handling**: https://pkg.go.dev/github.com/spf13/cobra
- **GitHub #464**: "Error from RootCmd.PersistentPreRunE printed twice"
- **GitHub #1967**: "Invoking --help bypasses PersistentPreRunE"
- **Blog**: https://www.jvt.me/posts/2024/11/29/gotcha-cobra-persistentpostrune/
