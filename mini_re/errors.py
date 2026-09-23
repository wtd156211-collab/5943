"""mini_re 的异常类型与错误码。"""


class ParseError(Exception):
    """模式语法错误。

    属性：
        pos:     0 起始的字符偏移（出错字符在模式串里的下标）
        column:  1 起始的列号，pos + 1，直接面向写规则的人
        code:    稳定的错误码（见 README 与下面的 CODES）
        pattern: 出错的模式原文
    """

    CODES = {
        "E_UNCLOSED_GROUP": "分组缺少右括号 ')'",
        "E_UNEXPECTED_RPAREN": "出现了没有对应左括号的 ')'",
        "E_UNCLOSED_CLASS": "字符类缺少右括号 ']'",
        "E_BAD_RANGE": "字符类里的区间写反了（起点大于终点）",
        "E_RANGE_CLASS": "字符类区间的一端不能是 \\d/\\w/\\s 这类转义字符类",
        "E_REPEAT_NOTHING": "量词前面没有可重复的内容",
        "E_REPEAT_MULTIPLE": "一个元素后面不能连续写多个量词",
        "E_REPEAT_BAD_NUMBER": "量词的数字非法（空数字或不是十进制数字）",
        "E_REPEAT_RANGE": "量词区间写反了：最小值大于最大值",
        "E_BAD_ESCAPE": "不认识的反斜杠转义",
        "E_EMPTY_PATTERN": "模式为空",
    }

    def __init__(self, code, pos, pattern, detail=None):
        self.code = code
        self.pos = pos
        self.column = pos + 1
        self.pattern = pattern
        what = self.CODES.get(code, code)
        if detail:
            what = f"{what}（{detail}）"
        msg = f"{code}: {what}，位于第 {self.column} 个字符"
        super().__init__(msg)


class BudgetExceeded(Exception):
    """一次匹配执行消耗的步数超过预算。

    属性：
        budget:  本次执行的步数上限
        pattern: 触发超预算的模式原文
        text_len: 被匹配文本的长度
    """

    def __init__(self, budget, pattern, text_len):
        self.budget = budget
        self.pattern = pattern
        self.text_len = text_len
        super().__init__(
            f"规则 {pattern!r} 在长度 {text_len} 的文本上超过步数预算 "
            f"{budget}，匹配已中止（引擎状态干净，可继续跑下一条）"
        )
