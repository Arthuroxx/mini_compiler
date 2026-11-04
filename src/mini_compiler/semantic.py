"""Semantic analyzer: validates types, declarations, and scopes."""

from __future__ import annotations

from dataclasses import replace

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
from mini_compiler.symbols import SemanticError, SymbolTable

ERROR_TYPE = "error"
NUMERIC_TYPES = frozenset({"int", "float"})
ARITHMETIC_OPERATORS = frozenset({"+", "-", "*", "/"})
EQUALITY_OPERATORS = frozenset({"==", "!="})
RELATIONAL_OPERATORS = frozenset({"<=", ">="})
LOGICAL_OPERATORS = frozenset({"&&", "||"})


class SemanticAnalyzer:
    """Walks an AST, type-checks it, and returns an annotated copy."""

    def __init__(self) -> None:
        self.symbol_table = SymbolTable()
        self.errors: list[SemanticError] = self.symbol_table.errors

    def analyze(self, program: Program) -> tuple[Program, list[SemanticError]]:
        """Return an annotated AST and the accumulated semantic errors."""

        self.symbol_table = SymbolTable()
        self.errors = self.symbol_table.errors
        annotated = self._visit_program(program)
        return annotated, self.errors

    def _visit_program(self, node: Program) -> Program:
        statements = tuple(
            self._visit_statement(statement) for statement in node.statements
        )
        return replace(node, statements=statements)

    def _visit_statement(self, node: Statement) -> Statement:
        if isinstance(node, Block):
            return self._visit_block(node)
        if isinstance(node, VarDecl):
            return self._visit_var_decl(node)
        if isinstance(node, Assign):
            return self._visit_assign(node)
        if isinstance(node, If):
            return self._visit_if(node)
        if isinstance(node, While):
            return self._visit_while(node)
        raise TypeError(f"Unsupported statement: {type(node).__name__}")

    def _visit_block(self, node: Block) -> Block:
        self.symbol_table.enter_scope("block")
        statements = tuple(
            self._visit_statement(statement) for statement in node.statements
        )
        self.symbol_table.exit_scope()
        return replace(node, statements=statements)

    def _visit_var_decl(self, node: VarDecl) -> VarDecl:
        value, value_type = self._visit_expression(node.value)

        if value_type != ERROR_TYPE and not self._is_compatible(
            node.var_type, value_type
        ):
            self._error(
                f"Cannot assign '{value_type}' to variable '{node.name}' "
                f"of type '{node.var_type}'",
                node.value,
            )

        self.symbol_table.define(node.name, node.var_type, node.line, node.column)
        return replace(node, value=value)

    def _visit_assign(self, node: Assign) -> Assign:
        symbol = self.symbol_table.lookup(node.name, node.line, node.column)
        value, value_type = self._visit_expression(node.value)

        if (
            symbol is not None
            and value_type != ERROR_TYPE
            and not self._is_compatible(symbol.type_name, value_type)
        ):
            self._error(
                f"Cannot assign '{value_type}' to variable '{node.name}' "
                f"of type '{symbol.type_name}'",
                node.value,
            )

        return replace(node, value=value)

    def _visit_if(self, node: If) -> If:
        condition, condition_type = self._visit_expression(node.condition)

        if condition_type not in (ERROR_TYPE, "bool"):
            self._error(
                f"If condition must be of type 'bool', got '{condition_type}'",
                node.condition,
            )

        then_branch = self._visit_block(node.then_branch)
        else_branch = (
            self._visit_block(node.else_branch)
            if node.else_branch is not None
            else None
        )
        return replace(
            node,
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

    def _visit_while(self, node: While) -> While:
        condition, condition_type = self._visit_expression(node.condition)

        if condition_type not in (ERROR_TYPE, "bool"):
            self._error(
                f"While condition must be of type 'bool', got '{condition_type}'",
                node.condition,
            )

        body = self._visit_block(node.body)
        return replace(node, condition=condition, body=body)

    def _visit_expression(self, node: Expression) -> tuple[Expression, str]:
        if isinstance(node, BinaryOp):
            return self._visit_binary(node)
        if isinstance(node, UnaryOp):
            return self._visit_unary(node)
        if isinstance(node, Literal):
            return self._visit_literal(node)
        if isinstance(node, Identifier):
            return self._visit_identifier(node)
        raise TypeError(f"Unsupported expression: {type(node).__name__}")

    def _visit_literal(self, node: Literal) -> tuple[Literal, str]:
        if isinstance(node.value, bool):
            type_name = "bool"
        elif isinstance(node.value, int):
            type_name = "int"
        elif isinstance(node.value, float):
            type_name = "float"
        elif isinstance(node.value, str):
            type_name = "string"
        else:
            raise TypeError(f"Unsupported literal value: {node.value!r}")

        return replace(node, type_name=type_name), type_name

    def _visit_identifier(self, node: Identifier) -> tuple[Identifier, str]:
        symbol = self.symbol_table.lookup(node.name, node.line, node.column)

        if symbol is None:
            return replace(node, type_name=ERROR_TYPE), ERROR_TYPE

        return replace(node, type_name=symbol.type_name), symbol.type_name

    def _visit_binary(self, node: BinaryOp) -> tuple[BinaryOp, str]:
        left, left_type = self._visit_expression(node.left)
        right, right_type = self._visit_expression(node.right)

        if ERROR_TYPE in (left_type, right_type):
            result_type = ERROR_TYPE
        elif node.operator in LOGICAL_OPERATORS:
            result_type = self._check_logical(node, left_type, right_type)
        elif node.operator in EQUALITY_OPERATORS:
            result_type = self._check_equality(node, left_type, right_type)
        elif node.operator in RELATIONAL_OPERATORS:
            result_type = self._check_relational(node, left_type, right_type)
        elif node.operator in ARITHMETIC_OPERATORS:
            result_type = self._check_arithmetic(node, left_type, right_type)
        else:
            self._error(f"Unknown binary operator '{node.operator}'", node)
            result_type = ERROR_TYPE

        annotated = replace(
            node,
            left=left,
            right=right,
            type_name=result_type,
        )
        return annotated, result_type

    def _check_logical(
        self,
        node: BinaryOp,
        left_type: str,
        right_type: str,
    ) -> str:
        if left_type == "bool" and right_type == "bool":
            return "bool"

        self._error(
            f"Operator '{node.operator}' requires bool operands, "
            f"got '{left_type}' and '{right_type}'",
            node,
        )
        return ERROR_TYPE

    def _check_equality(
        self,
        node: BinaryOp,
        left_type: str,
        right_type: str,
    ) -> str:
        if self._are_comparable(left_type, right_type):
            return "bool"

        self._error(
            f"Operator '{node.operator}' cannot compare "
            f"'{left_type}' and '{right_type}'",
            node,
        )
        return ERROR_TYPE

    def _check_relational(
        self,
        node: BinaryOp,
        left_type: str,
        right_type: str,
    ) -> str:
        if left_type in NUMERIC_TYPES and right_type in NUMERIC_TYPES:
            return "bool"

        self._error(
            f"Operator '{node.operator}' requires numeric operands, "
            f"got '{left_type}' and '{right_type}'",
            node,
        )
        return ERROR_TYPE

    def _check_arithmetic(
        self,
        node: BinaryOp,
        left_type: str,
        right_type: str,
    ) -> str:
        if left_type in NUMERIC_TYPES and right_type in NUMERIC_TYPES:
            if "float" in (left_type, right_type):
                return "float"
            return "int"

        self._error(
            f"Operator '{node.operator}' requires numeric operands, "
            f"got '{left_type}' and '{right_type}'",
            node,
        )
        return ERROR_TYPE

    def _visit_unary(self, node: UnaryOp) -> tuple[UnaryOp, str]:
        operand, operand_type = self._visit_expression(node.operand)

        if operand_type == ERROR_TYPE:
            result_type = ERROR_TYPE
        elif node.operator == "!":
            if operand_type == "bool":
                result_type = "bool"
            else:
                self._error(
                    f"Operator '!' requires a bool operand, got '{operand_type}'",
                    node,
                )
                result_type = ERROR_TYPE
        elif node.operator == "-":
            if operand_type in NUMERIC_TYPES:
                result_type = operand_type
            else:
                self._error(
                    f"Operator '-' requires a numeric operand, got '{operand_type}'",
                    node,
                )
                result_type = ERROR_TYPE
        else:
            self._error(f"Unknown unary operator '{node.operator}'", node)
            result_type = ERROR_TYPE

        annotated = replace(node, operand=operand, type_name=result_type)
        return annotated, result_type

    @staticmethod
    def _is_compatible(target: str, source: str) -> bool:
        return target == source or (target == "float" and source == "int")

    @staticmethod
    def _are_comparable(left: str, right: str) -> bool:
        if left == right:
            return True
        return left in NUMERIC_TYPES and right in NUMERIC_TYPES

    def _error(self, message: str, node: Expression) -> None:
        self.errors.append(SemanticError(message, node.line, node.column))
