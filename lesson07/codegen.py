import sys
from itertools import count

program_data_section = """
section .data
"""

program_prolog = """
section .text                       ; указываем, что дальше идёт код. ".text" - имя секции кода по стандарту
    global _start                   ; делаем метку _start видимой для сборщика исполняемого файла

print:
    mov rsi, rdi
    xor edx, edx
.loop:
    cmp byte [rsi + rdx], 0
    je .print
    inc edx
    jmp .loop
.print:
    mov edi, 1
    mov eax, edi
    syscall
    ret

_start:                             ; сама метка точки входа
    sub rsp, 8                      ; выравниваем стек
    call main                       ; вызываем основную функцию программы
    add rsp, 8                      ; возвращаем стек
    mov rdi, rax                    ; результат возврата main передаём в системный вызов
    mov rax, 60                     ; кладём номер системного вызова для возврата из программы в регистр rax
    syscall                         ; вызываем выход
"""

program_epilog = """\
"""

ABI_ARG_REGS = [
    "rdi",
    "rsi",
    "rdx",
    "rcx",
    "r8",
    "r9"
]

class CodeGenerator:
    # Объявляем программу как список текстовых фрагментов - так будет удобно модифицировать её
    program_body: list
    func_names: dict

    constants: count
    data_body: list

    def __init__(self):
        """Создаёт генератор с пустым телом программы и таблицей функций"""
        self.program_body = []
        self.data_body = []
        self.func_names = {}
        self.constants = count()

    def add_const_data(self, data: bytes):
        name = f"const_{next(self.constants)}"
        self.data_body.append(f"    {name} db " + ",".join((f"{hex(byte)}" for byte in data)) + "\n")
        return name

    def extend_body(self, func_body: list):
        """Добавляет сгенерированное тело функции в программу"""
        self.program_body.extend(func_body)

    def add_func(self, name: str, kind: str):
        """Добавляет имя внутренней или внешней функции в таблицу функций"""
        if kind == "extern":
            self.func_names[name] = "extern"
        else:
            self.func_names[name] = "intern"


    def write_program(self, path: str):
        """Записывает программу-список в файл, склеивая её в одну строку"""

        # Открываем файл на запись безопасно
        with open(path, 'w') as file:
            file.write("".join(
                [program_data_section] +
                self.data_body +
                [program_prolog] +
                [f"    extern {name}\n" for name, kind in self.func_names.items() if kind == "extern"] +
                self.program_body +
                [program_epilog]
            ))

class FuncCodeGenerator:
    locals: dict
    arrays_size: int

    endif_lab_count: count
    loop_lab_count: count

    name: str
    stack_alignment_offset: int

    parent: CodeGenerator

    def __init__(self, name: str, parent: CodeGenerator):
        """Создаёт генератор кода для функции с переданным именем"""
        self.func_body = []
        self.locals = {}
        self.endif_lab_count = count()
        self.loop_lab_count = count()
        self.name = name
        self.stack_alignment_offset = 8
        self.arrays_size = 0

        self.parent = parent

    def emit_use_args(self, arg_names: list):
        """Сохраняет аргументы функции в локальные переменные согласно ABI"""
        if not arg_names:
            return
        for n, arg in enumerate(arg_names):
            if n < len(ABI_ARG_REGS):
                self._emit(f"    mov rax, {ABI_ARG_REGS[n]}\n")
                self.emit_store_val_to_var(arg)
            else:
                self.locals[arg] = (1 + n - len(ABI_ARG_REGS)) * -8


    def _emit(self, string: str):
        """Добавляет строку assembler-кода в программу"""
        self.func_body.append(string)

    def emit_push(self, reg: str):
        """Добавляет в программу команду push - сохранение регистра в стек"""
        self._emit(f"    push {reg}\n")
        self.stack_alignment_offset += 8

    def emit_pop(self, reg: str):
        """Добавляет в программу команду pop - извлечение значения из стека в регистр"""
        self._emit(f"    pop {reg}\n")
        self.stack_alignment_offset -= 8

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
        """Добавляет безусловный переход на метку (возврат к началу цикла)"""
        self._emit(f"    jmp {loop_lab_id}\n")

    def emit_return(self, result_expr):
        """Записывает результат в rax и выходит из функции"""
        self.emit_reg_assign("rax", result_expr)
        self.func_body.extend(
            self.generate_leave()
        )

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

    def emit_eq(self):
        """Сравнивает rax и rbx, записывает 1 в rax если равны, иначе 0"""
        self._emit("    cmp rax, rbx\n")
        self._emit("    sete al\n")
        self._emit("    movzx rax, al\n")

    def emit_lt(self):
        """Сравнивает rax и rbx, записывает 1 в rax если rax < rbx, иначе 0"""
        self._emit("    cmp rax, rbx\n")
        self._emit("    setl al\n")
        self._emit("    movzx rax, al\n")

    def emit_gt(self):
        """Сравнивает rax и rbx, записывает 1 в rax если rax > rbx, иначе 0"""
        self._emit("    cmp rax, rbx\n")
        self._emit("    setg al\n")
        self._emit("    movzx rax, al\n")

    def emit_lte(self):
        """Сравнивает rax и rbx, записывает 1 в rax если rax <= rbx, иначе 0"""
        self._emit("    cmp rax, rbx\n")
        self._emit("    setle al\n")
        self._emit("    movzx rax, al\n")

    def emit_gte(self):
        """Сравнивает rax и rbx, записывает 1 в rax если rax >= rbx, иначе 0"""
        self._emit("    cmp rax, rbx\n")
        self._emit("    setge al\n")
        self._emit("    movzx rax, al\n")

    def emit_call(self, callee_name: str, args_count: int):
        """Передаёт аргументы, вызывает функцию и очищает стек после вызова"""
        self.emit_load_call_args(args_count)
        self._emit(f"    call {callee_name}\n")
        self.emit_clean_call_args(args_count)

    def emit_align_stack_before_call(self, args_count: int):
        """Выравнивает стек перед вызовом функции и возвращает размер смещения"""
        offset = (self.stack_alignment_offset + (args_count - len(ABI_ARG_REGS)) * 8) % 16
        if offset:
            self._emit(f"    sub rsp, {offset}\n")
        return offset

    def emit_restore_stack_alignment_after_call(self, offset: int):
        """Восстанавливает указатель стека после вызова функции"""
        if offset:
            self._emit(f"    add rsp, {offset}\n")

    def emit_load_call_args(self, args_count):
        """Переносит аргументы вызова из стека в регистры согласно ABI"""
        for n in range(args_count):
            if n < len(ABI_ARG_REGS):
                self.emit_pop(ABI_ARG_REGS[n])

    def emit_clean_call_args(self, args_count):
        """Удаляет из стека аргументы, которые не поместились в регистры"""
        if args_count <= len(ABI_ARG_REGS):
            return
        offset = 8 * (args_count - len(ABI_ARG_REGS))
        self._emit(f"    add rsp, {offset}\n")
        self.stack_alignment_offset -= offset

    def get_endif_lab_id(self):
        """Возвращает уникальное имя метки для завершения if"""
        return f".endif_{next(self.endif_lab_count)}"

    def get_loop_lab_id(self):
        """Возвращает уникальное имя метки для цикла"""
        return f".loop_{next(self.loop_lab_count)}"

    def get_locals_bp_offset(self):
        """Возвращает смещение для выделения памяти под локальные переменные"""
        return len(self.locals) * 8 + self.arrays_size

    def add_var(self, var_name: str):
        """Добавляет новую локальную переменную и возвращает её смещение от rbp"""
        if var_name in self.locals:
            print(f"Error: var '{var_name}' already exists", file=sys.stderr)
            return False
        bp_offset = self.get_locals_bp_offset() + 8
        self.locals[var_name] = bp_offset
        return bp_offset

    def get_var_addr(self, var_name: str):
        """Возвращает адрес переменной в стеке (относительно rbp)"""
        if var_name not in self.locals:
            print(f"Error: var '{var_name}' undefined", file=sys.stderr)
            return None

        return f'rbp-{self.locals[var_name]}'

    def emit_store_val_to_var(self, var_name: str):
        """Сохраняет значение из rax в переменную"""
        if var_name not in self.locals:
            self.add_var(var_name)

        self._emit(f"    mov [{self.get_var_addr(var_name)}], rax\n")

    def emit_load_val_from_var(self, var_name: str):
        """Загружает значение переменной из памяти в rax"""
        if var_name not in self.locals:
            print(f"Error: var '{var_name}' undefined", file=sys.stderr)
            return

        self._emit(f"    mov rax, [{self.get_var_addr(var_name)}]\n")

    def emit_add_array(self, size: int):
        array_offset = self.get_locals_bp_offset() + size
        self.arrays_size += size
        self._emit(f"    lea rax, [rbp-{array_offset}]\n")

    def emit_add_const_array(self, data: bytes):
        size = len(data)
        name = self.parent.add_const_data(data)

        self.emit_add_array(size)

        self.emit_push("rsi")
        self.emit_push("rdi")

        self.emit_reg_assign("rdi", "rax")

        self._emit(f"    mov rsi, {name}\n")
        self._emit(f"    mov rcx, {size}\n")
        self._emit(f"    cld\n")
        self._emit(f"    rep movsb\n")

        self.emit_pop("rdi")
        self.emit_pop("rsi")

    def emit_prepare_fill_array(self):
        self.emit_push("rsi")
        self.emit_push("rdi")
        self.emit_push("rax")
        self.emit_reg_assign("rdi", "rax")
        self._emit(f"    cld\n")

    def emit_store(self):
        self._emit("    stosq\n")

    def emit_load(self):
        self._emit("    lodsq\n")

    def emit_finish_fill_array(self):
        self.emit_pop("rax")
        self.emit_pop("rdi")
        self.emit_pop("rsi")


    def generate_entry(self):
        """Генерирует пролог функции - сохранение rbp и выделение места в стеке"""
        bp_offset = self.get_locals_bp_offset()

        # Выравниваем смещение, чтобы переменные не изменяли его
        bp_offset += 16 - bp_offset % 16

        return [
             "    push rbp\n",
             "    mov rbp, rsp\n",
            f"    sub rsp, {bp_offset}\n" if bp_offset else ""
        ]

    def generate_leave(self):
        """Генерирует эпилог функции - восстановление стека"""
        return [
            "    mov rsp, rbp\n",
            "    pop rbp\n"
            "    ret\n"
        ]

    def emit_to_parent(self):
        """Добавляет готовый код функции в основной генератор программы"""
        program = []
        entry = self.generate_entry()
        leave = self.generate_leave()

        program.append(f"{self.name}:\n")
        program.extend(entry)
        program.extend(self.func_body)
        program.extend(leave)

        self.parent.extend_body(program)
