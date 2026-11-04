"""Tests for three-address code generation."""

from dataclasses import FrozenInstanceError

import pytest

from mini_compiler.ir import (
    TACGenerator,
    TACInstruction,
    format_instructions,
)
from mini_compiler.lexer import Lexer
from mini_compiler.parser import Parser
from mini_compiler.semantic import SemanticAnalyzer


def compile_source(source: str):
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    assert lexer.errors == []
    parser = Parser(tokens)
    program = parser.parse()
    assert parser.errors == []
    return SemanticAnalyzer().analyze(program)


def generate(source: str) -> list[TACInstruction]:
    annotated, errors = compile_source(source)
    assert errors == []
    return TACGenerator().generate(annotated, errors)


def test_multiplication_respects_precedence():
    instructions = generate(
        "int a = 1; int b = 2; int x = 0; x = a + b * 5;"
    )

    assert format_instructions(instructions[-3:]) == (
        "t1 = b * 5\n"
        "t2 = a + t1\n"
        "x = t2"
    )


def test_while_generates_labels_and_jumps():
    instructions = generate(
        "int x = 3;\n"
        "while (x >= 0) {\n"
        "    x = x - 1;\n"
        "}"
    )

    assert format_instructions(instructions) == (
        "x = 3\n"
        "L1:\n"
        "t1 = x >= 0\n"
        "ifFalse t1 goto L2\n"
        "t2 = x - 1\n"
        "x = t2\n"
        "goto L1\n"
        "L2:"
    )


def test_if_else_generates_labels_and_jumps():
    instructions = generate(
        "int x = 1;\n"
        "if (x <= 10) { x = 2; } else { x = 3; }"
    )

    assert format_instructions(instructions) == (
        "x = 1\n"
        "t1 = x <= 10\n"
        "ifFalse t1 goto L1\n"
        "x = 2\n"
        "goto L2\n"
        "L1:\n"
        "x = 3\n"
        "L2:"
    )


def test_if_without_else_uses_a_single_label():
    instructions = generate("bool ok = true; if (ok) { ok = false; }")

    assert format_instructions(instructions) == (
        "ok = true\n"
        "ifFalse ok goto L1\n"
        "ok = false\n"
        "L1:"
    )


def test_int_to_float_cast_in_declaration():
    instructions = generate("float x = 1;")

    assert format_instructions(instructions) == (
        "t1 = int2float 1\n"
        "x = t1"
    )


def test_int_to_float_cast_in_mixed_arithmetic():
    instructions = generate("float x = 1 + 2.5;")

    assert format_instructions(instructions) == (
        "t1 = int2float 1\n"
        "t2 = t1 + 2.5\n"
        "x = t2"
    )


def test_int_to_float_cast_in_assignment():
    instructions = generate("float x = 1.0;\nx = 2;")

    assert format_instructions(instructions[-2:]) == (
        "t1 = int2float 2\n"
        "x = t1"
    )


def test_int_to_float_cast_in_mixed_comparison():
    instructions = generate("int x = 1;\nbool ok = x <= 1.5;")

    assert format_instructions(instructions) == (
        "x = 1\n"
        "t1 = int2float x\n"
        "t2 = t1 <= 1.5\n"
        "ok = t2"
    )


def test_unary_operator_generation():
    instructions = generate("int a = 1;\nint x = -a;")

    assert format_instructions(instructions[-2:]) == (
        "t1 = -a\n"
        "x = t1"
    )


def test_bool_and_string_literals_are_formatted():
    instructions = generate('bool ok = true;\nstring name = "hi";')

    assert format_instructions(instructions) == (
        "ok = true\n"
        'name = "hi"'
    )


def test_no_code_is_generated_when_semantic_errors_exist():
    annotated, errors = compile_source("int x = missing;")

    assert errors != []
    assert TACGenerator().generate(annotated, errors) == []


def test_formatter_handles_labels_jumps_casts_and_unary_ops():
    instructions = [
        TACInstruction("label", "L1"),
        TACInstruction("ifFalse", "L2", "t1"),
        TACInstruction("goto", "L1"),
        TACInstruction("int2float", "t3", "a"),
        TACInstruction("-", "t4", "a"),
    ]

    assert format_instructions(instructions) == (
        "L1:\n"
        "ifFalse t1 goto L2\n"
        "goto L1\n"
        "t3 = int2float a\n"
        "t4 = -a"
    )


def test_tac_instructions_are_immutable():
    instruction = TACInstruction("*", "t1", "b", "5")

    assert instruction.format() == "t1 = b * 5"

    with pytest.raises(FrozenInstanceError):
        instruction.op = "+"
