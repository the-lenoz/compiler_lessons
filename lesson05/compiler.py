import sys
import os

from codegen import CodeGenerator
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


def process_expr(expr: Expr | None, program: CodeGenerator):
    """Обходит AST выражения и генерирует assembler-код для вычисления его значения в rax"""
    if expr is None:
        return

    if isinstance(expr, BinOP):
        process_expr(expr.r_child, program)
        program.emit_push("rax")
        process_expr(expr.l_child, program)

        program.emit_pop("rbx")

        match expr:
            case Sum():
                program.emit_add()
            case Sub():
                program.emit_sub()
            case Mul():
                program.emit_mul()
            case Div():
                program.emit_div()
            case Eq():
                program.emit_eq()
            case Lt():
                program.emit_lt()
            case Gt():
                program.emit_gt()
            case Lte():
                program.emit_lte()
            case Gte():
                program.emit_gte()

    elif isinstance(expr, ParenExpr):
        process_expr(expr.expr, program)

    elif isinstance(expr, Number):
        program.emit_reg_assign("rax", expr.value)

    elif isinstance(expr, Id):
        program.emit_load_val_from_var(expr.value)


def process_stmt(statement: Stmt, program: CodeGenerator):
    """Обходит AST инструкции и генерирует assembler-код для неё"""
    match statement:
        case If(cond, body):
            process_expr(cond, program)
            endif_id = program.emit_if_begin()
            process_block(body, program)
            program.emit_endif(endif_id)
        case While(cond, body):
            loop_id = program.emit_loop_header()

            process_expr(cond, program)
            endif_id = program.emit_if_begin()
            process_block(body, program)

            program.emit_loop_back_edge(loop_id)
            program.emit_endif(endif_id)
        case Assignment(identifier, expr):
            process_expr(expr, program)
            program.emit_store_val_to_var(identifier.value)
        case Return(expr):
            process_expr(expr, program)
            program.emit_return("rax")

def process_block(block: Block | None, program: CodeGenerator):
    """Обходит AST блока (списка инструкций) и генерирует assembler-код для каждой инструкции"""
    if block is None or program.get_terminated():
        return

    process_stmt(block.first_statement, program)
    process_block(block.next_block, program)


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

    process_block(program, codegen)

    # Наконец, записываем всё получившееся в файл
    codegen.write_program(output_path)


# Если компилятор запущен, вызываем main
if __name__ == '__main__':
    main(sys.argv)
