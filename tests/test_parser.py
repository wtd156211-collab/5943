import unittest

import cleanre
from cleanre import PatternError


def error_of(pattern):
    try:
        cleanre.compile(pattern)
    except PatternError as e:
        return e
    raise AssertionError("模式 %r 应该报错" % pattern)


class TestPatternErrors(unittest.TestCase):
    def test_unclosed_group(self):
        e = error_of("(abc")
        self.assertEqual(e.code, 1001)
        self.assertEqual(e.pos, 0)

    def test_unclosed_group_nested(self):
        e = error_of("a(b(c)")
        self.assertEqual(e.code, 1001)
        self.assertEqual(e.pos, 1)

    def test_unclosed_class(self):
        e = error_of("ab[cd")
        self.assertEqual(e.code, 1002)
        self.assertEqual(e.pos, 2)

    def test_repeat_range_reversed(self):
        e = error_of("a{3,2}")
        self.assertEqual(e.code, 1003)
        self.assertEqual(e.pos, 1)

    def test_class_range_reversed(self):
        e = error_of("[z-a]")
        self.assertEqual(e.code, 1004)
        self.assertEqual(e.pos, 1)

    def test_nothing_to_repeat_at_start(self):
        e = error_of("*abc")
        self.assertEqual(e.code, 1005)
        self.assertEqual(e.pos, 0)

    def test_double_quantifier(self):
        e = error_of("a**")
        self.assertEqual(e.code, 1005)
        self.assertEqual(e.pos, 2)

    def test_quantifier_on_anchor(self):
        e = error_of("^*")
        self.assertEqual(e.code, 1005)
        self.assertEqual(e.pos, 1)

    def test_bad_escape(self):
        e = error_of(r"a\q")
        self.assertEqual(e.code, 1006)
        self.assertEqual(e.pos, 1)

    def test_trailing_backslash(self):
        e = error_of("ab\\")
        self.assertEqual(e.code, 1006)
        self.assertEqual(e.pos, 2)

    def test_unbalanced_paren(self):
        e = error_of("ab)")
        self.assertEqual(e.code, 1007)
        self.assertEqual(e.pos, 2)

    def test_repeat_too_large(self):
        e = error_of("a{100001}")
        self.assertEqual(e.code, 1008)

    def test_repeat_too_large_nested(self):
        e = error_of("(a{400}){400}")
        self.assertEqual(e.code, 1008)

    def test_error_message_contains_position_and_pattern(self):
        e = error_of("a{3,2}")
        self.assertIn("位置 1", str(e))
        self.assertIn("a{3,2}", str(e))


class TestValidPatterns(unittest.TestCase):
    """这些写法不应报错（与标准库行为对齐的边界）。"""

    def test_literal_brace(self):
        self.assertIsNotNone(cleanre.compile("a{").search("a{"))

    def test_literal_brace_no_digits(self):
        self.assertIsNotNone(cleanre.compile("a{x}").search("a{x}"))

    def test_empty_pattern(self):
        m = cleanre.compile("").search("abc")
        self.assertEqual(m.span(), (0, 0))

    def test_empty_group_and_branch(self):
        self.assertEqual(cleanre.compile("()").search("x").span(), (0, 0))
        self.assertEqual(cleanre.compile("a|").search("x").span(), (0, 0))

    def test_escaped_punctuation(self):
        self.assertEqual(cleanre.compile(r"\.\*\+").search("x.*+y").span(), (1, 4))

    def test_brace_after_quantifier_literal(self):
        # a*{ 中的 { 不是合法量词，按字面量
        self.assertIsNotNone(cleanre.compile("a*{").search("aaa{"))


if __name__ == "__main__":
    unittest.main()
