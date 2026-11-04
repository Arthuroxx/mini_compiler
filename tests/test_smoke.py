"""Smoke test: verifies that the package modules import correctly."""

import mini_compiler
from mini_compiler import ast_nodes, cli, ir, lexer, parser, semantic, symbols


def test_package_imports():
    assert mini_compiler is not None


def test_modules_import():
    modules = [lexer, ast_nodes, parser, symbols, semantic, ir, cli]
    assert all(module is not None for module in modules)
