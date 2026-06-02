# Selector language

The selector language is what makes Dasel uniform across formats. It is parsed once and evaluated against the in-memory value tree, so the same expression behaves identically whether the source bytes were JSON, YAML, TOML, or XML. The implementation is split across three packages — `selector/lexer`, `selector/ast`, and `selector/parser` — with a one-line entry point in `selector/parser.go`:

```go
func Parse(selector string) (ast.Expr, error) {
    tokens, err := lexer.NewTokenizer(selector).Tokenize()
    if err != nil { return nil, err }
    return parser.NewParser(tokens).Parse()
}
```

## Lexer

`selector/lexer/token.go` defines the token alphabet. The set covers structural punctuation (`.`, `,`, `:`, `[`, `]`, `{`, `}`, `(`, `)`, `;`), comparison and arithmetic operators (`==`, `!=`, `=`, `=~`, `!~`, `>`, `>=`, `<`, `<=`, `+`, `-`, `*`, `/`, `%`, `++`, `--`, `+=`, `-=`), logical operators (`and`, `or`, `!`), variable and group markers (`$`, dollar-prefixed identifiers), literals (`String`, `Number`, `Bool`, `Null`), control-flow keywords (`if`, `else`, `elseif`), traversal forms (`Dot`, `RecursiveDescent` (`..`), `Spread` (`...`), `Branch`), and collection-shaping keywords (`map`, `each`, `filter`, `search`, `sortBy`, `asc`, `desc`).

`selector/lexer/tokenize.go` walks the source rune by rune, skipping whitespace and `//`-style comments. Multi-character operators are recognized by peeking ahead; for example, three dots produce a `Spread` token, two produce `RecursiveDescent`, one produces `Dot`. The tokenizer emits typed errors (`UnexpectedTokenError`, `UnexpectedEOFError`) carrying the offending rune and position.

## AST

`selector/ast/ast.go` defines the `Expr` interface plus small helpers (`IsType`, `AsType`, `Last`, `RemoveLast`, `ChainExprs`). `selector/ast/expression_complex.go` and `expression_literal.go` enumerate the concrete expression kinds:

- Literal nodes: `StringExpr`, `NumberIntExpr`, `NumberFloatExpr`, `BoolExpr`, `NullExpr`, `RegexExpr`.
- Compound expressions: `BinaryExpr`, `UnaryExpr`, `CallExpr`, `ChainedExpr`, `ArrayExpr`, `ObjectExpr`, `KeyValue`.
- Traversal: `PropertyExpr`, `IndexExpr`, `RangeExpr`, `SpreadExpr`, `RecursiveDescentExpr`.
- Variable reference: `VariableExpr`.
- Higher-order forms: `MapExpr`, `EachExpr`, `FilterExpr`, `SearchExpr`, `SortByExpr`, `ConditionalExpr`, `BranchExpr`.

`ChainedExpr` is the workhorse for dot-separated traversals; `ChainExprs` collapses a single-element chain back to that element so the AST stays tidy.

## Parser

`selector/parser/parser.go` is a Pratt-style top-down parser with binding powers defined in `denotations.go`. `Parse` calls `parseExpressions`, splitting on semicolons (statement separators) and stopping at EOF. `parseExpression` first handles right-denotation tokens (unary prefix operators), then dispatches on the current token kind to a per-form helper — `parseStringLiteral`, `parseSymbol`, `parseArray`, `parseObject`, `parseGroup`, `parseIf`, `parseMap`, `parseEach`, `parseFilter`, `parseSearch`, `parseRecursiveDescent`, `parseSortBy`, and so on (each in its own `parse_*.go` file).

After producing the left-hand expression, the parser scans for chained dot-traversals (`a.b.c`), spread continuations, and any left-denotation operator whose binding power exceeds the caller's. `parser_binary.go` turns left-denotation tokens into `BinaryExpr` nodes, giving the language standard precedence for comparison, arithmetic, and logical operators.

The parser exposes a tiny surface (`hasToken`, `current`, `advance`, `peek`, `expect`) so the per-form helpers can stay focused on the grammar of their own construct.
