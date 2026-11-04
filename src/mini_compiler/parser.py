"""Recursive descent parser for the mini_compiler language.

The grammar below is written in EBNF. Every binary level is implemented
with a loop over its left-associative operators, so there is no left
recursion anywhere in the parser.

EBNF
----
program        = { statement } EOF ;
statement      = block | var_decl | assignment | if_stmt | while_stmt ;
block          = "{" { statement } "}" ;
var_decl       = type IDENT "=" expression ";" ;
type           = "int" | "float" | "string" | "bool" ;
assignment     = IDENT "=" expression ";" ;
if_stmt        = "if" "(" expression ")" block [ "else" block ] ;
while_stmt     = "while" "(" expression ")" block ;

expression     = logical_or ;
logical_or     = logical_and { "||" logical_and } ;
logical_and    = equality { "&&" equality } ;
equality       = relational { ( "==" | "!=" ) relational } ;
relational     = additive { ( "<=" | ">=" ) additive } ;
additive       = multiplicative { ( "+" | "-" ) multiplicative } ;
multiplicative = unary { ( "*" | "/" ) unary } ;
unary          = ( "!" | "-" ) unary | primary ;
primary        = INT | FLOAT | STRING | "true" | "false" | IDENT
               | "(" expression ")" ;
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mini_compiler.ast_nodes import (
    Assign,
    BinaryOp,
    Block,
    Expression,
    Identifier,
    If,
    Literal,
    Program,
    Statement,
    UnaryOp,
    VarDecl,
    While,
)
from mini_compiler.lexer import Token, TokenType

_ESCAPE_CHARACTERS = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "\\": "\\",
    '"': '"',
}

_TYPE_KEYWORDS = frozenset({"int", "float", "string", "bool"})


@dataclass(frozen=True)
class ParseError:
    """A syntax error with its 1-based source position."""

    message: str
    line: int
    column: int


class _ParseAbort(Exception):
    """Internal signal used to recover from a syntax error."""


class Parser:
    """Parses a token stream into an immutable AST."""

    def __init__(self, tokens: list[Token]) -> None:
        if not tokens or tokens[-1].type is not TokenType.EOF:
            raise ValueError("Token stream must end with an EOF token")
        self.tokens = tokens
        self.errors: list[ParseError] = []
        self._current = 0

    def parse(self) -> Program:
        """Return a Program node and accumulate syntax errors in ``errors``.

        Errors are recovered by synchronizing at the next semicolon.
        """

        self.errors.clear()
        self._current = 0
        start = self._peek()
        statements: list[Statement] = []

        while not self._check(TokenType.EOF):
            before = self._current
            try:
                statements.append(self._statement())
            except _ParseAbort:
                self._synchronize()
                if self._current == before:
                    self._advance()

        return Program(tuple(statements), start.line, start.column)

    def _statement(self) -> Statement:
        if self._check(TokenType.DELIMITER, "{"):
            return self._block()
        if self._check(TokenType.KEYWORD) and self._peek().value in _TYPE_KEYWORDS:
            return self._var_decl()
        if self._check(TokenType.KEYWORD, "if"):
            return self._if()
        if self._check(TokenType.KEYWORD, "while"):
            return self._while()
        if self._check(TokenType.ID):
            return self._assignment()

        token = self._peek()
        label = token.value or token.type.name
        self._error(f"Unexpected token {label!r}", token)
        raise _ParseAbort

    def _block(self) -> Block:
        opening = self._expect(TokenType.DELIMITER, "{", "Expected '{'")
        statements: list[Statement] = []

        while not self._check(TokenType.EOF) and not self._check(
            TokenType.DELIMITER, "}"
        ):
            before = self._current
            try:
                statements.append(self._statement())
            except _ParseAbort:
                self._synchronize()
                if self._current == before:
                    self._advance()

        self._expect(TokenType.DELIMITER, "}", "Expected '}'")
        return Block(tuple(statements), opening.line, opening.column)

    def _var_decl(self) -> VarDecl:
        kind = self._advance()
        name = self._expect(TokenType.ID, message="Expected identifier")
        self._expect(TokenType.OPERATOR, "=", "Expected '='")
        value = self._expression()
        self._expect(TokenType.DELIMITER, ";", "Expected ';'")
        return VarDecl(name.value, kind.value, value, kind.line, kind.column)

    def _assignment(self) -> Assign:
        name = self._expect(TokenType.ID, message="Expected identifier")
        self._expect(TokenType.OPERATOR, "=", "Expected '='")
        value = self._expression()
        self._expect(TokenType.DELIMITER, ";", "Expected ';'")
        return Assign(name.value, value, name.line, name.column)

    def _if(self) -> If:
        keyword = self._advance()
        self._expect(TokenType.DELIMITER, "(", "Expected '('")
        condition = self._expression()
        self._expect(TokenType.DELIMITER, ")", "Expected ')'")
        then_branch = self._block()

        else_branch = None
        if self._match(TokenType.KEYWORD, "else"):
            else_branch = self._block()

        return If(
            condition,
            then_branch,
            else_branch,
            keyword.line,
            keyword.column,
        )

    def _while(self) -> While:
        keyword = self._advance()
        self._expect(TokenType.DELIMITER, "(", "Expected '('")
        condition = self._expression()
        self._expect(TokenType.DELIMITER, ")", "Expected ')'")
        body = self._block()
        return While(condition, body, keyword.line, keyword.column)

    def _expression(self) -> Expression:
        return self._logical_or()

    def _logical_or(self) -> Expression:
        return self._binary(self._logical_and, frozenset({"||"}))

    def _logical_and(self) -> Expression:
        return self._binary(self._equality, frozenset({"&&"}))

    def _equality(self) -> Expression:
        return self._binary(self._relational, frozenset({"==", "!="}))

    def _relational(self) -> Expression:
        return self._binary(self._additive, frozenset({"<=", ">="}))

    def _additive(self) -> Expression:
        return self._binary(self._multiplicative, frozenset({"+", "-"}))

    def _multiplicative(self) -> Expression:
        return self._binary(self._unary, frozenset({"*", "/"}))

    def _binary(
        self,
        operand: Callable[[], Expression],
        operators: frozenset[str],
    ) -> Expression:
        left = operand()

        while self._check(TokenType.OPERATOR) and self._peek().value in operators:
            operator = self._advance()
            right = operand()
            left = BinaryOp(left, operator.value, right, left.line, left.column)

        return left

    def _unary(self) -> Expression:
        if self._check(TokenType.OPERATOR, "!") or self._check(
            TokenType.OPERATOR, "-"
        ):
            operator = self._advance()
            operand = self._unary()
            return UnaryOp(operator.value, operand, operator.line, operator.column)

        return self._primary()

    def _primary(self) -> Expression:
        token = self._peek()

        if self._check(TokenType.INT):
            self._advance()
            return Literal(int(token.value), token.line, token.column)

        if self._check(TokenType.FLOAT):
            self._advance()
            return Literal(float(token.value), token.line, token.column)

        if self._check(TokenType.STRING):
            self._advance()
            return Literal(_decode_string(token.value), token.line, token.column)

        if self._check(TokenType.KEYWORD, "true") or self._check(
            TokenType.KEYWORD, "false"
        ):
            self._advance()
            return Literal(token.value == "true", token.line, token.column)

        if self._check(TokenType.ID):
            self._advance()
            return Identifier(token.value, token.line, token.column)

        if self._check(TokenType.DELIMITER, "("):
            self._advance()
            expression = self._expression()
            self._expect(TokenType.DELIMITER, ")", "Expected ')'")
            return expression

        label = token.value or token.type.name
        self._error(f"Expected expression, got {label!r}", token)
        raise _ParseAbort

    def _check(self, token_type: TokenType, value: str | None = None) -> bool:
        token = self._peek()
        if token.type is not token_type:
            return False
        return value is None or token.value == value

    def _match(self, token_type: TokenType, value: str | None = None) -> Token | None:
        if self._check(token_type, value):
            return self._advance()
        return None

    def _expect(
        self,
        token_type: TokenType,
        value: str | None = None,
        message: str | None = None,
    ) -> Token:
        if self._check(token_type, value):
            return self._advance()

        token = self._peek()
        if message is not None:
            self._error(f"{message}, got {token.value!r}", token)
        else:
            expected = value or token_type.name
            self._error(f"Expected {expected}, got {token.value!r}", token)
        raise _ParseAbort

    def _advance(self) -> Token:
        token = self._peek()
        if token.type is not TokenType.EOF:
            self._current += 1
        return token

    def _peek(self, offset: int = 0) -> Token:
        index = min(self._current + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def _synchronize(self) -> None:
        while not self._check(TokenType.EOF):
            if self._check(TokenType.DELIMITER, ";"):
                self._advance()
                return
            if self._check(TokenType.DELIMITER, "}"):
                return
            self._advance()

    def _error(self, message: str, token: Token) -> None:
        self.errors.append(ParseError(message, token.line, token.column))


def _decode_string(raw: str) -> str:
    body = raw[1:-1]
    result: list[str] = []
    index = 0

    while index < len(body):
        character = body[index]
        if character == "\\" and index + 1 < len(body):
            result.append(_ESCAPE_CHARACTERS.get(body[index + 1], body[index + 1]))
            index += 2
        else:
            result.append(character)
            index += 1

    return "".join(result)
