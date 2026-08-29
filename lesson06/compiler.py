import sys
import os

from codegen import CodeGenerator, FuncCodeGenerator
from parser import *


def print_usage():
    """Печатает инструкцию по использованию программы в stderr"""
    print("Integer arithmetic compiler.\n"
          f"Usage: {sys.argv[0]} input_file output_file", file=sys.stderr)


def read_file(path):
    """Читает текст файла по пути path и возвращает его как строку"""

    # Если файл не существует или является папкой, выходим
    if not os.path.exists(path) or os.path.isdir(path):
        print(f"Error: could not open file '{path}'.", file=sys.stderr)
        print_usage()
        return ""

    # Открываем файл безопасно, гарантируя закрытие (с помощью менеджера "with")
    with open(path) as file:
        data = file.read()
    return data

def process_expr(expr: Expr | None, f_gen: FuncCodeGenerator):
    """Обходит AST выражения и генерирует assembler-код для вычисления его значения в rax"""
    if expr is None:
        return

    if isinstance(expr, BinOP):
        process_expr(expr.r_child, f_gen)
        f_gen.emit_push("rax")
        process_expr(expr.l_child, f_gen)

        f_gen.emit_pop("rbx")

        match expr:
            case Sum():
                f_gen.emit_add()
            case Sub():
                f_gen.emit_sub()
            case Mul():
                f_gen.emit_mul()
            case Div():
                f_gen.emit_div()
            case Eq():
                f_gen.emit_eq()
            case Lt():
                f_gen.emit_lt()
            case Gt():
                f_gen.emit_gt()
            case Lte():
                f_gen.emit_lte()
            case Gte():
                f_gen.emit_gte()

    elif isinstance(expr, ParenExpr):
        process_expr(expr.expr, f_gen)

    elif isinstance(expr, Call):
        args = []
        args_AST = expr.args
        while args_AST is not None:
            args.append(args_AST.first_arg)
            args_AST = args_AST.next_args

        process_call(expr.name.value, args, f_gen)

    elif isinstance(expr, Number):
        f_gen.emit_reg_assign("rax", expr.value)

    elif isinstance(expr, Id):
        f_gen.emit_load_val_from_var(expr.value)

def process_call(name: str, args: list[Expr], f_gen: FuncCodeGenerator):
    """Генерирует вычисление аргументов и вызов функции"""
    offset = f_gen.emit_align_stack_before_call(len(args))
    for arg in reversed(args):
        process_expr(arg, f_gen)
        f_gen.emit_push("rax")

    f_gen.emit_call(name, len(args))

    f_gen.emit_restore_stack_alignment_after_call(offset)

def process_stmt(statement: Stmt, f_gen: FuncCodeGenerator):
    """Обходит AST инструкции и генерирует assembler-код для неё"""
    match statement:
        case If(cond, body):
            process_expr(cond, f_gen)
            endif_id = f_gen.emit_if_begin()
            process_block(body, f_gen)
            f_gen.emit_endif(endif_id)
        case While(cond, body):
            loop_id = f_gen.emit_loop_header()

            process_expr(cond, f_gen)
            endif_id = f_gen.emit_if_begin()
            process_block(body, f_gen)

            f_gen.emit_loop_back_edge(loop_id)
            f_gen.emit_endif(endif_id)
        case Assignment(identifier, expr):
            process_expr(expr, f_gen)
            f_gen.emit_store_val_to_var(identifier.value)
        case Return(expr):
            process_expr(expr, f_gen)
            f_gen.emit_return("rax")
        case Expr():
            process_expr(statement, f_gen)

def process_block(block: Block | None, f_gen: FuncCodeGenerator):
    """Обходит AST блока (списка инструкций) и генерирует assembler-код для каждой инструкции"""
    if block is None:
        return

    process_stmt(block.first_statement, f_gen)
    process_block(block.next_block, f_gen)


def process_f_decl(decl: FDecl, codegen: CodeGenerator):
    """Регистрирует объявление внешней функции"""
    codegen.add_func(decl.name.value, "extern")


def process_f_def(definition: FDef, codegen: CodeGenerator):
    """Генерирует assembler-код определения функции"""
    f_gen = FuncCodeGenerator(definition.decl.name.value)

    arg_list = []
    arg_AST = definition.decl.args
    while arg_AST is not None:
        arg_list.append(arg_AST.first_arg.value)
        arg_AST = arg_AST.next_args

    f_gen.emit_use_args(arg_list)

    process_block(definition.body, f_gen)

    codegen.add_func(definition.decl.name.value, "intern")
    f_gen.emit_to_parent(codegen)


def process_f_block(block: FuncBlock | None, codegen: CodeGenerator):
    """Обходит AST блока функций и генерирует assembler-код для каждой функции"""
    if block is None:
        return

    match block.first_f:
        case FDecl():
            process_f_decl(block.first_f, codegen)
        case FDef():
            process_f_def(block.first_f, codegen)

    process_f_block(block.next_block, codegen)


def main(args):
    """Запускает компиляцию файла, переданного в аргументах командной строки"""

    # Проверка количества аргументов командной строки:
    # если не совпадает (должно быть 3, т. к. первый - имя самой прогрммы-компилятора), печатаем инструкцию и выходим
    if len(args) != 3:
        print_usage()
        return

    # Считываем аргументы в переменные
    input_path = args[1]
    output_path = args[2]

    # Читаем исходный код программы и убираем лишние пробелы
    source = read_file(input_path)
    source = source.strip()

    # Если программа пуста, либо файл не найден, выходим
    if not source:
        print("Error: no source provided", file=sys.stderr)
        return

    # Парсим программу
    p = Parser(source)

    program = p.parse()

    if program is None:
        print("Error: invalid syntax", file=sys.stderr)
        return

    codegen = CodeGenerator()

    process_f_block(program, codegen)

    # Наконец, записываем всё получившееся в файл
    codegen.write_program(output_path)


# Если компилятор запущен, вызываем main
if __name__ == '__main__':
    main(sys.argv)
