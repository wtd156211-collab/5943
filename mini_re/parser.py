"""递归下降解析器。

语法：
    regex      := branch ('|' branch)*
    branch     := quantified*
    quantified := atom quantifier?
    atom       := '(' regex ')' | '[' class ']' | '\\dDwWsS' | '.' | '^' | '$' | 普通字符
量词：* + ? {n} {n,} {n,m}，后面可跟 '?' 表示惰性。
"""

from .ast_nodes import (
    Empty, Literal, ClassPred, Concat, Alt, Group, Repeat, Anchor,
)
from .errors import ParseError
from .char_classes import (
    dot_pred, digit_pred, not_digit_pred, word_pred, not_word_pred,
    space_pred, not_space_pred, make_class,
)

_SIMPLE_ESCAPES = {
    "d": digit_pred, "D": not_digit_pred,
    "w": word_pred, "W": not_word_pred,
    "s": space_pred, "S": not_space_pred,
}


class Parser:
    def __init__(self, pattern):
        self.p = pattern
        self.n = len(pattern)
        self.i = 0
        self.group_count = 0

    # -- 基础工具 -------------------------------------------------------
    def error(self, code, pos, detail=None):
        raise ParseError(code, pos, self.p, detail)

    def parse(self):
        if self.n == 0:
            self.error("E_EMPTY_PATTERN", 0)
        node = self.parse_alt(0)
        if self.i != self.n:
            ch = self.p[self.i]
            if ch == ")":
                self.error("E_UNEXPECTED_RPAREN", self.i)
            self.error("E_UNEXPECTED_RPAREN", self.i, f"意外字符 {ch!r}")
        return node, self.group_count

    def parse_alt(self, open_pos):
        start = self.i
        branches = [self.parse_concat()]
        while self.i < self.n and self.p[self.i] == "|":
            self.i += 1
            branches.append(self.parse_concat())
        if self.i < self.n and self.p[self.i] == ")":
            if open_pos < 0:
                self.error("E_UNEXPECTED_RPAREN", self.i)
            self.i += 1
        else:
            if open_pos >= 0:
                self.error("E_UNCLOSED_GROUP", open_pos)
        if len(branches) == 1:
            return branches[0]
        return Alt(branches, start)

    def parse_concat(self):
        start = self.i
        items = []
        while self.i < self.n:
            ch = self.p[self.i]
            if ch in "|)":
                break
            atom = self.parse_atom()
            atom = self.parse_quantifier(atom)
            items.append(atom)
        if not items:
            return Empty(start)
        if len(items) == 1:
            return items[0]
        return Concat(items, start)

    def parse_atom(self):
        p = self.p
        i = self.i
        ch = p[i]
        if ch == "(":
            self.i += 1
            self.group_count += 1
            index = self.group_count
            inner = self.parse_alt(i)
            return Group(index, inner, i)
        if ch == "[":
            return self.parse_class()
        if ch == "\\":
            if i + 1 >= self.n:
                self.error("E_BAD_ESCAPE", i, "反斜杠位于模式末尾")
            tag = p[i + 1]
            factory = _SIMPLE_ESCAPES.get(tag)
            if factory is None:
                self.error("E_BAD_ESCAPE", i, f"\\{tag} 不在支持列表（\\d \\D \\w \\W \\s \\S）")
            self.i += 2
            return ClassPred(factory(), i)
        if ch == ".":
            self.i += 1
            return ClassPred(dot_pred(), i)
        if ch == "^":
            self.i += 1
            return Anchor("^", i)
        if ch == "$":
            self.i += 1
            return Anchor("$", i)
        self.i += 1
        return Literal(ch, i)

    def parse_quantifier(self, atom):
        if self.i >= self.n:
            return atom
        p = self.p
        ch = p[self.i]
        qpos = self.i
        if ch not in "*+?{":
            return atom
        if isinstance(atom, Repeat):
            self.error("E_REPEAT_MULTIPLE", qpos)
        if isinstance(atom, (Anchor,)):
            self.error("E_REPEAT_NOTHING", qpos)
        if ch in "*+?":
            table = {"*": (0, None), "+": (1, None), "?": (0, 1)}
            mn, mx = table[ch]
            self.i += 1
            lazy = False
            if self.i < self.n and p[self.i] == "?":
                lazy = True
                self.i += 1
            return Repeat(atom, mn, mx, lazy, qpos)
        # 花括号：只有完全长成 {n} / {n,} / {n,m} 时才算量词，
        # 其余（包括 '{,3}'、'{}'、不闭合）整体按普通字符处理。
        spec = self._try_brace_spec(qpos)
        if spec is None:
            return atom
        mn, mx, end = spec
        if isinstance(atom, (Anchor,)):
            self.error("E_REPEAT_NOTHING", qpos)
        if isinstance(atom, Repeat):
            self.error("E_REPEAT_MULTIPLE", qpos)
        self.i = end
        lazy = False
        if self.i < self.n and p[self.i] == "?":
            lazy = True
            self.i += 1
        return Repeat(atom, mn, mx, lazy, qpos)

    def _try_brace_spec(self, qpos):
        """返回 (min, max, 量词结束位置)；不是合法量词形式则返回 None。"""
        p = self.p
        n = self.n
        j = qpos + 1
        start = j
        while j < n and "0" <= p[j] <= "9":
            j += 1
        if j == start:
            return None
        mn = int(p[start:j])
        if j < n and p[j] == "}":
            return (mn, mn, j + 1)
        if j < n and p[j] == ",":
            k = j + 1
            dstart = k
            while k < n and "0" <= p[k] <= "9":
                k += 1
            if k < n and p[k] == "}":
                if k == dstart:
                    return (mn, None, k + 1)
                mx = int(p[dstart:k])
                if mn > mx:
                    self.error("E_REPEAT_RANGE", qpos, f"{mn} > {mx}")
                return (mn, mx, k + 1)
        return None

    # -- 字符类 ----------------------------------------------------------
    def parse_class(self):
        p = self.p
        n = self.n
        start = self.i  # '[' 的位置
        assert p[start] == "["
        j = start + 1
        negate = False
        if j < n and p[j] == "^":
            negate = True
            j += 1
        # ']' 紧跟在 '[' 或 '[^' 之后时是普通成员
        if j < n and p[j] == "]":
            j += 1
            first_literal = "]"
        else:
            first_literal = None
        literals = []
        if first_literal is not None:
            literals.append(first_literal)
        ranges = []
        classes = []
        while True:
            if j >= n:
                self.error("E_UNCLOSED_CLASS", start)
            if p[j] == "]":
                j += 1
                break
            lo, lo_is_class, after = self._class_element(j, start)
            # 看后面是不是 '-' 接一个端点
            if after < n and p[after] == "-" and after + 1 < n and p[after + 1] != "]":
                hi, hi_is_class, endj = self._class_element(after + 1, start)
                if lo_is_class or hi_is_class:
                    self.error("E_RANGE_CLASS", after)
                if ord(lo) > ord(hi):
                    self.error("E_BAD_RANGE", after, f"{lo!r}-{hi!r}")
                ranges.append((lo, hi))
                j = endj
            else:
                if lo_is_class:
                    classes.append(lo)
                else:
                    literals.append(lo)
                j = after
        self.i = j
        return ClassPred(make_class(literals, ranges, classes, negate), start)

    def _class_element(self, j, class_start):
        """读取字符类里的一个元素，返回 (值, 是否转义字符类谓词, 下一位置)。"""
        p = self.p
        n = self.n
        ch = p[j]
        if ch == "\\":
            if j + 1 >= n:
                self.error("E_BAD_ESCAPE", j, "反斜杠位于模式末尾")
            tag = p[j + 1]
            factory = _SIMPLE_ESCAPES.get(tag)
            if factory is not None:
                return (factory(), True, j + 2)
            self.error("E_BAD_ESCAPE", j, f"\\{tag} 不在支持列表（\\d \\D \\w \\W \\s \\S）")
        return (ch, False, j + 1)


def parse(pattern):
    parser = Parser(pattern)
    return parser.parse()
