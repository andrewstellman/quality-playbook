# ERB Public API

This document describes the public methods and constants of the `ERB` class, `ERB::Compiler`, `ERB::Util`, `ERB::Escape`, and `ERB::DefMethod`. All of these are defined in `lib/erb.rb`, `lib/erb/compiler.rb`, `lib/erb/util.rb`, and `lib/erb/def_method.rb`.

## ERB Class

### Constructor

```ruby
ERB.new(str, trim_mode: nil, eoutvar: '_erbout')
```

Compiles the template string `str` and stores the result. `trim_mode` controls whitespace handling (see below). `eoutvar` sets the name of the output accumulator variable in the generated code.

The positional-argument form of `safe_level`, `trim_mode`, and `eoutvar` (previously the 2nd, 3rd, and 4th arguments) is deprecated; keyword arguments are preferred.

#### trim_mode values

| Value | Effect |
|-------|--------|
| `nil` or omitted | No trimming |
| `'%'` | Lines beginning with `%` are treated as Ruby code |
| `'>'` | Suppress trailing newline for lines ending in `%>` |
| `'<>'` | Suppress trailing newline for lines that start with `<%` and end with `%>` |
| `'-'` | Suppress trailing newline for `-%>` tags |
| Combinations | e.g. `'%<>'` enables both `%`-lines and `<>` newline trimming |

### Class Methods

```ruby
ERB.version  #=> "4.0.3"
```

Returns the library version string.

### Instance Attributes

```ruby
erb.src       # String — the compiled Ruby source code (read-only)
erb.encoding  # Encoding — the encoding to use when evaluating src (read-only)
erb.filename  # String or nil — file name used in eval and error messages (read-write)
erb.lineno    # Integer — line offset used in eval (read-write)
```

### Setting Location

```ruby
erb.location = ['path/to/template.erb', 3]
```

Sets both `filename` and `lineno` in one call. Subsequent errors from `result` will reference the given location.

### Rendering

```ruby
erb.result(binding)          #=> String
erb.result                   #=> String  (uses near-toplevel binding)
erb.result_with_hash(hash)   #=> String
erb.run(binding)             # prints to stdout
erb.run                      # prints to stdout (uses near-toplevel binding)
```

`result` evaluates the compiled source in the given binding and returns the output string. `result_with_hash` creates a near-toplevel binding and sets local variables from the supplied hash before rendering. `run` is equivalent to `print result(binding)`.

### Compiler Factory

```ruby
erb.make_compiler(trim_mode)  #=> ERB::Compiler instance
```

Called internally during `ERB.new`. Subclasses can override this to supply a custom compiler.

### Output Variable Configuration

```ruby
erb.set_eoutvar(compiler, eoutvar = '_erbout')
```

Configures the compiler's `put_cmd`, `insert_cmd`, `pre_cmd`, and `post_cmd` so that output accumulates into the named variable. This is called by `ERB.new` and is available for callers who construct a compiler directly.

### Defining Methods from Templates

```ruby
erb.def_method(mod, methodname, fname = '(ERB)')
erb.def_module(methodname = 'erb')          #=> Module
erb.def_class(superklass = Object, methodname = 'result')  #=> Class
```

These methods compile the template into a named method on an existing module or class, or create a new anonymous module or class containing the method. The compiled method, when called, renders the template in the receiver's context (its instance variables and methods are accessible inside the template).

## ERB::Compiler

### Constructor

```ruby
ERB::Compiler.new(trim_mode)
```

### Attributes

```ruby
compiler.percent     # Boolean — whether %-line processing is active (read-only)
compiler.trim_mode   # String or nil — resolved trim mode character (read-only)
compiler.put_cmd     # String — output command for literal text (read-write)
compiler.insert_cmd  # String — output command for expressions (read-write)
compiler.pre_cmd     # Array of String — statements at start of output (read-write)
compiler.post_cmd    # Array of String — statements at end of output (read-write)
```

### Primary Method

```ruby
compiler.compile(template_string)  #=> [ruby_source, encoding, frozen_string_literal]
```

Returns the generated Ruby source, the encoding, and the frozen-string-literal flag.

## ERB::Util

`ERB::Util` is a module of helper functions intended for inclusion inside templates or in view-layer code.

```ruby
include ERB::Util

html_escape(str)   #=> String  (alias: h)
url_encode(str)    #=> String  (alias: u)
```

`html_escape` converts `&`, `"`, `'`, `<`, and `>` to their HTML entity equivalents. `url_encode` percent-encodes a string for use in a URL component (delegates to `CGI.escapeURIComponent`).

Both methods are also available as module functions:

```ruby
ERB::Util.html_escape(str)
ERB::Util.url_encode(str)
ERB::Util.h(str)
ERB::Util.u(str)
```

## ERB::Escape

`ERB::Escape` is a separate module that provides `html_escape` without the risk of monkey-patching interference. `ERB::Util` includes `ERB::Escape` to inherit its implementation.

```ruby
ERB::Escape.html_escape(str)  #=> String
```

On MRI/CRuby, `ERB::Escape.html_escape` is backed by the native C extension (`ext/erb/escape/escape.c`). On JRuby and TruffleRuby (which do not build the C extension), it falls back to `CGI.escapeHTML`.

## ERB::DefMethod

`ERB::DefMethod` is a module mixin for classes that want to define rendering methods directly from ERB template files.

```ruby
class MyClass
  extend ERB::DefMethod
  def_erb_method('render()', 'template.rhtml')
end
```

```ruby
ERB::DefMethod.def_erb_method(methodname, erb_or_fname)
```

Accepts either a filename string (reads and compiles the file) or an existing `ERB` object. Defines a method named `methodname` as an instance method of the extending class.

## Version

```ruby
ERB::VERSION  #=> "4.0.3"
ERB.version   #=> "4.0.3"
```

`ERB::VERSION` is a private constant; `ERB.version` is the public accessor.

## Binding Contract

ERB places the following requirements on caller-supplied bindings passed to `result`:

- The binding must be a `Binding` object (the return value of `Kernel#binding` called in a scope where the desired local variables are defined)
- Local variables in the binding scope are accessible by name in the template
- Instance variables of the object that created the binding are accessible via `@name` syntax
- Methods of the object that created the binding are callable without an explicit receiver

The `result_with_hash` method provides a simpler alternative when the only data to pass is a flat set of named values; it eliminates the need to construct a binding manually.
