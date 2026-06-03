# Flag Groups System

**Sources**:
- https://cobra.dev/docs/how-to-guides/working-with-flags/
- https://pkg.go.dev/github.com/spf13/cobra
- https://github.com/spf13/cobra/blob/main/flag_groups.go

**Accessed**: 2026-04-04

---

## Flag Groups Overview

Cobra provides a flag groups feature to define relationships and constraints between command flags. Flag groups allow you to enforce rules about which flags can be used together.

---

## Flag Group Relationships

### MarkFlagsOneRequired
At least one flag from the group must be provided:

```go
cmd.MarkFlagsOneRequired("json", "yaml", "xml")
```

**Behavior**:
- Error if NONE of the flags are provided
- OK if ONE flag is provided
- OK if MULTIPLE flags are provided (unless also mutually exclusive)

**Use case**: User must specify output format somehow

### MarkFlagsMutuallyExclusive
At most one flag from the group allowed:

```go
cmd.MarkFlagsMutuallyExclusive("json", "yaml", "xml")
```

**Behavior**:
- Error if MORE THAN ONE flag is provided
- OK if ZERO flags are provided
- OK if exactly ONE flag is provided

**Use case**: User can only specify one output format

### MarkFlagsRequiredTogether
All flags must be used together (all or none):

```go
cmd.MarkFlagsRequiredTogether("username", "password")
```

**Behavior**:
- Error if ONE is provided but not the other
- OK if BOTH are provided
- OK if NEITHER is provided

**Use case**: Paired configuration options

---

## Combining Group Constraints

### Exactly One Required (OneRequired + MutuallyExclusive)
Combine both constraints to require exactly one:

```go
cmd.MarkFlagsOneRequired("json", "yaml")
cmd.MarkFlagsMutuallyExclusive("json", "yaml")
// User must provide exactly one (neither causes error, both causes error)
```

---

## Flag Group Semantics

### Multiple Group Membership
A flag can belong to multiple groups:

```go
cmd.MarkFlagsOneRequired("output", "verbose")      // output group
cmd.MarkFlagsMutuallyExclusive("json", "yaml")     // format group
cmd.Flags().StringP("output", "o", "", "output file")
cmd.Flags().StringP("json", "j", "", "JSON format")
cmd.Flags().StringP("yaml", "y", "", "YAML format")
cmd.Flags().Bool("verbose", false, "verbose")

// Both "output" and one of "json"/"yaml" can be used together
```

### Group Composition
- A group can contain any number of flags
- A flag can appear in multiple groups
- Groups are independent constraints

---

## Validation Behavior

### Validation Timing
Flag group validation occurs:
1. After command execution starts
2. Before Run/RunE is called
3. During argument/flag parsing

### Error Reporting
When validation fails:
1. Error message specifies which group constraint violated
2. Usage information is printed
3. Command exits with non-zero status

### Error Precedence
With multiple group violations:
- All violations are reported (or first encountered, depending on implementation)
- Exit with single non-zero status

---

## Common Patterns

### Mutually Exclusive Output Formats
```go
cmd.MarkFlagsMutuallyExclusive("json", "yaml", "csv")

cmd.Flags().Bool("json", false, "output as JSON")
cmd.Flags().Bool("yaml", false, "output as YAML")
cmd.Flags().Bool("csv", false, "output as CSV")
```

**Usage**:
```
cmd --json        # OK
cmd --yaml        # OK
cmd --json --yaml # ERROR
cmd               # OK (defaults to some format)
```

### One Required from Group
```go
cmd.MarkFlagsOneRequired("dev", "staging", "prod")

cmd.Flags().Bool("dev", false, "dev environment")
cmd.Flags().Bool("staging", false, "staging environment")
cmd.Flags().Bool("prod", false, "prod environment")
```

**Usage**:
```
cmd --dev       # OK
cmd --staging   # OK
cmd             # ERROR (must specify environment)
cmd --dev --staging  # OK (not mutually exclusive)
```

### Required Together (Paired Flags)
```go
cmd.MarkFlagsRequiredTogether("src", "dst")

cmd.Flags().StringP("src", "s", "", "source file")
cmd.Flags().StringP("dst", "d", "", "destination file")
```

**Usage**:
```
cmd --src=a --dst=b   # OK
cmd --src=a           # ERROR (dst required)
cmd --dst=b           # ERROR (src required)
cmd                   # OK (neither required standalone)
```

---

## Advanced Patterns

### Conditional Group Membership
Groups are flat - there's no native conditional logic. Implement conditionally:

```go
PreRunE: func(cmd *cobra.Command, args []string) error {
    if otherFlagSet {
        // Validate group membership conditionally
    }
    return nil
}
```

### Dynamic Flag Groups
Create flag groups that change based on configuration:

```go
// After parsing config
if config.AllowMultiple {
    // Don't mark as mutually exclusive
} else {
    cmd.MarkFlagsMutuallyExclusive("opt1", "opt2")
}
```

---

## Implementation Details

### Flag Group Storage
Flag groups are stored in internal Command structures and validated during execution.

### Group Validation
Validation is implemented in Cobra's core and checks flag set state against group definitions.

---

## Known Limitations

### No Nested Groups
Cannot create groups of groups. Flag groups are flat.

### No Conditional Dependencies
No way to say "if flag A, then flag B must be present" - only "all or nothing" with MarkFlagsRequiredTogether.

### No Priority/Precedence
No way to specify that one flag group takes precedence over another.

---

## Best Practices

1. **Keep groups simple** - Few flags per group
2. **Use meaningful flag names** - Groups should be obvious from flag names
3. **Document in help** - Explain flag relationships in Long description
4. **Test combinations** - Verify all valid/invalid combinations work correctly
5. **Combine with PreRunE** - For complex validation logic beyond flag groups

---

## References

- **Flag Groups**: https://cobra.dev/docs/how-to-guides/working-with-flags/
- **API**: https://pkg.go.dev/github.com/spf13/cobra
- **Source**: https://github.com/spf13/cobra/blob/main/flag_groups.go
