"""samples/ 验收：挂死案例必须快速中止，语料上常见模式要在几秒内跑完。"""

import os
import time
import unittest

import cleanre
from cleanre import BudgetExceeded

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def load(name):
    with open(os.path.join(SAMPLES, name), encoding="utf-8") as f:
        return f.read()


class TestHangCase(unittest.TestCase):
    def test_hang_case_aborts_fast(self):
        pattern = load("hang-case.txt").strip()
        p = cleanre.compile(pattern)
        start = time.perf_counter()
        with self.assertRaises(BudgetExceeded):
            p.search("a" * 5000)
        self.assertLess(time.perf_counter() - start, 5)

    def test_engine_usable_after_hang_case(self):
        pattern = load("hang-case.txt").strip()
        p = cleanre.compile(pattern)
        with self.assertRaises(BudgetExceeded):
            p.search("a" * 5000)
        self.assertEqual(p.search("xaaabyy").span(), (1, 5))


class TestCorpusPerformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = load("corpus.txt")

    def assert_fast(self, pattern, expect_matches=True):
        start = time.perf_counter()
        found = cleanre.compile(pattern).findall(self.corpus)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 5, "模式 %r 跑了 %.1fs" % (pattern, elapsed))
        if expect_matches:
            self.assertTrue(found, "模式 %r 在语料上应能匹配到内容" % pattern)
        return found

    def test_datetime(self):
        self.assert_fast(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    def test_phone(self):
        self.assert_fast(r"1\d{10}")

    def test_email(self):
        self.assert_fast(r"\w+@\w+\.\w+")

    def test_order_id(self):
        self.assert_fast(r"OD\d+")

    def test_order_with_customer(self):
        found = self.assert_fast(r"订单 (OD\d+) 客户 (\S+)")
        self.assertTrue(all(len(t) == 2 for t in found))

    def test_json_id(self):
        self.assert_fast(r'"id":\d+')

    def test_anchored_lines(self):
        self.assert_fast(r"^\d+,.*,\d+\.\d{2}$")


if __name__ == "__main__":
    unittest.main()
