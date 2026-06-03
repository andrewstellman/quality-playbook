# POSIX Utility Conventions (IEEE 1003.1-2017)

**Source**: POSIX IEEE Std 1003.1-2017, Section 12: Utility Conventions
**URL**: https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap12.html

**Accessed**: 2026-04-04

---

## Argument Structure (Section 12.1)

### Standard Utility Invocation
```
utility_name [options] [option-arguments] [operands]
```

### Terminology

**Options**: Arguments with hyphen-minus and single letters or digits
- Examples: `-a`, `-1`, `-f`
- Single character (letter or digit) preceded by single hyphen-minus

**Option-arguments**: Values that follow certain options
- Can be required or optional
- Positioning rules depend on option definition

**Operands**: Arguments appearing after all options and option-arguments
- The actual subjects being operated on
- Cannot start with hyphen-minus (to distinguish from options)

---

## Syntax Guidelines (Section 12.2)

### Guideline 1: Separate Arguments
"A conforming application shall use separate arguments for that option and its option-argument."

**Meaning**:
```bash
# Correct
cmd -f filename

# Non-conforming
cmd -ffilename
```

**Exception**: Historical implementations sometimes bundle them.

### Guideline 2: Optional Arguments
When option-argument is optional, it shall immediately follow the option without intervening spaces.

**Notation**: `[-f[option_argument]]`

**Example**:
```bash
cmd -f              # Option alone
cmd -fvalue         # Option with adjacent argument
cmd -f value        # Not standard for optional arguments
```

### Guideline 3: Option Grouping
"One or more options without option-arguments, followed by at most one option that takes an option-argument, should be accepted when grouped."

**Valid groupings**:
```bash
cmd -abc filename    # a, b boolean; c takes filename
cmd -a -b -c file   # Separated form
```

**Invalid grouping**:
```bash
cmd -cab filename    # c takes argument but isn't last in group
```

### Guideline 4: Double Dash Terminator
"The first `--` argument that is not an option-argument should be accepted as a delimiter indicating the end of options."

**Behavior**:
```bash
cmd -v -- -file      # -file is operand, not option
cmd -- -file         # -file is operand
```

### Guideline 5: Numeric Values
- Default interpretation: decimal
- Standard range: 0 to 2,147,483,647
- Unless utility specifies differently

### Guideline 6: Format Notation
Brackets `[ ]`, pipes `|`, and ellipses `...` are notation, not actual characters.

---

## Option Syntax Details

### Option Format
- Single alphanumeric character
- Preceded by single hyphen-minus (-)
- Examples: `-f`, `-1`, `-x`

### Option Name Length
- Exactly one character (per strict POSIX)
- GNU extensions allow longer names with double dash

### Option-Argument Format
- Can be space-separated or adjacent to option
- Rules depend on option definition

### Operand Positioning
- Come after all options and option-arguments
- Begin with non-hyphen-minus character
- Multiple operands separated by whitespace

---

## Examples from POSIX

### grep Utility
```
grep [-E|-F] [-c|-l|-q] [-insvx] [-e pattern_list]... [-f pattern_file]... [file...]
```

**Options without arguments**: `-E, -F, -c, -l, -q, -i, -n, -s, -v, -x`
**Options with arguments**: `-e pattern_list, -f pattern_file`
**Operands**: `[file...]`

### find Utility
```
find [-H|-L|-P] [-D debugopts] [-x] [file...] [expression]
```

---

## Conformance Requirements

### For Applications
To be POSIX-conforming, applications must:
1. Recognize single-character options preceded by `-`
2. Group options where possible
3. Accept `--` to end options
4. Treat arguments starting with `-` (after `--`) as operands
5. Use standard option-argument syntax

### For Utilities (Special Cases)
Some utilities have special rules documented in their specifications.

---

## Relationship to Cobra

Cobra claims "fully POSIX-compliant flags" through:
- pflag library (POSIX/GNU compliant)
- Single dash support for short options
- Double dash support for long options
- `--` terminator handling
- Grouped short options

Cobra may be MORE permissive than strict POSIX:
- Allows interspersed flags (not standard POSIX)
- Supports GNU long options (not in strict POSIX)

---

## Key Differences: Strict POSIX vs Cobra Default

| Aspect | POSIX | Cobra Default |
|--------|-------|---------------|
| Flags before operands | Required | Flexible (interspersed) |
| Long options | Not standard | Supported |
| Option grouping | Limited | More flexible |
| Double dash | Required for end-of-options | Supported |
| Option-argument spacing | Strict rules | More flexible |

---

## References

- **Official POSIX**: https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap12.html
- **IEEE 1003.1-2017**: Base Specifications, Issue 7
