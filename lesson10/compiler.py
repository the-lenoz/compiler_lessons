import collections
import os
import sys
from typing import Dict, List, OrderedDict

from codegen import CodeGenerator, FuncCodeGenerator, I64, BuiltinType, AbstractVar, FuncDescription, StructType
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

struct_decl_table: Dict[str, StructType] = {}
var_type_table: Dict[str, Dict[str, type[BuiltinType] | StructType]] = {}
func_type_table: Dict[str, type[BuiltinType]] = {}
def infer_expr_type(expr: Expr | None, f_gen: FuncCodeGenerator) -> StructType | type[BuiltinType] | None:
    if expr is None:
        return None
    match expr:
        case BinOP(l_child, r_child):
            if l_child is None or r_child is None:
                return None
            l_type = infer_expr_type(l_child, f_gen)
            if l_type != infer_expr_type(r_child, f_gen):
                return None
            return l_type
        case ParenExpr(e):
            if e is None:
                return None
            return infer_expr_type(e, f_gen)
        case StaticCast(typename=t):
            return BuiltinType.from_name(t.value)
        case StrConst():
            return I64
        case Array():
            return I64
        case Deref(typename=t):
            return BuiltinType.from_name(t.value) or struct_decl_table[t.value]
        case Ref():
            return I64
        case Call(name):
            return func_type_table[name.value]
        case Number():
            return I64
        case Id(name):
            return var_type_table[f_gen.description.name][name]
        case FieldAccess(struct, field_name):
            struct_t = infer_expr_type(struct, f_gen)
            if not isinstance(struct_t, StructType):
                return None
            return struct_t.fields[field_name.value].type

    return None



def process_expr(expr: Expr | None, f_gen: FuncCodeGenerator):
    """Обходит AST выражения и генерирует assembler-код для вычисления его значения в rax"""
    if expr is None:
        return

    if isinstance(expr, BinOP):
        t_l = infer_expr_type(expr.l_child, f_gen)
        t_r = infer_expr_type(expr.r_child, f_gen)

        if t_l is None or t_r is None:
            print(f"Error: cannot determine expression type '{expr}'\n", file=sys.stderr)
            return

        process_expr(expr.r_child, f_gen)
        f_gen.emit_push(t_r.reg_a, t_r.name)

        process_expr(expr.l_child, f_gen)

        f_gen.emit_pop(t_r.reg_b, t_r.name)

        t = infer_expr_type(expr, f_gen)

        if t is None:
            print(f"Error: cannot determine expression type '{expr}'\n", file=sys.stderr)
            return

        match expr:
            case Sum():
                f_gen.emit_add(t.name)
            case Sub():
                f_gen.emit_sub(t.name)
            case Mul():
                f_gen.emit_mul(t.name)
            case Div():
                f_gen.emit_div(t.name)
            case Eq():
                f_gen.emit_eq(t.name)
            case Lt():
                f_gen.emit_lt(t.name)
            case Gt():
                f_gen.emit_gt(t.name)
            case Lte():
                f_gen.emit_lte(t.name)
            case Gte():
                f_gen.emit_gte(t.name)

    elif isinstance(expr, StrConst):
        f_gen.emit_add_const_array(expr.data)

    elif isinstance(expr, Array):
        data = []
        data_AST = expr.data
        while data_AST is not None:
            data.append(data_AST.first_arg)
            data_AST = data_AST.next_args

        size = len(data) * 8
        f_gen.emit_add_array(size)
        f_gen.emit_prepare_fill_array()

        arr_type = None

        for expr in data:
            t = infer_expr_type(expr, f_gen)
            if arr_type is not None and arr_type is not t or t is None:
                print(f"Error: cannot determine array type '{expr}'\n", file=sys.stderr)
                return
            arr_type = t
            process_expr(expr, f_gen)
            f_gen.emit_store(arr_type.name)
        f_gen.emit_finish_fill_array()

    elif isinstance(expr, ParenExpr):
        process_expr(expr.expr, f_gen)

    elif isinstance(expr, StaticCast):
        from_t = infer_expr_type(expr.expr, f_gen)

        if from_t is None:
            print(f"Error: cannot determine expression type\n", file=sys.stderr)
            return

        process_expr(expr.expr, f_gen)
        f_gen.emit_static_cast(from_t.name, expr.typename.value)

    elif isinstance(expr, Deref):
        process_expr(expr.ptr, f_gen)
        f_gen.emit_reg_assign("rsi", "rax")
        f_gen.emit_load(expr.typename.value)

    elif isinstance(expr, Ref):
        process_lvalue(expr.obj, f_gen)

    elif isinstance(expr, Call):
        data = []
        data_AST = expr.args
        while data_AST is not None:
            data.append(data_AST.first_arg)
            data_AST = data_AST.next_args

        process_call(expr.name.value, data, f_gen)

    elif isinstance(expr, FieldAccess):
        t = process_lvalue(expr, f_gen)
        if t is None:
            print("Error: can't determine expr type", file=sys.stderr)
            return
        f_gen.emit_reg_assign("rsi", "rax")
        f_gen.emit_load(t.name)

    elif isinstance(expr, Number):
        f_gen.emit_reg_assign("rax", expr.value)

    elif isinstance(expr, Id):
        f_gen.emit_load_val_from_var(AbstractVar(
            name=expr.value,
            type=var_type_table[f_gen.description.name][expr.value]
        ))


def process_call(name: str, args: List[Expr], f_gen: FuncCodeGenerator):
    """Генерирует вычисление аргументов и вызов функции"""
    callee_description = f_gen.parent.get_func(name)
    f_gen.emit_call(callee_description, [lambda e=e: process_expr(e, f_gen) for e in args])

def process_lvalue(lvalue: LValue, f_gen: FuncCodeGenerator):
    match lvalue:
        case Id(value):
            t = var_type_table[f_gen.description.name][value]
            f_gen.emit_load_var_addr(AbstractVar(
                        type=t,
                        name=value
                    ))
            return t
        case Deref(typename, ptr):
            process_expr(ptr, f_gen)
            return BuiltinType.from_name(typename.value) or struct_decl_table[typename.value]
        case FieldAccess(struct, field_name):
            process_lvalue(struct, f_gen)
            struct_t = infer_expr_type(struct, f_gen)
            if struct_t is None:
                print(f"Error: can't determine expr '{struct}' type", file=sys.stderr)
                return None
            field_offset = struct_t.fields[field_name.value].offset
            f_gen.emit_reg_assign("rbx", field_offset)
            f_gen.emit_add("i64")
            return struct_t.fields[field_name.value].type
    return None


def process_stmt(statement: Stmt, f_gen: FuncCodeGenerator):
    """Обходит AST инструкции и генерирует assembler-код для неё"""
    match statement:
        case VarDecl(typename, identifier):
            var_type_table[f_gen.description.name][identifier.value] = BuiltinType.from_name(typename.value) \
                                                                       or struct_decl_table[typename.value]
            f_gen.add_var(
                AbstractVar(var_type_table[f_gen.description.name][identifier.value], identifier.value)
            )
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
        case Assignment(lvalue, expr):
            t = process_lvalue(lvalue, f_gen)
            if t is None:
                print(f"Error: can't determine expr '{lvalue}' type", file=sys.stderr)
                return
            f_gen.emit_push("rax", "i64")
            process_expr(expr, f_gen)
            f_gen.emit_pop("rdi", "i64")
            f_gen.emit_store(t.name)

        case Return(expr):
            process_expr(expr, f_gen)
            f_gen.emit_return()
        case Expr():
            process_expr(statement, f_gen)

def process_block(block: Block | None, f_gen: FuncCodeGenerator):
    """Обходит AST блока (списка инструкций) и генерирует assembler-код для каждой инструкции"""
    if block is None:
        return

    process_stmt(block.first_statement, f_gen)
    process_block(block.next_block, f_gen)

def process_decl_args(args: DeclArgs | None):
    result = []
    arg = args
    while arg is not None:
        result.append(AbstractVar(
            type=BuiltinType.from_name(arg.first_arg.typename.value),
            name=arg.first_arg.id.value
        ))
        arg = arg.next_args
    return result

def process_f_decl(decl: FDecl, codegen: CodeGenerator):
    """Регистрирует объявление внешней функции"""
    codegen.add_func(FuncDescription(
        name=decl.name.value,
        return_type=BuiltinType.from_name(decl.return_type_name.value),
        linkage="extern",
        args=process_decl_args(decl.args)
    ))
    var_type_table[decl.name.value] = {}
    for arg in process_decl_args(decl.args):
        var_type_table[decl.name.value][arg.name] = arg.type
    func_type_table[decl.name.value] = BuiltinType.from_name(decl.return_type_name.value)


def process_f_def(definition: FDef, codegen: CodeGenerator):
    """Генерирует assembler-код определения функции"""
    descr = FuncDescription(
        name=definition.decl.name.value,
        return_type=BuiltinType.from_name(definition.decl.return_type_name.value),
        linkage="intern",
        args=process_decl_args(definition.decl.args)
    )
    func_type_table[descr.name] = descr.return_type
    var_type_table[definition.decl.name.value] = {}
    for arg in process_decl_args(definition.decl.args):
        var_type_table[definition.decl.name.value][arg.name] = arg.type

    f_gen = FuncCodeGenerator(descr, codegen)
    f_gen.emit_use_args()

    process_block(definition.body, f_gen)
    f_gen.emit_to_parent()

def process_struct_decl(decl: StructDecl):
    arg_list = []
    next_arg = decl.args
    while next_arg is not None:
        t = BuiltinType.from_name(next_arg.first_arg.typename.value) \
            or struct_decl_table.get(next_arg.first_arg.typename.value)
        if t is None:
            print(f"Error: unknown type {next_arg.first_arg.typename.value}", file=sys.stderr)
            return
        arg_list.append(AbstractVar(t, next_arg.first_arg.id.value))
        next_arg = next_arg.next_args

    struct_decl_table[decl.name.value] = StructType.make_struct_type(decl.name.value, arg_list)

def process_f_block(block: GlobalBlock | None, codegen: CodeGenerator):
    """Обходит AST блока функций и генерирует assembler-код для каждой функции"""
    if block is None:
        return

    match block.first_stmt:
        case FDecl():
            process_f_decl(block.first_stmt, codegen)
        case FDef():
            process_f_def(block.first_stmt, codegen)
        case StructDecl():
            process_struct_decl(block.first_stmt)

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
