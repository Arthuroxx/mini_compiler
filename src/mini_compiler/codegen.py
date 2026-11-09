"""Target code generation from three-address code.

The generator lowers TAC into a small, consistent assembly language.  Values
live in memory (``[name]``) unless they are temporaries held in one of the
three registers (``R0``-``R2``).  When more than three temporaries are live,
the allocator spills one to the stack starting at ``0x2000`` with ``STORE`` and
restores it on demand with ``LOAD``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from mini_compiler.ir import TACInstruction

REGISTERS: Final[tuple[str, ...]] = ("R0", "R1", "R2")
SPILL_BASE: Final[int] = 0x2000
SPILL_STEP: Final[int] = 4

_TEMP_PATTERN: Final[re.Pattern[str]] = re.compile(r"^t\d+$")
_NUMBER_PATTERN: Final[re.Pattern[str]] = re.compile(r"^-?\d+(?:\.\d+)?$")
_ARITHMETIC: Final[dict[str, str]] = {
    "+": "ADD",
    "-": "SUB",
    "*": "MUL",
    "/": "DIV",
}
_COMMUTATIVE: Final[frozenset[str]] = frozenset({"+", "*"})
_COMPARISON_JUMPS: Final[dict[str, str]] = {
    "==": "JZ",
    "!=": "JNZ",
    "<": "JL",
    "<=": "JLE",
    ">": "JG",
    ">=": "JGE",
}
_CONTROL_OPS: Final[frozenset[str]] = frozenset({"label", "goto", "ifFalse"})


@dataclass(frozen=True)
class AsmInstruction:
    """A single target assembly instruction."""

    op: str
    args: tuple[str, ...] = ()

    def format(self) -> str:
        """Return the instruction in assembly syntax."""

        if self.op == "label":
            return f"{self.args[0]}:"
        if not self.args:
            return self.op
        return f"{self.op} {', '.join(self.args)}"

    def __str__(self) -> str:
        return self.format()


def format_assembly(instructions: Sequence[AsmInstruction]) -> str:
    """Return the assembly instructions one per line."""

    return "\n".join(instruction.format() for instruction in instructions)


def _is_temp(name: str) -> bool:
    return _TEMP_PATTERN.fullmatch(name) is not None


class RegisterAllocator:
    """Assigns R0-R2 to temporaries and spills the rest to the stack."""

    def __init__(self) -> None:
        self._temp_to_register: dict[str, str] = {}
        self._register_to_temp: dict[str, str] = {}
        self._slots: dict[str, int] = {}
        self._next_slot = SPILL_BASE

    def register_for(self, temp: str) -> str | None:
        """Return the register currently holding ``temp``, if any."""

        return self._temp_to_register.get(temp)

    def temp_in(self, register: str) -> str | None:
        """Return the temporary currently held by ``register``, if any."""

        return self._register_to_temp.get(register)

    def bind(self, temp: str, register: str) -> None:
        """Associate ``temp`` with ``register``."""

        previous = self._register_to_temp.get(register)
        if previous is not None and previous != temp:
            self._temp_to_register.pop(previous, None)
        self._register_to_temp[register] = temp
        self._temp_to_register[temp] = register

    def unbind_register(self, register: str) -> str | None:
        """Release ``register`` and return the temporary it held."""

        temp = self._register_to_temp.pop(register, None)
        if temp is not None:
            self._temp_to_register.pop(temp, None)
        return temp

    def slot_for(self, temp: str) -> int:
        """Return the stable stack slot assigned to ``temp``."""

        slot = self._slots.get(temp)
        if slot is None:
            slot = self._next_slot
            self._slots[temp] = slot
            self._next_slot += SPILL_STEP
        return slot

    @staticmethod
    def format_slot(slot: int) -> str:
        """Format a stack slot as a memory operand."""

        return f"[0x{slot:04X}]"

    def free_dead(self, live_after: set[str]) -> None:
        """Release registers that hold temporaries dead after an instruction."""

        for register in REGISTERS:
            temp = self._register_to_temp.get(register)
            if temp is not None and temp not in live_after:
                self.unbind_register(register)

    def acquire(
        self,
        *,
        exclude: frozenset[str] = frozenset(),
    ) -> tuple[str, list[AsmInstruction]]:
        """Return a free register, evicting a live temporary if necessary."""

        for register in REGISTERS:
            if register in exclude:
                continue
            if self.temp_in(register) is None:
                return register, []

        for register in REGISTERS:
            if register in exclude:
                continue
            temp = self.temp_in(register)
            if temp is None:
                continue
            slot = self.slot_for(temp)
            self.unbind_register(register)
            return register, [
                AsmInstruction(
                    "STORE",
                    (register, self.format_slot(slot)),
                )
            ]

        raise RuntimeError("no register available")


class AssemblyGenerator:
    """Translates TAC instructions into target assembly."""

    def __init__(self) -> None:
        self.instructions: list[AsmInstruction] = []
        self._allocator = RegisterAllocator()
        self._label_count = 0

    def generate(self, tac: Sequence[TACInstruction]) -> list[AsmInstruction]:
        """Return assembly instructions for a sequence of TAC instructions."""

        self.instructions = []
        self._allocator = RegisterAllocator()
        self._label_count = 0

        if not tac:
            return self.instructions

        live_out = self._live_out(tac)
        for instruction, live_after in zip(tac, live_out, strict=True):
            self._generate_instruction(instruction, live_after)
            self._allocator.free_dead(live_after)

        return self.instructions

    def _generate_instruction(
        self,
        instruction: TACInstruction,
        live_after: set[str],
    ) -> None:
        op = instruction.op

        if op == "label":
            self._emit("label", instruction.result or "")
        elif op == "goto":
            self._emit("JMP", instruction.result or "")
        elif op == "ifFalse":
            self._if_false(instruction, live_after)
        elif op == "=":
            self._move(instruction, live_after)
        elif op == "int2float":
            self._int2float(instruction, live_after)
        elif op == "!":
            self._logical_not(instruction, live_after)
        elif op == "-" and instruction.arg2 is None:
            self._negate(instruction, live_after)
        elif op in _COMPARISON_JUMPS:
            self._compare(instruction, live_after)
        elif op in _ARITHMETIC:
            self._arithmetic(instruction, live_after)
        elif op in {"&&", "||"}:
            self._logical(instruction, live_after)
        else:
            raise ValueError(f"Unsupported TAC operation: {op}")

    def _arithmetic(
        self,
        instruction: TACInstruction,
        live_after: set[str],
    ) -> None:
        assert instruction.result is not None
        assert instruction.arg1 is not None
        assert instruction.arg2 is not None

        left_register, prelude, left_is_temp = self._load_operand(
            instruction.arg1
        )
        right_text, right_prelude, right_register = self._value_operand(
            instruction.arg2,
            exclude=frozenset({left_register}),
        )
        left_pinned = left_is_temp and instruction.arg1 in live_after
        right_pinned = (
            right_register is not None and instruction.arg2 in live_after
        )
        commutative = instruction.op in _COMMUTATIVE

        destination, destination_prelude = self._select_destination(
            left_register,
            right_register,
            left_pinned=left_pinned,
            right_pinned=right_pinned,
            commutative=commutative,
        )

        self.instructions.extend(prelude)
        self.instructions.extend(right_prelude)
        self.instructions.extend(destination_prelude)

        mnemonic = _ARITHMETIC[instruction.op]
        if destination == left_register:
            self._emit(mnemonic, destination, right_text)
        elif destination == right_register and commutative:
            self._emit(mnemonic, destination, left_register)
        else:
            self._emit("MOV", destination, left_register)
            self._emit(mnemonic, destination, right_text)

        self._bind_result(instruction.result, destination)

    def _compare(
        self,
        instruction: TACInstruction,
        live_after: set[str],
    ) -> None:
        assert instruction.result is not None
        assert instruction.arg1 is not None
        assert instruction.arg2 is not None

        left_register, prelude, left_is_temp = self._load_operand(
            instruction.arg1
        )
        right_text, right_prelude, right_register = self._value_operand(
            instruction.arg2,
            exclude=frozenset({left_register}),
        )
        left_pinned = left_is_temp and instruction.arg1 in live_after
        right_pinned = (
            right_register is not None and instruction.arg2 in live_after
        )

        destination, destination_prelude = self._select_destination(
            left_register,
            right_register,
            left_pinned=left_pinned,
            right_pinned=right_pinned,
            commutative=False,
        )

        self.instructions.extend(prelude)
        self.instructions.extend(right_prelude)
        self.instructions.extend(destination_prelude)

        self._emit("CMP", left_register, right_text)
        self._emit("MOV", destination, "1")
        true_label = self._new_comparison_label()
        self._emit(_COMPARISON_JUMPS[instruction.op], true_label)
        self._emit("MOV", destination, "0")
        self._emit("label", true_label)

        self._bind_result(instruction.result, destination)

    def _logical(
        self,
        instruction: TACInstruction,
        live_after: set[str],
    ) -> None:
        assert instruction.result is not None
        assert instruction.arg1 is not None
        assert instruction.arg2 is not None

        left_register, prelude, _ = self._load_operand(instruction.arg1)
        right_register, right_prelude, _ = self._load_operand(
            instruction.arg2,
            exclude=frozenset({left_register}),
        )
        destination, destination_prelude = self._allocator.acquire(
            exclude=frozenset({left_register, right_register}),
        )

        self.instructions.extend(prelude)
        self.instructions.extend(right_prelude)
        self.instructions.extend(destination_prelude)

        done_label = self._new_comparison_label()
        if instruction.op == "&&":
            self._emit("MOV", destination, "0")
            self._emit("CMP", left_register, "0")
            self._emit("JZ", done_label)
            self._emit("CMP", right_register, "0")
            self._emit("JZ", done_label)
            self._emit("MOV", destination, "1")
        else:
            self._emit("MOV", destination, "1")
            self._emit("CMP", left_register, "0")
            self._emit("JNZ", done_label)
            self._emit("CMP", right_register, "0")
            self._emit("JNZ", done_label)
            self._emit("MOV", destination, "0")
        self._emit("label", done_label)

        self._bind_result(instruction.result, destination)

    def _move(
        self,
        instruction: TACInstruction,
        live_after: set[str],
    ) -> None:
        assert instruction.result is not None
        assert instruction.arg1 is not None

        result = instruction.result
        argument = instruction.arg1

        if _is_temp(result):
            if _is_temp(argument):
                source_register, prelude = self._load_temp(argument)
                pinned = argument in live_after
                destination, destination_prelude = self._select_destination(
                    source_register,
                    None,
                    left_pinned=pinned,
                    right_pinned=False,
                    commutative=False,
                )
                self.instructions.extend(prelude)
                self.instructions.extend(destination_prelude)
                if destination != source_register:
                    self._emit("MOV", destination, source_register)
                self._bind_result(result, destination)
            else:
                destination, prelude = self._allocator.acquire()
                self.instructions.extend(prelude)
                self._emit("MOV", destination, self._operand_text(argument))
                self._bind_result(result, destination)
            return

        target = self._operand_text(result)
        if _is_temp(argument):
            source_register, prelude = self._load_temp(argument)
            self.instructions.extend(prelude)
            self._emit("MOV", target, source_register)
        else:
            self._emit("MOV", target, self._operand_text(argument))

    def _int2float(
        self,
        instruction: TACInstruction,
        live_after: set[str],
    ) -> None:
        assert instruction.result is not None
        assert instruction.arg1 is not None

        if _is_temp(instruction.arg1):
            source_register, prelude = self._load_temp(instruction.arg1)
            pinned = instruction.arg1 in live_after
            destination, destination_prelude = self._select_destination(
                source_register,
                None,
                left_pinned=pinned,
                right_pinned=False,
                commutative=False,
            )
            source_text = source_register
            self.instructions.extend(prelude)
            self.instructions.extend(destination_prelude)
        else:
            destination, prelude = self._allocator.acquire()
            source_text = self._operand_text(instruction.arg1)
            self.instructions.extend(prelude)

        self._emit("INT2FLOAT", destination, source_text)
        self._bind_result(instruction.result, destination)

    def _negate(
        self,
        instruction: TACInstruction,
        live_after: set[str],
    ) -> None:
        assert instruction.result is not None
        assert instruction.arg1 is not None

        source_register, prelude, source_is_temp = self._load_operand(
            instruction.arg1
        )
        pinned = source_is_temp and instruction.arg1 in live_after
        destination, destination_prelude = self._select_destination(
            source_register,
            None,
            left_pinned=pinned,
            right_pinned=False,
            commutative=False,
        )
        if destination == source_register:
            destination, extra = self._allocator.acquire(
                exclude=frozenset({source_register}),
            )
            destination_prelude.extend(extra)

        self.instructions.extend(prelude)
        self.instructions.extend(destination_prelude)
        self._emit("MOV", destination, "0")
        self._emit("SUB", destination, source_register)
        self._bind_result(instruction.result, destination)

    def _logical_not(
        self,
        instruction: TACInstruction,
        live_after: set[str],
    ) -> None:
        assert instruction.result is not None
        assert instruction.arg1 is not None

        source_register, prelude, source_is_temp = self._load_operand(
            instruction.arg1
        )
        pinned = source_is_temp and instruction.arg1 in live_after
        destination, destination_prelude = self._select_destination(
            source_register,
            None,
            left_pinned=pinned,
            right_pinned=False,
            commutative=False,
        )

        self.instructions.extend(prelude)
        self.instructions.extend(destination_prelude)
        self._emit("CMP", source_register, "0")
        self._emit("MOV", destination, "1")
        true_label = self._new_comparison_label()
        self._emit("JZ", true_label)
        self._emit("MOV", destination, "0")
        self._emit("label", true_label)
        self._bind_result(instruction.result, destination)

    def _if_false(
        self,
        instruction: TACInstruction,
        live_after: set[str],
    ) -> None:
        assert instruction.result is not None
        assert instruction.arg1 is not None

        register, prelude, _ = self._load_operand(instruction.arg1)
        self.instructions.extend(prelude)
        self._emit("CMP", register, "0")
        self._emit("JZ", instruction.result)
        del live_after

    def _load_operand(
        self,
        operand: str,
        *,
        exclude: frozenset[str] = frozenset(),
    ) -> tuple[str, list[AsmInstruction], bool]:
        if _is_temp(operand):
            register, prelude = self._load_temp(operand, exclude=exclude)
            return register, prelude, True

        register, prelude = self._allocator.acquire(exclude=exclude)
        prelude.append(AsmInstruction("MOV", (register, self._operand_text(operand))))
        return register, prelude, False

    def _load_temp(
        self,
        temp: str,
        *,
        exclude: frozenset[str] = frozenset(),
    ) -> tuple[str, list[AsmInstruction]]:
        register = self._allocator.register_for(temp)
        if register is not None:
            return register, []

        register, prelude = self._allocator.acquire(exclude=exclude)
        slot = self._allocator.slot_for(temp)
        self._allocator.bind(temp, register)
        prelude.append(
            AsmInstruction(
                "LOAD",
                (register, self._allocator.format_slot(slot)),
            )
        )
        return register, prelude

    def _value_operand(
        self,
        operand: str,
        *,
        exclude: frozenset[str] = frozenset(),
    ) -> tuple[str, list[AsmInstruction], str | None]:
        if _is_temp(operand):
            register, prelude = self._load_temp(operand, exclude=exclude)
            return register, prelude, register
        return self._operand_text(operand), [], None

    def _select_destination(
        self,
        left_register: str,
        right_register: str | None,
        *,
        left_pinned: bool,
        right_pinned: bool,
        commutative: bool,
    ) -> tuple[str, list[AsmInstruction]]:
        for register in REGISTERS:
            if self._allocator.temp_in(register) is None:
                return register, []

        if not left_pinned:
            return left_register, []

        if right_register is not None and commutative and not right_pinned:
            return right_register, []

        operand_registers = {left_register}
        if right_register is not None:
            operand_registers.add(right_register)

        for register in REGISTERS:
            if register in operand_registers:
                continue
            temp = self._allocator.temp_in(register)
            if temp is None:
                return register, []
            slot = self._allocator.slot_for(temp)
            self._allocator.unbind_register(register)
            return register, [
                AsmInstruction(
                    "STORE",
                    (register, self._allocator.format_slot(slot)),
                )
            ]

        raise RuntimeError("no destination register available")

    def _bind_result(self, result: str | None, register: str) -> None:
        if result is not None and _is_temp(result):
            self._allocator.bind(result, register)

    def _emit(self, op: str, *args: str) -> None:
        self.instructions.append(AsmInstruction(op, args))

    def _new_comparison_label(self) -> str:
        self._label_count += 1
        return f"Lcmp{self._label_count}"

    @staticmethod
    def _operand_text(operand: str) -> str:
        if operand == "true":
            return "1"
        if operand == "false":
            return "0"
        if (
            operand.startswith('"')
            or _NUMBER_PATTERN.fullmatch(operand) is not None
        ):
            return operand
        return f"[{operand}]"

    @staticmethod
    def _uses(instruction: TACInstruction) -> set[str]:
        if instruction.op in {"label", "goto"}:
            return set()
        names = {instruction.arg1, instruction.arg2}
        return {
            name for name in names if name is not None and _is_temp(name)
        }

    @staticmethod
    def _defs(instruction: TACInstruction) -> set[str]:
        if instruction.op in _CONTROL_OPS or instruction.result is None:
            return set()
        result = instruction.result
        return {result} if _is_temp(result) else set()

    @classmethod
    def _live_out(cls, tac: Sequence[TACInstruction]) -> list[set[str]]:
        live_in: list[set[str]] = [set() for _ in tac]
        live_out: list[set[str]] = [set() for _ in tac]

        for index in range(len(tac) - 1, -1, -1):
            if index + 1 < len(tac):
                live_out[index] = live_in[index + 1]
            live_in[index] = cls._uses(tac[index]) | (
                live_out[index] - cls._defs(tac[index])
            )

        return live_out
