"""Tests for the Rich rendering of compilation results."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import cast

import pytest
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

import mini_compiler.render as render_module
from mini_compiler.ast_nodes import Expression, Statement
from mini_compiler.cli import main, render_result
from mini_compiler.compiler import CompilationResult, compile_source
from mini_compiler.render import build_sections, render

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PROJECT_ROOT / "examples"


def read_example(name: str) -> str:
    return (EXAMPLES_DIR / name).read_text(encoding="utf-8")


def render_text(
    result: CompilationResult,
    phase: str = "all",
    *,
    color: bool = False,
    width: int = 100,
) -> str:
    stream = StringIO()
    console = Console(
        file=stream,
        width=width,
        force_terminal=color,
        color_system="standard" if color else None,
    )

    render(result, phase, console=console)
    return stream.getvalue()


def title_lines(output: str) -> list[str]:
    titles = {"Tokens", "AST", "Symbols", "TAC", "Errors"}
    return [line for line in output.splitlines() if line in titles]


def test_rich_render_prints_every_phase_title() -> None:
    result = compile_source(read_example("walkthrough.mc"))

    output = render_text(result)

    assert title_lines(output) == ["Tokens", "AST", "Symbols", "TAC"]
    assert "=== Tokens ===" not in output


@pytest.mark.parametrize(
    ("phase", "expected"),
    [
        ("tokens", "Tokens"),
        ("ast", "AST"),
        ("symbols", "Symbols"),
        ("tac", "TAC"),
    ],
)
def test_phase_option_limits_output(phase: str, expected: str) -> None:
    result = compile_source(read_example("walkthrough.mc"))

    output = render_text(result, phase)

    assert title_lines(output) == [expected]


def test_ast_phase_is_compact_for_walkthrough() -> None:
    result = compile_source(read_example("walkthrough.mc"))

    output = render_text(result, "ast")

    lines = output.splitlines()
    assert len(lines) < 25
    assert lines[0] == "AST"
    assert "Program" in lines
    assert "BinaryOp +" in output
    assert "Literal 1.5" in output
    assert "line=" not in output
    assert "column=" not in output


def test_ast_phase_builds_a_tree() -> None:
    result = compile_source(read_example("walkthrough.mc"))

    sections = build_sections(result, "ast")

    assert isinstance(sections[0], Text)
    assert sections[0].plain == "AST"
    assert isinstance(sections[1], Tree)


def test_ast_renders_else_and_nested_blocks() -> None:
    source = """
bool flag = true;

if (flag) {
    int x = 1;
} else {
    int x = 2;
}

while (flag) {
    {
        int y = 3;
    }
}
"""
    result = compile_source(source)

    output = render_text(result, "ast")

    assert "If flag" in output
    assert "then" in output
    assert "else" in output
    assert "While flag" in output
    assert "body" in output
    assert "Block" in output


def test_ast_renders_compound_assignments_and_unary_operators() -> None:
    source = """
int x = 1;
x = 2;
x = x + 1;
x = -x;
"""
    result = compile_source(source)

    output = render_text(result, "ast")

    assert "VarDecl x: int = 1" in output
    assert "Assign x = 2" in output
    assert "BinaryOp +" in output
    assert "UnaryOp -" in output
    assert "Identifier x" in output


def test_ast_formats_nested_conditions_with_parentheses() -> None:
    source = """
int x = 1;
if (!(x >= 0)) {
    x = 0;
}
if (1 + 2 >= 3) {
    x = 0;
}
if (3 >= 1 + 2) {
    x = 0;
}
if (-x >= 0) {
    x = 0;
}
"""
    result = compile_source(source)

    output = render_text(result, "ast")

    assert "If !(x >= 0)" in output
    assert "If (1 + 2) >= 3" in output
    assert "If 3 >= (1 + 2)" in output
    assert "If -x >= 0" in output


def test_symbols_phase_renders_scope_and_symbols() -> None:
    result = compile_source(read_example("walkthrough.mc"))

    output = render_text(result, "symbols")

    assert "Scope" in output
    assert "global" in output
    assert "ratio" in output
    assert "float" in output
    assert "4:1" in output
    sections = build_sections(result, "symbols")
    assert isinstance(sections[1], Table)


def test_symbols_phase_reports_unavailable_for_syntactic_error() -> None:
    result = compile_source(read_example("syntactic_error.mc"))

    output = render_text(result, "symbols")

    assert "<unavailable>" in output


def test_tac_phase_highlights_labels() -> None:
    result = compile_source(read_example("walkthrough.mc"))

    output = render_text(result, "tac", color=True)

    assert "L1:" in output
    assert "\x1b[1;33m" in output


def test_tac_phase_reports_not_generated_after_failure() -> None:
    result = compile_source(read_example("lexical_error.mc"))

    output = render_text(result, "tac")

    assert "<not generated>" in output


def test_errors_are_red() -> None:
    result = compile_source(read_example("lexical_error.mc"))

    output = render_text(result, color=True)

    assert "2:11: Unexpected character '@'" in output
    assert "\x1b[31m" in output


def test_errors_render_one_line_per_diagnostic() -> None:
    result = compile_source("@ @")

    output = render_text(result)

    assert output.count("Unexpected character '@'") == 2


def test_ast_phase_reports_unavailable_after_lexical_error() -> None:
    result = compile_source(read_example("lexical_error.mc"))

    output = render_text(result, "ast")

    assert "<unavailable>" in output
    assert "Errors" in title_lines(output)


def test_empty_result_renders_placeholders() -> None:
    result = CompilationResult((), None, None, (), (), None)

    assert "<empty>" in render_text(result, "tokens")
    assert "<unavailable>" in render_text(result, "ast")
    assert "<unavailable>" in render_text(result, "symbols")
    assert "<empty>" in render_text(result, "tac")


def test_empty_program_renders_empty_symbol_table_and_tac() -> None:
    result = compile_source("")

    output = render_text(result)

    assert "<empty>" in output
    assert "global" in output


def test_unknown_phase_is_rejected() -> None:
    result = compile_source(read_example("walkthrough.mc"))

    with pytest.raises(ValueError, match="Unknown phase"):
        build_sections(result, "bogus")


def test_ast_renderers_reject_unsupported_nodes() -> None:
    tree = Tree("root")

    with pytest.raises(TypeError, match="Unsupported statement"):
        render_module._add_statement(tree, cast(Statement, object()))

    with pytest.raises(TypeError, match="Unsupported expression"):
        render_module._add_expression(tree, cast(Expression, object()))

    with pytest.raises(TypeError, match="Unsupported expression"):
        render_module._format_expression(cast(Expression, object()))


def test_cli_plain_matches_the_legacy_renderer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path = EXAMPLES_DIR / "walkthrough.mc"
    expected = render_result(compile_source(read_example("walkthrough.mc")))

    exit_code = main([str(source_path), "--plain"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == expected + "\n"


def test_cli_rich_output_and_phase_option(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path = EXAMPLES_DIR / "walkthrough.mc"

    exit_code = main([str(source_path), "--phase", "ast"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Program" in captured.out
    assert "Tokens" not in title_lines(captured.out)
    assert len(captured.out.splitlines()) < 25
