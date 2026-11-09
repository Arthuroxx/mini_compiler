"""Rich terminal rendering for compilation results."""

from __future__ import annotations

import re
from typing import Final

from rich import box
from rich.console import Console, RenderableType
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from mini_compiler.ast_nodes import (
    Assign,
    BinaryOp,
    Block,
    Expression,
    Identifier,
    If,
    Literal,
    Statement,
    UnaryOp,
    VarDecl,
    While,
)
from mini_compiler.compiler import CompilationResult
from mini_compiler.ir import TACInstruction

PHASE_CHOICES: Final[tuple[str, ...]] = ("tokens", "ast", "symbols", "tac", "all")

_PHASE_TITLES: Final[dict[str, str]] = {
    "tokens": "Tokens",
    "ast": "AST",
    "symbols": "Symbols",
    "tac": "TAC",
}
_TITLE_STYLE = "bold cyan"
_LABEL_STYLE = "bold yellow"
_ERROR_STYLE = "red"
_MUTED_STYLE = "dim"
_LABEL_PATTERN = re.compile(r"\bL\d+\b")


def render(
    result: CompilationResult,
    phase: str = "all",
    *,
    console: Console | None = None,
) -> None:
    """Print the selected compiler phases with Rich formatting."""

    output = console if console is not None else Console()
    sections = build_sections(result, phase)

    for index in range(0, len(sections), 2):
        if index:
            output.print()
        output.print(sections[index])
        output.print(sections[index + 1])


def build_sections(
    result: CompilationResult,
    phase: str = "all",
) -> list[RenderableType]:
    """Build the renderables for the requested phase."""

    if phase not in PHASE_CHOICES:
        raise ValueError(f"Unknown phase: {phase}")

    phases = _selected_phases(result, phase)
    sections: list[RenderableType] = []

    for selected in phases:
        sections.append(_title(selected))
        sections.append(_phase_renderable(result, selected))

    if result.errors:
        sections.append(_title("Errors"))
        sections.append(_errors(result))

    return sections


def _selected_phases(result: CompilationResult, phase: str) -> list[str]:
    if phase != "all":
        return [phase]

    phases = ["tokens"]
    if result.ast is not None:
        phases.append("ast")
    if result.symbol_table is not None:
        phases.append("symbols")
    if result.failed_phase is None:
        phases.append("tac")
    return phases


def _phase_renderable(
    result: CompilationResult,
    phase: str,
) -> Table | Text | Tree:
    if phase == "tokens":
        return _tokens_table(result)
    if phase == "ast":
        return _ast_tree(result)
    if phase == "symbols":
        return _symbols_table(result)
    return _tac_text(result)


def _title(label: str) -> Text:
    return Text(_PHASE_TITLES.get(label, label), style=_TITLE_STYLE)


def _tokens_table(result: CompilationResult) -> Table | Text:
    if not result.tokens:
        return Text("<empty>", style=_MUTED_STYLE)

    table = Table(box=box.SIMPLE, header_style="bold")
    table.add_column("Type", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    table.add_column("Position", justify="right", style="magenta")

    for token in result.tokens:
        table.add_row(
            token.type.name,
            repr(token.value),
            f"{token.line}:{token.column}",
        )

    return table


def _ast_tree(result: CompilationResult) -> Tree | Text:
    if result.ast is None:
        return Text("<unavailable>", style=_MUTED_STYLE)

    tree = Tree(Text("Program", style="bold"), guide_style="dim")
    for statement in result.ast.statements:
        _add_statement(tree, statement)
    return tree


def _add_statement(parent: Tree, statement: Statement) -> None:
    if isinstance(statement, VarDecl):
        _add_declaration(parent, statement)
    elif isinstance(statement, Assign):
        _add_assignment(parent, statement)
    elif isinstance(statement, If):
        node = parent.add(Text(f"If {_format_expression(statement.condition)}"))
        _add_branch(node, "then", statement.then_branch)
        if statement.else_branch is not None:
            _add_branch(node, "else", statement.else_branch)
    elif isinstance(statement, While):
        node = parent.add(Text(f"While {_format_expression(statement.condition)}"))
        _add_branch(node, "body", statement.body)
    elif isinstance(statement, Block):
        node = parent.add(Text("Block"))
        for child in statement.statements:
            _add_statement(node, child)
    else:
        raise TypeError(f"Unsupported statement: {type(statement).__name__}")


def _add_declaration(parent: Tree, statement: VarDecl) -> None:
    label = f"VarDecl {statement.name}: {statement.var_type}"
    if isinstance(statement.value, (Literal, Identifier)):
        parent.add(Text(f"{label} = {_format_expression(statement.value)}"))
        return

    node = parent.add(Text(label))
    _add_expression(node, statement.value)


def _add_assignment(parent: Tree, statement: Assign) -> None:
    if isinstance(statement.value, (Literal, Identifier)):
        parent.add(
            Text(f"Assign {statement.name} = {_format_expression(statement.value)}")
        )
        return

    node = parent.add(Text(f"Assign {statement.name}"))
    _add_expression(node, statement.value)


def _add_branch(parent: Tree, label: str, block: Block) -> None:
    node = parent.add(Text(label))
    for statement in block.statements:
        _add_statement(node, statement)


def _add_expression(parent: Tree, expression: Expression) -> None:
    if isinstance(expression, Literal):
        parent.add(Text(f"Literal {expression.value!r}"))
    elif isinstance(expression, Identifier):
        parent.add(Text(f"Identifier {expression.name}"))
    elif isinstance(expression, UnaryOp):
        node = parent.add(Text(f"UnaryOp {expression.operator}"))
        _add_expression(node, expression.operand)
    elif isinstance(expression, BinaryOp):
        node = parent.add(Text(f"BinaryOp {expression.operator}"))
        _add_expression(node, expression.left)
        _add_expression(node, expression.right)
    else:
        raise TypeError(f"Unsupported expression: {type(expression).__name__}")


def _format_expression(expression: Expression) -> str:
    if isinstance(expression, Literal):
        return repr(expression.value)
    if isinstance(expression, Identifier):
        return expression.name
    if isinstance(expression, UnaryOp):
        operand = _format_expression(expression.operand)
        if isinstance(expression.operand, (BinaryOp, UnaryOp)):
            operand = f"({operand})"
        return f"{expression.operator}{operand}"
    if isinstance(expression, BinaryOp):
        left = _format_expression(expression.left)
        right = _format_expression(expression.right)
        if isinstance(expression.left, BinaryOp):
            left = f"({left})"
        if isinstance(expression.right, BinaryOp):
            right = f"({right})"
        return f"{left} {expression.operator} {right}"
    raise TypeError(f"Unsupported expression: {type(expression).__name__}")


def _symbols_table(result: CompilationResult) -> Table | Text:
    if result.symbol_table is None:
        return Text("<unavailable>", style=_MUTED_STYLE)

    table = Table(box=box.SIMPLE, header_style="bold")
    table.add_column("Scope", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Type", style="magenta")
    table.add_column("Position", justify="right")

    for scope in result.symbol_table.scopes:
        if not scope.symbols:
            table.add_row(scope.name, "<empty>", "", "")
            continue
        for symbol in scope.symbols.values():
            table.add_row(
                scope.name,
                symbol.name,
                symbol.type_name,
                f"{symbol.line}:{symbol.column}",
            )

    return table


def _tac_text(result: CompilationResult) -> Text:
    if result.failed_phase is not None:
        return Text("<not generated>", style=_MUTED_STYLE)
    if not result.tac:
        return Text("<empty>", style=_MUTED_STYLE)

    text = Text()
    for index, instruction in enumerate(result.tac):
        if index:
            text.append("\n")
        text.append_text(_tac_line(instruction))
    return text


def _tac_line(instruction: TACInstruction) -> Text:
    line = instruction.format()
    if line.endswith(":"):
        return Text(line, style=_LABEL_STYLE)

    text = Text()
    start = 0
    for match in _LABEL_PATTERN.finditer(line):
        text.append(line[start : match.start()])
        text.append(match.group(), style=_LABEL_STYLE)
        start = match.end()
    text.append(line[start:])
    return text


def _errors(result: CompilationResult) -> Text:
    text = Text()
    for index, error in enumerate(result.errors):
        if index:
            text.append("\n")
        text.append(
            f"{error.line}:{error.column}: {error.message}",
            style=_ERROR_STYLE,
        )
    return text
