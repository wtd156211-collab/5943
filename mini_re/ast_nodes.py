"""解析器产出的 AST 节点。pos 为模式串里 0 起始的偏移。"""


class Node:
    pass


class Empty(Node):
    __slots__ = ("pos",)

    def __init__(self, pos):
        self.pos = pos


class Literal(Node):
    __slots__ = ("char", "pos")

    def __init__(self, char, pos):
        self.char = char
        self.pos = pos


class ClassPred(Node):
    """点号 / 字符类 / 转义字符类统一用谓词节点表示。

    pred: 编译期构造好的可调用对象，pred(ch) -> bool
    """

    __slots__ = ("pred", "pos")

    def __init__(self, pred, pos):
        self.pred = pred
        self.pos = pos


class Concat(Node):
    __slots__ = ("items", "pos")

    def __init__(self, items, pos):
        self.items = items
        self.pos = pos


class Alt(Node):
    __slots__ = ("branches", "pos")

    def __init__(self, branches, pos):
        self.pos = pos
        self.branches = branches


class Group(Node):
    __slots__ = ("index", "node", "pos")

    def __init__(self, index, node, pos):
        self.index = index  # 捕获组编号，从 1 开始
        self.node = node
        self.pos = pos


class Repeat(Node):
    __slots__ = ("node", "min", "max", "lazy", "owner", "pos")

    def __init__(self, node, min_, max_, lazy, pos):
        self.node = node
        self.min = min_
        self.max = max_          # None 表示无上界
        self.lazy = lazy
        self.owner = id(self)    # VM 里重复帧的归属标识
        self.pos = pos


class Anchor(Node):
    __slots__ = ("kind", "pos")

    def __init__(self, kind, pos):
        self.kind = kind        # '^' 或 '$'
        self.pos = pos
