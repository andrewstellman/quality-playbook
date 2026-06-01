# Argument Validation System

**Sources**:
- https://cobra.dev/docs/how-to-guides/working-with-commands/
- GitHub Issues: #745, #838, #1298
- https://github.com/spf13/cobra/blob/main/args.go

**Accessed**: 2026-04-04

---

## Positional Arguments Validation

### Built-in Validators

| Validator | Behavior | Error Condition |
|-----------|----------|-----------------|
| `NoArgs` | Reject any positional arguments | args.length > 0 |
| `ExactArgs(n)` | Require exactly n arguments | args.length != n |
| `MinimumNArgs(n)` | Require at least n arguments | args.length < n |
| `MaximumNArgs(n)` | Limit to n arguments maximum | args.length > n |
| `RangeArgs(min, max)` | Enforce argument range | args.length < min or > max |
| `ArbitraryArgs` | Accept any count | Never fails |

### Usage Example
```go
cmd.Args = cobra.ExactArgs(1)
cmd.Args = cobra.MinimumNArgs(2)
cmd.Args = cobra.RangeArgs(1, 3)
```

---

## Content-Based Validation

### OnlyValidArgs Validator
Reports an error if there are any positional args not specified in the `ValidArgs` field:

```go
cmd.ValidArgs = []string{"create", "delete", "update"}
cmd.Args = cobra.OnlyValidArgs
```

**Behavior**:
- Validates that each argument is in ValidArgs list
- Case-sensitive by default
- Used for restricted argument values

---

## ValidArgs vs ValidArgsFunction

### ValidArgs (Static List)
```go
cmd.ValidArgs = []string{"option1", "option2", "option3"}
```

**Used for**:
- Fixed set of known values
- Completion suggestions
- Argument validation with OnlyValidArgs

### ValidArgsFunction (Dynamic)
```go
cmd.ValidArgsFunction = func(cmd *Command, args []string, toComplete string) ([]string, ShellCompDirective) {
    return dynamicallyGeneratedList(), ShellCompDirectiveDefault
}
```

**Used for**:
- Dynamic or computed argument values
- File listing, API queries, etc.
- Context-aware completions

### Critical Constraint
**Either ValidArgs OR ValidArgsFunction, but NOT BOTH** on the same command.

---

## Combining Validators

### MatchAll Function
Combine multiple validators:

```go
cmd.Args = cobra.MatchAll(
    cobra.ExactArgs(2),
    cobra.OnlyValidArgs,
)
```

**Use case**: Require exactly 2 arguments AND they must be in ValidArgs list

### Edge Cases Resolved by MatchAll

**Problem 1: ExactArgs + ValidArgs**
- `ExactArgs(1)` requires exactly one arg
- But it doesn't validate the arg is in ValidArgs
- Solution: Use `MatchAll(ExactArgs(1), OnlyValidArgs)`

**Problem 2: MinimumNArgs + OnlyValidArgs**
- Can't combine directly
- Solution: Use `MatchAll(MinimumNArgs(1), OnlyValidArgs)`

### ExactValidArgs Deprecation
`ExactValidArgs` is deprecated. Instead use:
```go
cobra.MatchAll(cobra.ExactArgs(n), cobra.OnlyValidArgs)
```

---

## Custom Validators

### Creating Custom Validators
Implement function matching `PositionalArgs` signature:

```go
type PositionalArgs func(*Command, []string) error

// Custom validator
func MyValidator(cmd *Command, args []string) error {
    if len(args) != 1 {
        return fmt.Errorf("expected exactly 1 argument")
    }
    // Additional custom validation
    if !isValidFormat(args[0]) {
        return fmt.Errorf("invalid format: %s", args[0])
    }
    return nil
}

cmd.Args = MyValidator
```

### Custom Validation with Built-in Validators
```go
cmd.Args = func(cmd *Command, args []string) error {
    // Run built-in validator
    if err := cobra.ExactArgs(1)(cmd, args); err != nil {
        return err
    }
    // Add custom validation
    if !isValidOption(args[0]) {
        return fmt.Errorf("invalid option: %s", args[0])
    }
    return nil
}
```

---

## Argument Validation and Completion

### OnlyValidArgs with ValidArgsFunction Bug
There's a known issue (GitHub #1298): `OnlyValidArgs` does not properly validate against values from `ValidArgsFunction`.

**Workaround**: Implement custom validator that checks against function results:
```go
cmd.Args = func(cmd *Command, args []string) error {
    // Get valid args from function
    validArgs, _ := cmd.ValidArgsFunction(cmd, []string{}, "")
    // Check args are in valid list
    for _, arg := range args {
        found := false
        for _, valid := range validArgs {
            if arg == valid {
                found = true
                break
            }
        }
        if !found {
            return fmt.Errorf("invalid argument: %s", arg)
        }
    }
    return nil
}
```

---

## Validation Timing

### When Validation Occurs
Argument validation happens:
1. After command is found
2. Before Run/RunE is called
3. After all hooks are prepared

### Error Handling
If Args validator returns an error:
1. Error is printed
2. Usage is printed
3. Command exits with non-zero status

---

## Common Patterns

### Optional Arguments
```go
cmd.Args = cobra.RangeArgs(0, 1)  // 0 or 1 argument
```

### Variable Arguments
```go
cmd.Args = cobra.MinimumNArgs(1)  // At least 1
```

### Fixed Choices
```go
cmd.ValidArgs = []string{"dev", "staging", "prod"}
cmd.Args = cobra.OnlyValidArgs
```

### No Arguments
```go
cmd.Args = cobra.NoArgs
```

---

## Argument Access in Run

### Getting Arguments
```go
cmd.RunE = func(cmd *cobra.Command, args []string) error {
    if len(args) > 0 {
        filename := args[0]
        // Process filename
    }
    return nil
}
```

### Using cmd.Args Function
After validation passes, args are available as-is in the Run function.

---

## References

- **Argument Validation**: https://cobra.dev/docs/how-to-guides/working-with-commands/
- **GitHub Issue #745**: "ExactArgs + ValidArgs + OnlyValidArgs combinations"
- **GitHub Issue #1298**: "OnlyValidArgs doesn't work with ValidArgsFunction"
- **Source**: https://github.com/spf13/cobra/blob/main/args.go
