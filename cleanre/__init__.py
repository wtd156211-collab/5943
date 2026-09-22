"""cleanre：内部批量文本清洗正则引擎。

- 只支持 samples/patterns.txt 清单里的语法
- 匹配全程统计步数，超预算立即中止（BudgetExceeded），引擎可继续复用
- 模式错误给出字符级定位（PatternError.pos）和错误码（PatternError.code）
"""

from .engine import Pattern, Match, compile, DEFAULT_MAX_STEPS
from .errors import RegexError, PatternError, BudgetExceeded

__all__ = [
    "Pattern",
    "Match",
    "compile",
    "DEFAULT_MAX_STEPS",
    "RegexError",
    "PatternError",
    "BudgetExceeded",
]
