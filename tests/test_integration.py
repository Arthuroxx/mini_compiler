"""Integration tests for the full compilation pipeline and CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from mini_compiler.cli import main, render_result
from mini_compiler.compiler import compile_source

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PROJECT_ROOT / "examples"


def read_example(name: str) -> str:
    return (EXAMPLES_DIR / name).read_text(encoding="utf-8")


def test_valid_example_completes_every_phase() -> None:
    result = compile_source(read_example("valid.mc"))

    assert result.failed_phase is None
    assert result.errors == ()
    assert result.tokens
    assert result.ast is not None
    assert result.symbol_table is not None
    assert result.tac


def test_lexical_error_example_stops_after_lexing() -> None:
    result = compile_source(read_example("lexical_error.mc"))

    assert result.failed_phase == "lexical"
    assert result.tokens
    assert result.ast is None
    assert result.symbol_table is None
    assert result.tac == ()
    assert result.errors[0].line == 2
    assert result.errors[0].column == 11


def test_syntactic_error_example_stops_after_parsing() -> None:
    result = compile_source(read_example("syntactic_error.mc"))

    assert result.failed_phase == "syntactic"
    assert result.tokens
    assert result.ast is not None
    assert result.symbol_table is None
    assert result.tac == ()
    assert result.errors[0].line == 2
    assert result.errors[0].column == 9


def test_semantic_error_example_stops_after_semantic_analysis() -> None:
    result = compile_source(read_example("semantic_error.mc"))

    assert result.failed_phase == "semantic"
    assert result.tokens
    assert result.ast is not None
    assert result.symbol_table is not None
    assert result.tac == ()
    assert result.errors[0].message == "Undefined variable 'missing'"


def test_render_valid_result_includes_all_four_sections_in_order() -> None:
    output = render_result(compile_source(read_example("valid.mc")))
    headings = [
        "=== Tokens ===",
        "=== AST ===",
        "=== Symbol Table ===",
        "=== TAC ===",
    ]

    positions = [output.index(heading) for heading in headings]

    assert positions == sorted(positions)
    assert "=== Errors ===" not in output


def test_render_stops_at_the_failing_phase() -> None:
    lexical = render_result(compile_source(read_example("lexical_error.mc")))
    syntactic = render_result(compile_source(read_example("syntactic_error.mc")))
    semantic = render_result(compile_source(read_example("semantic_error.mc")))

    assert "=== Tokens ===" in lexical
    assert "=== Errors ===" in lexical
    assert "=== AST ===" not in lexical
    assert "=== Symbol Table ===" not in lexical
    assert "=== TAC ===" not in lexical

    assert "=== AST ===" in syntactic
    assert "=== Errors ===" in syntactic
    assert "=== Symbol Table ===" not in syntactic
    assert "=== TAC ===" not in syntactic

    assert "=== Symbol Table ===" in semantic
    assert "=== Errors ===" in semantic
    assert "=== TAC ===" not in semantic


def test_cli_returns_exit_codes_for_each_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    expectations = [
        ("valid.mc", 0),
        ("lexical_error.mc", 1),
        ("syntactic_error.mc", 1),
        ("semantic_error.mc", 1),
    ]

    for name, expected_code in expectations:
        exit_code = main([str(EXAMPLES_DIR / name)])
        capsys.readouterr()
        assert exit_code == expected_code


def test_cli_reports_missing_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main([str(tmp_path / "missing.mc")])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert captured.err.startswith("error:")


def _run_module(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_path if not existing else source_path + os.pathsep + existing
    )

    return subprocess.run(
        [sys.executable, "-m", "mini_compiler", *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("name", "expected_code", "expected_section"),
    [
        ("valid.mc", 0, "=== TAC ==="),
        ("lexical_error.mc", 1, "=== Errors ==="),
        ("syntactic_error.mc", 1, "=== Errors ==="),
        ("semantic_error.mc", 1, "=== Errors ==="),
    ],
)
def test_running_the_module_prints_the_expected_phase(
    name: str,
    expected_code: int,
    expected_section: str,
) -> None:
    result = _run_module(str(EXAMPLES_DIR / name))

    assert result.returncode == expected_code
    assert expected_section in result.stdout
    assert result.stderr == ""
