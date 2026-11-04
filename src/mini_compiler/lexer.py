"""Lexer: converts source code into a sequence of tokens."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Kinds of tokens recognized by the lexer."""

    INT = auto()
    FLOAT = auto()
    STRING = auto()
    KEYWORD = auto()
    ID = auto()
    OPERATOR = auto()
    DELIMITER = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    """A lexical token with its 1-based source position."""

    type: TokenType
    value: str
    line: int
    column: int


@dataclass(frozen=True)
class LexicalError:
    """A lexical error with its 1-based source position."""

    message: str
    line: int
    column: int
