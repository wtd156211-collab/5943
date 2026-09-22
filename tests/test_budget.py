import unittest

import cleanre
from cleanre import BudgetExceeded


class TestBudget(unittest.TestCase):
    def test_hang_pattern_aborts(self):
        # 上次事故的规则：嵌套量词碰上长重复文本，灾难性回溯
        p = cleanre.compile("(a+)+b")
        with self.assertRaises(BudgetExceeded):
            p.search("a" * 5000)

    def test_abort_message_is_actionable(self):
        p = cleanre.compile("(a+)+b")
        try:
            p.search("a" * 5000)
            self.fail("应该超预算")
        except BudgetExceeded as e:
            msg = str(e)
            self.assertIn("(a+)+b", msg)       # 哪条规则
            self.assertIn("位置", msg)          # 文本里的位置
            self.assertIn("步数预算", msg)      # 超了什么预算
            self.assertEqual(e.code, 2001)

    def test_engine_reusable_after_abort(self):
        # 中止后不留脏状态：同一个 Pattern、同一个进程继续跑
        hang = cleanre.compile("(a+)+b", max_steps=20_000)
        normal = cleanre.compile(r"(\d+)")
        for _ in range(500):
            with self.assertRaises(BudgetExceeded):
                hang.search("a" * 200)
            m = normal.search("id=42")
            self.assertEqual(m.group(1), "42")
            # 挂死规则在正常文本上依然能出正确结果
            self.assertEqual(hang.search("xaaab").span(), (1, 5))

    def test_budget_is_configurable(self):
        p = cleanre.compile("(a+)+b", max_steps=1000)
        try:
            p.search("a" * 5000)
            self.fail("应该超预算")
        except BudgetExceeded as e:
            self.assertEqual(e.budget, 1000)

    def test_small_budget_still_allows_normal_work(self):
        p = cleanre.compile(r"\d+", max_steps=1000)
        self.assertEqual(p.findall("a1b22c333"), ["1", "22", "333"])

    def test_match_call_also_bounded(self):
        p = cleanre.compile("(a+)+b")
        with self.assertRaises(BudgetExceeded):
            p.match("a" * 5000)


if __name__ == "__main__":
    unittest.main()
