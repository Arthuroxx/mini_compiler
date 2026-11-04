# mini_compiler

A compiler simulator built in Python 3.10+ for the Compilers course.

## Structure

- `src/mini_compiler/`: package containing the compiler modules.
- `examples/`: sample programs for valid and failing compilations.
- `tests/`: pytest tests.

## Requirements

- Python 3.10 or higher.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Usage

Compile a source file with:

```bash
python -m mini_compiler examples/valid.mc
```

The command prints the tokens, annotated AST, symbol table, semantic errors
when present, and generated three-address code. The pipeline stops at the
first phase that reports errors.

Sample programs:

- `examples/valid.mc`: completes every phase.
- `examples/lexical_error.mc`: stops after lexing.
- `examples/syntactic_error.mc`: stops after parsing.
- `examples/semantic_error.mc`: stops after semantic analysis.

## Tests

```bash
pytest
```
