import sys
from dataclasses import dataclass

@dataclass
class Expr:
    def evaluate(self):
        """Вычисляет значение выражения"""
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
        """Возвращает значение числового литерала"""
        return self.value


@dataclass
class BinOP:
    l_child: Expr | None
    r_child: Expr | None


@dataclass
class Sum(Expr, BinOP):
    def evaluate(self):
        """Вычисляет сумму дочерних выражений"""
        if self.r_child is not None and self.l_child is not None:
            return self.l_child.evaluate() + self.r_child.evaluate()
        return None


@dataclass
class Sub(Expr, BinOP):
    def evaluate(self):
        """Вычисляет разность дочерних выражений"""
        if self.r_child is not None and self.l_child is not None:
            return self.l_child.evaluate() - self.r_child.evaluate()
        return None


@dataclass
class Mul(Term, BinOP):
    def evaluate(self):
        """Вычисляет произведение дочерних выражений"""
        if self.r_child is not None and self.l_child is not None:
            return self.l_child.evaluate() * self.r_child.evaluate()
        return None


@dataclass
class Div(Term, BinOP):
    def evaluate(self):
        """Вычисляет целочисленное частное дочерних выражений"""
        if self.r_child is not None and self.l_child is not None:
            return self.l_child.evaluate() // self.r_child.evaluate()
        return None


@dataclass
class ParenExpr(Atom):
    expr: Expr | None
    def evaluate(self):
        """Вычисляет выражение внутри скобок"""
        return self.expr.evaluate()


class Parser:
    source: str
    cursor: int

    def __init__(self, source: str):
        """Создаёт парсер для переданного исходного текста"""
        self.source = source
        self.cursor = 0

    def parse(self):
        """Разбирает исходный текст и возвращает AST выражения"""
        expr = self._parse_expr()
        if self.cursor < len(self.source):
            print(f"Warn: unexpected continuation ignored: '{self.source[self.cursor:]}'", file=sys.stderr)
        return Parser._fix_order(expr)

    @staticmethod
    def _fix_order(expr: Expr | None) -> Expr | None:
        """Исправляет дерево с учётом порядка выполнения одноуровневых операций"""
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


    def _skip_spaces(self):
        """Двигает курсор, пропуская пробельные символы"""

        # Пока текущий символ - пробел, и мы не дошли до конца - двигаем курсор дальше
        while self.cursor < len(self.source) and self.source[self.cursor].isspace():
            self.cursor += 1

    def _parse_expr(self):
        """Считывает арифметическое выражение"""
        return self._parse_sum() or self._parse_sub() or self._parse_term()

    def _parse_sum(self):
        """Считывает выражение сложения"""
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
        """Считывает выражение вычитания"""
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
        """Считывает терм: умножение, деление или атом"""
        return self._parse_mul() or self._parse_div() or self._parse_atom()

    def _parse_mul(self):
        """Считывает выражение умножения"""
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
        """Считывает выражение деления"""
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
        """Считывает атомарное выражение: скобки или число"""
        return self._parse_paren_expr() or self._parse_number()

    def _parse_paren_expr(self):
        """Считывает выражение в круглых скобках"""
        old_cursor = self.cursor

        if not self._match("("):
            self.cursor = old_cursor
            return None

        child_expr = self._parse_expr()

        if child_expr is None or not self._match(")"):
            self.cursor = old_cursor
            return None

        return ParenExpr(child_expr)


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

