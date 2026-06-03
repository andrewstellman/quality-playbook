# Cobra CLI Framework Documentation Collection

**Purpose**: Comprehensive behavioral specification documentation for the Go Cobra CLI framework (spf13/cobra)

**Use Case**: Spec auditing, bug identification, and understanding intended behavior vs. implementation

---

## Quick Start

1. **Start here**: Read `INDEX.md` for the master index and navigation guide
2. **Quick summary**: See `COLLECTION_SUMMARY.md` for statistics and file descriptions
3. **Find your topic**: Use the coverage map in INDEX.md to locate relevant files
4. **Deep dive**: Read the numbered files (01-17) for detailed specifications

---

## What's Included

### Core Behavioral Specifications
- **02-COMMAND_STRUCTURE.md** - Command organization and lifecycle
- **03-FLAGS_AND_ARGUMENTS.md** - Flag types, scoping, and declarations
- **04-FLAG_INHERITANCE_AND_SCOPING.md** - How flags inherit and shadow
- **05-FLAG_PARSING_AND_POSIX.md** - POSIX compliance and parsing behavior
- **06-SHELL_COMPLETIONS.md** - Completion system across all shells
- **07-ERROR_HANDLING.md** - Error propagation and handling
- **08-ARGUMENT_VALIDATION.md** - Argument validators and constraints
- **09-FLAG_GROUPS.md** - Flag group relationships and constraints
- **10-CONTEXT_AND_TRACING.md** - Context propagation and observability
- **11-ADVANCED_FEATURES.md** - DisableFlagParsing, TraverseChildren, etc.

### Standards & Implementation
- **12-POSIX_CONVENTIONS.md** - IEEE 1003.1-2017 specifications
- **13-GNU_CONVENTIONS.md** - GNU argument syntax conventions
- **14-PFLAG_LIBRARY.md** - pflag drop-in replacement implementation
- **15-GO_FLAG_PACKAGE.md** - Go standard library flag behavior

### Design & Issues
- **16-DESIGN_PHILOSOPHY.md** - Creator's vision and design principles
- **17-GITHUB_ISSUES_SUMMARY.md** - Known limitations and workarounds
- **01-OFFICIAL_COBRA_DOCS.md** - Overview of official documentation

---

## Collection Highlights

### Comprehensive Coverage
- 19 files covering all major feature areas
- 4,842 lines of behavioral specifications
- 160 KB of documentation
- Source URLs and access dates for all information

### Known Issues Documented
- Required persistent flags breaking help/completion
- Flag shadowing in help text edge cases
- OnlyValidArgs with ValidArgsFunction limitations
- PersistentPostRunE not running on errors
- Help command can't be completely removed

### Standards Compliance Details
- POSIX IEEE 1003.1-2017 utility conventions
- GNU argument syntax extensions
- pflag POSIX/GNU implementation details
- Go flag package standard behavior

### Design Intent
- Philosophy of simplicity and developer experience
- Orthogonal design (Cobra + Viper)
- Enterprise patterns and best practices
- Security-first approach

---

## How to Use This Collection

### Finding Documentation
1. Use the coverage map in **INDEX.md**
2. Look for specific feature areas (flags, commands, completions, etc.)
3. Cross-reference related sections

### Understanding Behavior
1. Read the "Behavioral spec" or "Behavior" sections
2. Check constraints and limitations
3. Review practical examples provided

### Identifying Divergences
1. Read the behavioral specification
2. Cross-reference with POSIX/GNU specs if applicable
3. Check GitHub Issues for known limitations
4. Compare with actual implementation

---

## File Organization

```
docs_gathered/
├── README.md                          ← YOU ARE HERE
├── INDEX.md                           ← START HERE
├── COLLECTION_SUMMARY.md              ← Quick overview
├── 01-OFFICIAL_COBRA_DOCS.md          ← Cobra overview
├── 02-COMMAND_STRUCTURE.md            ← Commands
├── 03-FLAGS_AND_ARGUMENTS.md          ← Flags
├── 04-FLAG_INHERITANCE_AND_SCOPING.md ← Flag inheritance
├── 05-FLAG_PARSING_AND_POSIX.md       ← Parsing behavior
├── 06-SHELL_COMPLETIONS.md            ← Completions
├── 07-ERROR_HANDLING.md               ← Errors
├── 08-ARGUMENT_VALIDATION.md          ← Validation
├── 09-FLAG_GROUPS.md                  ← Flag groups
├── 10-CONTEXT_AND_TRACING.md          ← Observability
├── 11-ADVANCED_FEATURES.md            ← Advanced
├── 12-POSIX_CONVENTIONS.md            ← POSIX standards
├── 13-GNU_CONVENTIONS.md              ← GNU standards
├── 14-PFLAG_LIBRARY.md                ← pflag impl
├── 15-GO_FLAG_PACKAGE.md              ← Go flag pkg
├── 16-DESIGN_PHILOSOPHY.md            ← Design
├── 17-GITHUB_ISSUES_SUMMARY.md        ← Issues & gotchas
```

---

## Key Features

### Complete Specifications
Every feature includes:
- Behavioral specification (what should happen)
- Practical examples
- Known limitations
- Workarounds and solutions

### Standards References
- POSIX IEEE 1003.1-2017 (Issue 7)
- GNU Coding Standards
- Go standard library conventions

### Source Traceability
- All information sourced from official documentation
- URLs included for every source
- Access dates for version context
- Direct quotes from specifications

---

## Quick Reference: Common Tasks

### Understanding flag behavior → 03-FLAGS_AND_ARGUMENTS.md + 04-FLAG_INHERITANCE_AND_SCOPING.md
### Understanding command lifecycle → 02-COMMAND_STRUCTURE.md
### Understanding error handling → 07-ERROR_HANDLING.md
### Understanding completions → 06-SHELL_COMPLETIONS.md
### Checking POSIX compliance → 05-FLAG_PARSING_AND_POSIX.md + 12-POSIX_CONVENTIONS.md
### Finding known issues → 17-GITHUB_ISSUES_SUMMARY.md
### Understanding design intent → 16-DESIGN_PHILOSOPHY.md

---

## Documentation Quality

✓ Sourced from official documentation
✓ Standards-referenced specifications
✓ Known limitations documented
✓ Practical examples provided
✓ Cross-referenced sections
✓ Source URLs and dates included
✓ Behavioral specifications (not tutorials)
✓ Community issue discussions analyzed

---

## Compilation Details

- **Compiled**: 2026-04-04
- **Baseline**: Cobra v1.3.2 behavior context
- **Source Count**: 20+ official and standards sources
- **GitHub Issues Reviewed**: 25+ significant discussions
- **Total Research**: Comprehensive behavioral specification gathering

---

## Next Steps

1. **Read INDEX.md** - Get oriented with the full structure
2. **Check your area** - Find files relevant to what you're investigating
3. **Review specifications** - Understand documented vs actual behavior
4. **Check limitations** - Review GitHub issues for known gotchas
5. **Cross-reference** - Use the coverage map to find related topics

---

**This collection is designed to give spec auditors enough context to identify when Cobra code diverges from documented intent.**

For updates or corrections, refer to official sources:
- https://cobra.dev/
- https://github.com/spf13/cobra
- https://pkg.go.dev/github.com/spf13/cobra
