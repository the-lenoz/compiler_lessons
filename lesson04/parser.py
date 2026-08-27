from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass
class Block:
    first_statement: Stmt
    next_block: Block | None

@dataclass
class Stmt:
    pass


@dataclass
class Assignment(Stmt):
    id: Id
    expr: Expr

@dataclass
class Return(Stmt):
    expr: Expr


@dataclass
class Expr:
    def evaluate(self):
        pass


@dataclass
class Term(Expr):
    pass


@dataclass
class Atom(Term):
    pass


@dataclass
class Number(Atom):
    value: int

    def evaluate(self):
        return self.value


@dataclass
class BinOP:
    l_child: Expr | None
    r_child: Expr | None


@dataclass
class Sum(Expr, BinOP):
    def evaluate(self):
        if self.r_child is not None and self.l_child is not None:
            return self.l_child.evaluate() + self.r_child.evaluate()
        return None


@dataclass
class Sub(Expr, BinOP):
    def evaluate(self):
        if self.r_child is not None and self.l_child is not None:
            return self.l_child.evaluate() - self.r_child.evaluate()
        return None


@dataclass
class Mul(Term, BinOP):
    def evaluate(self):
        if self.r_child is not None and self.l_child is not None:
            return self.l_child.evaluate() * self.r_child.evaluate()
        return None


@dataclass
class Div(Term, BinOP):
    def evaluate(self):
        if self.r_child is not None and self.l_child is not None:
            return self.l_child.evaluate() // self.r_child.evaluate()
        return None


@dataclass
class ParenExpr(Atom):
    expr: Expr | None

    def evaluate(self):
        return self.expr.evaluate()


@dataclass
class Id(Atom):
    value: str


class Parser:
    source: str
    cursor: int

    def __init__(self, source: str):
        self.source = source
        self.cursor = 0

    def parse(self):
        program = self._parse_program()
        if self.cursor < len(self.source):
            print(f"Warn: unexpected continuation ignored: '{self.source[self.cursor:]}'", file=sys.stderr)
        return program

    @staticmethod
    def _fix_order(expr: Expr | None) -> Expr | None:
        if expr is None:
            return None

        if isinstance(expr, BinOP):
            expr.l_child = Parser._fix_order(expr.l_child)
            expr.r_child = Parser._fix_order(expr.r_child)

            if (expr.r_child and
                    (isinstance(expr.r_child, (Sum, Sub)) and isinstance(expr, (Sum, Sub)) or
                     isinstance(expr.r_child, (Mul, Div)) and isinstance(expr, (Mul, Div)))):
                root = expr.r_child
                expr.r_child = root.l_child
                root.l_child = expr

                root.l_child = Parser._fix_order(root.l_child)

                return root
        elif isinstance(expr, ParenExpr):
            expr.expr = Parser._fix_order(expr.expr)

        return expr

    def _parse_program(self):
        return self._parse_block()

    def _parse_block(self):
        old_cursor = self.cursor

        first = self._parse_stmt()
        if not first:
            self.cursor = old_cursor
            return None

        next_block = self._parse_block()

        return Block(first, next_block)

    def _parse_stmt(self):
        return self._parse_return() or self._parse_assignment()

    def _parse_return(self):
        old_cursor = self.cursor

        if not self._match("return"):
            self.cursor = old_cursor
            return None

        expr = self._parse_expr()

        if expr is None or not self._match(";"):
            self.cursor = old_cursor
            return None

        return Return(expr)

    def _parse_assignment(self):
        old_cursor = self.cursor

        identifier = self._parse_id()
        if not identifier or not self._match("="):
            self.cursor = old_cursor
            return None

        expr = self._parse_expr()
        if expr is None or not self._match(";"):
            self.cursor = old_cursor
            return None

        return Assignment(identifier, expr)

    def _parse_expr(self):
        expr = self._parse_sum() or self._parse_sub() or self._parse_term()
        return Parser._fix_order(expr)

    def _parse_sum(self):
        old_cursor = self.cursor

        l_child = self._parse_term()
        if not l_child or not self._match("+"):
            self.cursor = old_cursor
            return None

        r_child = self._parse_expr()
        if not r_child:
            self.cursor = old_cursor
            return None

        return Sum(l_child, r_child)

    def _parse_sub(self):
        old_cursor = self.cursor

        l_child = self._parse_term()
        if not l_child or not self._match("-"):
            self.cursor = old_cursor
            return None

        r_child = self._parse_expr()
        if not r_child:
            self.cursor = old_cursor
            return None

        return Sub(l_child, r_child)

    def _parse_term(self):
        return self._parse_mul() or self._parse_div() or self._parse_atom()

    def _parse_mul(self):
        old_cursor = self.cursor

        l_child = self._parse_atom()
        if not l_child or not self._match("*"):
            self.cursor = old_cursor
            return None

        r_child = self._parse_term()
        if not r_child:
            self.cursor = old_cursor
            return None

        return Mul(l_child, r_child)

    def _parse_div(self):
        old_cursor = self.cursor

        l_child = self._parse_atom()
        if not l_child or not self._match("/"):
            self.cursor = old_cursor
            return None

        r_child = self._parse_term()
        if not r_child:
            self.cursor = old_cursor
            return None

        return Div(l_child, r_child)

    def _parse_atom(self):
        return self._parse_paren_expr() or self._parse_number() or self._parse_id()

    def _parse_paren_expr(self):
        old_cursor = self.cursor

        if not self._match("("):
            self.cursor = old_cursor
            return None

        child_expr = self._parse_expr()

        if child_expr is None or not self._match(")"):
            self.cursor = old_cursor
            return None

        return ParenExpr(child_expr)

    def _parse_id(self):
        """Считывает идентификатор, игнорируя пробелы, и сдвигает курсор"""

        # Сохраняем курсор, чтобы вернуть обратно, если спарсить не получится
        old_cursor = self.cursor

        self._skip_spaces()

        # Сохраняам начало числа
        begin = self.cursor

        # Двигаемся, пока захватываются ещё валидные символы
        while self.cursor < len(self.source) and (self.source[self.cursor].isalpha() or
                                                  self.source[self.cursor] == '_' or
                                                  self.cursor != begin and self.source[self.cursor].isdigit()):
            self.cursor += 1

        # Если не было ни одного символа - имени нет. восстанавливаем курсор и выходим
        if begin == self.cursor:
            self.cursor = old_cursor
            return None

        value = self.source[begin:self.cursor]

        # Идентификатор есть. Возвращаем его
        return Id(value)

    def _parse_number(self):
        """Считывает число, игнорируя пробелы, и сдвигает курсор"""

        # Сохраняем курсор, чтобы вернуть обратно, если спарсить число не получится
        old_cursor = self.cursor

        self._skip_spaces()

        # Сохраняам начало числа
        begin = self.cursor

        # Двигаемся, пока захватываются ещё цифры
        while self.cursor < len(self.source) and (self.source[self.cursor].isdigit() or
                                                  self.cursor == begin and self.source[self.cursor] == '-'):
            self.cursor += 1

        # Если не было ни одной цифры - числа нет. восстанавливаем курсор и выходим
        if begin == self.cursor:
            self.cursor = old_cursor
            return None

        value = self.source[begin:self.cursor]

        # Число есть. Возвращаем его
        return Number(int(value))

    def _match(self, expected: str):
        """Проверяет, что дальше в источнике идёт ожидаемая строка, и сдвигает курсор"""
        old_cursor = self.cursor
        self._skip_spaces()
        if not self.source[self.cursor:].startswith(expected):
            self.cursor = old_cursor
            return False

        self.cursor += len(expected)
        return True

    def _skip_spaces(self):
        """Двигает курсор, пропуская пробельные символы"""

        # Пока текущий символ - пробел, и мы не дошли до конца - двигаем курсор дальше
        while self.cursor < len(self.source) and self.source[self.cursor].isspace():
            self.cursor += 1



