"""模式解析：把正则字符串解析成 AST。

只支持 samples/patterns.txt 清单里列出的语法，清单外的一律报错或按字面量处理
（与标准库 re 的行为对齐，例如 `a{` 中的 `{` 按字面量处理）。
"""

from .errors import (
    PatternError,
    E_UNCLOSED_GROUP,
    E_UNCLOSED_CLASS,
    E_REPEAT_RANGE_REVERSED,
    E_CLASS_RANGE_REVERSED,
    E_NOTHING_TO_REPEAT,
    E_BAD_ESCAPE,
    E_UNBALANCED_PAREN,
)

# 支持反斜杠转义的字符类
CLASS_ESCAPES = frozenset("dDwWsS")


class Literal:
    __slots__ = ("ch",)

    def __init__(self, ch):
        self.ch = ch


class Dot:
    __slots__ = ()


class CharClass:
    """字符类。items 为 ('rng', lo, hi) 或 ('set', kind)，kind 取 'd'/'D'/'w'/'W'/'s'/'S'。"""

    __slots__ = ("negated", "items")

    def __init__(self, negated, items):
        self.negated = negated
        self.items = items


class ClassEscape:
    __slots__ = ("kind",)

    def __init__(self, kind):
        self.kind = kind


class Anchor:
    __slots__ = ("kind",)  # 'bol' 或 'eol'

    def __init__(self, kind):
        self.kind = kind


class Group:
    __slots__ = ("index", "child")

    def __init__(self, index, child):
        self.index = index
        self.child = child


class Alternate:
    __slots__ = ("branches",)

    def __init__(self, branches):
        self.branches = branches


class Concat:
    __slots__ = ("items",)

    def __init__(self, items):
        self.items = items


class Repeat:
    """min 重复下限；max 为 None 表示无上限；lazy 表示惰性。"""

    __slots__ = ("child", "min", "max", "lazy", "pos")

    def __init__(self, child, min, max, lazy, pos):
        self.child = child
        self.min = min
        self.max = max
        self.lazy = lazy
        self.pos = pos


def _is_ascii_alnum(ch):
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9")


class Parser:
    def __init__(self, pattern):
        self.s = pattern
        self.n = len(pattern)
        self.i = 0
        self.ngroups = 0

    def error(self, code, pos, message):
        raise PatternError(code, pos, message, self.s)

    def parse(self):
        node = self.parse_alternate()
        if self.i < self.n:
            # 剩下的只能是右括号
            self.error(E_UNBALANCED_PAREN, self.i, "多余的右括号 )")
        return node, self.ngroups

    def parse_alternate(self):
        branches = [self.parse_concat()]
        while self.i < self.n and self.s[self.i] == "|":
            self.i += 1
            branches.append(self.parse_concat())
        if len(branches) == 1:
            return branches[0]
        return Alternate(branches)

    def parse_concat(self):
        items = []
        while self.i < self.n and self.s[self.i] not in "|)":
            items.append(self.parse_repeat())
        if len(items) == 1:
            return items[0]
        return Concat(items)

    def parse_repeat(self):
        atom = self.parse_atom()
        if self.i >= self.n:
            return atom
        ch = self.s[self.i]
        pos = self.i
        if ch in "*+?":
            self.i += 1
            if isinstance(atom, Anchor):
                self.error(E_NOTHING_TO_REPEAT, pos, "锚点不能加量词")
            if ch == "*":
                lo, hi = 0, None
            elif ch == "+":
                lo, hi = 1, None
            else:
                lo, hi = 0, 1
            node = Repeat(atom, lo, hi, False, pos)
        elif ch == "{":
            spec = self.try_parse_brace()
            if spec is None:
                return atom  # 非法的 { 按字面量处理，由下一轮作为普通字符读入
            if isinstance(atom, Anchor):
                self.error(E_NOTHING_TO_REPEAT, pos, "锚点不能加量词")
            lo, hi = spec
            node = Repeat(atom, lo, hi, False, pos)
        else:
            return atom
        # 惰性标记
        if self.i < self.n and self.s[self.i] == "?":
            node.lazy = True
            self.i += 1
        # 连续量词，如 a**
        if self.i < self.n and (self.s[self.i] in "*+?" or self.s[self.i] == "{"):
            if self.s[self.i] == "{" and self.try_parse_brace(peek_only=True) is None:
                return node
            self.error(E_NOTHING_TO_REPEAT, self.i, "连续的量词（量词不能直接修饰量词）")
        return node

    def try_parse_brace(self, peek_only=False):
        """尝试把 {n} / {n,} / {n,m} 解析为量词；不是合法量词写法时返回 None。

        peek_only 为 True 时不移动游标（用于判断连续量词）。
        """
        s, n = self.s, self.n
        j = self.i + 1
        start = j
        while j < n and s[j].isdigit():
            j += 1
        if j == start:
            return None
        lo = int(s[start:j])
        hi = lo
        if j < n and s[j] == ",":
            j += 1
            start = j
            while j < n and s[j].isdigit():
                j += 1
            hi = int(s[start:j]) if j > start else None
        if j >= n or s[j] != "}":
            return None
        if hi is not None and lo > hi:
            self.error(E_REPEAT_RANGE_REVERSED, self.i,
                       "量词区间下限大于上限 {%d,%d}" % (lo, hi))
        if not peek_only:
            self.i = j + 1
        return lo, hi

    def parse_atom(self):
        ch = self.s[self.i]
        pos = self.i
        if ch == "(":
            self.i += 1
            self.ngroups += 1
            index = self.ngroups
            child = self.parse_alternate()
            if self.i >= self.n or self.s[self.i] != ")":
                self.error(E_UNCLOSED_GROUP, pos, "左括号 ( 未闭合")
            self.i += 1
            return Group(index, child)
        if ch == "[":
            return self.parse_class()
        if ch == ".":
            self.i += 1
            return Dot()
        if ch == "^":
            self.i += 1
            return Anchor("bol")
        if ch == "$":
            self.i += 1
            return Anchor("eol")
        if ch == "\\":
            return self.parse_escape(in_class=False)
        if ch in "*+?":
            self.error(E_NOTHING_TO_REPEAT, pos, "量词 %s 前面没有可作用的对象" % ch)
        # '{' 在不能构成量词时是普通字符，')'、'|' 由上层处理
        self.i += 1
        return Literal(ch)

    def parse_escape(self, in_class):
        pos = self.i
        self.i += 1  # 跳过反斜杠
        if self.i >= self.n:
            self.error(E_BAD_ESCAPE, pos, "反斜杠后没有内容，转义序列不完整")
        ch = self.s[self.i]
        self.i += 1
        if ch in CLASS_ESCAPES:
            if in_class:
                return ("set", ch)
            return ClassEscape(ch)
        if _is_ascii_alnum(ch):
            self.error(E_BAD_ESCAPE, pos,
                       "不支持的转义序列 \\%s（仅支持 \\d \\D \\w \\W \\s \\S 和标点转义）" % ch)
        # 标点符号转义后按字面量处理，如 \. \[ \\
        if in_class:
            return ("char", ch)
        return Literal(ch)

    def parse_class(self):
        pos = self.i
        self.i += 1  # 跳过 [
        negated = False
        if self.i < self.n and self.s[self.i] == "^":
            negated = True
            self.i += 1
        items = []
        first = True
        while True:
            if self.i >= self.n:
                self.error(E_UNCLOSED_CLASS, pos, "字符类 [ 未闭合（缺少 ]）")
            if self.s[self.i] == "]" and not first:
                self.i += 1
                break
            first = False
            lo_pos = self.i
            atom = self.parse_class_item()
            # 区间写法 a-z：前一个原子是单个字符，后面跟 '-' 且 '-' 后不是 ']'
            if (atom[0] == "char" and self.i < self.n and self.s[self.i] == "-"
                    and self.i + 1 < self.n and self.s[self.i + 1] != "]"):
                self.i += 1  # 跳过 -
                hi_atom = self.parse_class_item()
                if hi_atom[0] != "char":
                    self.error(E_CLASS_RANGE_REVERSED, lo_pos,
                               "字符类区间的终点不能是转义字符类")
                lo, hi = atom[1], hi_atom[1]
                if ord(lo) > ord(hi):
                    self.error(E_CLASS_RANGE_REVERSED, lo_pos,
                               "字符类区间写反：%s-%s（起点大于终点）" % (lo, hi))
                items.append(("rng", ord(lo), ord(hi)))
            elif atom[0] == "char":
                items.append(("rng", ord(atom[1]), ord(atom[1])))
            else:
                items.append(atom)
        return CharClass(negated, items)

    def parse_class_item(self):
        if self.s[self.i] == "\\":
            return self.parse_escape(in_class=True)
        ch = self.s[self.i]
        self.i += 1
        return ("char", ch)


def parse(pattern):
    """解析模式，返回 (AST, 捕获组数量)。"""
    if not isinstance(pattern, str):
        raise TypeError("模式必须是字符串")
    return Parser(pattern).parse()
