"""带种子的随机对拍：随机生成模式和文本，与标准库 re 对比。

对比内容：search 的匹配区间与捕获组、finditer 的全部匹配区间与捕获组。
标准库侧统一使用 re.MULTILINE（本引擎的 ^ $ 是行首行尾语义）。
"""

import random
import re
import unittest

import cleanre
from cleanre import BudgetExceeded

SEED = 20260922
ROUNDS = 4000
MAX_STEPS = 10_000_000

LITERALS = "abcabd12_ ."
TEXT_ALPHABET = "aabbc d12_\n"


def gen_class(rng):
    parts = []
    for _ in range(rng.randint(1, 3)):
        kind = rng.random()
        if kind < 0.35:
            parts.append(rng.choice("abc1_"))
        elif kind < 0.6:
            lo = rng.choice("abcd12")
            hi = rng.choice("abcd12")
            if lo > hi:
                lo, hi = hi, lo
            parts.append(lo + "-" + hi)
        else:
            parts.append("\\" + rng.choice("dws"))
    neg = "^" if rng.random() < 0.3 else ""
    return "[" + neg + "".join(parts) + "]"


def gen_atom(rng, depth):
    r = rng.random()
    if r < 0.30:
        return rng.choice(LITERALS)
    if r < 0.38:
        return "."
    if r < 0.50:
        return gen_class(rng)
    if r < 0.62:
        return "\\" + rng.choice("dDwWsS")
    if r < 0.68:
        return "\\" + rng.choice(".*+?()[]{}|\\")
    if r < 0.74:
        return rng.choice(["^", "$"])
    if depth > 0:
        return "(" + gen_alternate(rng, depth - 1) + ")"
    return rng.choice(LITERALS)


def gen_quantified(rng, depth):
    atom = gen_atom(rng, depth)
    if atom in ("^", "$"):
        return atom
    r = rng.random()
    if r < 0.45:
        return atom
    q = rng.random()
    if q < 0.25:
        rep = rng.choice("*+?")
    elif q < 0.45:
        rep = "{%d}" % rng.randint(0, 3)
    elif q < 0.65:
        rep = "{%d,}" % rng.randint(0, 3)
    else:
        lo = rng.randint(0, 3)
        hi = lo + rng.randint(0, 3)
        rep = "{%d,%d}" % (lo, hi)
    if rng.random() < 0.3:
        rep += "?"
    return atom + rep


def gen_concat(rng, depth):
    return "".join(gen_quantified(rng, depth) for _ in range(rng.randint(1, 4)))


def gen_alternate(rng, depth):
    branches = [gen_concat(rng, depth)]
    if rng.random() < 0.35:
        branches.append(gen_concat(rng, depth))
        if rng.random() < 0.3:
            branches.append(gen_concat(rng, depth))
    return "|".join(branches)


def gen_pattern(rng):
    return gen_alternate(rng, depth=2)


def gen_text(rng):
    return "".join(rng.choice(TEXT_ALPHABET) for _ in range(rng.randint(0, 24)))


def match_tuple(m):
    if m is None:
        return None
    return (m.span(), m.groups())


class TestDifferential(unittest.TestCase):
    def test_random_against_stdlib(self):
        rng = random.Random(SEED)
        failures = []
        skipped = 0
        for i in range(ROUNDS):
            pattern = gen_pattern(rng)
            text = gen_text(rng)
            try:
                mine = cleanre.compile(pattern, max_steps=MAX_STEPS)
                ref = re.compile(pattern, re.MULTILINE)
            except Exception as exc:  # 生成器只产生合法模式，两边都应编译成功
                self.fail("编译失败 pattern=%r: %r" % (pattern, exc))
            try:
                got_search = match_tuple(mine.search(text))
                got_iter = [match_tuple(m) for m in mine.finditer(text)]
            except BudgetExceeded:
                # 随机生成的灾难性回溯模式会触发预算中止，这是设计行为，跳过
                skipped += 1
                continue
            want_search = match_tuple(ref.search(text))
            want_iter = [match_tuple(m) for m in ref.finditer(text)]
            if got_search != want_search or got_iter != want_iter:
                failures.append((pattern, text, got_search, want_search,
                                 got_iter, want_iter))
                if len(failures) >= 5:
                    break
        for pattern, text, gs, ws, gi, wi in failures:
            print("pattern=%r text=%r" % (pattern, text))
            print("  search  mine=%r re=%r" % (gs, ws))
            print("  finditer mine=%r" % (gi,))
            print("  finditer re  =%r" % (wi,))
        self.assertEqual(failures, [])
        # 极少数随机模式会触发预算中止，比例不应高
        self.assertLess(skipped, ROUNDS // 100 + 1)


if __name__ == "__main__":
    unittest.main()
