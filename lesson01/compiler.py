import sys
import os

program_prefix = """
section .text
    global _start                   ; команда для обозначения точки входа в программу

_start:
    mov rax, 60                     ; номер системного вызова для возврата из программы
    mov rdi, """                    # кладём в регистр rdi наше число

program_suffix = """
    syscall                         ; вызываем выход
"""


def print_usage():
    print("The simplest compiler: compiles just one integer number (0-255).\n"
          f"Usage: {sys.argv[0]} input_file output_file", file=sys.stderr)

def read_file(path):
    if not os.path.exists(path):
        print(f"Error: file '{path}' not found.", file=sys.stderr)
        print_usage()
        return None

    with open(path) as file:
        data = file.read()

    return data

def write_program(program, path):
    with open(path, 'w') as file:
        for item in program:
            file.write(item)

def emit_prefix(program):
    program.append(program_prefix)

def emit_suffix(program):
    program.append(program_suffix)

def emit_number(program, number):
    program.append(str(number))

def main(args):
    if len(args) != 3:
        print_usage()
        return

    input_path = args[1]
    output_path = args[2]

    source = read_file(input_path)
    if not source:
        print("Error: no source provided.", file=sys.stderr)
        return

    source = source.strip()
    number = int(source)

    if number not in range(0, 256):
        print(f"Error: number should be in range of 0-255. Got {number}.", file=sys.stderr)
        return

    program = []
    emit_prefix(program)
    emit_number(program, number)
    emit_suffix(program)

    write_program(program, output_path)


if __name__ == '__main__':
    main(sys.argv)
