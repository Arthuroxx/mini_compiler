# mini_compiler

[![CI](https://github.com/Arthuroxx/mini_compiler/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/Arthuroxx/mini_compiler/actions/workflows/ci.yml)

A compiler simulator built in Python 3.10+ for the Compilers course. The default
command-line output uses [Rich](https://rich.readthedocs.io/) tables and trees;
the original plain-text format remains available through `--plain`.

## Structure

- `src/mini_compiler/`: compiler modules and command-line entry point.
- `examples/`: sample programs for valid and failing compilations.
- `tests/`: pytest tests.

## Requirements

- Python 3.10 or higher.
- Rich 15.0 or higher, installed automatically as a runtime dependency.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Runtime dependencies include Rich. Development dependencies include pytest,
pytest-cov, ruff, and mypy.

## Pipeline

```text
source (.mc)
    |
    v
Lexer                 mini_compiler.lexer.Lexer
    | tokens
    v
Parser / AST          mini_compiler.parser.Parser
    | Program         mini_compiler.ast_nodes
    v
Symbol table          mini_compiler.symbols.SymbolTable
    | scopes/symbols  (used by the semantic analyzer)
    v
Semantic analyzer     mini_compiler.semantic.SemanticAnalyzer
    | annotated AST
    v
TAC generator         mini_compiler.ir.TACGenerator
    | instructions
    v
CLI / orchestration   mini_compiler.compiler.compile_source
                      mini_compiler.cli.main
```

The pipeline stops at the first phase that reports errors.

## Compiler phases

| Phase | What it does | Implementing class |
| --- | --- | --- |
| Lexical analysis | Converts source text into tokens and reports invalid characters, unterminated strings, and unterminated block comments. | `mini_compiler.lexer.Lexer` |
| Parsing and AST | Builds an immutable abstract syntax tree with a recursive descent parser and recovers from syntax errors at semicolons. | `mini_compiler.parser.Parser`, `mini_compiler.ast_nodes.Program` |
| Symbol table | Tracks declarations, nested scopes, shadowing, redeclarations, and unresolved names. | `mini_compiler.symbols.SymbolTable` |
| Semantic analysis | Type-checks declarations, assignments, conditions, and operators, and annotates expressions with their result types. | `mini_compiler.semantic.SemanticAnalyzer` |
| Three-address code | Generates TAC for assignments, arithmetic, comparisons, `if`/`else`, `while`, and `int`-to-`float` casts. | `mini_compiler.ir.TACGenerator` |

## Usage

Compile a source file with:

```bash
python -m mini_compiler examples/valid.mc
```

By default the command prints the tokens in a table, the annotated AST as a
tree, the symbol table, errors in red when present, and the generated
three-address code with highlighted labels. It exits with `0` on success, `1`
when a compiler phase reports errors, and `2` when the input file cannot be
read.

Use `--phase` to render a single phase, or `--plain` to keep the original
plain-text output:

```bash
python -m mini_compiler examples/walkthrough.mc --phase tokens
python -m mini_compiler examples/walkthrough.mc --phase ast
python -m mini_compiler examples/walkthrough.mc --phase symbols
python -m mini_compiler examples/walkthrough.mc --phase tac
python -m mini_compiler examples/walkthrough.mc --plain
```

`--phase` accepts `tokens`, `ast`, `symbols`, `tac`, or `all` (the default).

### Sample programs

| Program | Stops after | Exit code |
| --- | --- | --- |
| `examples/valid.mc` | TAC generation | `0` |
| `examples/walkthrough.mc` | TAC generation | `0` |
| `examples/lexical_error.mc` | Lexical analysis | `1` |
| `examples/syntactic_error.mc` | Parsing | `1` |
| `examples/semantic_error.mc` | Semantic analysis | `1` |
| `examples/type_error.mc` | Semantic analysis | `1` |

### Rich output

The default renderer prints a section title per phase, tokens in a three-column
table, the AST as a tree of nodes and operators, the symbol table, and TAC with
highlighted labels. Abridged output for `examples/walkthrough.mc` (the token
table is shortened with `...`; the AST, symbol table, and TAC are complete;
Rich draws Unicode box characters in terminals that support them):

```text
Tokens
+--------------------------------+
| Type      | Value   | Position |
|-----------+---------+----------|
| KEYWORD   | 'int'   |      1:1 |
| ID        | 'a'     |      1:5 |
...
| EOF       | ''      |     13:1 |
+--------------------------------+

AST
Program
+-- VarDecl a: int = 2
+-- VarDecl b: int = 3
+-- VarDecl x: int
|   `-- BinaryOp +
|       +-- Identifier a
|       `-- BinaryOp *
|           +-- Identifier b
|           `-- Literal 5
+-- VarDecl ratio: float = x
+-- If x >= 10
|   `-- then
|       `-- Assign ratio
|           `-- BinaryOp +
|               +-- Identifier ratio
|               `-- Literal 1.5
`-- While x >= 0
    `-- body
        `-- Assign x
            `-- BinaryOp -
                +-- Identifier x
                `-- Literal 1

Symbols
+-----------------------------------+
| Scope  | Name  | Type  | Position |
|--------+-------+-------+----------|
| global | a     | int   |      1:1 |
| global | b     | int   |      2:1 |
| global | x     | int   |      3:1 |
| global | ratio | float |      4:1 |
+-----------------------------------+

TAC
a = 2
b = 3
t1 = b * 5
t2 = a + t1
x = t2
t3 = int2float x
ratio = t3
t4 = x >= 10
ifFalse t4 goto L1
t5 = ratio + 1.5
ratio = t5
L1:
L2:
t6 = x >= 0
ifFalse t6 goto L3
t7 = x - 1
x = t7
goto L2
L3:
```

Errors are printed in red after the phases that ran successfully. Output for
`examples/lexical_error.mc`:

```text
Tokens
+------------------------------+
| Type      | Value | Position |
|-----------+-------+----------|
| KEYWORD   | 'int' |      2:1 |
| ID        | 'x'   |      2:5 |
| OPERATOR  | '='   |      2:7 |
| INT       | '1'   |      2:9 |
| INT       | '2'   |     2:13 |
| DELIMITER | ';'   |     2:14 |
| EOF       | ''    |      3:1 |
+------------------------------+

Errors
2:11: Unexpected character '@'
```

### Plain output

Pass `--plain` to keep the original plain-text format. It prints
`=== Phase ===` headers and the full dataclass representation of the AST:

```text
=== Tokens ===
KEYWORD 'int' (1:1)
ID 'a' (1:5)
OPERATOR '=' (1:7)
INT '2' (1:9)
DELIMITER ';' (1:10)
...

=== AST ===
Program(statements=(VarDecl(name='a',
                            var_type='int',
                            value=Literal(value=2, line=1, column=9, type_name='int'),
                            line=1,
                            column=1),
...

=== Symbol Table ===
global:
  a: int (1:1)
  b: int (2:1)
  x: int (3:1)
  ratio: float (4:1)

=== TAC ===
a = 2
b = 3
t1 = b * 5
t2 = a + t1
x = t2
...
```

Plain output for `examples/lexical_error.mc`:

```text
=== Tokens ===
KEYWORD 'int' (2:1)
ID 'x' (2:5)
OPERATOR '=' (2:7)
INT '1' (2:9)
INT '2' (2:13)
DELIMITER ';' (2:14)
EOF '' (3:1)

=== Errors ===
2:11: Unexpected character '@'
```

## Tests and quality checks

Run the test suite:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

Run strict type checking:

```bash
mypy .
```
