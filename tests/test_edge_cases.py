"""Tests for defensive branches and less common edge cases."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from typing import cast

import pytest

from mini_compiler.ast_nodes import (
    BinaryOp,
    Expression,
    Literal,
    Program,
    Statement,
    UnaryOp,
    VarDecl,
)
from mini_compiler.cli import render_result
from mini_compiler.compiler import CompilationResult
from mini_compiler.ir import TACGenerator, TACInstruction
from mini_compiler.lexer import Lexer, Token, TokenType
from mini_compiler.parser import Parser
from mini_compiler.semantic import SemanticAnalyzer
from mini_compiler.symbols import SymbolTable

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse(source: str) -> Program:
    tokens = Lexer(source).tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    assert parser.errors == []
    return program


def test_parser_rejects_missing_eof_token() -> None:
    with pytest.raises(ValueError, match="EOF"):
        Parser([])

    with pytest.raises(ValueError, match="EOF"):
        Parser([Token(TokenType.INT, "1", 1, 1)])


def test_parenthesized_expressions_are_parsed() -> None:
    program = parse("int x = (1 + 2) * 3;")

    declaration = program.statements[0]
    assert isinstance(declaration, VarDecl)
    assert declaration.value == BinaryOp(
        BinaryOp(Literal(1, 1, 10), "+", Literal(2, 1, 14), 1, 10),
        "*",
        Literal(3, 1, 19),
        1,
        10,
    )


def test_cli_renders_empty_tokens_and_empty_tac() -> None:
    result = CompilationResult((), None, None, (), (), None)

    output = render_result(result)

    assert "=== Tokens ===\n<empty>" in output
    assert "=== TAC ===\n<empty>" in output


def test_tac_instruction_without_arguments_is_plain_text() -> None:
    instruction = TACInstruction("nop")

    assert instruction.format() == "nop"
    assert str(instruction) == "nop"


def test_tac_generator_rejects_unsupported_nodes() -> None:
    generator = TACGenerator()

    with pytest.raises(TypeError, match="Unsupported statement"):
        generator._generate_statement(cast(Statement, object()))

    with pytest.raises(TypeError, match="Unsupported expression"):
        generator._generate_expression(cast(Expression, object()))


def test_tac_generator_lookup_returns_none_for_unknown_names() -> None:
    assert TACGenerator()._lookup_type("missing") is None


def test_tac_casts_the_right_operand_when_float_comes_first() -> None:
    program = parse("float x = 2.5 + 1;")
    annotated, errors = SemanticAnalyzer().analyze(program)

    assert errors == []
    instructions = TACGenerator().generate(annotated, errors)

    assert [instruction.format() for instruction in instructions] == [
        "t1 = int2float 1",
        "t2 = 2.5 + t1",
        "x = t2",
    ]


def test_tac_generates_code_for_a_top_level_block() -> None:
    program = parse("{ int x = 1; }")
    annotated, errors = SemanticAnalyzer().analyze(program)

    assert errors == []
    instructions = TACGenerator().generate(annotated, errors)

    assert [instruction.format() for instruction in instructions] == ["x = 1"]


def test_semantic_analyzer_rejects_unsupported_nodes() -> None:
    analyzer = SemanticAnalyzer()

    with pytest.raises(TypeError, match="Unsupported statement"):
        analyzer._visit_statement(cast(Statement, object()))

    with pytest.raises(TypeError, match="Unsupported expression"):
        analyzer._visit_expression(cast(Expression, object()))

    with pytest.raises(TypeError, match="Unsupported literal"):
        analyzer._visit_literal(
            Literal(cast(int | float | str | bool, object()), 1, 1)
        )


def test_semantic_analyzer_rejects_unknown_operators() -> None:
    analyzer = SemanticAnalyzer()

    binary, binary_type = analyzer._visit_binary(
        BinaryOp(Literal(1, 1, 1), "%", Literal(2, 1, 5), 1, 1)
    )
    unary, unary_type = analyzer._visit_expression(
        UnaryOp("~", Literal(1, 1, 1), 1, 1)
    )

    assert binary_type == "error"
    assert binary.type_name == "error"
    assert unary_type == "error"
    assert isinstance(unary, UnaryOp)
    assert unary.type_name == "error"
    assert [error.message for error in analyzer.errors] == [
        "Unknown binary operator '%'",
        "Unknown unary operator '~'",
    ]


def test_relational_operators_require_numeric_operands() -> None:
    program = parse('bool ok = "a" <= "b";')
    _, errors = SemanticAnalyzer().analyze(program)

    assert [error.message for error in errors] == [
        "Operator '<=' requires numeric operands, got 'string' and 'string'"
    ]


def test_unary_minus_requires_a_numeric_operand() -> None:
    program = parse('int x = -"a";')
    _, errors = SemanticAnalyzer().analyze(program)

    assert [error.message for error in errors] == [
        "Operator '-' requires a numeric operand, got 'string'"
    ]


def test_unary_propagates_an_operand_error() -> None:
    program = parse("int x = -missing;")
    annotated, errors = SemanticAnalyzer().analyze(program)

    assert [error.message for error in errors] == ["Undefined variable 'missing'"]
    declaration = annotated.statements[0]
    assert isinstance(declaration, VarDecl)
    assert declaration.value.type_name == "error"


def test_equality_accepts_matching_types() -> None:
    program = parse("bool ok = 1 == 2;")
    annotated, errors = SemanticAnalyzer().analyze(program)

    assert errors == []
    declaration = annotated.statements[0]
    assert isinstance(declaration, VarDecl)
    assert declaration.value.type_name == "bool"


def test_symbol_table_exposes_scope_stack() -> None:
    table = SymbolTable()
    table.enter_scope("block")

    assert [scope.name for scope in table.scopes] == ["global", "block"]


def test_module_entry_point_compiles_a_file(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path = PROJECT_ROOT / "examples" / "valid.mc"
    monkeypatch.setattr(sys, "argv", ["mini_compiler", str(source_path)])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("mini_compiler", run_name="__main__")

    assert exit_info.value.code == 0
    assert "TAC" in capsys.readouterr().out
