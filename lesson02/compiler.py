import sys
import os

program_prolog = """
section .text                       ; указываем, что дальше идёт код. ".text" - имя секции кода по стандарту
    global _start                   ; делаем метку _start видимой для сборщика исполняемого файла

_start:                             ; сама метка точки входа
"""

program_epilog = """\
    mov rax, 60                     ; кладём номер системного вызова для возврата из программы в регистр rax
    syscall                         ; вызываем выход
"""


def print_usage():
    """Печатает инструкцию по использованию программы в stderr"""
    print("The simplest compiler: compiles just one integer number (0-255).\n"
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


def write_program(program, path):
    """Записывает программу-список в файл, склеивая её в одну строку"""

    # Открываем файл на запись безопасно
    with open(path, 'w') as file:
        file.write("".join(program))

def emit_prolog(program):
    """Добавляет в программу необходимое начало"""
    program.append(program_prolog)


def emit_epilog(program):
    """Добавляет в программу необходимое завершение"""
    program.append(program_epilog)

def emit_reg_assign(program, reg, expr):
    """Добавляет в программу команду записи выражения в регистр"""
    program.append(f"    mov {reg}, {expr}\n")

def emit_reg_add(program, reg, expr):
    """Добавляет в программу команду прибавления выражения к регистру"""
    program.append(f"    add {reg}, {expr}\n")

def emit_result(program, result_expr):
    """Добавляет в программу запись результата в регистр rdi для последующего возврата"""
    emit_reg_assign(program, "rdi", result_expr)

# Глобальный курсор для нашего парсера: указывает на текущее место считывания
cursor = 0

def skip_spaces(source):
    """Двигает курсор, пропуская пробельные символы"""

    # Захватываем глобальную переменную
    global cursor

    # Пока текущий символ - пробел, и мы не дошли до конца - двигаем курсор дальше
    while cursor < len(source) and source[cursor].isspace():
        cursor += 1

def parse_int(source):
    """Считывает целое число, игнорируя пробелы, и сдвигает курсор"""

    # Захватываем глобальную переменную
    global cursor

    # Сохраняем курсор, чтобы вернуть обратно, если спарсить число не получится
    old_cursor = cursor

    skip_spaces(source)

    # Сохраняам начало числа
    begin = cursor

    # Двигаемся, пока захватываются ещё цифры
    while cursor < len(source) and source[cursor].isdigit():
        cursor += 1

    # Если не было ни одной цифры - числа нет. восстанавливаем курсор и выходим
    if begin == cursor:
        cursor = old_cursor
        return None

    # Число есть. Возвращаем его
    return int(source[begin:cursor])


def parse_sum(source):
    """Считывает выражение суммы чисел и сдвигает курсор"""

    # Захватываем глобальную переменную
    global cursor

    # Сохраняем курсор для восстановления
    old_cursor = cursor

    # Парсим число
    left_number = parse_int(source)

    # Если числа нет, то суммы - тем более. Выходим
    if left_number is None:
        cursor = old_cursor
        return None

    skip_spaces(source)

    # Если дальше нет "+", это не сложение. Выходим
    if cursor >= len(source) or source[cursor] != "+":
        cursor = old_cursor
        return None

    # Пропускаем "+"
    cursor += 1

    # Парсим правую часть: число, либо ещё одна сумма
    right_arg = parse_sum(source) or parse_int(source)

    # Если справа от "+" ничего нет - это не сложение. Выходим
    if right_arg is None:
        cursor = old_cursor
        return None

    # Возвращаем кортеж из слагаемых
    return left_number, right_arg


def parse_program(source):
    """Считывает всю программу"""

    # Захватываем глобальную переменную и сбрасываем её
    global cursor
    cursor = 0

    # Наша программа - это сумма, либо просто число
    return parse_sum(source) or parse_int(source)


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
        print("Error: no source provided.", file=sys.stderr)
        return

    # Парсим программу
    expression = parse_program(source)
    if expression is None:
        print("Error: invalid syntax", file=sys.stderr)
        return

    # Объявляем программу как список текстовых фрагментов - так будет удобно модифицировать её
    program = []

    # Добавляем в программу необходимые начальные строки
    emit_prolog(program)

    # Кладём в регистр rax 0, там будем считать сумму,
    emit_reg_assign(program, "rax", 0)

    # Разбираем выражение по частям - отбираем левую часть, пока не останется число
    addition = expression
    while isinstance(addition, tuple):
        # Вставляем прибавление числа слева
        emit_reg_add(program, "rax", addition[0])

        # Оставшееся выражение - правая часть старого, так как левую мы обработали
        addition = addition[1]

    # Добавляем последнее число
    emit_reg_add(program, "rax", addition)

    # Теперь итоговая сумма в rax

    # Кладём эту сумму из rax в итоговый регистр rdi
    emit_result(program, "rax")

    # Добавляем завершение программы
    emit_epilog(program)

    # Наконец, записываем всё получившееся в файл
    write_program(program, output_path)


# Если компилятор запущен, вызываем main
if __name__ == '__main__':
    main(sys.argv)