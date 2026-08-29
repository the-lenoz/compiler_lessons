
program_prolog = """
section .text                       ; указываем, что дальше идёт код. ".text" - имя секции кода по стандарту
    global _start                   ; делаем метку _start видимой для сборщика исполняемого файла

_start:                             ; сама метка точки входа
"""

program_epilog = """\
    mov rax, 60                     ; кладём номер системного вызова для возврата из программы в регистр rax
    syscall                         ; вызываем выход
"""

class CodeGenerator:
    # Объявляем программу как список текстовых фрагментов - так будет удобно модифицировать её
    program: list

    def __init__(self):
        """Создаёт генератор с пустым списком assembler-инструкций"""
        self.program = []

    def _emit(self, string: str):
        """Добавляет строку assembler-кода в программу"""
        self.program.append(string)

    def emit_push(self, reg: str):
        """Добавляет в программу команду push - сохранение регистра в стек"""
        self._emit(f"    push {reg}\n")

    def emit_pop(self, reg: str):
        """Добавляет в программу команду pop - извлечение значения из стека в регистр"""
        self._emit(f"    pop {reg}\n")

    def emit_prolog(self):
        """Добавляет в программу необходимое начало"""
        self._emit(program_prolog)

    def emit_epilog(self):
        """Добавляет в программу необходимое завершение"""
        self._emit(program_epilog)

    def emit_reg_assign(self, reg, expr):
        """Добавляет в программу команду записи выражения в регистр"""
        self._emit(f"    mov {reg}, {expr}\n")

    def emit_result(self, result_expr):
        """Добавляет в программу запись результата в регистр rdi для последующего возврата"""
        self.emit_reg_assign("rdi", result_expr)

    def emit_add(self):
        """Складывает rbx и rax, результат в rax"""
        self._emit("    add rax, rbx\n")

    def emit_sub(self):
        """Вычитает rbx из rax, результат в rax"""
        self._emit("    sub rax, rbx\n")

    def emit_mul(self):
        """Умножает rax на rbx, результат в rax"""
        self._emit("    imul rax, rbx\n")

    def emit_div(self):
        """Делит rax на rbx, результат в rax"""
        self._emit("    cqo\n")
        self._emit("    idiv rbx\n")

    def write_program(self, path: str):
        """Записывает программу-список в файл, склеивая её в одну строку"""

        # Открываем файл на запись безопасно
        with open(path, 'w') as file:
            file.write("".join(self.program))
