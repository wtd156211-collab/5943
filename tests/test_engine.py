import unittest

import cleanre


class TestBasicMatching(unittest.TestCase):
    def test_literal(self):
        m = cleanre.compile("abc").search("xxabcyy")
        self.assertEqual(m.span(), (2, 5))

    def test_dot_excludes_newline(self):
        self.assertIsNone(cleanre.compile("a.b").search("a\nb"))
        self.assertEqual(cleanre.compile("a.b").search("axb").span(), (0, 3))

    def test_char_class(self):
        self.assertEqual(cleanre.compile("[abc]+").search("zabca").span(), (1, 5))
        self.assertEqual(cleanre.compile("[^abc]+").search("abxyab").span(), (2, 4))
        self.assertEqual(cleanre.compile("[a-z]+").search("09abcZ").span(), (2, 5))

    def test_class_escapes(self):
        self.assertEqual(cleanre.compile(r"\d+").search("ab123").span(), (2, 5))
        self.assertEqual(cleanre.compile(r"\D+").search("12ab34").span(), (2, 4))
        self.assertEqual(cleanre.compile(r"\w+").search(" 周敏_1 ").span(), (1, 5))
        self.assertEqual(cleanre.compile(r"\s+").search("a \t\nb").span(), (1, 4))
        self.assertEqual(cleanre.compile(r"\S+").search(" a b").span(), (1, 2))

    def test_quantifiers(self):
        self.assertEqual(cleanre.compile("ab*c").search("abbbc").span(), (0, 5))
        self.assertIsNone(cleanre.compile("ab+c").search("ac"))
        self.assertEqual(cleanre.compile("ab?c").search("ac").span(), (0, 2))
        self.assertEqual(cleanre.compile("a{3}").search("aaaa").span(), (0, 3))
        self.assertEqual(cleanre.compile("a{2,}").search("aaaa").span(), (0, 4))
        self.assertEqual(cleanre.compile("a{2,3}").search("aaaa").span(), (0, 3))

    def test_lazy_quantifiers(self):
        self.assertEqual(cleanre.compile("a+?").search("aaa").span(), (0, 1))
        self.assertEqual(cleanre.compile("a*?b").search("aab").span(), (0, 3))
        self.assertEqual(cleanre.compile("a??").search("a").span(), (0, 0))
        self.assertEqual(cleanre.compile("a{2,4}?").search("aaaa").span(), (0, 2))

    def test_groups_and_captures(self):
        m = cleanre.compile(r"(\d+)-(\d+)").search("x12-345y")
        self.assertEqual(m.span(), (1, 7))
        self.assertEqual(m.group(0), "12-345")
        self.assertEqual(m.group(1), "12")
        self.assertEqual(m.group(2), "345")
        self.assertEqual(m.groups(), ("12", "345"))
        self.assertEqual(m.span(2), (4, 7))

    def test_group_numbering_by_left_paren(self):
        m = cleanre.compile("(a(b))(c)").search("abc")
        self.assertEqual(m.group(1), "ab")
        self.assertEqual(m.group(2), "b")
        self.assertEqual(m.group(3), "c")

    def test_unmatched_group_is_none(self):
        m = cleanre.compile("(a)|(b)").search("b")
        self.assertIsNone(m.group(1))
        self.assertEqual(m.group(2), "b")
        self.assertEqual(m.span(1), (-1, -1))

    def test_alternation(self):
        self.assertEqual(cleanre.compile("cat|dog").search("hotdog").span(), (3, 6))
        self.assertEqual(cleanre.compile("a|b|c").search("xc").span(), (1, 2))

    def test_anchors_multiline(self):
        text = "abc\ndef\nghi"
        self.assertEqual(cleanre.compile("^def").search(text).span(), (4, 7))
        self.assertEqual(cleanre.compile("def$").search(text).span(), (4, 7))
        self.assertEqual(cleanre.compile("^abc$").search(text).span(), (0, 3))
        self.assertIsNone(cleanre.compile("^def").search("xdef"))

    def test_dollar_before_final_newline(self):
        self.assertEqual(cleanre.compile("abc$").search("abc\n").span(), (0, 3))

    def test_match_only_at_pos(self):
        p = cleanre.compile("abc")
        self.assertIsNone(p.match("xabc"))
        self.assertIsNotNone(p.match("abc"))
        self.assertIsNotNone(p.match("xabc", 1))

    def test_findall(self):
        self.assertEqual(cleanre.compile(r"\d+").findall("a1b22c333"), ["1", "22", "333"])
        self.assertEqual(cleanre.compile(r"(\d)(\d)").findall("12 34"), [("1", "2"), ("3", "4")])

    def test_finditer_empty_matches(self):
        spans = [m.span() for m in cleanre.compile("x*").finditer("ab")]
        self.assertEqual(spans, [(0, 0), (1, 1), (2, 2)])

    def test_overlapping_not_returned(self):
        self.assertEqual(cleanre.compile("aa").findall("aaaa"), ["aa", "aa"])

    def test_empty_loop_guard(self):
        # (a*)* 之类不能死循环，结果要与标准库一致
        m = cleanre.compile("(a*)*").search("b")
        self.assertEqual(m.span(), (0, 0))
        self.assertEqual(m.group(1), "")
        m = cleanre.compile("(a*)+").search("aa")
        self.assertEqual(m.span(), (0, 2))

    def test_unicode_word_char(self):
        self.assertEqual(cleanre.compile(r"\w+").search("周敏").span(), (0, 2))


if __name__ == "__main__":
    unittest.main()
