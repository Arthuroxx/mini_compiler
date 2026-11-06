"""Tests for the symbol table."""

from mini_compiler.symbols import SemanticError, Symbol, SymbolTable


def test_global_scope_definition_and_lookup() -> None:
    table = SymbolTable()

    symbol = table.define("x", "int", 1, 1)

    assert table.current_scope.name == "global"
    assert symbol == Symbol("x", "int", "global", 1, 1)
    assert table.lookup("x", 2, 5) == symbol
    assert table.errors == []


def test_function_scope_links_to_global() -> None:
    table = SymbolTable()
    global_scope = table.current_scope

    function_scope = table.enter_scope("function")
    symbol = table.define("param", "float", 1, 10)

    assert function_scope.enclosing_scope is global_scope
    assert table.current_scope is function_scope
    assert symbol is not None
    assert symbol.scope_name == "function"
    assert table.lookup("param", 2, 5) == symbol
    assert table.errors == []


def test_lookup_walks_from_nested_block_to_global() -> None:
    table = SymbolTable()
    table.define("global_var", "int", 1, 1)
    table.enter_scope("function")
    table.define("param", "float", 2, 5)
    table.enter_scope("block")
    local = table.define("tmp", "string", 3, 9)

    assert table.lookup("tmp", 4, 1) == local
    param = table.lookup("param", 4, 5)
    global_var = table.lookup("global_var", 4, 9)
    assert param is not None
    assert global_var is not None
    assert param.type_name == "float"
    assert global_var.type_name == "int"
    assert table.errors == []


def test_variable_is_inaccessible_after_leaving_its_block() -> None:
    table = SymbolTable()
    table.enter_scope("block")
    table.define("tmp", "int", 1, 5)

    popped = table.exit_scope()

    assert popped is not None
    assert popped.name == "block"
    assert table.current_scope.name == "global"
    assert table.lookup("tmp", 3, 7) is None
    assert table.errors == [
        SemanticError("Undefined variable 'tmp'", 3, 7),
    ]


def test_redeclaration_in_the_same_scope_reports_an_error() -> None:
    table = SymbolTable()
    table.define("x", "int", 1, 1)

    result = table.define("x", "float", 2, 5)

    assert result is None
    assert table.errors == [
        SemanticError(
            "Variable 'x' is already declared in scope 'global'",
            2,
            5,
        )
    ]
    assert len(table.current_scope.symbols) == 1
    symbol = table.lookup("x", 3, 1)
    assert symbol is not None
    assert symbol.type_name == "int"


def test_shadowing_in_a_nested_scope_is_allowed() -> None:
    table = SymbolTable()
    table.define("x", "int", 1, 1)
    table.enter_scope("block")

    local = table.define("x", "float", 2, 5)

    assert local is not None
    assert local.type_name == "float"
    assert table.lookup("x", 3, 1) == local
    assert table.errors == []

    table.exit_scope()
    outer = table.lookup("x", 4, 1)
    assert outer is not None
    assert outer.type_name == "int"
    assert table.errors == []


def test_dump_is_readable_and_keeps_scope_hierarchy() -> None:
    table = SymbolTable()
    table.define("x", "int", 1, 1)
    table.enter_scope("function")
    table.define("p", "float", 2, 4)
    table.enter_scope("block")
    table.define("tmp", "string", 3, 8)

    assert table.dump() == (
        "global:\n"
        "  x: int (1:1)\n"
        "  function (enclosing: global):\n"
        "    p: float (2:4)\n"
        "    block (enclosing: function):\n"
        "      tmp: string (3:8)"
    )


def test_dump_of_empty_global_scope() -> None:
    assert SymbolTable().dump() == "global:\n  <empty>"


def test_global_scope_cannot_be_exited() -> None:
    table = SymbolTable()

    assert table.exit_scope() is None
    assert table.current_scope.name == "global"
