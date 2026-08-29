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


def emit_result(program, number):
    """Добавляет в программу запись числа в регистр rdi для последующего возврата"""
    program.append(f"    mov rdi, {number}\n") # Кладём в регистр rdi наше число - это будет код возврата


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
        print("Error: no source provided.", file=sys.stderr)
        return

    # Если введено не число, выходим
    if not source.isdigit():
        print(f"Error: an integer expected, got '{source}'.", file=sys.stderr)
        return

    # Обрабатываем исходный код - сохраняем наше число как int
    number = int(source)

    # Проверяем, является ли число допустимым
    if number not in range(0, 256):
        print(f"Error: number should be in range of 0-255. Got {number}.", file=sys.stderr)
        return

    # Объявляем программу как список текстовых фрагментов - так будет удобно модифицировать её
    program = []

    # Добавляем в программу необходимые начальные строки
    emit_prolog(program)

    # Добавляем наше число
    emit_result(program, number)

    # Добавляем завершение программы
    emit_epilog(program)

    # Наконец, записываем всё получившееся в файл
    write_program(program, output_path)


# Если компилятор запущен, вызываем main
if __name__ == '__main__':
    main(sys.argv)
