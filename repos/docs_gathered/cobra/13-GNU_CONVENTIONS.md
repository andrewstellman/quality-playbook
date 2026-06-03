# GNU Argument Syntax Conventions

**Sources**:
- GNU Software Manual: Argument Syntax
- GNU Coding Standards
- Unix command line evolution

**Accessed**: 2026-04-04

---

## Overview

GNU added extensions to POSIX conventions for command-line argument handling. These extensions are now widely used in modern CLI tools and are supported by Cobra through pflag.

---

## Single-Dash Short Options (Unix Tradition)

### Format
Single letter preceded by single hyphen-minus:
```
-v          # Enable verbose
-f FILE     # Specify file
-abc        # Multiple boolean flags (grouped)
```

### Grouping Rules
Mode-flag options (boolean) can be grouped together:
```bash
-v          # verbose
-x          # execute
-vx or -xv  # both (order doesn't matter for booleans)
-n 1234 -x  # numeric flag followed by boolean
```

### All but Last Must Be Boolean
In a group like `-abcn1234`, all but the last are treated as boolean flags, and the last can take an argument.

---

## Double-Dash Long Options (GNU Extension)

### Format
Full option name preceded by double hyphen-minus:
```
--verbose           # Enable verbose mode
--config FILE       # Specify config file
--output=file.txt   # Option with equals
```

### Syntax Variants
```
--flag value        # Space-separated
--flag=value        # With equals sign
```

### Cannot Be Grouped
GNU long options cannot be grouped like short options:
```bash
--verbose --debug       # Two separate options
--verbose-debug         # NOT the same as above (different flag)
```

### Advantages
- Self-documenting
- Less ambiguous than single letters
- Supports meaningful names

---

## Long Option Equivalents

### Design Pattern
GNU standards recommend providing long-named options equivalent to single-letter options:

"Please define long-named options that are equivalent to the single-letter Unix-style options. We hope to make GNU more user friendly this way."

### Example
```
-v, --verbose
-o, --output
-f, --file
```

### Benefit
Users can use whichever form they prefer:
```bash
app -v --output file.txt    # Mixed forms
app --verbose --output file.txt  # All long
app -vo file.txt            # All short
```

---

## Double Dash as End-of-Options Marker

### Purpose
The `--` marker tells the command:
"Stop parsing options. Everything following is an operand."

### Behavior
```bash
app --flag value -- --not-a-flag-arg.txt
# --flag is option
# value is its argument
# --not-a-flag-arg.txt is an operand (not an option)
```

### Practical Use
When operands might look like options:
```bash
# Remove file named "-f"
rm -- -f

# Grep for lines starting with "-"
grep -- "-pattern" file.txt
```

### Implementation
- The `--` itself is typically discarded
- Most utilities don't pass it to command logic
- POSIX-mandated behavior

---

## GNU vs POSIX Summary

| Aspect | POSIX | GNU |
|--------|-------|-----|
| Short options | `-v` (single letter only) | `-v` (single letter) |
| Long options | Not standard | `--verbose` (GNU extension) |
| Option syntax | Strict rules | More flexible |
| Grouping | Defined rules | Shorthands grouped, longs not |
| Convenience | Less user-friendly | More user-friendly |
| Tool familiarity | Varies | Expected by modern users |

---

## Common GNU Tools

GNU utilities typically follow these patterns:

```bash
# GNU grep
grep -r -i --include="*.txt" pattern /path

# GNU tar
tar -czf archive.tar.gz --exclude="*.o" /path

# GNU ls
ls -la --color=auto --group-directories-first
```

---

## Cobra's GNU Support

Cobra implements GNU conventions through **pflag library**:

```go
cmd.Flags().BoolVarP(&verbose, "verbose", "v", false, "verbose output")
// Supports both: -v and --verbose

cmd.Flags().StringVarP(&file, "file", "f", "", "input file")
// Supports both: -f value and --file=value
```

---

## Designing User-Friendly CLIs

### Best Practices
1. Provide both short and long forms
2. Keep short options to single letter
3. Use long options for clarity
4. Group related options
5. Use double dash support for ambiguous arguments

### Example Well-Designed CLI
```bash
# All valid
myapp -c config.yaml
myapp --config config.yaml
myapp -c config.yaml -v --output result.txt
myapp --help
myapp --version
```

---

## References

- **GNU Software Manual**: https://www.gnu.org/software/libc/manual/
- **GNU Coding Standards**: https://www.gnu.org/prep/standards/standards.html
- **getopt_long**: Reference implementation for GNU-style parsing
