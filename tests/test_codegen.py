"""Tests for target code generation and register allocation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from mini_compiler.codegen import (
    AsmInstruction,
    AssemblyGenerator,
    format_assembly,
)
from mini_compiler.compiler import compile_source
from mini_compiler.ir import TACInstruction

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def compile_asm(source: str) -> str:
    result = compile_source(source)
    assert result.errors == ()
    return format_assembly(result.asm)


def read_example(name: str) -> str:
    return (EXAMPLES_DIR / name).read_text(encoding="utf-8")


def test_instruction_formatting_and_immutability() -> None:
    instruction = AsmInstruction("MOV", ("R0", "[a]"))

    assert instruction.format() == "MOV R0, [a]"
    assert str(instruction) == "MOV R0, [a]"
    assert AsmInstruction("label", ("L1",)).format() == "L1:"
    assert AsmInstruction("NOP").format() == "NOP"

    with pytest.raises(FrozenInstanceError):
        instruction.op = "ADD"  # type: ignore[misc]


def test_empty_tac_produces_no_assembly() -> None:
    assert AssemblyGenerator().generate([]) == []


def test_literal_declarations_and_addition() -> None:
    assembly = compile_asm("int a = 2; int b = 3; int x = a + b;")

    assert assembly == "\n".join(
        [
            "MOV [a], 2",
            "MOV [b], 3",
            "MOV R0, [a]",
            "ADD R0, [b]",
            "MOV [x], R0",
        ]
    )


def test_arithmetic_uses_mul_sub_and_div() -> None:
    assembly = compile_asm(
        "int a = 8; int b = 2; int x = a * b; int y = x - a; int z = y / b;"
    )

    assert "MUL" in assembly
    assert "SUB" in assembly
    assert "DIV" in assembly


def test_comparison_materializes_a_boolean() -> None:
    assembly = compile_asm("int x = 1; bool ok = x >= 10;")

    assert "CMP R0, 10" in assembly
    assert "JGE Lcmp1" in assembly
    assert "MOV R0, 1" in assembly
    assert "MOV R0, 0" in assembly
    assert "Lcmp1:" in assembly
    assert "MOV [ok], R0" in assembly


@pytest.mark.parametrize(
    ("operator", "jump"),
    [
        ("==", "JZ"),
        ("!=", "JNZ"),
        ("<", "JL"),
        ("<=", "JLE"),
        (">", "JG"),
        (">=", "JGE"),
    ],
)
def test_each_comparison_uses_its_conditional_jump(
    operator: str,
    jump: str,
) -> None:
    tac = [
        TACInstruction(operator, "t1", "a", "b"),
        TACInstruction("=", "x", "t1"),
    ]

    assembly = format_assembly(AssemblyGenerator().generate(tac))

    assert f"{jump} Lcmp1" in assembly


def test_control_flow_generates_labels_and_jumps() -> None:
    assembly = compile_asm(
        "int x = 1;\n"
        "while (x >= 0) {\n"
        "    x = x - 1;\n"
        "}"
    )

    assert "L1:" in assembly
    assert "JZ L2" in assembly
    assert "JMP L1" in assembly
    assert assembly.rstrip().endswith("L2:")


def test_if_false_uses_jz() -> None:
    assembly = compile_asm("bool ok = true; if (ok) { ok = false; }")

    assert "CMP R0, 0" in assembly
    assert "JZ L1" in assembly


def test_int_to_float_uses_the_conversion_instruction() -> None:
    assembly = compile_asm("int a = 1; int b = 2; float x = a + b;")

    assert "INT2FLOAT R1, R0" in assembly


def test_int_to_float_accepts_a_variable_operand() -> None:
    assembly = compile_asm("int a = 1; float x = a;")

    assert "INT2FLOAT R0, [a]" in assembly


def test_unary_minus_and_logical_not() -> None:
    assembly = compile_asm(
        "int a = 1; int x = -a; bool ok = true; bool no = !ok;"
    )

    assert "MOV R1, 0" in assembly
    assert "SUB R1, R0" in assembly
    assert "CMP R0, 0" in assembly
    assert "JZ Lcmp" in assembly


def test_logical_and_short_circuits_through_labels() -> None:
    assembly = compile_asm(
        "bool a = true; bool b = false; bool c = a && b; bool d = a || b;"
    )

    assert "MOV R2, 0" in assembly
    assert "JZ Lcmp1" in assembly
    assert "MOV R2, 1" in assembly
    assert "JNZ Lcmp2" in assembly


def test_spill_forces_store_and_load_with_four_live_temporaries() -> None:
    result = compile_source(read_example("spill.mc"))
    assembly = format_assembly(result.asm)

    assert "t1" in {instruction.result for instruction in result.tac}
    assert "STORE R0, [0x2000]" in assembly
    assert "LOAD R1, [0x2000]" in assembly
    assert assembly.index("STORE") < assembly.index("LOAD")


def test_dead_temporaries_release_registers_without_spilling() -> None:
    assembly = compile_asm("int a = 1; int b = 2; int x = a + b + a;")

    assert "STORE" not in assembly
    assert "LOAD" not in assembly


def test_commutative_operation_can_reuse_the_right_register() -> None:
    tac = [
        TACInstruction("=", "t0", "1"),
        TACInstruction("=", "t1", "2"),
        TACInstruction("=", "t2", "3"),
        TACInstruction("+", "t3", "t1", "t2"),
        TACInstruction("+", "t4", "t1", "t3"),
        TACInstruction("+", "t5", "t0", "t4"),
        TACInstruction("=", "x", "t5"),
    ]

    assembly = format_assembly(AssemblyGenerator().generate(tac))

    assert "ADD R2, R1" in assembly
    assert "STORE" not in assembly


def test_moves_between_temporaries_and_variables() -> None:
    tac = [
        TACInstruction("=", "t1", "7"),
        TACInstruction("=", "t2", "t1"),
        TACInstruction("=", "a", "t2"),
        TACInstruction("=", "b", "a"),
        TACInstruction("=", "c", "false"),
        TACInstruction("=", "name", '"hi"'),
    ]

    assembly = format_assembly(AssemblyGenerator().generate(tac))

    assert "MOV R0, 7" in assembly
    assert "MOV [a], R1" in assembly
    assert "MOV [b], [a]" in assembly
    assert "MOV [c], 0" in assembly
    assert 'MOV [name], "hi"' in assembly


def test_unsupported_tac_operation_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported TAC operation"):
        AssemblyGenerator().generate([TACInstruction("%", "t1", "a", "b")])
