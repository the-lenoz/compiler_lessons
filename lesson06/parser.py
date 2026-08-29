from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass
class BinOP:
    l_child: Expr | None
    r_child: Expr | None


@dataclass
class FuncBlock:
    first_f: FuncDecl
    next_block: FuncBlock | None

@dataclass
class FuncDecl:
    pass

@dataclass
class FDef(FuncDecl):
    decl: FDecl
    body: Block

@dataclass
class FDecl(FuncDecl):
    name: Id
    args: DeclArgs | None

@dataclass
class DeclArgs:
    first_arg: Id
    next_args: DeclArgs | None

@dataclass
class Block:
    first_statement: Stmt
    next_block: Block | None

@dataclass
class Stmt:
    pass

@dataclass
class If(Stmt):
    condition: Expr
    body: Block

@dataclass
class While(Stmt):
    condition: Expr
    body: Block

@dataclass
class Assignment(Stmt):
    id: Id
    expr: Expr

@dataclass
class Expr(Stmt):
    def evaluate(self):
        """Вычисляет значение выражения"""
        pass

@dataclass
class Return(Stmt):
    expr: Expr

@dataclass
class Eq(Expr, BinOP):
    pass

@dataclass
class Lt(Expr, BinOP):
    pass

@dataclass
class Gt(Expr, BinOP):
    pass

@dataclass
class Lte(Expr, BinOP):
    pass

@dataclass
class Gte(Expr, BinOP):
    pass

@dataclass
class Arith(Expr):
    pass

@dataclass
class Term(Expr):
    pass


@dataclass
class Atom(Term):
    pass

@dataclass
class Call(Atom):
    name: Id
    args: CallArgs | None

@dataclass
class CallArgs:
    first_arg: Expr
    next_args: CallArgs | None


@dataclass
class Number(Atom):
    value: int

    def evaluate(self):
        """Возвращает значение числового литерала"""
        return self.value


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


@dataclass
class Id(Atom):
    value: str


class Parser:
    source: str
    cursor: int

    def __init__(self, source: str):
        """Создаёт парсер для переданного исходного текста"""
        self.source = source
        self.cursor = 0

    def parse(self):
        """Разбирает исходный текст и возвращает AST программы"""
        program = self._parse_program()
        if self.cursor < len(self.source):
            print(f"Warn: unexpected continuation ignored: '{self.source[self.cursor:]}'", file=sys.stderr)
        return program

    @staticmethod
    def _fix_order(expr: Arith | None) -> Arith | None:
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

    def _parse_program(self):
        """Считывает программу как блок объявлений и определений функций"""
        return self._parse_func_block()

    def _parse_func_block(self):
        """Считывает последовательность объявлений и определений функций"""
        old_cursor = self.cursor

        first = self._parse_func_decl()
        if not first:
            self.cursor = old_cursor
            return None

        next_block = self._parse_func_block()

        return FuncBlock(first, next_block)

    def _parse_func_decl(self) -> FuncDecl | None:
        """Считывает объявление или определение функции"""
        old_cursor = self.cursor

        definition = self._parse_f_def()
        if definition:
            return definition

        decl = self._parse_f_decl()
        if not decl or not self._match(";"):
            self.cursor = old_cursor
            return None

        return decl

    def _parse_f_def(self):
        """Считывает определение функции с телом"""
        old_cursor = self.cursor

        decl = self._parse_f_decl()
        if not decl or not self._match("{"):
            self.cursor = old_cursor
            return None

        body = self._parse_block()

        if not body or not self._match("}"):
            self.cursor = old_cursor
            return None

        return FDef(decl, body)

    def _parse_f_decl(self):
        """Считывает заголовок функции"""
        old_cursor = self.cursor

        if not self._match("fn"):
            self.cursor = old_cursor
            return None

        name = self._parse_id()
        if not name or not self._match("("):
            self.cursor = old_cursor
            return None

        args = self._parse_decl_args()

        if not self._match(")"):
            self.cursor = old_cursor
            return None

        return FDecl(name, args)

    def _parse_decl_args(self):
        """Считывает список имён аргументов функции"""
        old_cursor = self.cursor

        first_arg = self._parse_id()
        if not first_arg:
            self.cursor = old_cursor
            return None

        next_args = None
        if self._match(","):
            next_args = self._parse_decl_args()
            if not next_args:
                self.cursor = old_cursor
                return None

        return DeclArgs(first_arg, next_args)

    def _parse_block(self):
        """Считывает последовательность инструкций"""
        old_cursor = self.cursor

        first = self._parse_stmt()
        if not first:
            self.cursor = old_cursor
            return None

        next_block = self._parse_block()

        return Block(first, next_block)

    def _parse_stmt(self):
        """Считывает одну инструкцию"""
        return self._parse_if() or self._parse_while() or self._parse_return() \
            or self._parse_assignment() or self._parse_exec_expr()

    def _parse_if(self):
        """Считывает условную инструкцию if"""
        old_cursor = self.cursor

        if not self._match("if"):
            self.cursor = old_cursor
            return None

        cond = self._parse_paren_expr()
        if not cond or not cond.expr or not self._match("{"):
            self.cursor = old_cursor
            return None

        body = self._parse_block()

        if not body or not self._match("}"):
            self.cursor = old_cursor
            return None

        return If(cond.expr, body)

    def _parse_while(self):
        """Считывает цикл while"""
        old_cursor = self.cursor

        if not self._match("while"):
            self.cursor = old_cursor
            return None

        cond = self._parse_paren_expr()
        if not cond or not cond.expr or not self._match("{"):
            self.cursor = old_cursor
            return None

        body = self._parse_block()

        if not body or not self._match("}"):
            self.cursor = old_cursor
            return None

        return While(cond.expr, body)

    def _parse_return(self):
        """Считывает инструкцию return"""
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
        """Считывает присваивание значения переменной"""
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

    def _parse_exec_expr(self):
        """Считывает выражение, записанное как инструкция"""
        old_cursor = self.cursor
        expr = self._parse_expr()
        if not expr or not self._match(";"):
            self.cursor = old_cursor
            return None
        return expr

    def _parse_expr(self):
        """Считывает выражение сравнения или арифметическое выражение"""
        return (self._parse_eq() or self._parse_lt() or self._parse_gt() or
                self._parse_lte() or self._parse_gte() or self._parse_arith())

    def _parse_eq(self):
        """Считывает выражение сравнения на равенство"""
        old_cursor = self.cursor

        l_child = self._parse_arith()
        if not l_child or not self._match("=="):
            self.cursor = old_cursor
            return None

        r_child = self._parse_expr()
        if not r_child:
            self.cursor = old_cursor
            return None

        return Eq(l_child, r_child)

    def _parse_lt(self):
        """Считывает выражение сравнения «меньше»"""
        old_cursor = self.cursor

        l_child = self._parse_arith()
        if not l_child or not self._match("<"):
            self.cursor = old_cursor
            return None

        r_child = self._parse_expr()
        if not r_child:
            self.cursor = old_cursor
            return None

        return Lt(l_child, r_child)

    def _parse_gt(self):
        """Считывает выражение сравнения «больше»"""
        old_cursor = self.cursor

        l_child = self._parse_arith()
        if not l_child or not self._match(">"):
            self.cursor = old_cursor
            return None

        r_child = self._parse_expr()
        if not r_child:
            self.cursor = old_cursor
            return None

        return Gt(l_child, r_child)

    def _parse_lte(self):
        """Считывает выражение сравнения «меньше или равно»"""
        old_cursor = self.cursor

        l_child = self._parse_arith()
        if not l_child or not self._match("<="):
            self.cursor = old_cursor
            return None

        r_child = self._parse_expr()
        if not r_child:
            self.cursor = old_cursor
            return None

        return Lte(l_child, r_child)

    def _parse_gte(self):
        """Считывает выражение сравнения «больше или равно»"""
        old_cursor = self.cursor

        l_child = self._parse_arith()
        if not l_child or not self._match(">="):
            self.cursor = old_cursor
            return None

        r_child = self._parse_expr()
        if not r_child:
            self.cursor = old_cursor
            return None

        return Gte(l_child, r_child)

    def _parse_arith(self):
        """Считывает арифметическое выражение"""
        arith = self._parse_sum() or self._parse_sub() or self._parse_term()
        return Parser._fix_order(arith)

    def _parse_sum(self):
        """Считывает выражение сложения"""
        old_cursor = self.cursor

        l_child = self._parse_term()
        if not l_child or not self._match("+"):
            self.cursor = old_cursor
            return None

        r_child = self._parse_arith()
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

        r_child = self._parse_arith()
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
        """Считывает атомарное выражение: скобки, вызов, число или имя переменной"""
        return self._parse_paren_expr() or self._parse_call() or self._parse_number() or self._parse_id()

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

    def _parse_call(self):
        """Считывает вызов функции"""
        old_cursor = self.cursor

        callee_name = self._parse_id()
        if not callee_name or not self._match("("):
            self.cursor = old_cursor
            return None

        args = self._parse_call_args()
        if not self._match(")"):
            self.cursor = old_cursor
            return None

        return Call(callee_name, args)

    def _parse_call_args(self):
        """Считывает список выражений-аргументов вызова функции"""
        old_cursor = self.cursor

        first_arg = self._parse_expr()
        if not first_arg:
            self.cursor = old_cursor
            return None

        next_args = None
        if self._match(","):
            next_args = self._parse_call_args()
            if not next_args:
                self.cursor = old_cursor
                return None

        return CallArgs(first_arg, next_args)

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


