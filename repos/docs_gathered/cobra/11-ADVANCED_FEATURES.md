# Advanced Features

**Sources**:
- https://cobra.dev/docs/how-to-guides/working-with-commands/
- https://pkg.go.dev/github.com/spf13/cobra
- GitHub issues and discussions

**Accessed**: 2026-04-04

---

## DisableFlagParsing

### Purpose
When `DisableFlagParsing = true`, Cobra passes all arguments directly to the command without parsing them as flags.

### Behavioral Spec
"If this is true all flags will be passed to the command as arguments. This means Cobra does not know about flags for this command and lets the command handle them itself."

### Use Cases
**Plugin systems**: Helm uses this for plugins

```go
cmd.DisableFlagParsing = true
// Plugin receives all args as-is
// Plugin handles its own flags internally
```

**Wrapper commands**: Commands that need to pass through flags unchanged

### Important Constraint
When `DisableFlagParsing = true`:
- Required flags are NOT checked
- Flag parsing errors don't occur
- All args are treated as positional arguments

---

## TraverseChildren

### Purpose
By default, Cobra only parses local flags on the target command. With `TraverseChildren = true`, Cobra parses local flags on each parent before executing the target.

### Behavioral Spec
"Parses flags on all parents before executing child command."

```go
cmd.TraverseChildren = true
```

### Execution Order
With TraverseChildren enabled:
1. Parse flags on root
2. Parse flags on parent
3. Parse flags on target command
4. Execute target command

### Use Case
Commands with deeply nested structures where parent flags need processing before child execution.

---

## Help Command Behavior

### Default Help Command
Cobra automatically provides a help command and -h/--help flag handling.

### Customizing Help Function
```go
cmd.SetHelpFunc(func(cmd *Command, args []string) {
    // Custom help rendering
})
```

### Customizing Help Template
```go
cmd.SetHelpTemplate(`
    Usage: {{.UseLine}}
    Short: {{.Short}}
    {{if .Long}}{{.Long}}{{end}}
`)
```

### Important Limitation
You cannot completely disable the help command:
- InitDefaultHelpCmd automatically creates it if missing
- SetHelpCommand(nil) causes default to be re-added
- Workaround: Use custom command with Hidden: true

---

## Hidden Flags and Commands

### Hiding Flags
```go
rootCmd.PersistentFlags().MarkHidden("debug")
```

**Behavior**:
- Flag still works if used
- Doesn't appear in help text
- Useful for deprecated or internal flags

### Hiding Commands
```go
cmd.Hidden = true
```

**Behavior**:
- Command still executes
- Doesn't appear in subcommand list
- Useful for administrative commands

---

## Deprecated Flags and Commands

### Deprecating Flags
```go
rootCmd.PersistentFlags().MarkDeprecated("colour", "use --color instead")
```

**Behavior**:
- Flag still works
- Shows deprecation message when used
- Users see replacement suggestion

### Deprecating Commands
```go
cmd.Deprecated = "use 'newcommand' instead"
```

**Behavior**:
- Command still executes
- Deprecation warning shown in help
- Clear migration path for users

### Deprecation Best Practices
- Keep deprecated items functional for at least one minor release
- Provide clear migration path
- Document in changelog

---

## Command Aliases

### Defining Aliases
```go
cmd.Aliases = []string{"i", "add", "install"}
```

**Behavior**:
- Command works with any alias name
- All aliases behave identically
- Aliases don't appear in help subcommand list

### Use Cases
- Backward compatibility during refactoring
- Shorter common abbreviations
- Different command naming conventions

---

## Typo Correction (Suggestions)

### Automatic Suggestions
Cobra automatically suggests similar commands when user types something unknown:

```bash
$ app srever
Error: unknown command "srever" for "app"

Did you mean this?
        server
```

### SuggestionsMinimumDistance
Controls when suggestions appear:

```go
cmd.SuggestionsMinimumDistance = 2  // Default
```

**Behavior**:
- Uses Levenshtein distance
- Distance of 2 or less triggers suggestions (by default)
- Ignores case when calculating distance

### Customization
```go
cmd.SuggestionsMinimumDistance = 1  // More aggressive
cmd.SuggestionsMinimumDistance = 3  // Less aggressive
```

---

## Error Handling Features

### FParseErrWhitelist
Selectively ignore flag parsing errors:

```go
cmd.FParseErrWhitelist = cobra.FParseErrWhitelist{
    UnknownFlags: true,  // Ignore unknown flags
}
```

**Behavior**:
- Specified error types don't cause failure
- Command continues execution
- Useful for flexible parsing

### FlagErrorFunc
Custom handler for flag parsing errors:

```go
cmd.SetFlagErrorFunc(func(cmd *Command, err error) error {
    // Custom error handling
    fmt.Fprintf(os.Stderr, "Invalid flag: %v\n", err)
    return err
})
```

---

## Help Generation Features

### HasAvailableFlags()
Check for non-hidden, non-deprecated flags:

```go
if cmd.HasAvailableFlags() {
    // Command has flags to display
}
```

### HasAvailableSubCommands()
Check for non-hidden subcommands:

```go
if cmd.HasAvailableSubCommands() {
    // Command has subcommands to display
}
```

---

## OnFinalize Callback

### Purpose
Runs cleanup code regardless of command success or failure:

```go
cmd.OnFinalize(func() {
    // Always runs
    cleanup()
    // Even if RunE returned an error
})
```

### Difference from PersistentPostRunE
- `PersistentPostRunE` doesn't run if RunE returns an error
- `OnFinalize` always runs
- Use for guaranteed cleanup

---

## Version Handling

### Setting Command Version
```go
cmd.Version = "1.2.3"
```

### Auto --version Flag
When Version is set, Cobra automatically provides --version flag.

---

## References

- **Advanced Features**: https://cobra.dev/docs/how-to-guides/working-with-commands/
- **API Documentation**: https://pkg.go.dev/github.com/spf13/cobra
