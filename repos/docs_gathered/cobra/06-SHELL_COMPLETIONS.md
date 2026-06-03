# Shell Completions System

**Sources**:
- https://cobra.dev/docs/how-to-guides/shell-completion/
- https://github.com/spf13/cobra/blob/main/site/content/completions/_index.md
- GitHub completions implementation files

**Accessed**: 2026-04-04

---

## Overview

Cobra provides automatic shell completion for bash, zsh, fish, and PowerShell through a unified completion framework.

### Supported Shells
- **Bash** (v1 and v2)
- **Zsh**
- **Fish**
- **PowerShell**

---

## Completion Generation

### Fundamental Approach
Commands can specify completion logic through three mechanisms:

1. **ValidArgs** - Static list of valid argument values
2. **ValidArgsFunction** - Dynamic function providing argument completions
3. **RegisterFlagCompletionFunc()** - Function providing flag value completions

### Important Constraint
Either `ValidArgs` or `ValidArgsFunction` can be used for a single command, but **not both**.

---

## Bash Completion

### Installation Process

**Step 1: Generate completion script**
```bash
./your-cli completion bash
```

**Step 2: Install to appropriate directory**

System-wide:
```bash
./your-cli completion bash | sudo tee /etc/bash_completion.d/your-cli
```

User-only:
```bash
./your-cli completion bash > ~/.local/share/bash-completion/completions/your-cli
```

**Step 3: Reload shell**
```bash
source ~/.bashrc
```

### Bash Completion Versions

#### Bash v1 (Legacy)
- Thousands of lines of shell script
- Complex bash-only implementation
- Limited features

#### Bash v2 (Recommended)
- ~300 lines of shell script
- Based on Go completions system
- Supports completion descriptions
- Modern and efficient

**Usage**:
```go
cmd.GenBashCompletionV2(writer, true)  // true = include descriptions
```

### Bash v2 Descriptions
Completions can include descriptive text:
```go
// For commands
cmd.Short = "Description shown in completion"

// For flag values, use CompletionWithDesc()
```

---

## Zsh Completion

### Installation Process

**Step 1: Generate completion file**
```bash
./your-cli completion zsh > _your-cli
```

**Step 2: Install to function directory**

System-wide:
```bash
sudo mv _your-cli /usr/local/share/zsh/site-functions/
```

User-only:
```bash
mkdir -p ~/.zsh/completions
mv _your-cli ~/.zsh/completions/
echo 'fpath=(~/.zsh/completions $fpath)' >> ~/.zshrc
```

**Step 3: Reload shell**
```bash
source ~/.zshrc
```

### Zsh Features
- Supports completion descriptions
- Descriptions automatically provided from flag/command usage text
- Context-aware completions

---

## Fish Completion

### Installation Process (Simplest)
```bash
./your-cli completion fish > ~/.config/fish/completions/your-cli.fish
```

**That's it** - Fish automatically loads from `~/.config/fish/completions/`

### Fish Limitations
Custom completions implemented in Bash scripting (legacy) are not supported and will be ignored for fish. Use:
- `ValidArgsFunction` for command argument completion
- `RegisterFlagCompletionFunc()` for flag value completion

These are portable to different shells.

### Fish Features
- Descriptions supported
- Portable Go completion logic applies
- Simplest installation process

---

## PowerShell Completion

### Installation Process

**Step 1: Generate completion script**
```powershell
./your-cli completion powershell
```

**Step 2: Add to PowerShell profile**
```powershell
./your-cli completion powershell | Out-String | Invoke-Expression
```

Or save to profile file:
```powershell
./your-cli completion powershell | Out-String | Add-Content $PROFILE
```

**Step 3: Adjust execution policy if needed**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### PowerShell Features
- Modern completion system integration
- Descriptions supported

---

## Dynamic Completions

### ValidArgsFunction
Provides dynamic argument completion:

```go
cmd.ValidArgsFunction = func(cmd *Command, args []string, toComplete string) ([]string, ShellCompDirective) {
    return []string{"option1", "option2"}, ShellCompDirectiveDefault
}
```

**Called when**: User requests completion for positional arguments

**Parameters**:
- `cmd` - Current command
- `args` - Previously parsed arguments
- `toComplete` - The string being completed

**Returns**:
- `[]string` - List of completion suggestions
- `ShellCompDirective` - Behavioral directive for shell

### Flag Completion Functions
```go
cmd.RegisterFlagCompletionFunc("flag", func(cmd *Command, args []string, toComplete string) ([]string, ShellCompDirective) {
    return []string{"value1", "value2"}, ShellCompDirectiveDefault
})
```

---

## ShellCompDirective Values

Bit-field values controlling shell completion behavior:

| Directive | Meaning |
|-----------|---------|
| `ShellCompDirectiveDefault` | Shell performs default behavior (file completion if no matches) |
| `ShellCompDirectiveNoSpace` | Don't add space after completion |
| `ShellCompDirectiveNoFileComp` | Disable file completion when no matches |
| `ShellCompDirectiveFilterFileExt` | Only complete files with specified extensions |
| `ShellCompDirectiveFilterDirs` | Only complete directory names |

### Combining Directives
```go
cobra.ShellCompDirectiveNoSpace | cobra.ShellCompDirectiveNoFileComp
```

---

## Completion Helper Functions

### NoFileCompletions
Disables file completion for a flag:
```go
cmd.RegisterFlagCompletionFunc("flag", cobra.NoFileCompletions)
```

### FixedCompletions
Provides fixed set of completions:
```go
cmd.RegisterFlagCompletionFunc("output-format", cobra.FixedCompletions(
    []string{"json", "yaml", "xml"},
    ShellCompDirectiveDefault,
))
```

### CompletionWithDesc
Adds descriptions to completions:
```go
[]string{
    cobra.CompletionWithDesc("option1", "description"),
    cobra.CompletionWithDesc("option2", "description"),
}
```

---

## Completion Directives

### MarkFlagFilename
Marks flag as expecting file paths with optional extensions:

```go
cmd.MarkFlagFilename("config", "yaml", "json")
// Completes with filenames ending in .yaml or .json
```

### MarkFlagDirname
Marks flag as expecting directory paths:

```go
cmd.MarkFlagDirname("output-dir")
```

### MarkFlagCustom
Legacy bash completion using custom completion function:

```go
cmd.MarkFlagCustom("custom", "bashFunctionName")
```

---

## Active Help (Contextual Hints)

### AppendActiveHelp
Adds contextual help during completion:

```go
func(cmd *Command, args []string, toComplete string) ([]string, ShellCompDirective) {
    completions := []string{"option1", "option2"}
    completions = cobra.AppendActiveHelp(completions, "Select an option from the list")
    return completions, ShellCompDirectiveDefault
}
```

---

## Unified Go Completion Logic

### Cross-Shell Implementation
Fish, Zsh, and PowerShell share the same Go completion logic with strongly aligned behavior. The same Go completion code also powers Bash v2 completion.

This means:
- Define `ValidArgsFunction` once
- Works across all four shells
- Consistent behavior everywhere

### Shell-Specific Installation Only
While completion logic is unified, shell-specific installation and script generation differ by shell.

---

## Descriptions in Completions

### Automatic Descriptions
Cobra automatically provides descriptions based on:
- Command `Short` field
- Flag `Usage` text

### Manual Descriptions
For custom completions, use `CompletionWithDesc()`:
```go
return cobra.CompletionWithDesc("value", "Description"), directive
```

---

## References

- **Shell Completion Guide**: https://cobra.dev/docs/how-to-guides/shell-completion/
- **Completions Documentation**: https://github.com/spf13/cobra/blob/main/site/content/completions/_index.md
