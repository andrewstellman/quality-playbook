# ERB Scanning — Lexical Analysis of Templates

Scanning is the first stage of ERB's compilation pipeline. The scanner reads a raw template string and produces a sequence of tokens that the compiler assembles into Ruby code. All scanner classes live inside `lib/erb/compiler.rb` under the `ERB::Compiler` namespace.

## Tag Vocabulary

ERB defines a fixed set of start tags (stags) and end tags (etags):

**Default start tags:**
```
<%%    — escaped literal <%
<%=    — expression tag
<%#    — comment tag
<%     — code tag
```

**Default end tags:**
```
%%>    — escaped literal %>
%>     — closes any open stag
```

All other text is literal content and passes through unchanged.

## Scanner Registry

`ERB::Compiler::Scanner` maintains a class-level hash (`@scanner_map`) keyed by `[trim_mode, percent_mode]` pairs. The factory method `Scanner.make_scanner(src, trim_mode, percent)` looks up the appropriate class in the registry and falls back to `@default_scanner` (which is `TrimScanner`) if no specific class is registered for the requested combination.

New scanner classes can be registered with `Scanner.register_scanner(klass, trim_mode, percent)`. The alias `regist_scanner` is retained for compatibility.

## TrimScanner

`TrimScanner` is the default, pure-Ruby scanner. It handles all trim modes and percent mode via a combination of line-iteration and regex scanning.

### Initialization

At construction time, `TrimScanner#initialize` selects one of four scanning strategies based on `trim_mode`:

| Trim mode | Scan regex pattern | Line handler method |
|-----------|--------------------|---------------------|
| `nil` | Matches stags, etags, `\n`, `\z` | `scan_line` |
| `'>'` | Matches `%>\r?\n` as a unit, plus stags, etags, `\n`, `\z` | `trim_line1` |
| `'<>'` | Same pattern as `'>'` | `trim_line2` |
| `'-'` | Matches `<%-`, `-%>\r?\n`, `-%>`, plus stags, etags, `\z` | `explicit_trim_line` |

### Percent Mode

When `percent` is `true` (from `%` in `trim_mode`), `TrimScanner#scan` iterates the source line by line and calls `percent_line` for each. `percent_line` intercepts lines whose first character is `%`:

- A line starting with `%%` has the first `%` stripped and is passed to the normal scanner (producing a literal `%` in output)
- A line starting with `%` followed by any other character is yielded as a `PercentLine` object

`PercentLine` is a simple value wrapper whose `to_s` returns the line content without the leading `%`.

### Trim Line Behaviors

**`scan_line` (no trim):** Scans with the regex, yielding each non-empty match token as-is.

**`trim_line1` (`>` mode):** When a `%>\n` or `%>\r\n` token is matched, emits `%>` followed by the `:cr` symbol. The `:cr` symbol is the signal to the compiler buffer to emit a newline without the trailing literal newline of the template line.

**`trim_line2` (`<>` mode):** Tracks the first token on each logical line (`head`). When a line-closing `%>\n` is encountered:
- If `head` was an ERB stag (`<%=`, `<%#`, or `<%`), emit `:cr` (suppress the newline)
- If `head` was literal text, emit a literal `\n` (preserve the newline)

This implements the "omit newline for lines starting with `<%` and ending in `%>`" contract.

**`explicit_trim_line` (`-` mode):** Converts `<%-` to `<%` and handles `-%>\n` or `-%>\r\n` by emitting `%>` followed by `:cr`, and `-%>` (without newline) by emitting just `%>`.

## SimpleScanner

`SimpleScanner` is registered for `[nil, false]` and uses Ruby's `StringScanner` (from `strscan`). It alternates between two regex patterns — one for scanning between stag occurrences, one for scanning between etag occurrences — advancing the scanner forward on each call. This avoids re-running the full regex over the entire input, making it more efficient for templates with many tags.

`SimpleScanner` is only loaded when `strscan` is available; `require 'strscan'` is attempted in a `rescue LoadError` block, and `TrimScanner` serves as the universal fallback.

## ExplicitScanner

`ExplicitScanner` is registered for `['-', false]` and also uses `StringScanner`. It expands the start-tag pattern to recognize `<%-` (consuming any leading whitespace before the `<%-`) and the end-tag pattern to recognize `-%>`. On matching `<%-`, it normalizes the token to `<%`; on matching `-%>`, it emits `%>` and then conditionally emits `:cr` if the next character is a newline.

## Token Types

Tokens yielded by any scanner fall into one of these categories:

| Token | Type | Meaning |
|-------|------|---------|
| `'<%'` | String | Opens a code block |
| `'<%='` | String | Opens an expression block |
| `'<%#'` | String | Opens a comment block |
| `'<%%'` | String | Escaped `<%` literal |
| `'%>'` | String | Closes the current block |
| `'%%>'` | String | Escaped `%>` literal |
| `"\n"` | String | Newline in literal content |
| `:cr` | Symbol | Suppress newline (trim signal) |
| `PercentLine` | Object | A `%`-prefixed line of code |
| Arbitrary text | String | Literal content to pass through |

The compiler's `compile_stag` and `compile_etag` methods dispatch on these token types.

## Interaction with the Compiler

The scanner does not build an AST or token list; it drives the compiler through a block interface. `Scanner#scan` yields one token at a time, and the compiler immediately processes each token in its state machine. This streaming design keeps memory use proportional to the output buffer size rather than the full token sequence length.
