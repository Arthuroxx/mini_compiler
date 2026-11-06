# mini_compiler

[![CI](https://github.com/Arthuroxx/mini_compiler/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/Arthuroxx/mini_compiler/actions/workflows/ci.yml)

A compiler simulator built in Python 3.10+ for the Compilers course.

## Structure

- `src/mini_compiler/`: compiler modules and command-line entry point.
- `examples/`: sample programs for valid and failing compilations.
- `tests/`: pytest tests.

## Requirements

- Python 3.10 or higher.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

Development dependencies include pytest, ruff, and mypy.

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

The command prints the tokens, annotated AST, symbol table, errors when present,
and generated three-address code. It exits with `0` on success, `1` when a
compiler phase reports errors, and `2` when the input file cannot be read.

### Sample programs

| Program | Stops after | Exit code |
| --- | --- | --- |
| `examples/valid.mc` | TAC generation | `0` |
| `examples/lexical_error.mc` | Lexical analysis | `1` |
| `examples/syntactic_error.mc` | Parsing | `1` |
| `examples/semantic_error.mc` | Semantic analysis | `1` |

### Real output

Abridged output for `examples/valid.mc` (token and AST sections are shortened
with `...`; the symbol table and TAC are complete):

```text
=== Tokens ===
KEYWORD 'int' (2:1)
ID 'a' (2:5)
OPERATOR '=' (2:7)
INT '2' (2:9)
DELIMITER ';' (2:10)
...
EOF '' (17:1)

=== AST ===
Program(statements=(VarDecl(name='a',
                            var_type='int',
                            value=Literal(value=2, line=2, column=9, type_name='int'),
                            line=2,
                            column=1),
...
=== Symbol Table ===
global:
  a: int (2:1)
  b: int (3:1)
  ratio: float (4:1)
  x: int (5:1)
  y: float (6:1)

=== TAC ===
a = 2
b = 3
t1 = int2float 1
ratio = t1
t2 = b * 5
t3 = a + t2
x = t3
t4 = int2float x
t5 = t4 + ratio
y = t5
t6 = x >= 10
ifFalse t6 goto L1
t7 = x - 1
x = t7
goto L2
L1:
x = 0
L2:
L3:
t8 = x >= 0
ifFalse t8 goto L4
t9 = x - 1
x = t9
goto L3
L4:
```

Output for `examples/lexical_error.mc`:

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

Output for `examples/syntactic_error.mc`:

```text
=== Tokens ===
KEYWORD 'int' (2:1)
ID 'x' (2:5)
OPERATOR '=' (2:7)
DELIMITER ';' (2:9)
EOF '' (3:1)

=== AST ===
Program(statements=(), line=2, column=1)

=== Errors ===
2:9: Expected expression, got ';'
```

Output for `examples/semantic_error.mc`:

```text
=== Tokens ===
KEYWORD 'int' (2:1)
ID 'x' (2:5)
OPERATOR '=' (2:7)
ID 'missing' (2:9)
OPERATOR '+' (2:17)
INT '1' (2:19)
DELIMITER ';' (2:20)
EOF '' (3:1)

=== AST ===
Program(statements=(VarDecl(name='x',
                            var_type='int',
                            value=BinaryOp(left=Identifier(name='missing',
                                                           line=2,
                                                           column=9,
                                                           type_name='error'),
                                           operator='+',
                                           right=Literal(value=1,
                                                         line=2,
                                                         column=19,
                                                         type_name='int'),
                                           line=2,
                                           column=9,
                                           type_name='error'),
                            line=2,
                            column=1),),
        line=2,
        column=1)

=== Symbol Table ===
global:
  x: int (2:1)

=== Errors ===
2:9: Undefined variable 'missing'
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
