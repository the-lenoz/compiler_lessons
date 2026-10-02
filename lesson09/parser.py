from __future__ import annotations

import sys
from dataclasses import dataclass

escape_chars = {'b': '\b', 'n': '\n', 'r': '\r', 't': '\t', '\\': '\\'}


@dataclass
class BinOP:
    l_child: Expr | None
    r_child: Expr | None

@dataclass
class GlobalBlock:
    first_stmt: GlobalStmt
    next_block: GlobalBlock | None

@dataclass
class GlobalStmt:
    pass

@dataclass
class FDef(GlobalStmt):
    decl: FDecl
    body: Block | None

@dataclass
class FDecl(GlobalStmt):
    name: Id
    args: DeclArgs | None
    return_type_name: TypeName

@dataclass
class DeclArgs:
    first_arg: VarDecl
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
    body: Block | None

@dataclass
class While(Stmt):
    condition: Expr
    body: Block | None

@dataclass
class VarDecl(Stmt):
    typename: TypeName
    id: Id

@dataclass
class Assignment(Stmt):
    lvalue: LValue
    expr: Expr

@dataclass
class LValue:
    pass

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
class Ref(Atom):
    obj: LValue

@dataclass
class Deref(Atom, LValue):
    typename: TypeName
    ptr: Expr

@dataclass
class Call(Atom):
    name: Id
    args: CommaVals | None

@dataclass
class CommaVals:
    first_arg: Expr
    next_args: CommaVals | None

@dataclass
class Array(Atom):
    data: CommaVals

@dataclass
class StrConst(Atom):
    data: bytes

@dataclass
class Number(Atom):
    value: int

@dataclass
class Sum(Expr, BinOP):
    pass

@dataclass
class Sub(Expr, BinOP):
    pass

@dataclass
class Mul(Term, BinOP):
    pass

@dataclass
class Div(Term, BinOP):
    pass

@dataclass
class ParenExpr(Atom):
    expr: Expr | None

@dataclass
class StaticCast(Atom):
    typename: TypeName
    expr: Expr

@dataclass
class Id(Atom, LValue):
    value: str

@dataclass
class TypeName:
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

    def _parse_program(self):
        """Считывает программу как глобальный блок"""
        return self._parse_global_block()

    def _parse_global_block(self):
        """Считывает последовательность объявлений и определений"""
        old_cursor = self.cursor

        first = self._parse_global_stmt()
        if not first:
            self.cursor = old_cursor
            return None

        next_block = self._parse_global_block()

        return GlobalBlock(first, next_block)

    def _parse_global_stmt(self) -> GlobalStmt | None:
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

        if not self._match("}"):
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

        if not self._match(")") or not self._match("->"):
            self.cursor = old_cursor
            return None

        return_type_name = self._parse_typename()
        if not return_type_name:
            self.cursor = old_cursor
            return None

        return FDecl(name, args, return_type_name)

    def _parse_decl_args(self):
        """Считывает список имён аргументов функции"""
        old_cursor = self.cursor

        arg_typename = self._parse_typename()
        arg_id = self._parse_id()
        if not arg_typename or not arg_id:
            self.cursor = old_cursor
            return None

        next_args = None
        if self._match(","):
            next_args = self._parse_decl_args()
            if not next_args:
                self.cursor = old_cursor
                return None

        return DeclArgs(VarDecl(arg_typename, arg_id), next_args)

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
            or self._parse_var_decl() or self._parse_assignment() or self._parse_exec_expr()

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

        if not self._match("}"):
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

        if not self._match("}"):
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

    def _parse_var_decl(self):
        """Считывает объявление переменной"""
        old_cursor = self.cursor

        typename = self._parse_typename()
        if not typename:
            self.cursor = old_cursor
            return None
        identifier = self._parse_id()
        if not identifier or not self._match(";"):
            self.cursor = old_cursor
            return None

        return VarDecl(typename, identifier)

    def _parse_assignment(self):
        """Считывает присваивание значения переменной"""
        old_cursor = self.cursor

        lvalue = self._parse_lvalue()
        if not lvalue or not self._match("="):
            self.cursor = old_cursor
            return None

        expr = self._parse_expr()
        if expr is None or not self._match(";"):
            self.cursor = old_cursor
            return None

        return Assignment(lvalue, expr)

    def _parse_lvalue(self):
        return self._parse_deref() or self._parse_id()

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
        l_child = self._parse_arith()
        if l_child is None:
            return None

        for operator, node_type in (("==", Eq), ("<=", Lte), (">=", Gte),
                                    ("<", Lt), (">", Gt)):
            if self._match(operator):
                r_child = self._parse_expr()
                if r_child is None:
                    return None
                return node_type(l_child, r_child)

        return l_child

    def _parse_arith(self):
        """Считывает арифметическое выражение"""
        expr = self._parse_term()
        if expr is None:
            return None

        while True:
            if self._match("+"):
                r_child = self._parse_term()
                if r_child is None:
                    return None
                expr = Sum(expr, r_child)
            elif self._match("-"):
                r_child = self._parse_term()
                if r_child is None:
                    return None
                expr = Sub(expr, r_child)
            else:
                return expr

    def _parse_term(self):
        """Считывает терм: умножение, деление или атом"""
        expr = self._parse_atom()
        if expr is None:
            return None

        while True:
            if self._match("*"):
                r_child = self._parse_atom()
                if r_child is None:
                    return None
                expr = Mul(expr, r_child)
            elif self._match("/"):
                r_child = self._parse_atom()
                if r_child is None:
                    return None
                expr = Div(expr, r_child)
            else:
                return expr

    def _parse_atom(self):
        """Считывает атомарное выражение"""
        return (self._parse_paren_expr() or self._parse_static_cast() or self._parse_str_const() or
                self._parse_array() or self._parse_number() or self._parse_ref() or self._parse_deref() or
                self._parse_call() or self._parse_id())

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

    def _parse_static_cast(self):
        """Считывает каст"""
        old_cursor = self.cursor

        if not self._match("static_cast") or not self._match("<"):
            self.cursor = old_cursor
            return None

        typename = self._parse_typename()
        if not typename or not self._match(">") or not self._match("("):
            self.cursor = old_cursor
            return None

        expr = self._parse_expr()
        if not expr or not self._match(")"):
            self.cursor = old_cursor
            return None

        return StaticCast(typename, expr)

    def _parse_str_const(self):
        """Считывает строковую константу"""
        old_cursor = self.cursor

        if not self._match("\""):
            self.cursor = old_cursor
            return None

        escaped = False
        data = bytearray()
        while self.source[self.cursor] != '"' or escaped:
            char = self.source[self.cursor]
            if self.source[self.cursor].isascii() and (escaped or char != '\\'):
                byte = escape_chars[char] if escaped else char
                data.append(ord(byte))

            self.cursor += 1
            escaped = True if char == '\\' and not escaped else False

            if self.cursor >= len(self.source):
                self.cursor = old_cursor
                return None
        self.cursor += 1

        data.append(0) # Добавляем завершение для C-строки

        return StrConst(data)

    def _parse_array(self):
        """Считывает массив"""
        old_cursor = self.cursor

        if not self._match("["):
            self.cursor = old_cursor
            return None

        data = self._parse_comma_vals()

        if data is None or not self._match("]"):
            self.cursor = old_cursor
            return None

        return Array(data)

    def _parse_ref(self):
        """Считывает взятие адреса"""
        old_cursor = self.cursor

        if not self._match("&"):
            return None

        obj = self._parse_lvalue()
        if not obj:
            self.cursor = old_cursor
            return None

        return Ref(obj)

    def _parse_deref(self):
        """Считывает рызыменование указателя"""
        old_cursor = self.cursor

        if not self._match("*"):
            return None

        typename = self._parse_typename()
        if not typename:
            self.cursor = old_cursor
            return None

        ptr = self._parse_atom()
        if not ptr:
            self.cursor = old_cursor
            return None

        return Deref(typename, ptr)

    def _parse_call(self):
        """Считывает вызов функции"""
        old_cursor = self.cursor

        callee_name = self._parse_id()
        if not callee_name or not self._match("("):
            self.cursor = old_cursor
            return None

        args = self._parse_comma_vals()
        if not self._match(")"):
            self.cursor = old_cursor
            return None

        return Call(callee_name, args)

    def _parse_comma_vals(self):
        """Считывает список выражений"""
        old_cursor = self.cursor

        first_arg = self._parse_expr()
        if not first_arg:
            self.cursor = old_cursor
            return None

        next_args = None
        if self._match(","):
            next_args = self._parse_comma_vals()
            if not next_args:
                self.cursor = old_cursor
                return None

        return CommaVals(first_arg, next_args)

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

    def _parse_typename(self):
        identifier = self._parse_id()
        if identifier:
            return TypeName(identifier.value)

        return None

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
        if not self.source.startswith(expected, self.cursor):
            self.cursor = old_cursor
            return False

        self.cursor += len(expected)
        return True

    def _skip_spaces(self):
        """Двигает курсор, пропуская пробельные символы"""

        # Пока текущий символ - пробел, и мы не дошли до конца - двигаем курсор дальше
        while self.cursor < len(self.source) and self.source[self.cursor].isspace():
            self.cursor += 1

