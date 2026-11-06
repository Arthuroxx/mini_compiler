"""Intermediate representation (IR) generated from the validated AST."""

from __future__ import annotations

from dataclasses import dataclass

from mini_compiler.ast_nodes import (
    Assign,
    BinaryOp,
    Block,
    Expression,
    Identifier,
    If,
    Literal,
    Program,
    Statement,
    UnaryOp,
    VarDecl,
    While,
)
from mini_compiler.symbols import SemanticError

CASTABLE_OPERATORS = frozenset({"+", "-", "*", "/", "==", "!=", "<=", ">="})


@dataclass(frozen=True)
class TACInstruction:
    """A single three-address code instruction."""

    op: str
    result: str | None = None
    arg1: str | None = None
    arg2: str | None = None

    def format(self) -> str:
        """Return a readable representation of this instruction."""

        if self.op == "label":
            return f"{self.result}:"
        if self.op == "goto":
            return f"goto {self.result}"
        if self.op == "ifFalse":
            return f"ifFalse {self.arg1} goto {self.result}"
        if self.op == "int2float":
            return f"{self.result} = int2float {self.arg1}"
        if self.arg2 is not None:
            return f"{self.result} = {self.arg1} {self.op} {self.arg2}"
        if self.op == "=":
            return f"{self.result} = {self.arg1}"
        if self.arg1 is not None:
            return f"{self.result} = {self.op}{self.arg1}"
        return self.op

    def __str__(self) -> str:
        return self.format()


def format_instructions(instructions: list[TACInstruction]) -> str:
    """Return the instructions one per line in readable TAC form."""

    return "\n".join(instruction.format() for instruction in instructions)


class TACGenerator:
    """Generates three-address code from a semantically annotated AST."""

    def __init__(self) -> None:
        self.instructions: list[TACInstruction] = []
        self._temp_count = 0
        self._label_count = 0
        self._type_scopes: list[dict[str, str]] = [{}]

    def generate(
        self,
        program: Program,
        errors: list[SemanticError] | None = None,
    ) -> list[TACInstruction]:
        """Return TAC instructions, or an empty list when semantic errors exist."""

        self.instructions = []
        self._temp_count = 0
        self._label_count = 0
        self._type_scopes = [{}]

        if errors:
            return self.instructions

        self._generate_program(program)
        return self.instructions

    def _generate_program(self, node: Program) -> None:
        for statement in node.statements:
            self._generate_statement(statement)

    def _generate_statement(self, node: Statement) -> None:
        if isinstance(node, Block):
            self._type_scopes.append({})
            for statement in node.statements:
                self._generate_statement(statement)
            self._type_scopes.pop()
        elif isinstance(node, VarDecl):
            self._generate_var_decl(node)
        elif isinstance(node, Assign):
            self._generate_assign(node)
        elif isinstance(node, If):
            self._generate_if(node)
        elif isinstance(node, While):
            self._generate_while(node)
        else:
            raise TypeError(f"Unsupported statement: {type(node).__name__}")

    def _generate_var_decl(self, node: VarDecl) -> None:
        value = self._generate_expression(node.value)
        value = self._ensure_type(value, node.value.type_name, node.var_type)
        self._emit("=", node.name, value)
        self._type_scopes[-1][node.name] = node.var_type

    def _generate_assign(self, node: Assign) -> None:
        target_type = self._lookup_type(node.name)
        value = self._generate_expression(node.value)
        value = self._ensure_type(value, node.value.type_name, target_type)
        self._emit("=", node.name, value)

    def _generate_if(self, node: If) -> None:
        else_label = self._new_label()
        end_label = self._new_label() if node.else_branch is not None else None

        condition = self._generate_expression(node.condition)
        self._emit("ifFalse", else_label, condition)

        self._generate_statement(node.then_branch)

        if node.else_branch is not None:
            self._emit("goto", end_label)
            self._emit("label", else_label)
            self._generate_statement(node.else_branch)
            self._emit("label", end_label)
        else:
            self._emit("label", else_label)

    def _generate_while(self, node: While) -> None:
        start_label = self._new_label()
        end_label = self._new_label()

        self._emit("label", start_label)
        condition = self._generate_expression(node.condition)
        self._emit("ifFalse", end_label, condition)

        self._generate_statement(node.body)

        self._emit("goto", start_label)
        self._emit("label", end_label)

    def _generate_expression(self, node: Expression) -> str:
        if isinstance(node, Literal):
            return self._literal_operand(node.value)
        if isinstance(node, Identifier):
            return node.name
        if isinstance(node, BinaryOp):
            return self._generate_binary(node)
        if isinstance(node, UnaryOp):
            return self._generate_unary(node)
        raise TypeError(f"Unsupported expression: {type(node).__name__}")

    def _generate_binary(self, node: BinaryOp) -> str:
        left = self._generate_expression(node.left)
        right = self._generate_expression(node.right)

        if node.operator in CASTABLE_OPERATORS:
            if node.left.type_name == "int" and node.right.type_name == "float":
                left = self._ensure_type(left, "int", "float")
            elif node.left.type_name == "float" and node.right.type_name == "int":
                right = self._ensure_type(right, "int", "float")

        result = self._new_temp()
        self._emit(node.operator, result, left, right)
        return result

    def _generate_unary(self, node: UnaryOp) -> str:
        operand = self._generate_expression(node.operand)
        result = self._new_temp()
        self._emit(node.operator, result, operand)
        return result

    def _ensure_type(
        self,
        place: str,
        from_type: str | None,
        to_type: str | None,
    ) -> str:
        if from_type == "int" and to_type == "float":
            result = self._new_temp()
            self._emit("int2float", result, place)
            return result
        return place

    def _new_temp(self) -> str:
        self._temp_count += 1
        return f"t{self._temp_count}"

    def _new_label(self) -> str:
        self._label_count += 1
        return f"L{self._label_count}"

    def _lookup_type(self, name: str) -> str | None:
        for scope in reversed(self._type_scopes):
            if name in scope:
                return scope[name]
        return None

    def _emit(
        self,
        op: str,
        result: str | None = None,
        arg1: str | None = None,
        arg2: str | None = None,
    ) -> None:
        self.instructions.append(TACInstruction(op, result, arg1, arg2))

    @staticmethod
    def _literal_operand(value: int | float | str | bool) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return str(value)
