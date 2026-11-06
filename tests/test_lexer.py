"""Tests for the lexer."""

from dataclasses import FrozenInstanceError

import pytest

from mini_compiler.lexer import Lexer, LexicalError, Token, TokenType


def tokenize(source: str) -> list[Token]:
    return Lexer(source).tokenize()


def types(source: str) -> list[TokenType]:
    return [token.type for token in tokenize(source)]


def test_keywords_and_identifiers() -> None:
    source = (
        "int float string bool if else while true false "
        "identifier _tmp var123 integer while1"
    )

    tokens = tokenize(source)

    assert [token.type for token in tokens[:-1]] == [
        TokenType.KEYWORD,
        TokenType.KEYWORD,
        TokenType.KEYWORD,
        TokenType.KEYWORD,
        TokenType.KEYWORD,
        TokenType.KEYWORD,
        TokenType.KEYWORD,
        TokenType.KEYWORD,
        TokenType.KEYWORD,
        TokenType.ID,
        TokenType.ID,
        TokenType.ID,
        TokenType.ID,
        TokenType.ID,
    ]
    assert [token.value for token in tokens[:-1]] == source.split()


def test_float_is_recognized_before_int() -> None:
    assert types("3.14 42 0.5 7") == [
        TokenType.FLOAT,
        TokenType.INT,
        TokenType.FLOAT,
        TokenType.INT,
        TokenType.EOF,
    ]


def test_strings_keep_their_quotes() -> None:
    tokens = tokenize('"hello world" ""')

    assert [token.type for token in tokens] == [
        TokenType.STRING,
        TokenType.STRING,
        TokenType.EOF,
    ]
    assert [token.value for token in tokens[:-1]] == ['"hello world"', '""']


def test_operators_and_delimiters() -> None:
    source = "== != <= >= && || ! = + - * / ( ) { } ;"

    tokens = tokenize(source)

    expected_values = source.split()
    assert [token.value for token in tokens[:-1]] == expected_values
    assert [token.type for token in tokens[:-1]] == [
        TokenType.OPERATOR,
        TokenType.OPERATOR,
        TokenType.OPERATOR,
        TokenType.OPERATOR,
        TokenType.OPERATOR,
        TokenType.OPERATOR,
        TokenType.OPERATOR,
        TokenType.OPERATOR,
        TokenType.OPERATOR,
        TokenType.OPERATOR,
        TokenType.OPERATOR,
        TokenType.OPERATOR,
        TokenType.DELIMITER,
        TokenType.DELIMITER,
        TokenType.DELIMITER,
        TokenType.DELIMITER,
        TokenType.DELIMITER,
    ]


def test_comments_are_ignored_and_positions_are_tracked() -> None:
    source = (
        "int a = 1; // line comment\n"
        "/* block\n"
        "comment */ float b = 2;"
    )

    tokens = tokenize(source)

    assert [token.value for token in tokens] == [
        "int",
        "a",
        "=",
        "1",
        ";",
        "float",
        "b",
        "=",
        "2",
        ";",
        "",
    ]
    assert tokens[5] == Token(TokenType.KEYWORD, "float", 3, 12)
    assert tokens[6] == Token(TokenType.ID, "b", 3, 18)
    assert tokens[-1] == Token(TokenType.EOF, "", 3, 24)


def test_lexical_errors_are_accumulated_without_stopping() -> None:
    source = 'int a = @;\n$ x = "oops\nint b = 2;'

    lexer = Lexer(source)
    tokens = lexer.tokenize()

    assert [token.value for token in tokens] == [
        "int",
        "a",
        "=",
        ";",
        "x",
        "=",
        "int",
        "b",
        "=",
        "2",
        ";",
        "",
    ]
    assert lexer.errors == [
        LexicalError("Unexpected character '@'", 1, 9),
        LexicalError("Unexpected character '$'", 2, 1),
        LexicalError("Unterminated string", 2, 7),
    ]
    assert tokens[-1] == Token(TokenType.EOF, "", 3, 11)


def test_unterminated_block_comment_is_reported() -> None:
    lexer = Lexer("int a;\n/* never closed")

    tokens = lexer.tokenize()

    assert [token.value for token in tokens] == ["int", "a", ";", ""]
    assert lexer.errors == [LexicalError("Unterminated block comment", 2, 1)]
    assert tokens[-1] == Token(TokenType.EOF, "", 2, 16)


def test_empty_source_produces_only_eof() -> None:
    assert tokenize("") == [Token(TokenType.EOF, "", 1, 1)]


def test_eof_position_after_comment_only_source() -> None:
    assert tokenize("// comment\n")[-1] == Token(TokenType.EOF, "", 2, 1)


def test_tokens_are_immutable() -> None:
    token = Token(TokenType.INT, "1", 1, 1)

    with pytest.raises(FrozenInstanceError):
        token.value = "2"  # type: ignore[misc]
