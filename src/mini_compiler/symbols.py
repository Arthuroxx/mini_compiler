"""Symbol table for tracking identifiers and their attributes."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Symbol:
    """A declared identifier with its type, scope, and source position."""

    name: str
    type_name: str
    scope_name: str
    line: int
    column: int


@dataclass
class Scope:
    """A named scope holding its local symbols and a link to its parent."""

    name: str
    enclosing_scope: Scope | None
    symbols: dict[str, Symbol] = field(default_factory=dict)
