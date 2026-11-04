"""Immutable abstract syntax tree (AST) node definitions.

Expression nodes carry an optional ``type_name`` annotation that the
semantic analyzer fills in.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Program:
    """Root node holding every statement in a program."""

    statements: tuple[Statement, ...]
    line: int
    column: int


@dataclass(frozen=True)
class Block:
    """A sequence of statements enclosed in braces."""

    statements: tuple[Statement, ...]
    line: int
    column: int


@dataclass(frozen=True)
class VarDecl:
    """A typed variable declaration with an initializer."""

    name: str
    var_type: str
    value: Expression
    line: int
    column: int


@dataclass(frozen=True)
class Assign:
    """An assignment of an expression to a variable."""

    name: str
    value: Expression
    line: int
    column: int


@dataclass(frozen=True)
class If:
    """A conditional statement with an optional else branch."""

    condition: Expression
    then_branch: Block
    else_branch: Block | None
    line: int
    column: int


@dataclass(frozen=True)
class While:
    """A while loop with a block body."""

    condition: Expression
    body: Block
    line: int
    column: int


@dataclass(frozen=True)
class BinaryOp:
    """A binary operation between two expressions."""

    left: Expression
    operator: str
    right: Expression
    line: int
    column: int
    type_name: str | None = None


@dataclass(frozen=True)
class UnaryOp:
    """A prefix unary operation applied to an expression."""

    operator: str
    operand: Expression
    line: int
    column: int
    type_name: str | None = None


@dataclass(frozen=True)
class Literal:
    """An integer, float, string, or boolean literal value."""

    value: int | float | str | bool
    line: int
    column: int
    type_name: str | None = None


@dataclass(frozen=True)
class Identifier:
    """A reference to a variable by name."""

    name: str
    line: int
    column: int
    type_name: str | None = None


Statement = Block | VarDecl | Assign | If | While
Expression = BinaryOp | UnaryOp | Literal | Identifier
