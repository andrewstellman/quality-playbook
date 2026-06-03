# GitHub Issues: Known Limitations and Design Decisions

**Source**: https://github.com/spf13/cobra/issues
**Context**: Analyzed significant issues and maintainer discussions

**Accessed**: 2026-04-04

---

## Flag System Issues

### Issue #412: Flags Don't Contain Inherited Flags
**Status**: Known limitation
**Impact**: `cmd.Flags()` methods may not report all inherited flags
**Workaround**: Use `cmd.InheritedFlags()` separately

### Issue #921: MarkFlagRequired Doesn't Look at Inherited Flags
**Status**: Known limitation
**Impact**: Required flag validation doesn't always work with inherited flags
**Workaround**: Validate in `PreRunE` instead
```go
PreRunE: func(cmd *Command, args []string) error {
    if _, err := cmd.Flags().GetString("required"); err != nil {
        return fmt.Errorf("required flag missing")
    }
    return nil
}
```

### Issue #1651: Help Text Shadowing Bug
**Status**: Fixed in PR #1776
**Impact**: When child shadowed parent flag, help didn't show the shadowing flag
**Resolution**: Help now correctly shows which flag takes priority

### Issue #1982: Exclude Persistent Flag from Sub-Command
**Status**: No native solution
**Impact**: Cannot prevent subcommand from inheriting specific persistent flag
**Workaround**: Check flag existence programmatically and error if needed

---

## Required Flags Issues

### Issue #2212: Required Persistent Flag Breaks Help/Completion
**Status**: Known limitation
**Impact**: If root has required persistent flag, `--help` and `completion` commands fail
**Cause**: Flag requirement checked before builtin command dispatch
**Workaround**: Don't mark persistent flags as required on root
- Validate in command-specific `PreRunE` instead
- Use flag groups instead

---

## Argument Validation Issues

### Issue #745: ExactArgs + ValidArgs + OnlyValidArgs
**Status**: Resolved via MatchAll
**Problem**: Can't combine ExactArgs with OnlyValidArgs
**Solution**: Use `MatchAll(ExactArgs(n), OnlyValidArgs)`

### Issue #838: MinimumValidNArgs, MaximumValidNArgs
**Status**: Feature request, not implemented
**Impact**: Cannot easily combine minimum/maximum with valid args validation
**Workaround**: Use custom validator

### Issue #1298: OnlyValidArgs Doesn't Work with ValidArgsFunction
**Status**: Known limitation
**Impact**: Dynamic valid args aren't checked by OnlyValidArgs
**Workaround**: Implement custom validator checking against function results

---

## Help and Documentation Issues

### Issue #587: How to Remove Help Subcommand
**Status**: Not easily possible
**Impact**: Cannot completely disable help subcommand
**Cause**: InitDefaultHelpCmd re-adds it if missing or nil
**Workaround**: SetHelpCommand to custom hidden command (imperfect)

### Issue #1368: How to Write Custom Help Command
**Status**: Partially supported
**Solutions**:
- SetHelpFunc for custom rendering
- SetHelpTemplate for template customization
- SetHelpCommand for custom command object

### Issue #1636: Define Help for Just Root Command
**Status**: Workaround available
**Solution**: Use custom help function that checks command level

### Issue #2084: Support text/template Templates for Docs
**Status**: Feature request
**Impact**: Want better template support for documentation generation
**Note**: Currently supports Go text/template

---

## Flag Parsing Issues

### Issue #1676: ContinueOnError During Flag Parsing
**Status**: Feature request
**Impact**: Want to continue parsing after flag errors in some cases
**Use Case**: Flexible CLI with optional arguments

### Issue #1733: Avoid Flag Parsing in Positional Arguments
**Status**: Known edge case
**Issue**: Flags can be interpreted within quoted argument strings
**Note**: Related to interspersed flag parsing behavior

### Issue #1307: Custom Completion Should Respect Interspersed Option
**Status**: Enhancement
**Impact**: Completions don't respect SetInterspersed(false) properly

---

## Error Handling Issues

### Issue #464: Error from PersistentPreRunE Printed Twice
**Status**: Known issue
**Impact**: Error messages can appear duplicated
**Workaround**: Set SilenceErrors appropriately

### Issue #914: How Best to Handle Errors in Run
**Status**: Design discussion
**Outcome**: RunE pattern is recommended
**Best Practice**: Use RunE, centralize error handling at Execute() level

### Issue #1967: --help Bypasses PersistentPreRunE
**Status**: Known limitation
**Impact**: Cannot enforce required configuration through PersistentPreRunE before help
**Workaround**: Documentation only, validation elsewhere if needed

### Issue #340: On Error in RunE, Don't Display Usage
**Status**: Resolved via SilenceUsage
**Solution**: Set `cmd.SilenceUsage = true`

---

## Hook and Lifecycle Issues

### Issue #219: Pre Run and Post Run Chain Functions
**Status**: Implemented
**Feature**: PersistentPreRun, PreRun, PostRun, PersistentPostRun
**Note**: EnableTraverseRunHooks controls parent hook execution

---

## Completion Issues

### Issue #1048: Fish Completion Support
**Status**: Implemented
**Feature**: Full Fish shell completion support with descriptions

### Issue #1146: Bash Completion V2 with Descriptions
**Status**: Implemented
**Feature**: GenBashCompletionV2 with description support
**Improvement**: Significantly smaller script size (~300 lines vs thousands)

### Issue #1161: DisableFlagParsing Must Trigger Custom Completion
**Status**: Fixed
**Impact**: When DisableFlagParsing is true, custom completion logic applies

### Issue #1095: Ignore Required Flags When DisableFlagParsing
**Status**: Fixed
**Impact**: Required flag validation doesn't apply when flag parsing disabled

---

## Flag Groups and Validation

### Issue #1725: Alias Behavior
**Status**: Works as designed
**Note**: Aliases don't appear in help, working as intended

### Issue #2145: SilenceErrors Override Hierarchy
**Status**: Feature discussion
**Impact**: Child command SilenceErrors may not override parent
**Note**: Inheritance behavior can be confusing

---

## DisableFlagParsing Issues

### Issue #1328: DisableFlagParsing Should Disable Help Flag Creation
**Status**: Design discussion
**Note**: Help flag still created, but may not work as expected
**Impact**: Plugin systems need to handle their own flag parsing

---

## Command-Level Issues

### Issue #266: Nested Commands Through cobra add
**Status**: Possible with --parent flag
**Solution**: `cobra-cli add cmd --parent parentCmd`

### Issue #1059: About Subcommand Directory
**Status**: Design discussion
**Note**: Directory organization is up to user

### Issue #1197: Child Packages Declaration
**Status**: Works with modular layout
**Pattern**: Each package exports a command constructor

---

## Summary of Common Patterns

### What Works Well
- Simple command hierarchies
- Flag inheritance with clear semantics
- Shell completions
- Error propagation via RunE
- Hook system for setup/cleanup

### What Has Limitations
- Complex flag validation combinations
- Required persistent flags on root
- Removing help command
- Dynamic validation against ValidArgsFunction
- Required flag visibility in help

### Recommended Workarounds
1. Validate in PreRunE instead of using MarkFlagRequired
2. Use custom validators for complex argument rules
3. Don't mark root persistent flags as required
4. Use MatchAll for combined validators
5. Handle errors centrally at Execute() level

---

## Design Philosophy Reflected in Issues

### Conservative Feature Addition
Cobra maintainers are cautious about adding features that might:
- Complicate the API
- Create maintenance burden
- Introduce edge cases

### Backward Compatibility First
When possible, issues are resolved through:
- Workarounds rather than breaking changes
- New functions rather than modifying existing ones
- Documentation rather than feature changes

### Real-World Pragmatism
Solutions reflect actual usage patterns:
- Plugin systems (DisableFlagParsing)
- Enterprise patterns (Context, tracing)
- User expectations (suggestions, help)

---

## References

- **GitHub Issues**: https://github.com/spf13/cobra/issues
- **Pull Requests**: https://github.com/spf13/cobra/pulls
