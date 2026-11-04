"""Tests for the parser."""

from dataclasses import FrozenInstanceError

import pytest

from mini_compiler.ast_nodes import (
    Assign,
    BinaryOp,
    Block,
    Identifier,
    If,
    Literal,
    Program,
    UnaryOp,
    VarDecl,
    While,
)
from mini_compiler.lexer import Lexer
from mini_compiler.parser import ParseError, Parser


def parse(source: str) -> tuple[Program, list[ParseError]]:
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    assert lexer.errors == []
    parser = Parser(tokens)
    return parser.parse(), parser.errors


def test_multiplication_nests_under_addition():
    program, errors = parse("int x = a + b * 5;")

    assert errors == []
    assert program == Program(
        (
            VarDecl(
                "x",
                "int",
                BinaryOp(
                    Identifier("a", 1, 9),
                    "+",
                    BinaryOp(
                        Identifier("b", 1, 13),
                        "*",
                        Literal(5, 1, 17),
                        1,
                        13,
                    ),
                    1,
                    9,
                ),
                1,
                1,
            ),
        ),
        1,
        1,
    )


def test_full_precedence_chain():
    program, errors = parse("int x = a || b && c == d <= e + f * g;")

    assert errors == []
    declaration = program.statements[0]
    assert isinstance(declaration, VarDecl)

    logical_or = declaration.value
    assert isinstance(logical_or, BinaryOp)
    assert logical_or.operator == "||"

    logical_and = logical_or.right
    assert isinstance(logical_and, BinaryOp)
    assert logical_and.operator == "&&"

    equality = logical_and.right
    assert isinstance(equality, BinaryOp)
    assert equality.operator == "=="

    relational = equality.right
    assert isinstance(relational, BinaryOp)
    assert relational.operator == "<="

    additive = relational.right
    assert isinstance(additive, BinaryOp)
    assert additive.operator == "+"

    multiplicative = additive.right
    assert isinstance(multiplicative, BinaryOp)
    assert multiplicative.operator == "*"
    assert multiplicative.left == Identifier("f", 1, 33)
    assert multiplicative.right == Identifier("g", 1, 37)


def test_unary_operators():
    program, errors = parse("int x = !a && -b;")

    assert errors == []
    declaration = program.statements[0]
    assert isinstance(declaration, VarDecl)
    assert declaration.value == BinaryOp(
        UnaryOp("!", Identifier("a", 1, 10), 1, 9),
        "&&",
        UnaryOp("-", Identifier("b", 1, 16), 1, 15),
        1,
        9,
    )


def test_binary_operators_are_left_associative():
    program, errors = parse("int x = 1 - 2 - 3;")

    assert errors == []
    declaration = program.statements[0]
    assert isinstance(declaration, VarDecl)
    assert declaration.value == BinaryOp(
        BinaryOp(Literal(1, 1, 9), "-", Literal(2, 1, 13), 1, 9),
        "-",
        Literal(3, 1, 17),
        1,
        9,
    )


def test_if_else_and_while():
    source = (
        "if (x <= 10) {\n"
        "    x = x + 1;\n"
        "} else {\n"
        "    while (x != 0) {\n"
        "        x = x - 1;\n"
        "    }\n"
        "}"
    )

    program, errors = parse(source)

    assert errors == []
    if_node = program.statements[0]
    assert isinstance(if_node, If)
    assert (if_node.line, if_node.column) == (1, 1)
    assert if_node.condition == BinaryOp(
        Identifier("x", 1, 5), "<=", Literal(10, 1, 10), 1, 5
    )
    assert if_node.then_branch == Block(
        (
            Assign(
                "x",
                BinaryOp(Identifier("x", 2, 9), "+", Literal(1, 2, 13), 2, 9),
                2,
                5,
            ),
        ),
        1,
        14,
    )

    assert isinstance(if_node.else_branch, Block)
    assert (if_node.else_branch.line, if_node.else_branch.column) == (3, 8)
    while_node = if_node.else_branch.statements[0]
    assert isinstance(while_node, While)
    assert (while_node.line, while_node.column) == (4, 5)
    assert while_node.condition == BinaryOp(
        Identifier("x", 4, 12), "!=", Literal(0, 4, 17), 4, 12
    )
    assert while_node.body == Block(
        (
            Assign(
                "x",
                BinaryOp(Identifier("x", 5, 13), "-", Literal(1, 5, 17), 5, 13),
                5,
                9,
            ),
        ),
        4,
        20,
    )


def test_literal_values_are_converted():
    program, errors = parse(
        'int a = 1; float b = 2.5; string c = "hi\\nthere";'
    )

    assert errors == []
    declarations = program.statements
    assert [declaration.value.value for declaration in declarations] == [
        1,
        2.5,
        "hi\nthere",
    ]
    assert [type(declaration.value.value) for declaration in declarations] == [
        int,
        float,
        str,
    ]


def test_bool_declarations_and_literals():
    program, errors = parse("bool a = true; bool b = false;")

    assert errors == []
    assert program.statements == (
        VarDecl("a", "bool", Literal(True, 1, 10), 1, 1),
        VarDecl("b", "bool", Literal(False, 1, 25), 1, 16),
    )


def test_reports_missing_identifier_with_position():
    program, errors = parse("int = ;")

    assert program.statements == ()
    assert errors == [ParseError("Expected identifier, got '='", 1, 5)]


def test_recovers_at_semicolon():
    program, errors = parse("int = ;\nint y = 2;")

    assert errors == [ParseError("Expected identifier, got '='", 1, 5)]
    assert program.statements == (
        VarDecl("y", "int", Literal(2, 2, 9), 2, 1),
    )


def test_recovers_inside_a_block():
    program, errors = parse("if (x) { int = ; x = 1; }")

    assert errors == [ParseError("Expected identifier, got '='", 1, 14)]
    if_node = program.statements[0]
    assert isinstance(if_node, If)
    assert if_node.else_branch is None
    assert if_node.then_branch == Block(
        (Assign("x", Literal(1, 1, 22), 1, 18),),
        1,
        8,
    )


def test_accumulates_multiple_errors():
    program, errors = parse("int = ;\nint y = ;")

    assert program.statements == ()
    assert errors == [
        ParseError("Expected identifier, got '='", 1, 5),
        ParseError("Expected expression, got ';'", 2, 9),
    ]


def test_unexpected_top_level_token_recovers():
    program, errors = parse("}")

    assert program == Program((), 1, 1)
    assert errors == [ParseError("Unexpected token '}'", 1, 1)]


def test_empty_program():
    program, errors = parse("")

    assert program == Program((), 1, 1)
    assert errors == []


def test_ast_nodes_are_immutable():
    program, _ = parse("int x = 1;")
    declaration = program.statements[0]

    with pytest.raises(FrozenInstanceError):
        declaration.name = "y"
