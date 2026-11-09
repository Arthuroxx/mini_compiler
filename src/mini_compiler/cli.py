"""Command-line interface for compiling a source file."""

from __future__ import annotations

import argparse
import pprint
import sys
from collections.abc import Sequence
from pathlib import Path

from mini_compiler.compiler import (
    CompilationError,
    CompilationResult,
    compile_source,
)
from mini_compiler.lexer import Token
from mini_compiler.render import PHASE_CHOICES
from mini_compiler.render import render as render_rich


def render_result(result: CompilationResult) -> str:
    """Render the artifacts and diagnostics of a compilation result."""

    lines: list[str] = ["=== Tokens ==="]
    if result.tokens:
        lines.extend(_format_token(token) for token in result.tokens)
    else:
        lines.append("<empty>")

    if result.ast is not None:
        lines.extend(
            [
                "",
                "=== AST ===",
                pprint.pformat(result.ast, width=88, sort_dicts=False),
            ]
        )

    if result.symbol_table is not None:
        lines.extend(
            [
                "",
                "=== Symbol Table ===",
                result.symbol_table.dump(),
            ]
        )

    if result.errors:
        lines.extend(["", "=== Errors ==="])
        lines.extend(_format_error(error) for error in result.errors)

    if result.failed_phase is None:
        lines.extend(["", "=== TAC ==="])
        if result.tac:
            lines.extend(instruction.format() for instruction in result.tac)
        else:
            lines.append("<empty>")

        lines.extend(["", "=== ASM ==="])
        if result.asm:
            lines.extend(instruction.format() for instruction in result.asm)
        else:
            lines.append("<empty>")

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface and return a process exit code."""

    args = _build_argument_parser().parse_args(argv)

    try:
        source = args.path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    result = compile_source(source)
    if args.plain:
        print(render_result(result))
    else:
        render_rich(result, args.phase)
    return 0 if result.failed_phase is None else 1


def _format_token(token: Token) -> str:
    return f"{token.type.name} {token.value!r} ({token.line}:{token.column})"


def _format_error(error: CompilationError) -> str:
    return f"{error.line}:{error.column}: {error.message}"


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mini_compiler",
        description="Compile a mini_compiler source file and print each phase.",
    )
    parser.add_argument("path", type=Path, help="path to a .mc source file")
    parser.add_argument(
        "--phase",
        choices=PHASE_CHOICES,
        default="all",
        help="phase to render (default: all)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="print the original plain-text output",
    )
    return parser
