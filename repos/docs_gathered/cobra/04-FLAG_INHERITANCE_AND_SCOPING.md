# Flag Inheritance and Scoping Behavior

**Sources**:
- https://cobra.dev/docs/how-to-guides/working-with-flags/
- GitHub Issues: #412, #921, #1651, #1776, #1982
- https://opdev.github.io/cobra-primer/hands_on/persistent_flags.html

**Accessed**: 2026-04-04

---

## Flag Inheritance Hierarchy

### Persistent Flags
"Persistent flags live on a parent and are available to all descendants (unless shadowed)."

**Behavioral spec**:
- Defined on parent command via `PersistentFlags()`
- Automatically inherited by all child commands and their descendants
- Can be overridden by child commands (shadowing)

### Local Flags
"Local flags live on a single command and do not inherit to children."

**Behavioral spec**:
- Defined on command via `Flags()`
- Restrict to specific command only
- Not available in subcommands unless redefined

---

## Flag Shadowing Behavior

### What is Flag Shadowing?
When a child command defines a local flag with the same name as a parent's persistent flag, the child's local flag "shadows" or hides the parent's flag.

### Shadowing Example
```go
// Parent command
rootCmd.PersistentFlags().Bool("verbose", false, "verbose output")

// Child command
serveCmd.Flags().Bool("verbose", false, "custom verbose behavior")
// serveCmd uses its own --verbose flag, not parent's
```

### Shadowing Semantics
When a child flag shadows a parent flag:
- The child flag is the one actually used during execution
- The parent's flag value is ignored for that command
- Subcommands of the child inherit the child's shadowed flag (not the parent's)

### Help Output Bug (Fixed)
There was a bug where the help command did not respect shadowing and gave priority to persistent flags, so the shadowing flag was not shown in the help output. This was fixed in PR #1776, making help output consistent with actual execution behavior.

---

## Accessing Flag Values

### Recommended Pattern
When accessing flag values from a command, use `cmd.Flags()` not `cmd.PersistentFlags()`:

```go
// CORRECT
value, _ := cmd.Flags().GetString("flagname")

// WRONG (doesn't get inherited flags)
value, _ := cmd.PersistentFlags().GetString("flagname")
```

**Why**: `cmd.Flags()` returns all flags applicable to the command (local + inherited), while `cmd.PersistentFlags()` only returns that specific command's persistent flags.

### Flag Access Methods

```go
cmd.Flags()              // All flags (local + inherited) - USE THIS
cmd.LocalFlags()         // Local flags only
cmd.PersistentFlags()    // Persistent defined on THIS command only
cmd.InheritedFlags()     // Flags inherited FROM PARENTS
cmd.Flag("name")         // Get specific flag by name (searches all)
```

---

## Flag Marking Issues

### MarkFlagRequired() Limitation
`MarkFlagRequired()` has issues with inherited flags - it doesn't always recognize flags inherited from parents without special handling.

**Known issue** (GitHub #921): `command.MarkFlagRequired` does not properly look at inherited flags.

**Workaround**: Perform required flag validation in `PreRunE`:
```go
PreRunE: func(cmd *cobra.Command, args []string) error {
    if _, err := cmd.Flags().GetString("required-flag"); err != nil {
        return fmt.Errorf("required flag 'required-flag' not set")
    }
    return nil
}
```

---

## Flag Scope Best Practices

### When to Use Persistent Flags
Use persistent flags for:
- Global configuration (config file path, verbose mode)
- Authentication credentials
- Logging settings
- Options that apply to all subcommands

```go
rootCmd.PersistentFlags().String("config", "", "config file")
```

### When to Use Local Flags
Use local flags for:
- Command-specific options
- Feature flags unique to that command
- Parameters that don't apply to subcommands

```go
serveCmd.Flags().Int("port", 8080, "server port")
```

### Design Guideline
"Use persistent flags sparingly—only for truly global concerns."

Too many persistent flags can make your command structure confusing and flag discovery harder.

---

## Exclusive Persistent Flag Behavior

### Excluding Persistent Flags from Subcommands
There is no built-in mechanism in Cobra to exclude a persistent flag from specific subcommands. This is a known limitation (GitHub #1982).

**Workaround**: Check flag availability programmatically:
```go
if cmd.Parent() != nil && someCondition {
    // Handle flag differently or error
}
```

---

## Required Persistent Flags Edge Case

### The Help/Completion Problem
When a required persistent flag is set on the root command, the built-in "completion" and "help" commands may fail if the required flag is not provided.

**Why**: Flag requirement validation happens before builtin command dispatch, so `--help` requires the persistent flag.

**Example of the problem**:
```bash
$ app --help
Error: required flag "config" not provided
```

**Workaround**:
- Don't mark persistent flags as required on root
- Instead, validate in `PersistentPreRunE` of specific commands
- Or use flag groups with `MarkFlagsOneRequired()` instead of hard requirements

---

## Flag Inheritance with Multiple Levels

### Multi-Level Nesting
In deeply nested commands, flags inherit through the entire hierarchy:

```
root (defines --verbose persistent)
└── parent (defines --output persistent)
    └── child (defines --format local)
```

**Child sees**:
- --verbose (from root)
- --output (from parent)
- --format (local)

### Shadowing in Nested Hierarchies
If multiple levels define the same flag:
```
root (--verbose persistent)
└── parent (--verbose persistent - shadows root's)
    └── child (inherits parent's --verbose)
```

Child inherits parent's version, not root's.

---

## Traversing Parent Flags

### TraverseChildren Flag
When enabled, parses local flags on each parent before executing the target command:

```go
cmd.TraverseChildren = true
// Parse flags on: root → parent → target command
```

**Default behavior**: Only parses flags on the target command and its persistent flags.

---

## Hidden and Deprecated Inherited Flags

### Hiding Inherited Flags
```go
rootCmd.PersistentFlags().MarkHidden("debug")
// Flag still works in subcommands but doesn't appear in their help
```

### Deprecating Inherited Flags
```go
rootCmd.PersistentFlags().MarkDeprecated("old-flag", "use --new-flag")
// Subcommands inherit the deprecation warning
```

---

## Testing Flag Inheritance

When testing commands, verify:
1. Flags defined on parent are accessible from child
2. Shadowing works correctly
3. Help output shows correct flag priority
4. Required flag validation follows intended hierarchy

---

## References

- **Flag Scoping**: https://cobra.dev/docs/how-to-guides/working-with-flags/
- **GitHub Issue #412**: "Flags don't contain inherited flags"
- **GitHub Issue #921**: "MarkFlagRequired does not look at inherited flags"
- **GitHub Issue #1651**: "Help text shadowing bug"
- **GitHub Issue #1982**: "Exclude persistent flag in sub-command"
