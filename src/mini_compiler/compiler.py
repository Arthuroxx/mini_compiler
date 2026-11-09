"""Compilation pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from mini_compiler.ast_nodes import Program
from mini_compiler.codegen import AsmInstruction, AssemblyGenerator
from mini_compiler.ir import TACGenerator, TACInstruction
from mini_compiler.lexer import Lexer, LexicalError, Token
from mini_compiler.parser import ParseError, Parser
from mini_compiler.semantic import SemanticAnalyzer
from mini_compiler.symbols import SemanticError, SymbolTable

CompilationError = LexicalError | ParseError | SemanticError


@dataclass(frozen=True)
class CompilationResult:
    """Artifacts and diagnostics produced by the compilation pipeline."""

    tokens: tuple[Token, ...]
    ast: Program | None
    symbol_table: SymbolTable | None
    tac: tuple[TACInstruction, ...]
    asm: tuple[AsmInstruction, ...]
    errors: tuple[CompilationError, ...]
    failed_phase: str | None


def compile_source(source: str) -> CompilationResult:
    """Run each compiler phase in order and stop at the first failure."""

    lexer = Lexer(source)
    tokens = tuple(lexer.tokenize())
    if lexer.errors:
        return CompilationResult(
            tokens,
            None,
            None,
            (),
            (),
            tuple(lexer.errors),
            "lexical",
        )

    parser = Parser(list(tokens))
    program = parser.parse()
    if parser.errors:
        return CompilationResult(
            tokens,
            program,
            None,
            (),
            (),
            tuple(parser.errors),
            "syntactic",
        )

    analyzer = SemanticAnalyzer()
    annotated, semantic_errors = analyzer.analyze(program)
    if semantic_errors:
        return CompilationResult(
            tokens,
            annotated,
            analyzer.symbol_table,
            (),
            (),
            tuple(semantic_errors),
            "semantic",
        )

    tac = tuple(TACGenerator().generate(annotated, semantic_errors))
    asm = tuple(AssemblyGenerator().generate(tac))
    return CompilationResult(
        tokens,
        annotated,
        analyzer.symbol_table,
        tac,
        asm,
        (),
        None,
    )
