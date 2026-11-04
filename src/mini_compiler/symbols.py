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


@dataclass(frozen=True)
class SemanticError:
    """A semantic error with its 1-based source position."""

    message: str
    line: int
    column: int


GLOBAL_SCOPE_NAME = "global"


class SymbolTable:
    """Tracks symbols across a stack of nested scopes.

    Semantic errors are accumulated in ``errors`` instead of raising
    exceptions.
    """

    def __init__(self) -> None:
        self.errors: list[SemanticError] = []
        self._scopes: list[Scope] = [Scope(GLOBAL_SCOPE_NAME, None)]

    @property
    def current_scope(self) -> Scope:
        return self._scopes[-1]

    @property
    def scopes(self) -> tuple[Scope, ...]:
        return tuple(self._scopes)

    def enter_scope(self, name: str) -> Scope:
        """Push a new named scope nested inside the current one."""

        scope = Scope(name, self.current_scope)
        self._scopes.append(scope)
        return scope

    def exit_scope(self) -> Scope | None:
        """Pop the current scope, or return None when only global remains."""

        if len(self._scopes) == 1:
            return None
        return self._scopes.pop()

    def define(
        self,
        name: str,
        type_name: str,
        line: int,
        column: int,
    ) -> Symbol | None:
        """Declare a symbol in the current scope.

        Redeclaring a name in the same scope records an error and returns
        None. Shadowing a name from an enclosing scope is allowed.
        """

        scope = self.current_scope

        if name in scope.symbols:
            self.errors.append(
                SemanticError(
                    f"Variable '{name}' is already declared in scope '{scope.name}'",
                    line,
                    column,
                )
            )
            return None

        symbol = Symbol(name, type_name, scope.name, line, column)
        scope.symbols[name] = symbol
        return symbol

    def lookup(self, name: str, line: int, column: int) -> Symbol | None:
        """Find a symbol from the current scope up to the global scope.

        An unresolved lookup records an error at the given position.
        """

        scope: Scope | None = self.current_scope
        while scope is not None:
            if name in scope.symbols:
                return scope.symbols[name]
            scope = scope.enclosing_scope

        self.errors.append(SemanticError(f"Undefined variable '{name}'", line, column))
        return None

    def dump(self) -> str:
        """Return a readable representation of the active scope stack."""

        lines: list[str] = []

        for depth, scope in enumerate(self._scopes):
            indent = "  " * depth
            parent = (
                f" (enclosing: {scope.enclosing_scope.name})"
                if scope.enclosing_scope is not None
                else ""
            )
            lines.append(f"{indent}{scope.name}{parent}:")

            if not scope.symbols:
                lines.append(f"{indent}  <empty>")

            for symbol in scope.symbols.values():
                lines.append(
                    f"{indent}  {symbol.name}: {symbol.type_name} "
                    f"({symbol.line}:{symbol.column})"
                )

        return "\n".join(lines)
