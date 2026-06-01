# Command Structure and Organization

**Sources**:
- https://cobra.dev/docs/how-to-guides/working-with-commands/
- https://pkg.go.dev/github.com/spf13/cobra
- https://github.com/spf13/cobra/blob/main/site/content/user_guide.md

**Accessed**: 2026-04-04

---

## Core Command Concepts

### Commands
Cobra commands are defined as `*cobra.Command` structs. Each command represents an action a user can perform.

### Command Struct Key Fields
```go
type Command struct {
    Use       string                    // One-line usage message (command name)
    Aliases   []string                  // Alternative names for the command
    Short     string                    // Short description (help output)
    Long      string                    // Long description (detailed help)
    Example   string                    // Usage examples
    ValidArgs []string                  // List of valid arguments
    Args      PositionalArgs            // Expected arguments validation
    Version   string                    // Command version
    Run       func(*Command, []string)  // Main logic (no error return)
    RunE      func(*Command, []string) error  // Main logic (with error return)
}
```

---

## Command Execution Lifecycle

Commands execute in the following order:
1. **PersistentPreRun** (inherited from parents)
2. **PreRun** (local only)
3. **Run** or **RunE** (main logic)
4. **PostRun** (local only)
5. **PersistentPostRun** (inherited from parents)

### Execution Pattern Example
```go
cmd.PersistentPreRunE = func(cmd *Command, args []string) error { ... }
cmd.RunE = func(cmd *Command, args []string) error { ... }
cmd.PersistentPostRun = func(cmd *Command, args []string) { ... }
```

---

## Subcommand Organization

### Adding Subcommands
The standard pattern attaches subcommands to a parent using `AddCommand()`, typically in the child's `init()` function.

```go
rootCmd.AddCommand(serveCmd)
rootCmd.AddCommand(configCmd)

// Nested subcommands
serveCmd.AddCommand(serveLocalCmd)
```

### Subcommand Nesting
Cobra's sophisticated command tree architecture supports **unlimited nesting depth** with automatic parent-child relationships.

**Examples of nested structures:**
- `app server` (one level)
- `app database migrate` (two levels)
- `app service kubernetes cluster node` (three levels)

---

## Command Aliases

### Definition
Aliases let users type what they expect. In Cobra, `Aliases` is a slice of strings (`[]string`), not a single string.

```go
cmd.Aliases = []string{"i", "add"}
// Commands can be invoked as:
// app install
// app i
// app add
```

### Best Practices for Aliases
- Provide at most one or two obvious aliases
- Too many aliases cause ambiguity
- Useful for backward compatibility during refactoring
- Aliases are not shown in help output (users must know about them through documentation)

### Important Behavior
While aliases function identically to the main command when invoked, they don't appear in the help subcommand list. Users need to know about aliases through documentation rather than discovering them via help.

---

## Command Path and Routing

### Understanding Command Paths
Commands are organized hierarchically. The full invocation represents the command path:
- `myapp` (root)
- `myapp greet` (subcommand)
- `myapp server config` (nested subcommand)

### Command Finding
Cobra's `Find()` method traverses the command tree to locate the target command based on the command path provided in arguments.

### Parent-Child Relationships
- Each subcommand knows its parent via `cmd.Parent()`
- Root command has no parent
- Command path can be retrieved via `cmd.CommandPath()`

---

## Command Organization Patterns

### Pattern 1: Simple Layout
All commands in a single `cmd/` package with one file per command:
```
▾ cmd/
  root.go
  server.go
  config.go
  deploy.go
```

**Good for**: Small CLIs with handful of commands
**Limitations**: Doesn't scale well beyond 5-10 commands

### Pattern 2: Modular Layout (Recommended at Scale)
Each feature gets its own package returning a `*cobra.Command` constructor:
```
▾ cmd/
  ▾ server/
    server.go     // returns *cobra.Command
  ▾ config/
    config.go     // returns *cobra.Command
  ▾ deploy/
    deploy.go     // returns *cobra.Command
  root.go
```

**Advantages**:
- Clear dependency boundaries
- Each team can own different features
- Scales to large command sets
- Better code organization

**When to transition**: When your command set grows beyond a handful of files

---

## Creating Commands

### Basic Command Creation
```go
var serveCmd = &cobra.Command{
    Use:   "serve",
    Short: "Start the server",
    Long:  "Start the web server...",
    RunE: func(cmd *cobra.Command, args []string) error {
        return startServer()
    },
}
```

### Adding to Parent
```go
func init() {
    rootCmd.AddCommand(serveCmd)
}
```

---

## Command Discovery and Help

### HasSubCommands()
```go
if cmd.HasSubCommands() {
    // Has child commands
}
```

### Finding Commands in Tree
```go
targetCmd, _, err := rootCmd.Find([]string{"server", "start"})
```

### CommandPath()
Returns the full command path from root to current command:
```go
cmd.CommandPath()  // Returns "myapp serve" for serve subcommand
```

---

## Command Validation and Defaults

### Marking Commands as Hidden
```go
cmd.Hidden = true  // Command works but doesn't appear in help
```

### Marking Commands as Deprecated
```go
cmd.Deprecated = "use 'newcommand' instead"
```

---

## Advanced Command Behaviors

### DisableFlagParsing
When true, all flags are passed to the command as arguments (used for plugin systems where the plugin handles its own flags).

```go
cmd.DisableFlagParsing = true
```

### TraverseChildren
Parses flags on all parents before executing child command.

```go
cmd.TraverseChildren = true  // Parse parent flags before child
```

---

## References

- **Working with Commands**: https://cobra.dev/docs/how-to-guides/working-with-commands/
- **API Documentation**: https://pkg.go.dev/github.com/spf13/cobra
- **User Guide**: https://github.com/spf13/cobra/blob/main/site/content/user_guide.md
