# ERB Architecture and Design Philosophy

ERB is a Ruby templating library that embeds Ruby code directly inside plain-text documents. It occupies a well-defined niche: rather than defining a separate template language, it lets the full Ruby language serve as the templating language, leveraging Ruby's existing syntax, binding model, and object system.

## Core Design Philosophy

ERB operates on a compile-then-evaluate model. When a template string is passed to `ERB.new`, the library immediately compiles it into a Ruby source string (accessible via `ERB#src`). Evaluation happens later when `ERB#result` is called with a binding. This separation means the compiled code can be inspected, stored, or reused without repeating the compilation step.

The design places no constraint on what the output format is. ERB templates may produce HTML, plain text, configuration files, email bodies, or any other text artifact. The library makes no assumptions about output format; it simply concatenates literal text fragments and Ruby expression results into a string.

## Module and File Layout

```
lib/
  erb.rb              # Main ERB class, public API surface
  erb/
    compiler.rb       # ERB::Compiler — template-to-Ruby-code translation
    util.rb           # ERB::Util and ERB::Escape — output encoding helpers
    def_method.rb     # ERB::DefMethod — convenience mixin for class integration
    version.rb        # VERSION constant
ext/
  erb/escape/
    escape.c          # Native C extension for html_escape (MRI/CRuby)
    extconf.rb        # mkmf build configuration
libexec/
  erb                 # Standalone command-line tool (ERB::Main)
```

The gem declares `lib` as its require path. Requiring `'erb'` pulls in all submodules in dependency order: version, compiler, def_method, and util.

## Subsystems and Their Relationships

Five principal subsystems collaborate in every rendering pipeline:

1. **ERB class** (`lib/erb.rb`) — The public entry point. Holds the compiled source, filename/lineno metadata, and the output-variable configuration. Acts as the coordinator between the compiler and the evaluator.

2. **Compiler** (`lib/erb/compiler.rb`) — Translates a template string into Ruby source code. Contains the Scanner hierarchy (lexer) and Buffer (code accumulator). Exposes hooks (`put_cmd`, `insert_cmd`, `pre_cmd`, `post_cmd`) that control the shape of generated code.

3. **Escape and Util** (`lib/erb/util.rb`, `ext/erb/escape/escape.c`) — Output-encoding helpers used within templates. Two layers: a fast C extension for ASCII-compatible inputs and a Ruby fallback via `CGI.escapeHTML`.

4. **DefMethod** (`lib/erb/def_method.rb`) — An optional mixin that lets classes compile templates into instance methods at class-definition time.

5. **CLI** (`libexec/erb`) — A standalone command-line program that exposes ERB rendering with flag-based configuration. Uses the same `ERB` class as the library API.

## Data Flow

```
Template string
    │
    ▼
ERB::Compiler#compile
    ├── Scanner: lexes into tokens (literal text, stags, etags, percent-lines)
    └── Buffer: assembles tokens into Ruby source lines
    │
    ▼
Ruby source string (ERB#src)
    │
    ▼
Kernel#eval  ←── Binding (caller-supplied or toplevel)
    │
    ▼
Rendered output string
```

The produced Ruby source, when evaluated, populates a mutable string variable (the output variable, default `_erbout`), appending each literal text segment and each expression result in order. The final value of that variable is the template result.

## Binding Model

ERB does not own or manage variable scope. The caller supplies a `Binding` object — the Ruby mechanism for capturing a local variable environment — and `eval` runs the compiled template in that context. This design allows templates to resolve any name that is visible in the caller's scope without any explicit "context object" indirection.

Three convenience paths exist for producing a binding:

- `ERB#result(b)` — caller passes an explicit binding
- `ERB#result_with_hash(hash)` — the library creates a near-toplevel binding and populates it from a hash of name-value pairs
- `ERB#run(b)` — like `result` but prints to stdout instead of returning

When no binding is supplied, `ERB#new_toplevel` duplicates `TOPLEVEL_BINDING`, giving each render a fresh top-level scope.

## Character Encoding

ERB propagates encoding information from the template string into the generated Ruby source via a `#coding:` magic comment at the top of the output. If the template contains an in-template magic comment (`<%# -*- coding: Big5 -*- %>`), the compiler detects it and overrides the encoding annotation. The result string carries the encoding of its source template (or the override), matching the rest of Ruby's string encoding model.

## Extension and Customization Surface

ERB was designed with customization hooks built directly into the compiler:

- `ERB::Compiler#put_cmd` / `insert_cmd` — control how literal text and expression results are appended to the output variable
- `ERB::Compiler#pre_cmd` / `post_cmd` — inject code at the start and end of the compiled source, used for initializing and returning the output variable
- `ERB#make_compiler(trim_mode)` — a factory method that subclasses can override to supply a custom compiler

The `ERB::Scanner` registry (`Scanner.register_scanner`) allows alternative scanner implementations to be registered for specific trim-mode and percent-mode combinations, enabling specialized tokenization strategies without changing the compiler core.
