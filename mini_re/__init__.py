"""mini_re: 带步数预算的小型正则引擎（仅实现 samples/patterns.txt 列出的语法）。

公开接口与标准库 re 对齐的部分：
    compile(pattern, default_budget=...) -> Pattern
    Pattern.search / finditer / findall
    Match.group / groups / span / start / end
异常：
    ParseError      模式语法错误（带位置）
    BudgetExceeded  执行超过步数预算
"""

from .errors import ParseError, BudgetExceeded
from .pattern import compile, Pattern, Match

__all__ = ["compile", "Pattern", "Match", "ParseError", "BudgetExceeded"]
