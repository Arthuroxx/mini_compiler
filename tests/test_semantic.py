"""Tests for the semantic analyzer."""

from mini_compiler.ast_nodes import (
    BinaryOp,
    Identifier,
    Literal,
    Program,
    UnaryOp,
    VarDecl,
)
from mini_compiler.lexer import Lexer
from mini_compiler.parser import Parser
from mini_compiler.semantic import SemanticAnalyzer
from mini_compiler.symbols import SemanticError


def parse_source(source: str) -> Program:
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    assert lexer.errors == []
    parser = Parser(tokens)
    program = parser.parse()
    assert parser.errors == []
    return program


def analyze(source: str) -> tuple[Program, list[SemanticError]]:
    return SemanticAnalyzer().analyze(parse_source(source))


def test_int_to_float_promotion_in_declaration() -> None:
    program, errors = analyze("float x = 1;")

    assert errors == []
    declaration = program.statements[0]
    assert isinstance(declaration, VarDecl)
    assert declaration.var_type == "float"
    assert declaration.value == Literal(1, 1, 11, "int")


def test_string_times_bool_is_rejected() -> None:
    program, errors = analyze('int y = "a" * true;')

    assert errors == [
        SemanticError(
            "Operator '*' requires numeric operands, got 'string' and 'bool'",
            1,
            9,
        )
    ]
    declaration = program.statements[0]
    assert isinstance(declaration, VarDecl)
    assert declaration.value.type_name == "error"


def test_undeclared_variable_is_reported_with_position() -> None:
    program, errors = analyze("int x = missing;")

    assert errors == [SemanticError("Undefined variable 'missing'", 1, 9)]
    declaration = program.statements[0]
    assert isinstance(declaration, VarDecl)
    assert declaration.value.type_name == "error"


def test_assignment_requires_compatible_types() -> None:
    source = "int x = 1;\nfloat y = 2.5;\nx = y;"

    _, errors = analyze(source)

    assert errors == [
        SemanticError(
            "Cannot assign 'float' to variable 'x' of type 'int'",
            3,
            5,
        )
    ]


def test_assignment_allows_int_to_float_promotion() -> None:
    source = "float y = 2.5;\ny = 1;"

    _, errors = analyze(source)

    assert errors == []


def test_declaration_rejects_narrowing_and_bool_mismatch() -> None:
    _, errors = analyze("int x = 2.5;\nbool b = 1;")

    assert errors == [
        SemanticError(
            "Cannot assign 'float' to variable 'x' of type 'int'",
            1,
            9,
        ),
        SemanticError(
            "Cannot assign 'int' to variable 'b' of type 'bool'",
            2,
            10,
        ),
    ]


def test_string_arithmetic_is_rejected() -> None:
    _, errors = analyze('string s = "a" + "b";')

    assert errors == [
        SemanticError(
            "Operator '+' requires numeric operands, got 'string' and 'string'",
            1,
            12,
        )
    ]


def test_if_and_while_conditions_must_be_bool() -> None:
    source = "int x = 1;\nif (x) { x = 2; }\nwhile (x) { x = 3; }"

    _, errors = analyze(source)

    assert errors == [
        SemanticError("If condition must be of type 'bool', got 'int'", 2, 5),
        SemanticError("While condition must be of type 'bool', got 'int'", 3, 8),
    ]


def test_bool_conditions_are_valid() -> None:
    source = (
        "bool ok = true;\n"
        "if (ok) { ok = false; }\n"
        "while (ok) { ok = false; }"
    )

    _, errors = analyze(source)

    assert errors == []


def test_block_scope_ends_after_the_block() -> None:
    source = "{ int tmp = 1; }\nint x = tmp;"

    _, errors = analyze(source)

    assert errors == [SemanticError("Undefined variable 'tmp'", 2, 9)]


def test_outer_variables_are_visible_inside_blocks() -> None:
    source = "int outer = 1;\n{ int inner = outer + 1; }"

    _, errors = analyze(source)

    assert errors == []


def test_shadowing_does_not_leak_after_the_block() -> None:
    source = "int x = 1;\n{ float x = 2.5; x = x + 1; }\nint y = x;"

    _, errors = analyze(source)

    assert errors == []


def test_redeclaration_in_the_same_scope_is_reported() -> None:
    source = "int x = 1;\nint x = 2;"

    _, errors = analyze(source)

    assert errors == [
        SemanticError(
            "Variable 'x' is already declared in scope 'global'",
            2,
            1,
        )
    ]


def test_logical_operators_require_bool_operands() -> None:
    _, errors = analyze("bool x = 1 && 2;")

    assert errors == [
        SemanticError(
            "Operator '&&' requires bool operands, got 'int' and 'int'",
            1,
            10,
        )
    ]


def test_unary_operators_validate_their_operand() -> None:
    _, errors = analyze("bool x = !1;")

    assert errors == [
        SemanticError("Operator '!' requires a bool operand, got 'int'", 1, 10)
    ]


def test_equality_rejects_incompatible_types() -> None:
    _, errors = analyze('bool b = "a" == 1;')

    assert errors == [
        SemanticError(
            "Operator '==' cannot compare 'string' and 'int'",
            1,
            10,
        )
    ]


def test_numeric_operations_are_annotated_with_their_result_type() -> None:
    source = "float x = 1 + 2.5;\nbool b = 1 <= 2.0;\nbool c = 1 == 2.5;"

    program, errors = analyze(source)

    assert errors == []
    first = program.statements[0]
    assert isinstance(first, VarDecl)
    assert isinstance(first.value, BinaryOp)
    assert first.value.type_name == "float"
    assert first.value.left.type_name == "int"
    assert first.value.right.type_name == "float"

    second = program.statements[1]
    assert isinstance(second, VarDecl)
    assert second.value.type_name == "bool"

    third = program.statements[2]
    assert isinstance(third, VarDecl)
    assert third.value.type_name == "bool"


def test_identifiers_are_annotated_with_declared_types() -> None:
    source = "int a = 1;\nint b = a + 1;"

    program, errors = analyze(source)

    assert errors == []
    declaration = program.statements[1]
    assert isinstance(declaration, VarDecl)
    addition = declaration.value
    assert isinstance(addition, BinaryOp)
    assert addition.type_name == "int"
    assert addition.left == Identifier("a", 2, 9, "int")


def test_logical_expression_types_are_annotated() -> None:
    source = "bool a = true;\nbool b = false;\nbool c = a && !b;"

    program, errors = analyze(source)

    assert errors == []
    declaration = program.statements[2]
    assert isinstance(declaration, VarDecl)
    logical_and = declaration.value
    assert isinstance(logical_and, BinaryOp)
    assert logical_and.type_name == "bool"
    assert logical_and.left.type_name == "bool"
    assert isinstance(logical_and.right, UnaryOp)
    assert logical_and.right.type_name == "bool"


def test_literal_annotations_include_bool() -> None:
    program, errors = analyze("bool b = true;")

    assert errors == []
    declaration = program.statements[0]
    assert isinstance(declaration, VarDecl)
    assert declaration.value == Literal(True, 1, 10, "bool")
