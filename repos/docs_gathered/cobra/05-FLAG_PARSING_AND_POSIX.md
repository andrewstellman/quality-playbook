# Flag Parsing and POSIX Compliance

**Sources**:
- POSIX IEEE 1003.1-2017 Section 12: Utility Conventions
- https://pkg.go.dev/github.com/spf13/pflag
- GNU Argument Syntax Conventions
- https://github.com/spf13/cobra issues on argument parsing

**Accessed**: 2026-04-04

---

## POSIX Utility Argument Structure

### Utility Invocation Pattern (POSIX)
```
utility_name [options] [option-arguments] [operands]
```

### POSIX Terminology

**Options**: Arguments with hyphen-minus and single letters or digits (e.g., `-a`, `-1`)

**Option-arguments**: Values that follow certain options

**Operands**: Arguments appearing after all options and option-arguments

---

## POSIX Flag Syntax Rules

### Guideline 1: Separator Requirement
"A conforming application shall use separate arguments for that option and its option-argument" (with historical exceptions permitted).

**Meaning**: Options and their arguments should be separate command-line arguments.
```
# Correct per POSIX
cmd -f filename
cmd --file filename

# Discouraged (but often accepted)
cmd -ffilename
```

### Guideline 2: Optional Arguments
When notation shows `[-f[option_argument]]`, the option-argument must be directly adjacent to the option without spaces.

### Guideline 3: Grouping
"One or more options without option-arguments, followed by at most one option that takes an option-argument, should be accepted when grouped."

**Meaning**: `-abc` where a, b are boolean flags and c takes an argument is acceptable.

### Guideline 4: Double Dash Terminator
"The first `--` argument that is not an option-argument should be accepted as a delimiter indicating the end of options. Any following arguments should be treated as operands, even if they begin with the '-' character."

**Example**:
```bash
cmd -v -- -file-starting-with-dash.txt
# "-file-starting-with-dash.txt" is an operand, not a flag
```

### Guideline 5: Numeric Values
Default interpretation is decimal; range 0 to 2,147,483,647 unless otherwise specified.

### Guideline 6: Format Notation
- `[ ]` indicates optional elements
- `|` denotes mutually-exclusive choices
- `...` (ellipses) indicate one or more (or zero or more if bracketed) occurrences

**These symbols don't appear in actual input.**

---

## Cobra's POSIX Compliance

### Using pflag for POSIX Support
Cobra provides POSIX-compliant flags through the **pflag library**, which is a drop-in replacement for Go's flag package that adds POSIX/GNU compliance.

**Key feature**: "Flag functionality is provided by the pflag library, a fork of the flag standard library which maintains the same interface while adding POSIX compliance."

---

## Flag Syntax in Cobra

### Single Dash Short Flags
```
-f          # Boolean flag
-n 1234     # Flag with value
-n=1234     # Flag with value using equals
-abc        # Combined boolean short flags
```

### Double Dash Long Flags
```
--flag              # Boolean flag
--flag value        # Flag with value
--flag=value        # Flag with value using equals
```

### Combined Behavior
pflag supports combining both single and double dashes with various formats.

---

## Flag Parsing Rules

### Go's Flag Package Behavior
From the Go standard library flag package:
- Parsing stops at first non-flag argument or after `--`
- All these forms are permitted:
  - `-flag`
  - `--flag` (double dashes also work)
  - `-flag=x`
  - `-flag x` (space-separated, non-boolean flags only)

### Boolean Flag Limitation
Boolean flags cannot use space-separated form:
```
-flag false   # INVALID
-flag=false   # VALID
```

### Supported Integer Formats
Integer flags accept:
- Decimal: `1234`
- Octal: `0664`
- Hexadecimal: `0x1234`
- Negative values: `-42`

### Boolean Flag Formats
Boolean flags accept:
- `1, 0, t, f, T, F, true, false, TRUE, FALSE, True, False`

### Duration Flag Formats
Duration flags accept values valid for `time.ParseDuration`:
```
300ms, 1.5h, 2h45m
```

---

## Interspersed Flag Parsing

### Default Behavior
By default (in pflag), flags can be interspersed with arguments anywhere before the `--` terminator:
```
app --flag value arg1 arg2
app arg1 --flag value arg2
app arg1 arg2 --flag value
```

All three forms are equivalent with interspersed parsing enabled (default).

### Disabling Interspersed Parsing
To enforce POSIX-style where flags must come before operands:
```go
flags.SetInterspersed(false)
```

**Effect**: After the first non-flag argument, all remaining arguments are treated as operands, not flags.

### POSIX Compliance Note
Strict POSIX style requires flags before operands, but many modern CLIs (and Cobra by default) allow interspersed flags for convenience.

---

## GNU Extensions to POSIX

### Long Options (GNU Style)
GNU added support for long options that don't exist in strict POSIX:
```
--verbose     # GNU extension
--config=file # GNU extension
```

### GNU vs. POSIX Differences
| Feature | POSIX | GNU |
|---------|-------|-----|
| Long options | No (only single-letter) | Yes (`--verbose`) |
| Option grouping | `-abcd` (limited) | `-abc` (flexible) |
| Option syntax | Strict | More flexible |
| End-of-options | `--` | `--` (same) |

### Cobra Support
Cobra supports both POSIX and GNU styles through pflag:
```
-v              # POSIX style (single letter)
--verbose       # GNU style (long option)
-v --verbose    # Both in same application
```

---

## Option-Argument Handling

### Separate Arguments (Recommended)
```
--file filename
--config /path/to/config
```

### Combined with Equals
```
--file=filename
--config=/path/to/config
```

### Flag Value Types Behavior
- **Boolean flags**: No argument expected, cannot use `=` form
- **String flags**: Argument required or optional (via NoOptDefVal)
- **Integer flags**: Argument required

---

## Double Dash (`--`) Semantics

### Purpose
The `--` marker tells the command: "stop parsing tokens as options; treat everything following as operands."

### Important Behavior
- The `--` itself is not passed to the program as an operand
- Most utilities discard it
- Useful when legitimate arguments start with `-`

### Practical Example
```bash
# Remove file named "-f"
rm -- -f

# Cobra application
app command -- --looks-like-a-flag-but-isnt
```

---

## Cobra's Compliance

### POSIX Claim
"Cobra supports fully POSIX-compliant flags as well as the Go flag package."

### In Practice
- Uses pflag for POSIX/GNU compliance
- Supports both short (`-v`) and long (`--verbose`) forms
- Handles double dash correctly
- Allows interspersed flags by default (modern convenience, not strict POSIX)

---

## References

- **POSIX Utility Conventions**: https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap12.html
- **pflag Documentation**: https://pkg.go.dev/github.com/spf13/pflag
- **Go Flag Package**: https://pkg.go.dev/flag
