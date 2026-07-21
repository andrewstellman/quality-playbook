# ERB::Compiler — Template Compilation

`ERB::Compiler` is the subsystem that translates an ERB template string into executable Ruby source code. It is defined in `lib/erb/compiler.rb` and is instantiated internally by `ERB.new`, but it is also available for direct use when custom code-generation hooks are needed.

## Role in the Pipeline

The compiler sits between the raw template text and the Ruby `eval` step. Its output — a Ruby source string — is what `ERB#src` exposes and what `ERB#result` evaluates. The compiler converts every template token into one of:

- An append call for literal text (via `put_cmd`)
- An append call for a Ruby expression result (via `insert_cmd`)
- Raw Ruby code inserted as a statement (for `<% ... %>` blocks)
- A comment placeholder that advances the line counter without emitting code (for `<%# ... %>`)

## Instantiation

```ruby
ERB::Compiler.new(trim_mode)
```

`trim_mode` is a string composed of zero or more mode characters (`%`, `>`, `<>`, `-`), or `nil` for no trimming. The compiler's `prepare_trim_mode` method normalizes this into an internal `[percent_bool, trim_char]` pair.

## Configuration Hooks

Four mutable attributes control what the generated source code looks like:

| Attribute | Default | Purpose |
|-----------|---------|---------|
| `put_cmd` | `'print'` | Command used to output a literal text segment |
| `insert_cmd` | `'print'` | Command used to output a Ruby expression result |
| `pre_cmd` | `[]` | Array of Ruby statements prepended to the compiled output |
| `post_cmd` | `[]` | Array of Ruby statements appended to the compiled output |

When `ERB.new` calls `set_eoutvar`, it reconfigures all four to accumulate output into a string variable (`_erbout` by default) rather than printing it:

```ruby
compiler.put_cmd    = "_erbout.<<"
compiler.insert_cmd = "_erbout.<<"
compiler.pre_cmd    = ["_erbout = +''"]
compiler.post_cmd   = ["_erbout"]
```

Code that uses `ERB::Compiler` directly (bypassing `ERB.new`) will get the `print`-based defaults unless it sets these attributes explicitly.

## Compile Method

```ruby
compiler.compile(template_string) #=> [ruby_source, encoding, frozen_string_literal]
```

Returns a three-element array: the generated Ruby source string, the encoding (from magic comment or the template string's own encoding), and the frozen-string-literal flag (from magic comment or `nil`).

The method:
1. Converts the input to its byte representation (`String#b`) for safe scanning
2. Calls `detect_magic_comment` to extract encoding and frozen-string-literal directives
3. Creates a `Buffer` pre-populated with the `pre_cmd` statements and an optional `#coding:` directive
4. Runs the chosen `Scanner` over the template, dispatching each token to `compile_stag` or `compile_etag`
5. Closes the buffer (appending `post_cmd`) and returns `[script, encoding, frozen]`

## Scanner Hierarchy

The scanner (lexer) is responsible for splitting the template into tokens. `ERB::Compiler` maintains a registry (`Scanner.register_scanner`) mapping `[trim_mode, percent_mode]` pairs to scanner classes.

### TrimScanner

The default scanner (registered as the fallback via `Scanner.default_scanner = TrimScanner`). Uses Ruby regex scanning with mode-specific patterns:

- **`nil` / no trim** — baseline regex that identifies stags and etags
- **`'>'` mode** — `%>\n` is consumed as `%>` followed by a carriage-return token
- **`'<>'` mode** — carriage-return suppression applies only when the line starts with an ERB tag
- **`'-'` mode** — explicit trim with `<%-` and `-%>` markers for per-tag newline control

When percent-mode is active (`%` in `trim_mode`), `TrimScanner` processes each line independently, intercepting lines whose first character is `%` and yielding them as `PercentLine` objects.

### SimpleScanner

Registered for `[nil, false]` (no trim mode, no percent). Uses Ruby's `StringScanner` (from the `strscan` standard library) for forward-scan tokenization. Slightly faster than the regex approach for simple templates.

### ExplicitScanner

Registered for `['-', false]`. Uses `StringScanner` with patterns that recognize the explicit-trim markers (`<%-`, `-%>`).

The scanner selection is transparent to callers; `make_scanner` picks the appropriate class from the registry.

## Buffer

`ERB::Compiler::Buffer` accumulates the generated Ruby source. It collects statements in a line buffer (`@line`) and flushes them as semicolon-joined statements when a newline boundary is reached. This produces compact single-logical-line output that preserves line numbers for error reporting.

```ruby
Buffer#push(cmd)   # add a statement to the current line
Buffer#cr          # flush current line to @script, append "\n"
Buffer#close       # flush + append post_cmd
Buffer#script      # return the accumulated source string
```

## Compile State Machine

The compiler runs a simple state machine over the token stream from the scanner. The scanner's `@stag` attribute tracks whether the compiler is currently inside a tag:

- When `stag` is `nil`: `compile_stag` dispatches on the token type
  - Literal text accumulates in `self.content`
  - `<%`, `<%=`, `<%#` set `scanner.stag` and flush accumulated content
  - `\n` terminates a content line and calls `add_put_cmd`
  - `<%%` is an escaped `<%` that becomes literal text
- When `stag` is set: `compile_etag` dispatches on the closing token
  - `%>` calls `compile_content` which handles the current tag type
  - `%%>` is an escaped `%>` that becomes literal text

`compile_content` differentiates the three active tag types:
- `<%` — raw code: pushed directly to the buffer, with newline handling for trailing newlines
- `<%=` — expression: wrapped with `add_insert_cmd` (adds `.to_s` conversion)
- `<%#` — comment: replaced with blank lines to preserve line count

## Magic Comment Detection

`detect_magic_comment` scans the beginning of the template for ERB comment tags (`<%# ... %>` or `%# ...`) that contain Emacs-style `coding:` or `frozen-string-literal:` directives. These directives influence the `#coding:` and `#frozen-string-literal:` annotations at the top of the generated source, which Ruby's parser then reads during `eval`.
