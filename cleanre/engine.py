"""匹配引擎：带回溯的正则虚拟机，全程统计步数，超预算立即中止。

设计要点：
- 解释器是迭代式的（显式回溯栈），不消耗 Python 调用栈，长文本不会爆栈。
- 每执行一条虚拟机指令计 1 步；预算按“从某个起始位置的一次匹配尝试”计算，
  超出即抛出 BudgetExceeded，整个查询中止。
- 所有匹配状态（程序计数器、位置、寄存器、回溯栈）都是单次调用的局部变量，
  中止后不留任何脏状态，同一 Pattern 可立即复用。
"""

from . import compiler as _compiler
from .compiler import CHAR, ANY, CLASS, SPLIT, JMP, SAVE, BOL, EOL, SETGUARD, JMPNE, MATCH
from .errors import BudgetExceeded
from .parser import parse

# 默认步数预算：单个起始位置上一次匹配尝试允许执行的指令数
DEFAULT_MAX_STEPS = 1_000_000


class Match:
    """一次匹配的结果，接口对齐标准库 re.Match 的常用子集。"""

    __slots__ = ("_text", "_regs", "_ngroups")

    def __init__(self, text, regs, ngroups):
        self._text = text
        self._regs = regs
        self._ngroups = ngroups

    def span(self, group=0):
        lo = self._regs[2 * group]
        hi = self._regs[2 * group + 1]
        if lo is None:
            return (-1, -1)
        return (lo, hi)

    def start(self, group=0):
        return self.span(group)[0]

    def end(self, group=0):
        return self.span(group)[1]

    def group(self, *ids):
        if not ids:
            ids = (0,)
        result = tuple(self._group_one(i) for i in ids)
        return result[0] if len(result) == 1 else result

    def _group_one(self, i):
        lo, hi = self.span(i)
        if lo < 0:
            return None
        return self._text[lo:hi]

    def groups(self, default=None):
        return tuple(
            self._group_one(i) if self.span(i)[0] >= 0 else default
            for i in range(1, self._ngroups + 1)
        )

    def __getitem__(self, i):
        return self._group_one(i)

    def __repr__(self):
        return "<Match span=%r groups=%d>" % (self.span(), self._ngroups)


class Pattern:
    """编译后的模式。对象不可变，可跨线程、跨调用安全复用。"""

    def __init__(self, pattern, max_steps=DEFAULT_MAX_STEPS):
        self.pattern = pattern
        self.max_steps = max_steps
        node, ngroups = parse(pattern)
        self.groups = ngroups
        self._code, self._nregs = _compiler.compile_ast(node, ngroups, pattern)

    # ---- 内部：虚拟机 ----
    def _run_at(self, text, start, forbid_empty=False):
        """从 start 位置尝试匹配，成功返回寄存器元组，失败返回 None。

        步数预算针对这一次尝试；超预算抛 BudgetExceeded。
        forbid_empty 为 True 时空匹配视为失败并继续回溯（对齐标准库
        finditer 在空匹配之后允许同位置非空匹配的行为）。
        """
        code = self._code
        n = len(text)
        steps = self.max_steps
        empty_regs = (None,) * self._nregs
        stack = [(0, start, empty_regs)]
        while stack:
            pc, pos, regs = stack.pop()
            while True:
                steps -= 1
                if steps < 0:
                    raise BudgetExceeded(self.pattern, self.max_steps, start, text)
                ins = code[pc]
                op = ins[0]
                if op == CHAR:
                    if pos < n and text[pos] == ins[1]:
                        pos += 1
                        pc += 1
                        continue
                    break
                if op == ANY:
                    if pos < n and text[pos] != "\n":
                        pos += 1
                        pc += 1
                        continue
                    break
                if op == CLASS:
                    if pos < n and ins[1](text[pos]):
                        pos += 1
                        pc += 1
                        continue
                    break
                if op == SPLIT:
                    stack.append((ins[2], pos, regs))
                    pc = ins[1]
                    continue
                if op == JMP:
                    pc = ins[1]
                    continue
                if op == SAVE or op == SETGUARD:
                    slot = ins[1]
                    regs = regs[:slot] + (pos,) + regs[slot + 1:]
                    pc += 1
                    continue
                if op == BOL:
                    if pos == 0 or text[pos - 1] == "\n":
                        pc += 1
                        continue
                    break
                if op == EOL:
                    if pos == n or text[pos] == "\n":
                        pc += 1
                        continue
                    break
                if op == JMPNE:
                    if pos != regs[ins[1]]:
                        pc = ins[2]
                        continue
                    pc += 1
                    continue
                # MATCH
                if forbid_empty and regs[0] == regs[1]:
                    break
                return regs
        return None

    def _search(self, text, pos, forbid_empty_at=-1):
        n = len(text)
        start = pos
        while start <= n:
            regs = self._run_at(text, start, forbid_empty=(start == forbid_empty_at))
            if regs is not None:
                return Match(text, regs, self.groups)
            start += 1
        return None

    # ---- 公开 API ----
    def match(self, text, pos=0):
        """只从 pos 位置开始尝试匹配（不要求匹配到文本末尾）。"""
        regs = self._run_at(text, pos)
        if regs is None:
            return None
        return Match(text, regs, self.groups)

    def search(self, text, pos=0):
        """从 pos 起扫描，返回第一个匹配，没有则返回 None。"""
        return self._search(text, pos)

    def finditer(self, text):
        """逐个产生不重叠的匹配，行为对齐标准库 re.finditer。"""
        n = len(text)
        pos = 0
        forbid_empty_at = -1
        while pos <= n:
            m = self._search(text, pos, forbid_empty_at)
            if m is None:
                return
            yield m
            end = m.end()
            if end == m.start():
                # 空匹配：下一次允许从同一位置取非空匹配，但禁止同位置空匹配
                pos = end
                forbid_empty_at = end
            else:
                pos = end
                forbid_empty_at = -1

    def findall(self, text):
        """无捕获组时返回整体匹配列表；有捕获组时返回各组内容（对齐 re.findall）。"""
        result = []
        for m in self.finditer(text):
            if self.groups == 0:
                result.append(m.group(0))
            elif self.groups == 1:
                result.append(m.group(1))
            else:
                result.append(m.groups())
        return result

    def __repr__(self):
        return "<Pattern %r>" % (self.pattern,)


def compile(pattern, max_steps=DEFAULT_MAX_STEPS):
    """编译模式，返回 Pattern。模式非法时抛 PatternError。"""
    return Pattern(pattern, max_steps=max_steps)
