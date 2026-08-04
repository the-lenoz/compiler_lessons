import sys
import os

from codegen import CodeGenerator
from parser import Parser, Expr, BinOP, Sum, Sub, Mul, Div, ParenExpr, Number


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
    elif isinstance(expr, ParenExpr):
        process_expr(expr.expr, program)

    elif isinstance(expr, Number):
        program.emit_reg_assign("rax", expr.value)


def main(args):
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

    expression = p.parse()

    if expression is None:
        print("Error: invalid syntax", file=sys.stderr)
        return

    program = CodeGenerator()

    # Добавляем в программу необходимые начальные строки
    program.emit_prolog()

    process_expr(expression, program)


    program.emit_reg_assign("rdi", "rax")

    # Добавляем завершение программы
    program.emit_epilog()

    # Наконец, записываем всё получившееся в файл
    program.write_program(output_path)


# Если компилятор запущен, вызываем main
if __name__ == '__main__':
    main(sys.argv)