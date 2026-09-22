"""错误类型与错误码。

错误码一览（README 中有完整说明）：

解析阶段（PatternError）：
    1001 左括号未闭合
    1002 字符类未闭合（缺 ]）
    1003 量词区间下限大于上限（如 {3,2}）
    1004 字符类区间写反（如 [z-a]）
    1005 量词没有可作用的对象（含连续量词、对锚点加量词）
    1006 不支持的转义序列
    1007 多余的右括号
    1008 重复次数过大（量词展开后指令数超限）

匹配阶段（BudgetExceeded）：
    2001 匹配步数超出预算，已中止
"""

E_UNCLOSED_GROUP = 1001
E_UNCLOSED_CLASS = 1002
E_REPEAT_RANGE_REVERSED = 1003
E_CLASS_RANGE_REVERSED = 1004
E_NOTHING_TO_REPEAT = 1005
E_BAD_ESCAPE = 1006
E_UNBALANCED_PAREN = 1007
E_REPEAT_TOO_LARGE = 1008
E_BUDGET_EXCEEDED = 2001


class RegexError(Exception):
    """本引擎所有错误的基类。"""

    code = None


class PatternError(RegexError):
    """模式解析/编译错误。pos 为出错字符在模式中的下标（从 0 开始）。"""

    def __init__(self, code, pos, message, pattern):
        self.code = code
        self.pos = pos
        self.pattern = pattern
        super().__init__("[错误码 %d] 位置 %d：%s（模式：%r）" % (code, pos, message, pattern))


class BudgetExceeded(RegexError):
    """匹配步数超出预算，引擎已中止本次匹配。

    抛出后引擎不残留任何状态，同一 Pattern 对象可继续安全使用。
    """

    code = E_BUDGET_EXCEEDED

    def __init__(self, pattern, budget, start_pos, text):
        self.pattern = pattern
        self.budget = budget
        self.start_pos = start_pos
        self.text_length = len(text)
        excerpt = text[start_pos:start_pos + 40]
        if start_pos + 40 < len(text):
            excerpt += "..."
        super().__init__(
            "[错误码 %d] 规则 %r 在文本（长度 %d）位置 %d 处起匹配时超过步数预算 %d，已中止。"
            "附近文本：%r" % (self.code, pattern, self.text_length, start_pos, budget, excerpt)
        )
