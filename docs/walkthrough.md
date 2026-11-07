# Compiler Walkthrough

This walkthrough follows one program through every compiler phase and then
shows one failing example per phase. Every output below comes from a real run
of the commands shown.

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

The process exits with code `0` because every phase completes.

## 1. Lexical analysis

The lexer scans the source and emits tokens with 1-based line and column
positions. Comments and whitespace are ignored.

```text
KEYWORD 'int' (1:1)
ID 'a' (1:5)
OPERATOR '=' (1:7)
INT '2' (1:9)
DELIMITER ';' (1:10)
KEYWORD 'int' (2:1)
ID 'b' (2:5)
OPERATOR '=' (2:7)
INT '3' (2:9)
DELIMITER ';' (2:10)
KEYWORD 'int' (3:1)
ID 'x' (3:5)
OPERATOR '=' (3:7)
ID 'a' (3:9)
OPERATOR '+' (3:11)
ID 'b' (3:13)
OPERATOR '*' (3:15)
INT '5' (3:17)
DELIMITER ';' (3:18)
KEYWORD 'float' (4:1)
ID 'ratio' (4:7)
OPERATOR '=' (4:13)
ID 'x' (4:15)
DELIMITER ';' (4:16)
KEYWORD 'if' (6:1)
DELIMITER '(' (6:4)
ID 'x' (6:5)
OPERATOR '>=' (6:7)
INT '10' (6:10)
DELIMITER ')' (6:12)
DELIMITER '{' (6:14)
ID 'ratio' (7:5)
OPERATOR '=' (7:11)
ID 'ratio' (7:13)
OPERATOR '+' (7:19)
FLOAT '1.5' (7:21)
DELIMITER ';' (7:24)
DELIMITER '}' (8:1)
KEYWORD 'while' (10:1)
DELIMITER '(' (10:7)
ID 'x' (10:8)
OPERATOR '>=' (10:10)
INT '0' (10:13)
DELIMITER ')' (10:14)
DELIMITER '{' (10:16)
ID 'x' (11:5)
OPERATOR '=' (11:7)
ID 'x' (11:9)
OPERATOR '-' (11:11)
INT '1' (11:13)
DELIMITER ';' (11:14)
DELIMITER '}' (12:1)
EOF '' (13:1)
```

## 2. Parsing and AST

The recursive descent parser builds the immutable AST. Binary operators are
nested according to the precedence table, so multiplication is below addition
in the tree. The output below is the `=== AST ===` section of the same run.

```text
Program(statements=(VarDecl(name='a',
                            var_type='int',
                            value=Literal(value=2, line=1, column=9, type_name='int'),
                            line=1,
                            column=1),
                    VarDecl(name='b',
                            var_type='int',
                            value=Literal(value=3, line=2, column=9, type_name='int'),
                            line=2,
                            column=1),
                    VarDecl(name='x',
                            var_type='int',
                            value=BinaryOp(left=Identifier(name='a',
                                                           line=3,
                                                           column=9,
                                                           type_name='int'),
                                           operator='+',
                                           right=BinaryOp(left=Identifier(name='b',
                                                                          line=3,
                                                                          column=13,
                                                                          type_name='int'),
                                                          operator='*',
                                                          right=Literal(value=5,
                                                                        line=3,
                                                                        column=17,
                                                                        type_name='int'),
                                                          line=3,
                                                          column=13,
                                                          type_name='int'),
                                           line=3,
                                           column=9,
                                           type_name='int'),
                            line=3,
                            column=1),
                    VarDecl(name='ratio',
                            var_type='float',
                            value=Identifier(name='x',
                                             line=4,
                                             column=15,
                                             type_name='int'),
                            line=4,
                            column=1),
                    If(condition=BinaryOp(left=Identifier(name='x',
                                                          line=6,
                                                          column=5,
                                                          type_name='int'),
                                          operator='>=',
                                          right=Literal(value=10,
                                                        line=6,
                                                        column=10,
                                                        type_name='int'),
                                          line=6,
                                          column=5,
                                          type_name='bool'),
                       then_branch=Block(statements=(Assign(name='ratio',
                                                            value=BinaryOp(left=Identifier(name='ratio',
                                                                                           line=7,
                                                                                           column=13,
                                                                                           type_name='float'),
                                                                           operator='+',
                                                                           right=Literal(value=1.5,
                                                                                         line=7,
                                                                                         column=21,
                                                                                         type_name='float'),
                                                                           line=7,
                                                                           column=13,
                                                                           type_name='float'),
                                                            line=7,
                                                            column=5),),
                                         line=6,
                                         column=14),
                       else_branch=None,
                       line=6,
                       column=1),
                    While(condition=BinaryOp(left=Identifier(name='x',
                                                             line=10,
                                                             column=8,
                                                             type_name='int'),
                                             operator='>=',
                                             right=Literal(value=0,
                                                           line=10,
                                                           column=13,
                                                           type_name='int'),
                                             line=10,
                                             column=8,
                                             type_name='bool'),
                          body=Block(statements=(Assign(name='x',
                                                        value=BinaryOp(left=Identifier(name='x',
                                                                                       line=11,
                                                                                       column=9,
                                                                                       type_name='int'),
                                                                       operator='-',
                                                                       right=Literal(value=1,
                                                                                     line=11,
                                                                                     column=13,
                                                                                     type_name='int'),
                                                                       line=11,
                                                                       column=9,
                                                                       type_name='int'),
                                                        line=11,
                                                        column=5),),
                                     line=10,
                                     column=16),
                          line=10,
                          column=1)),
        line=1,
        column=1)
```

## 3. Symbol table

The semantic analyzer populates the symbol table while it walks the AST.
Declarations record their name, type, and source position. Nested block scopes
are entered and left during the walk; the CLI prints the scopes that remain
active at the end of compilation.

```text
global:
  a: int (1:1)
  b: int (2:1)
  x: int (3:1)
  ratio: float (4:1)
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
`int2float` conversion.

```text
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

## Error examples

The pipeline stops at the first phase that reports errors. The remaining
phases do not run.

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

The pipeline reports `2:11: Unexpected character '@'` and does not parse the
program.

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

The lookup fails with `2:9: Undefined variable 'missing'`. The declaration of
`x` is still recorded in the global scope.

### Semantic error

`examples/type_error.mc` uses a string operand in arithmetic:

```c
int x = "text" * 2;
```

```bash
python -m mini_compiler examples/type_error.mc
```

```text
=== Tokens ===
KEYWORD 'int' (1:1)
ID 'x' (1:5)
OPERATOR '=' (1:7)
STRING '"text"' (1:9)
OPERATOR '*' (1:16)
INT '2' (1:18)
DELIMITER ';' (1:19)
EOF '' (2:1)

=== AST ===
Program(statements=(VarDecl(name='x',
                            var_type='int',
                            value=BinaryOp(left=Literal(value='text',
                                                        line=1,
                                                        column=9,
                                                        type_name='string'),
                                           operator='*',
                                           right=Literal(value=2,
                                                         line=1,
                                                         column=18,
                                                         type_name='int'),
                                           line=1,
                                           column=9,
                                           type_name='error'),
                            line=1,
                            column=1),),
        line=1,
        column=1)

=== Symbol Table ===
global:
  x: int (1:1)

=== Errors ===
1:9: Operator '*' requires numeric operands, got 'string' and 'int'
```

The analyzer reports `1:9: Operator '*' requires numeric operands, got
'string' and 'int'` and marks the expression type as `error`.

### TAC after an earlier error

The TAC generator has no diagnostics of its own. It is invoked only after
semantic analysis succeeds, and it returns no instructions when semantic
errors are passed to it. This can be observed through the compiler API:

```bash
python -c "from pathlib import Path; from mini_compiler.compiler import compile_source; result = compile_source(Path('examples/type_error.mc').read_text(encoding='utf-8')); print('failed_phase:', result.failed_phase); print('tac:', result.tac)"
```

```text
failed_phase: semantic
tac: ()
```

The pipeline stops before code generation, so no TAC is emitted for this
program.
