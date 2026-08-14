import sys
from itertools import count

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
    program_body: list
    locals: dict
    terminated: bool
    endif_lab_count: count
    loop_lab_count: count

    def __init__(self):
        self.program_body = []
        self.locals = {}
        self.terminated = False
        self.endif_lab_count = count()
        self.loop_lab_count = count()

    def _emit(self, string: str):
        self.program_body.append(string)

    def emit_push(self, reg: str):
        self._emit(f"    push {reg}\n")

    def emit_pop(self, reg: str):
        self._emit(f"    pop {reg}\n")

    def emit_reg_assign(self, reg, expr):
        """Добавляет в программу команду записи выражения в регистр"""
        self._emit(f"    mov {reg}, {expr}\n")

    def emit_if_begin(self) -> str:
        """Добавляет проверку условия и условный переход. Возвращает имя метки для завершения тела if"""
        self._emit("    test rax, rax\n")
        endif_id = self.get_endif_lab_id()
        self._emit(f"    jz {endif_id}\n")
        return endif_id

    def emit_endif(self, endif_id: str):
        """Добавляет метку для завершения тела if"""
        self._emit(f"{endif_id}:\n")

    def emit_loop_header(self) -> str:
        """Добавляет метку для начала тела цикла. Возвращает её имя"""
        loop_id = self.get_loop_lab_id()
        self._emit(f"{loop_id}:\n")
        return loop_id

    def emit_loop_back_edge(self, loop_lab_id: str):
        """Добавляет безуловный переход на метку"""
        self._emit(f"    jmp {loop_lab_id}\n")

    def emit_return(self, result_expr):
        """Добавляет в программу запись результата в регистр rdi для последующего возврата"""
        self.emit_reg_assign("rdi", result_expr)

    def emit_add(self):
        """Adds RBX to RAX"""
        self._emit("    add rax, rbx\n")

    def emit_sub(self):
        self._emit("    sub rax, rbx\n")

    def emit_mul(self):
        self._emit("    imul rax, rbx\n")

    def emit_div(self):
        self._emit("    cqo\n")
        self._emit("    idiv rbx\n")

    def emit_eq(self):
        self._emit("    cmp rax, rbx\n")
        self._emit("    sete al\n")
        self._emit("    movzx rax, al\n")

    def emit_lt(self):
        self._emit("    cmp rax, rbx\n")
        self._emit("    setl al\n")
        self._emit("    movzx rax, al\n")

    def emit_gt(self):
        self._emit("    cmp rax, rbx\n")
        self._emit("    setg al\n")
        self._emit("    movzx rax, al\n")

    def emit_lte(self):
        self._emit("    cmp rax, rbx\n")
        self._emit("    setle al\n")
        self._emit("    movzx rax, al\n")

    def emit_gte(self):
        self._emit("    cmp rax, rbx\n")
        self._emit("    setge al\n")
        self._emit("    movzx rax, al\n")

    def get_endif_lab_id(self):
        return f".endif_{next(self.endif_lab_count)}"

    def get_loop_lab_id(self):
        return f".loop_{next(self.loop_lab_count)}"

    def get_locals_bp_offset(self):
        return len(self.locals) * 8

    def add_var(self, var_name: str):
        if var_name in self.locals:
            print(f"Error: var '{var_name}' already exists", file=sys.stderr)
            return False
        bp_offset = self.get_locals_bp_offset() + 8
        self.locals[var_name] = bp_offset
        return bp_offset

    def get_var_addr(self, var_name: str):
        if var_name not in self.locals:
            print(f"Error: var '{var_name}' undefined", file=sys.stderr)
            return None

        return f'rbp-{self.locals[var_name]}'

    def emit_store_val_to_var(self, var_name: str):
        if var_name not in self.locals:
            self.add_var(var_name)

        self._emit(f"    mov [{self.get_var_addr(var_name)}], rax\n")

    def emit_load_val_from_var(self, var_name: str):
        if var_name not in self.locals:
            print(f"Error: var '{var_name}' undefined", file=sys.stderr)
            return

        self._emit(f"    mov rax, [{self.get_var_addr(var_name)}]\n")

    def generate_entry(self):
        bp_offset = self.get_locals_bp_offset()
        if bp_offset == 0:
            return []

        return [
             "    mov rbp, rsp\n",
            f"    sub rsp, {bp_offset}\n"
        ]

    def generate_leave(self):
        return [
            "    mov rsp, rbp\n"
        ]

    def write_program(self, path: str):
        """Записывает программу-список в файл, склеивая её в одну строку"""

        program = []
        main_entry = self.generate_entry()
        main_leave = self.generate_leave()

        program.append(program_prolog)
        program.extend(main_entry)
        program.extend(self.program_body)
        program.extend(main_leave)
        program.append(program_epilog)

        # Открываем файл на запись безопасно
        with open(path, 'w') as file:
            file.write("".join(program))

    def set_terminated(self):
        self.terminated = True

    def unset_terminated(self):
        self.terminated = False

    def get_terminated(self):
        return self.terminated
