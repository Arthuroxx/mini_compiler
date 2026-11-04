"""Lexer: converts source code into a sequence of tokens."""

from __future__ import annotations

import re
from bisect import bisect_right
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


TOKEN_PATTERN = re.compile(
    r"""
    (?P<BLOCK_COMMENT>/\*[\s\S]*?\*/)
  | (?P<UNTERMINATED_BLOCK_COMMENT>/\*[\s\S]*)
  | (?P<LINE_COMMENT>//[^\n]*)
  | (?P<STRING>"(?:\\.|[^"\\\n])*")
  | (?P<UNTERMINATED_STRING>"(?:\\.|[^"\\\n])*)
  | (?P<FLOAT>\d+\.\d+)
  | (?P<INT>\d+)
  | (?P<KEYWORD>\b(?:int|float|string|bool|if|else|while|true|false)\b)
  | (?P<ID>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<OPERATOR>==|!=|<=|>=|&&|\|\||[!=+\-*/])
  | (?P<DELIMITER>[(){};])
  | (?P<WHITESPACE>[^\S\n]+)
  | (?P<NEWLINE>\n)
  | (?P<MISMATCH>.)
    """,
    re.VERBOSE,
)

TOKEN_TYPES = {
    "STRING": TokenType.STRING,
    "FLOAT": TokenType.FLOAT,
    "INT": TokenType.INT,
    "KEYWORD": TokenType.KEYWORD,
    "ID": TokenType.ID,
    "OPERATOR": TokenType.OPERATOR,
    "DELIMITER": TokenType.DELIMITER,
}

IGNORED_GROUPS = frozenset({"BLOCK_COMMENT", "LINE_COMMENT", "WHITESPACE", "NEWLINE"})


class Lexer:
    """Tokenizes source code while collecting lexical errors."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.errors: list[LexicalError] = []

    def tokenize(self) -> list[Token]:
        """Return the tokens in the source, including the final EOF token.

        Lexical errors are accumulated in ``self.errors`` and do not stop
        tokenization.
        """

        self.errors = []
        line_starts = self._line_starts()
        tokens: list[Token] = []

        for match in TOKEN_PATTERN.finditer(self.source):
            group = match.lastgroup
            value = match.group()
            line, column = self._position(match.start(), line_starts)

            if group in IGNORED_GROUPS:
                continue
            if group == "UNTERMINATED_BLOCK_COMMENT":
                self.errors.append(
                    LexicalError("Unterminated block comment", line, column)
                )
                continue
            if group == "UNTERMINATED_STRING":
                self.errors.append(LexicalError("Unterminated string", line, column))
                continue
            if group == "MISMATCH":
                self.errors.append(
                    LexicalError(f"Unexpected character {value!r}", line, column)
                )
                continue

            token_type = TOKEN_TYPES.get(group)
            if token_type is not None:
                tokens.append(Token(token_type, value, line, column))

        line, column = self._position(len(self.source), line_starts)
        tokens.append(Token(TokenType.EOF, "", line, column))
        return tokens

    def _line_starts(self) -> list[int]:
        starts = [0]
        starts.extend(match.end() for match in re.finditer("\n", self.source))
        return starts

    @staticmethod
    def _position(index: int, line_starts: list[int]) -> tuple[int, int]:
        line_index = bisect_right(line_starts, index) - 1
        return line_index + 1, index - line_starts[line_index] + 1
