from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from itertools import count
from typing import List, Dict, Literal, Iterable, OrderedDict

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

class BuiltinType:
    name: str
    size: int

    reg_a: str
    reg_b: str

    mov: str

    add: str
    sub: str
    mul: str
    div: str
    cmp: str

    upcast: str
    downcast: str
    cross_cast: str

    widest: str

    abi_regs: List[str]

    @classmethod
    def make_add(cls):
        return f"    {cls.add} {cls.reg_a}, {cls.reg_b}\n"

    @classmethod
    def make_sub(cls):
        return f"    {cls.sub} {cls.reg_a}, {cls.reg_b}\n"

    @classmethod
    def make_mul(cls):
        return f"    {cls.mul} {cls.reg_a}, {cls.reg_b}\n"

    @classmethod
    def make_div(cls):
        return ("    cqo\n"
                f"    {cls.div} {cls.reg_b}\n") if cls.div == "idiv" else f"    {cls.div} {cls.reg_a}, {cls.reg_b}\n"

    @classmethod
    def make_lt(cls):
        return (f"    {cls.cmp} {cls.reg_a}, {cls.reg_b}\n"
                "    setl al\n"
                "    movzx rax, al\n")

    @classmethod
    def make_gt(cls):
        return (f"    {cls.cmp} {cls.reg_a}, {cls.reg_b}\n"
                "    setg al\n"
                "    movzx rax, al\n")

    @classmethod
    def make_lte(cls):
        return (f"    {cls.cmp} {cls.reg_a}, {cls.reg_b}\n"
                "    setle al\n"
                "    movzx rax, al\n")

    @classmethod
    def make_gte(cls):
        return (f"    {cls.cmp} {cls.reg_a}, {cls.reg_b}\n"
                "    setge al\n"
                "    movzx rax, al\n")

    @classmethod
    def make_eq(cls):
        return (f"    {cls.cmp} {cls.reg_a}, {cls.reg_b}\n"
                "    sete al\n"
                "    movzx rax, al\n")

    @classmethod
    def make_upcast_from(cls):
        widest = cls.from_name(cls.widest)
        return "" if widest is cls else f"    {cls.upcast} {widest.reg_a}, {cls.reg_a}\n"

    @classmethod
    def make_downcast_to(cls):
        widest = cls.from_name(cls.widest)
        return "" if widest is cls or cls.downcast == "nop" else f"    {cls.downcast} {cls.reg_a}, {widest.reg_a}\n"

    @classmethod
    def make_cross_cast(cls, to):
        return f"    {cls.cross_cast} {to.reg_a}, {cls.reg_a}\n"

    @classmethod
    def align(cls, address: int, call_abi: bool = False):
        alignment = cls.from_name(cls.widest).size if call_abi else cls.size

        offset = address % alignment
        if offset == 0:
            return address
        return address + alignment - offset

    @staticmethod
    def from_name(name: str):
        match name:
            case "i8":
                return I8
            case "i32":
                return I32
            case "i64":
                return I64
            case "fp32":
                return FP32
            case "fp64":
                return FP64
        return None


class I8(BuiltinType):
    name = "i8"
    size = 1
    reg_a = "al"
    reg_b = "bl"
    mov = "mov"
    add = "add"
    sub = "sub"
    mul = "imul"
    div = "idiv"
    cmp = "cmp"
    upcast = "movsx"
    downcast = "nop"
    widest = "i64"
    abi_regs = ["dil", "sil", "dl", "cl", "r8b", "r9b"]
class I32(BuiltinType):
    name = "i32"
    size = 4
    reg_a = "eax"
    reg_b = "ebx"
    mov = "mov"
    add = "add"
    sub = "sub"
    mul = "imul"
    div = "idiv"
    cmp = "cmp"
    upcast = "movsxd"
    downcast = "nop"
    widest = "i64"
    abi_regs = ["edi", "esi", "edx", "ecx", "r8d", "r9d"]
class I64(BuiltinType):
    name = "i64"
    size = 8
    reg_a = "rax"
    reg_b = "rbx"
    mov = "mov"
    add = "add"
    sub = "sub"
    mul = "imul"
    div = "idiv"
    cmp = "cmp"
    cross_cast = "cvtsi2sd"
    widest = "i64"
    abi_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
class FP32(BuiltinType):
    name = "fp32"
    size = 4
    reg_a = "xmm0"
    reg_b = "xmm1"
    mov = "movss"
    add = "addss"
    sub = "subss"
    mul = "mulss"
    div = "divss"
    cmp = "ucomiss"
    upcast = "cvtss2sd"
    downcast = "cvtsd2ss"
    widest = "fp64"
    abi_regs = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7"]
class FP64(BuiltinType):
    name = "fp64"
    size = 8
    reg_a = "xmm0"
    reg_b = "xmm1"
    mov = "movsd"
    add = "addsd"
    sub = "subsd"
    mul = "mulsd"
    div = "divsd"
    cmp = "ucomisd"
    cross_cast = "cvtsd2si"
    widest = "fp64"
    abi_regs = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7"]

@dataclass(frozen=True)
class AbstractVar:
    type: type[BuiltinType]
    name: str

@dataclass(frozen=True)
class LocalVar(AbstractVar):
    offset: int

@dataclass
class FuncDescription:
    name: str
    args: List[AbstractVar]
    return_type: type[BuiltinType]
    linkage: Literal["intern", "extern"]

class CodeGenerator:
    # Объявляем программу как список текстовых фрагментов - так будет удобно модифицировать её
    program_body: list
    funcs: Dict[str, FuncDescription]

    constants: count
    data_body: list

    def __init__(self):
        """Создаёт генератор с пустым телом программы и таблицей функций"""
        self.program_body = []
        self.data_body = []
        self.funcs = {}
        self.constants = count()

    def add_const_data(self, data: bytes):
        name = f"const_{next(self.constants)}"
        self.data_body.append(f"    {name} db " + ",".join((f"{hex(byte)}" for byte in data)) + "\n")
        return name

    def extend_body(self, func_body: list):
        """Добавляет сгенерированное тело функции в программу"""
        self.program_body.extend(func_body)

    def add_func(self, description: FuncDescription):
        """Добавляет имя внутренней или внешней функции в таблицу функций"""
        self.funcs[description.name] = description

    def get_func(self, name: str):
        return self.funcs.get(name, None)

    def write_program(self, path: str):
        """Записывает программу-список в файл, склеивая её в одну строку"""

        # Открываем файл на запись безопасно
        with open(path, 'w') as file:
            file.write("".join(
                [program_data_section] +
                self.data_body +
                [program_prolog] +
                [f"    extern {name}\n" for name, kind in self.funcs.items() if kind == "extern"] +
                self.program_body
            ))

class FuncCodeGenerator:
    locals: Dict[str, LocalVar]
    arrays_size: int

    endif_lab_count: count
    loop_lab_count: count

    description: FuncDescription

    stack_alignment_offset: int

    parent: CodeGenerator

    def __init__(self, description: FuncDescription, parent: CodeGenerator):
        """Создаёт генератор кода для функции с переданным именем"""
        self.func_body = []
        self.locals = {}
        self.endif_lab_count = count()
        self.loop_lab_count = count()
        self.description = description
        self.stack_alignment_offset = 8
        self.arrays_size = 0

        self.parent = parent

        self.parent.add_func(description)

    def emit_use_args(self):
        """Сохраняет аргументы функции в локальные переменные согласно ABI"""
        abi_reg_counters = defaultdict(lambda: 0)
        current_arg_offset = 16
        for arg in self.description.args:
            if abi_reg_counters[arg.type.widest] < len(arg.type.abi_regs):
                self._emit(
                    f"    {arg.type.mov} {arg.type.reg_a}, {arg.type.abi_regs[abi_reg_counters[arg.type.widest]]}\n"
                )
                self.emit_store_val_to_var(arg)
                abi_reg_counters[arg.type.widest] += 1
            else:
                current_arg_offset = arg.type.align(current_arg_offset, call_abi=True)
                self.locals[arg.name] = LocalVar(
                    type=arg.type,
                    name=arg.name,
                    offset=-current_arg_offset
                )
                current_arg_offset += arg.type.size


    def _emit(self, string: str):
        """Добавляет строку assembler-кода в программу"""
        self.func_body.append(string)

    def emit_push(self, reg: str, typename: str):
        """Добавляет в программу команду push - сохранение регистра в стек"""
        t = self.get_type_or_error(typename)
        w = self.get_type_or_error(t.widest)

        self._emit(f"    sub rsp, {w.size}\n")
        self._emit(f"    {t.mov} [rsp], {reg}\n")

        self.stack_alignment_offset += w.size

    def emit_pop(self, reg: str, typename: str):
        """Добавляет в программу команду pop - извлечение значения из стека в регистр"""
        t = self.get_type_or_error(typename)
        w = self.get_type_or_error(t.widest)

        self._emit(f"    {t.mov} {reg}, [rsp]\n")
        self._emit(f"    add rsp, {w.size}\n")

        self.stack_alignment_offset -= w.size

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

    def emit_return(self):
        """Выходит из функции"""
        self.func_body.extend(
            self.generate_leave()
        )

    def emit_lea(self, addr_expr):
        self._emit(f"    lea rax, [{addr_expr}]\n")

    def emit_add(self, typename: str):
        self._emit(
            self.get_type_or_error(typename).make_add()
        )

    def emit_sub(self, typename: str):
        self._emit(
            self.get_type_or_error(typename).make_sub()
        )

    def emit_mul(self, typename: str):
        self._emit(
            self.get_type_or_error(typename).make_mul()
        )

    def emit_div(self, typename: str):
        self._emit(
            self.get_type_or_error(typename).make_div()
        )

    def emit_eq(self, typename: str):
        self._emit(
            self.get_type_or_error(typename).make_eq()
        )

    def emit_lt(self, typename: str):
        self._emit(
            self.get_type_or_error(typename).make_lt()
        )

    def emit_gt(self, typename: str):
        self._emit(
            self.get_type_or_error(typename).make_gt()
        )

    def emit_lte(self, typename: str):
        self._emit(
            self.get_type_or_error(typename).make_lte()
        )

    def emit_gte(self, typename: str):
        self._emit(
            self.get_type_or_error(typename).make_gte()
        )

    def emit_static_cast(self, from_t: str, to_t: str):
        t1 = self.get_type_or_error(from_t)
        t2 = self.get_type_or_error(to_t)

        w1 = self.get_type_or_error(t1.widest)
        w2 = self.get_type_or_error(t2.widest)

        self._emit(t1.make_upcast_from())

        if w1 is not w2:
            self._emit(w1.make_cross_cast(w2))

        self._emit(t2.make_downcast_to())

    def emit_call(self, callee_description: FuncDescription, args_calc: List):
        """Передаёт аргументы, вызывает функцию и очищает стек после вызова"""
        offset = self.emit_align_stack_before_call(callee_description.args)
        self.emit_load_call_args(callee_description.args, args_calc)
        self._emit(f"    call {callee_description.name}\n")
        self.emit_clean_call_args(callee_description.args)
        self.emit_restore_stack_alignment_after_call(offset)

    def emit_align_stack_before_call(self, args: List[AbstractVar]):
        """Выравнивает стек перед вызовом функции и возвращает размер смещения"""
        offset = (self.stack_alignment_offset + self.get_args_offset(args)) % 16
        if offset:
            self._emit(f"    sub rsp, {offset}\n")
        return offset

    def emit_restore_stack_alignment_after_call(self, offset: int):
        """Восстанавливает указатель стека после вызова функции"""
        if offset:
            self._emit(f"    add rsp, {offset}\n")

    def emit_load_call_args(self, args: List[AbstractVar], args_calc: List):
        """Вычисляет аргументы функции и рамещает их в регистры и стек согласно ABI"""
        int_counter = 0
        fp_counter = 0
        stack_args = OrderedDict(zip(args, args_calc))
        reg_args = OrderedDict()
        for arg in args:
            if arg.type.widest == "i64" and int_counter < len(arg.type.abi_regs):
                int_counter += 1
                reg_args[arg] = stack_args.pop(arg)
        for arg in args:
            if arg.type.widest == "fp64" and fp_counter < len(arg.type.abi_regs):
                fp_counter += 1
                reg_args[arg] = stack_args.pop(arg)

        for arg, emit_process_arg in reversed(stack_args.items()):
            emit_process_arg()
            self.emit_push(arg.type.reg_a, arg.type.name)

        for arg, emit_process_arg in reversed(reg_args.items()):
            emit_process_arg()
            self.emit_push(arg.type.reg_a, arg.type.name)

        reg_arg_vars = list(reg_args.keys())
        for i in range(int_counter):
            self.emit_pop(reg_arg_vars[i].type.abi_regs[i], reg_arg_vars[i].type.name)
        for i in range(fp_counter):
            self.emit_pop(reg_arg_vars[i + int_counter].type.abi_regs[i], reg_arg_vars[i + int_counter].type.name)

    def emit_clean_call_args(self, args: List[AbstractVar]):
        """Удаляет из стека аргументы, которые не поместились в регистры"""
        offset = self.get_args_offset(args)
        if offset == 0:
            return
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
        return self.get_vars_offset(self.locals.values()) + self.arrays_size

    @staticmethod
    def get_vars_offset(variables: Iterable[AbstractVar]):
        offset = 0
        for var in variables:
            offset += var.type.size
        return offset

    def get_args_offset(self, args: List[AbstractVar]):
        offset = 0
        abi_reg_counters = defaultdict(lambda: 0)
        for arg in args:
            if abi_reg_counters[arg.type.widest] < len(arg.type.abi_regs):
                abi_reg_counters[arg.type.widest] += 1
            else:
                w = self.get_type_or_error(arg.type.widest)
                offset += w.size
        return offset

    def add_var(self, var: AbstractVar):
        """Добавляет новую локальную переменную и возвращает её смещение от rbp"""
        if var.name in self.locals:
            print(f"Error: var '{var.name}' already exists", file=sys.stderr)
            return False
        bp_offset = self.get_locals_bp_offset() + var.type.size
        self.locals[var.name] = LocalVar(
            type=var.type,
            name=var.name,
            offset=bp_offset
        )
        return bp_offset

    def get_var_addr(self, var: AbstractVar):
        """Возвращает адрес переменной в стеке (относительно rbp)"""
        if var.name not in self.locals:
            print(f"Error: var '{var.name}' undefined", file=sys.stderr)
            return None

        return f'rbp-{self.locals[var.name].offset}'

    def emit_store_val_to_var(self, var: AbstractVar):
        """Сохраняет значение из rax в переменную"""
        if var.name not in self.locals:
            self.add_var(var)

        self._emit(f"    {var.type.mov} [{self.get_var_addr(var)}], {var.type.reg_a}\n")

    def emit_load_val_from_var(self, var: AbstractVar):
        """Загружает значение переменной из памяти в rax"""
        if var.name not in self.locals:
            print(f"Error: var '{var.name}' undefined", file=sys.stderr)
            return

        self._emit(f"    {var.type.mov} {var.type.reg_a}, [{self.get_var_addr(var)}]\n")

    def emit_add_array(self, size: int):
        array_offset = self.get_locals_bp_offset() + size
        self.arrays_size += size
        self._emit(f"    lea rax, [rbp-{array_offset}]\n")

    def emit_add_const_array(self, data: bytes):
        size = len(data)
        name = self.parent.add_const_data(data)

        self.emit_add_array(size)

        self.emit_push("rsi", "i64")
        self.emit_push("rdi", "i64")

        self.emit_reg_assign("rdi", "rax")

        self._emit(f"    mov rsi, {name}\n")
        self._emit(f"    mov rcx, {size}\n")
        self._emit(f"    cld\n")
        self._emit(f"    rep movsb\n")

        self.emit_pop("rdi", "i64")
        self.emit_pop("rsi", "i64")

    def emit_prepare_fill_array(self):
        self.emit_push("rsi", "i64")
        self.emit_push("rdi", "i64")
        self.emit_push("rax", "i64")
        self.emit_reg_assign("rdi", "rax")
        self._emit(f"    cld\n")

    def emit_store(self, typename: str):
        t = self.get_type_or_error(typename)
        self._emit(f"    {t.mov} [rdi], {t.reg_a}\n")

    def emit_load(self, typename: str):
        t = self.get_type_or_error(typename)
        self._emit(f"    {t.mov} {t.reg_a}, [rsi]\n")

    def emit_finish_fill_array(self):
        self.emit_pop("rax", "i64")
        self.emit_pop("rdi", "i64")
        self.emit_pop("rsi", "i64")

    @staticmethod
    def get_type_or_error(typename: str) -> type[BuiltinType]:
        res_type = BuiltinType.from_name(typename)
        if res_type is None:
            print(f"Error: type {typename} does not support this operation", file=sys.stderr)
            return BuiltinType
        return res_type

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

    @staticmethod
    def generate_leave():
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

        program.append(f"{self.description.name}:\n")
        program.extend(entry)
        program.extend(self.func_body)
        program.extend(leave)

        self.parent.extend_body(program)
