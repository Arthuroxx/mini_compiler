# Compiler Walkthrough

This walkthrough follows one program through every compiler phase and then
shows one failing example per phase. Every output below comes from a real run
of the commands shown. The default renderer uses [Rich](https://rich.readthedocs.io/)
tables and trees; pass `--plain` to reproduce the original plain-text format.

Run the commands from the repository root after installing the development
dependencies:

```bash
pip install -e ".[dev]"
```

## Example program

The walkthrough uses `examples/walkthrough.mc`:

```c
int a = 2;
int b = 3;
int x = a + b * 5;
float ratio = x;

if (x >= 10) {
    ratio = ratio + 1.5;
}

while (x >= 0) {
    x = x - 1;
}
```

Compile it with:

```bash
python -m mini_compiler examples/walkthrough.mc
```

The process exits with code `0` because every phase completes. The default
run prints the five sections shown below in a single pass; each section can
also be rendered on its own with `--phase`.

## 1. Lexical analysis

The lexer scans the source and emits tokens with 1-based line and column
positions. Comments and whitespace are ignored. Render only this phase with:

```bash
python -m mini_compiler examples/walkthrough.mc --phase tokens
```

```text
Tokens
+--------------------------------+
| Type      | Value   | Position |
|-----------+---------+----------|
| KEYWORD   | 'int'   |      1:1 |
| ID        | 'a'     |      1:5 |
| OPERATOR  | '='     |      1:7 |
| INT       | '2'     |      1:9 |
| DELIMITER | ';'     |     1:10 |
| KEYWORD   | 'int'   |      2:1 |
| ID        | 'b'     |      2:5 |
| OPERATOR  | '='     |      2:7 |
| INT       | '3'     |      2:9 |
| DELIMITER | ';'     |     2:10 |
| KEYWORD   | 'int'   |      3:1 |
| ID        | 'x'     |      3:5 |
| OPERATOR  | '='     |      3:7 |
| ID        | 'a'     |      3:9 |
| OPERATOR  | '+'     |     3:11 |
| ID        | 'b'     |     3:13 |
| OPERATOR  | '*'     |     3:15 |
| INT       | '5'     |     3:17 |
| DELIMITER | ';'     |     3:18 |
| KEYWORD   | 'float' |      4:1 |
| ID        | 'ratio' |      4:7 |
| OPERATOR  | '='     |     4:13 |
| ID        | 'x'     |     4:15 |
| DELIMITER | ';'     |     4:16 |
| KEYWORD   | 'if'    |      6:1 |
| DELIMITER | '('     |      6:4 |
| ID        | 'x'     |      6:5 |
| OPERATOR  | '>='    |      6:7 |
| INT       | '10'    |     6:10 |
| DELIMITER | ')'     |     6:12 |
| DELIMITER | '{'     |     6:14 |
| ID        | 'ratio' |      7:5 |
| OPERATOR  | '='     |     7:11 |
| ID        | 'ratio' |     7:13 |
| OPERATOR  | '+'     |     7:19 |
| FLOAT     | '1.5'   |     7:21 |
| DELIMITER | ';'     |     7:24 |
| DELIMITER | '}'     |      8:1 |
| KEYWORD   | 'while' |     10:1 |
| DELIMITER | '('     |     10:7 |
| ID        | 'x'     |     10:8 |
| OPERATOR  | '>='    |    10:10 |
| INT       | '0'     |    10:13 |
| DELIMITER | ')'     |    10:14 |
| DELIMITER | '{'     |    10:16 |
| ID        | 'x'     |     11:5 |
| OPERATOR  | '='     |     11:7 |
| ID        | 'x'     |     11:9 |
| OPERATOR  | '-'     |    11:11 |
| INT       | '1'     |    11:13 |
| DELIMITER | ';'     |    11:14 |
| DELIMITER | '}'     |     12:1 |
| EOF       | ''      |     13:1 |
+--------------------------------+
```

## 2. Parsing and AST

The recursive descent parser builds the immutable AST. Binary operators are
nested according to the precedence table, so multiplication is below addition
in the tree. The Rich tree shows only node names and operators or values; line
and column information stays out of the way.

```bash
python -m mini_compiler examples/walkthrough.mc --phase ast
```

```text
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
```

The `--phase ast` output is 23 lines, staying under the 25-line target. The
same tree can be printed with Unicode guides on terminals that support them.

## 3. Symbol table

The semantic analyzer populates the symbol table while it walks the AST.
Declarations record their name, type, and source position. Nested block scopes
are entered and left during the walk; the CLI prints the scopes that remain
active at the end of compilation.

```bash
python -m mini_compiler examples/walkthrough.mc --phase symbols
```

```text
Symbols
+-----------------------------------+
| Scope  | Name  | Type  | Position |
|--------+-------+-------+----------|
| global | a     | int   |      1:1 |
| global | b     | int   |      2:1 |
| global | x     | int   |      3:1 |
| global | ratio | float |      4:1 |
+-----------------------------------+
```

## 4. Semantic analysis

`SemanticAnalyzer` checks declarations, assignments, conditions, and operators.
It also annotates every expression with a `type_name`. In the AST above, for
example, the multiplication is `int` and each comparison is `bool`. Assigning
the `int` value of `x` to the `float` variable `ratio` is accepted because
`int` is implicitly compatible with `float`; the conversion becomes explicit
in TAC as `int2float`. No separate semantic section is printed when analysis
succeeds.

## 5. Three-address code

After semantic analysis succeeds, `TACGenerator` lowers the annotated AST to
three-address code. The output includes temporaries, labels, jumps, and the
`int2float` conversion. Labels are highlighted in the terminal.

```bash
python -m mini_compiler examples/walkthrough.mc --phase tac
```

```text
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

## 6. Target code

After TAC generation, `AssemblyGenerator` lowers the instructions to a small
assembly language. Variables live in memory (`[name]`), temporaries are held in
`R0`-`R2`, comparisons materialize `0`/`1`, and labels are highlighted in the
terminal.

```bash
python -m mini_compiler examples/walkthrough.mc --phase asm
```

```text
ASM
MOV [a], 2
MOV [b], 3
MOV R0, [b]
MUL R0, 5
MOV R1, [a]
ADD R1, R0
MOV [x], R1
INT2FLOAT R0, [x]
MOV [ratio], R0
MOV R0, [x]
CMP R0, 10
MOV R0, 1
JGE Lcmp1
MOV R0, 0
Lcmp1:
CMP R0, 0
JZ L1
MOV R0, [ratio]
ADD R0, 1.5
MOV [ratio], R0
L1:
L2:
MOV R0, [x]
CMP R0, 0
MOV R0, 1
JGE Lcmp2
MOV R0, 0
Lcmp2:
CMP R0, 0
JZ L3
MOV R0, [x]
SUB R0, 1
MOV [x], R0
JMP L2
L3:
```

The allocator computes liveness for every temporary. When a fourth temporary is
live at the same time, one is spilled to the stack starting at `0x2000`:

```bash
python -m mini_compiler examples/spill.mc --phase asm
```

```text
ASM
MOV [a], 1
MOV [b], 2
MOV [c], 3
MOV [d], 4
MOV [e], 5
MOV [f], 6
MOV [g], 7
MOV [h], 8
MOV R0, [a]
ADD R0, [b]
MOV R1, [c]
ADD R1, [d]
MOV R2, [e]
ADD R2, [f]
STORE R0, [0x2000]
MOV R0, [g]
ADD R0, [h]
ADD R2, R0
MOV R0, R1
ADD R0, R2
LOAD R1, [0x2000]
MOV R2, R1
ADD R2, R0
MOV [x], R2
```

`examples/spill.mc` keeps four temporaries alive at once, so `STORE R0,
[0x2000]` frees a register and `LOAD R1, [0x2000]` restores it later.

## Error examples

The pipeline stops at the first phase that reports errors. The remaining
phases do not run, and diagnostics are printed in red. Every error example
below still passes through the phases that completed successfully.

### Lexical error

`examples/lexical_error.mc` contains an invalid character:

```c
// Lexical error: '@' is not a valid token.
int x = 1 @ 2;
```

```bash
python -m mini_compiler examples/lexical_error.mc
```

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

The pipeline reports `2:11: Unexpected character '@'` and does not parse the
program. Asking for a later phase shows that it was not produced:

```bash
python -m mini_compiler examples/lexical_error.mc --phase tac
```

```text
TAC
<not generated>

Errors
2:11: Unexpected character '@'
```

### Syntax error

`examples/syntactic_error.mc` is missing the initializer expression:

```c
// Syntactic error: the declaration is missing an initializer expression.
int x = ;
```

```bash
python -m mini_compiler examples/syntactic_error.mc
```

```text
Tokens
+------------------------------+
| Type      | Value | Position |
|-----------+-------+----------|
| KEYWORD   | 'int' |      2:1 |
| ID        | 'x'   |      2:5 |
| OPERATOR  | '='   |      2:7 |
| DELIMITER | ';'   |      2:9 |
| EOF       | ''    |      3:1 |
+------------------------------+

AST
Program

Errors
2:9: Expected expression, got ';'
```

The parser recovers at the semicolon, produces an empty statement list, and
reports `2:9: Expected expression, got ';'`.

### Symbol table error

`examples/semantic_error.mc` refers to an undeclared name:

```c
// Semantic error: 'missing' has not been declared.
int x = missing + 1;
```

```bash
python -m mini_compiler examples/semantic_error.mc
```

```text
Tokens
+----------------------------------+
| Type      | Value     | Position |
|-----------+-----------+----------|
| KEYWORD   | 'int'     |      2:1 |
| ID        | 'x'       |      2:5 |
| OPERATOR  | '='       |      2:7 |
| ID        | 'missing' |      2:9 |
| OPERATOR  | '+'       |     2:17 |
| INT       | '1'       |     2:19 |
| DELIMITER | ';'       |     2:20 |
| EOF       | ''        |      3:1 |
+----------------------------------+

AST
Program
`-- VarDecl x: int
    `-- BinaryOp +
        +-- Identifier missing
        `-- Literal 1

Symbols
+---------------------------------+
| Scope  | Name | Type | Position |
|--------+------+------+----------|
| global | x    | int  |      2:1 |
+---------------------------------+

Errors
2:9: Undefined variable 'missing'
```

The lookup fails with `2:9: Undefined variable 'missing'`. The declaration of
`x` is still recorded in the global scope.

### Semantic type error

`examples/type_error.mc` uses a string operand in arithmetic:

```c
int x = "text" * 2;
```

```bash
python -m mini_compiler examples/type_error.mc
```

```text
Tokens
+---------------------------------+
| Type      | Value    | Position |
|-----------+----------+----------|
| KEYWORD   | 'int'    |      1:1 |
| ID        | 'x'      |      1:5 |
| OPERATOR  | '='      |      1:7 |
| STRING    | '"text"' |      1:9 |
| OPERATOR  | '*'      |     1:16 |
| INT       | '2'      |     1:18 |
| DELIMITER | ';'      |     1:19 |
| EOF       | ''       |      2:1 |
+---------------------------------+

AST
Program
`-- VarDecl x: int
    `-- BinaryOp *
        +-- Literal 'text'
        `-- Literal 2

Symbols
+---------------------------------+
| Scope  | Name | Type | Position |
|--------+------+------+----------|
| global | x    | int  |      1:1 |
+---------------------------------+

Errors
1:9: Operator '*' requires numeric operands, got 'string' and 'int'
```

The analyzer reports `1:9: Operator '*' requires numeric operands, got
'string' and 'int'` and marks the expression type as `error`.

### Target code after an earlier error

The TAC and assembly generators have no diagnostics of their own. They run only
after semantic analysis succeeds, so no instructions are emitted when an
earlier phase fails. This can be observed through the compiler API:

```bash
python -c "from pathlib import Path; from mini_compiler.compiler import compile_source; result = compile_source(Path('examples/type_error.mc').read_text(encoding='utf-8')); print('failed_phase:', result.failed_phase); print('tac:', result.tac); print('asm:', result.asm)"
```

```text
failed_phase: semantic
tac: ()
asm: ()
```

The pipeline stops before code generation, so neither TAC nor assembly is
emitted for this program.

## Plain output

The original renderer is still available. Use `--plain` to print
`=== Phase ===` headers, one token per line, and the full dataclass
representation of the AST:

```bash
python -m mini_compiler examples/walkthrough.mc --plain
```

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
...

=== ASM ===
MOV [a], 2
MOV [b], 3
...
```
