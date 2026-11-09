# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-11-08

### Added

- Rich terminal renderer that prints tokens as a table, the annotated AST as a
  tree, the symbol table, TAC with highlighted labels, and target assembly.
- `--phase` to render a single phase (`tokens`, `ast`, `symbols`, `tac`,
  `asm`, or `all`) and `--plain` to keep the original plain-text output.
- `rich>=15.0,<16` as a runtime dependency.
- Target code generation from TAC with `MOV`, `ADD`, `SUB`, `MUL`, `DIV`,
  `CMP`, `JMP`, `JZ`, comparison jumps, labels, `INT2FLOAT`, `STORE`, and
  `LOAD`.
- Liveness-based register allocation for `R0`-`R2` with stack spilling from
  `0x2000`, demonstrated by `examples/spill.mc`.
- `asm` phase in the CLI, `--phase`, `--plain`, and the Rich renderer, with
  README and walkthrough documentation.

### Changed

- The default CLI output now uses the Rich renderer; the plain format remains
  available through `--plain`.
- The walkthrough documents the assembly phase and the spill behavior.

## [1.0.0] - 2026-11-07

### Added

- Continuous integration workflow that runs `ruff`, strict `mypy`, and
  `pytest` on Python 3.10, 3.11, and 3.12 for pull requests targeting
  `develop` and `main` and for pushes to `develop`.
- CI status badge in the README.
- `pytest-cov` development dependency and a 90% minimum coverage gate
  enforced by pytest and CI.
- Boundary and defensive tests for the lexer, parser, semantic analyzer,
  symbol table, TAC generator, CLI, and module entry point, raising total
  coverage to 99.48%.
- `docs/walkthrough.md`, following one program through tokens, AST, symbol
  table, semantic analysis, and TAC, with a real failing example per phase.
- `examples/walkthrough.mc` and `examples/type_error.mc` so every documented
  output is reproducible.
- Branch protection rules for `main` and `develop` requiring pull requests
  and passing CI checks.

### Changed

- Bumped the project version to 1.0.0.
- The CI test step now runs pytest with coverage reporting.

## [0.1.0] - 2026-11-06

### Added

- Lexical analysis with token positions and accumulated lexical diagnostics.
- Recursive descent parser producing an immutable AST with syntax error
  recovery at statement boundaries.
- Symbol table with nested scopes, declarations, shadowing, and lookups.
- Semantic analysis with type checking and expression annotations.
- Three-address code generation for expressions, control flow, and casts.
- Integrated compilation pipeline and CLI that run each phase in order and
  stop at the first failure.
- Example programs for valid input and for lexical, syntactic, and semantic
  errors.
- README documentation for the pipeline, phases, and quality checks.
- `ruff` and strict `mypy` quality tooling.
- Test suite covering the lexer, parser, symbol table, semantic analyzer,
  intermediate representation, and integration behavior.

[Unreleased]: https://github.com/Arthuroxx/mini_compiler/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Arthuroxx/mini_compiler/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Arthuroxx/mini_compiler/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/Arthuroxx/mini_compiler/releases/tag/v0.1.0
