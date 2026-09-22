"""编译器：把 AST 编译成回溯虚拟机指令序列。

指令集（整数操作码）：
    CHAR c        当前字符等于 c 则前进，否则失败
    ANY           当前字符不是换行则前进，否则失败
    CLASS pred    当前字符满足谓词 pred 则前进，否则失败
    SPLIT a b     优先尝试 a，失败则回溯到 b
    JMP x         无条件跳转
    SAVE k        把当前位置写入寄存器 k（捕获组边界）
    BOL / EOL     行首 / 行尾断言（多行语义：\n 之后 / 之前也算）
    SETGUARD k    把当前位置写入守卫寄存器 k（防空循环）
    JMPNE k x     当前位置与守卫寄存器 k 不同则跳转 x，否则顺序执行
    MATCH         匹配成功
"""

from . import parser as ast
from .errors import PatternError, E_REPEAT_TOO_LARGE

CHAR, ANY, CLASS, SPLIT, JMP, SAVE, BOL, EOL, SETGUARD, JMPNE, MATCH = range(11)

# 量词展开后允许的指令数上限，超过报 1008
MAX_INSTRUCTIONS = 100_000


def _is_word(ch):
    # 与标准库 re 的 \w 对齐：Unicode 字母数字加下划线
    return ch == "_" or ch.isalnum()


def _is_space(ch):
    # 与标准库 re 的 \s 对齐：排除 str.isspace() 多出来的 \x1c-\x1f
    return ch.isspace() and ch not in "\x1c\x1d\x1e\x1f"


def _class_predicate(kind):
    if kind == "d":
        return str.isdecimal
    if kind == "D":
        return lambda ch: not ch.isdecimal()
    if kind == "w":
        return _is_word
    if kind == "W":
        return lambda ch: not _is_word(ch)
    if kind == "s":
        return _is_space
    return lambda ch: not _is_space(ch)  # 'S'


def _build_class_matcher(node):
    ranges = []
    preds = []
    for item in node.items:
        if item[0] == "rng":
            ranges.append((item[1], item[2]))
        else:
            preds.append(_class_predicate(item[1]))
    ranges = tuple(ranges)
    preds = tuple(preds)
    negated = node.negated

    def match(ch):
        o = ord(ch)
        inside = False
        for lo, hi in ranges:
            if lo <= o <= hi:
                inside = True
                break
        if not inside:
            for pred in preds:
                if pred(ch):
                    inside = True
                    break
        return inside != negated

    return match


class Compiler:
    def __init__(self, ngroups, pattern):
        self.pattern = pattern
        self.code = []
        self.nguards = 0
        # 寄存器布局：0..2*ngroups+1 为捕获组边界，之后是守卫寄存器
        self.guard_base = 2 * (ngroups + 1)

    def emit(self, ins):
        self.code.append(ins)
        if len(self.code) > MAX_INSTRUCTIONS:
            raise PatternError(E_REPEAT_TOO_LARGE, 0,
                               "量词展开后指令数超过上限 %d" % MAX_INSTRUCTIONS,
                               self.pattern)

    def new_guard(self):
        slot = self.guard_base + self.nguards
        self.nguards += 1
        return slot

    def emit_node(self, node):
        if isinstance(node, ast.Literal):
            self.emit((CHAR, node.ch))
        elif isinstance(node, ast.Dot):
            self.emit((ANY,))
        elif isinstance(node, ast.ClassEscape):
            self.emit((CLASS, _class_predicate(node.kind)))
        elif isinstance(node, ast.CharClass):
            self.emit((CLASS, _build_class_matcher(node)))
        elif isinstance(node, ast.Anchor):
            self.emit((BOL,) if node.kind == "bol" else (EOL,))
        elif isinstance(node, ast.Concat):
            for item in node.items:
                self.emit_node(item)
        elif isinstance(node, ast.Group):
            self.emit((SAVE, 2 * node.index))
            self.emit_node(node.child)
            self.emit((SAVE, 2 * node.index + 1))
        elif isinstance(node, ast.Alternate):
            self.emit_alternate(node.branches)
        elif isinstance(node, ast.Repeat):
            self.emit_repeat(node)
        else:
            raise AssertionError("未知节点 %r" % (node,))

    def emit_alternate(self, branches):
        # a|b|c => SPLIT L1, next; L1: a; JMP end; next: SPLIT ...
        end_jumps = []
        for idx, branch in enumerate(branches):
            if idx < len(branches) - 1:
                split_pos = len(self.code)
                self.emit(None)  # SPLIT 占位
                self.emit_node(branch)
                jmp_pos = len(self.code)
                self.emit(None)  # JMP end 占位
                end_jumps.append(jmp_pos)
                self.code[split_pos] = (SPLIT, split_pos + 1, len(self.code))
            else:
                self.emit_node(branch)
        end = len(self.code)
        for jmp_pos in end_jumps:
            self.code[jmp_pos] = (JMP, end)

    def emit_repeat(self, node):
        lo, hi, lazy = node.min, node.max, node.lazy
        child = node.child
        if hi is None:
            # e{n,} = e 重复 n 次后接 e*
            for _ in range(lo):
                self.emit_node(child)
            self.emit_star(child, lazy)
        else:
            for _ in range(lo):
                self.emit_node(child)
            # 可选部分嵌套：e{n,m} 的多余 m-n 次 => e (e (e)?)?)?
            self.emit_optional_chain(child, hi - lo, lazy)

    def emit_optional_chain(self, child, count, lazy):
        if count == 0:
            return
        # 展开成 count 段可选迭代，每段带空迭代守卫：
        # 某次迭代没有消费字符就停止后续迭代（对齐标准库 REPEAT 的空检查），
        # 该次空迭代写入的捕获保留。
        splits = []
        out_jumps = []
        for k in range(count):
            split_pos = len(self.code)
            self.emit(None)  # SPLIT 占位
            splits.append(split_pos)
            guard = self.new_guard()
            self.emit((SETGUARD, guard))
            self.emit_node(child)
            if k < count - 1:
                # 消费了字符才进入下一段迭代，否则直接跳到整体出口
                self.emit((JMPNE, guard, len(self.code) + 2))
                jmp_pos = len(self.code)
                self.emit(None)  # JMP out 占位
                out_jumps.append(jmp_pos)
        out = len(self.code)
        for split_pos in splits:
            body_pos = split_pos + 1
            if lazy:
                self.code[split_pos] = (SPLIT, out, body_pos)
            else:
                self.code[split_pos] = (SPLIT, body_pos, out)
        for jmp_pos in out_jumps:
            self.code[jmp_pos] = (JMP, out)

    def emit_star(self, child, lazy):
        guard = self.new_guard()
        split_pos = len(self.code)
        self.emit(None)  # SPLIT 占位
        body_pos = len(self.code)
        self.emit((SETGUARD, guard))
        self.emit_node(child)
        # 只有本次迭代消费了字符才允许继续循环，防止 (a*)* 之类空转死循环
        self.emit((JMPNE, guard, split_pos))
        end = len(self.code)
        if lazy:
            self.code[split_pos] = (SPLIT, end, body_pos)
        else:
            self.code[split_pos] = (SPLIT, body_pos, end)


def compile_ast(node, ngroups, pattern):
    """编译 AST，返回 (指令列表, 寄存器总数)。"""
    compiler = Compiler(ngroups, pattern)
    compiler.emit((SAVE, 0))
    compiler.emit_node(node)
    compiler.emit((SAVE, 1))
    compiler.emit((MATCH,))
    nregs = compiler.guard_base + compiler.nguards
    return compiler.code, nregs
