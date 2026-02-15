import unittest

from smartclipboard_core.search_query import parse_search_query


class SearchQueryParseTests(unittest.TestCase):
    def test_empty(self):
        p = parse_search_query("")
        self.assertEqual(p.query, "")
        self.assertIsNone(p.tag)

    def test_parses_tag_and_type_and_limit(self):
        p = parse_search_query('type:file tag:work limit:20 oauth token')
        self.assertEqual(p.type, "file")
        self.assertEqual(p.tag, "work")
        self.assertEqual(p.limit, 20)
        self.assertEqual(p.query, "oauth token")

    def test_parses_quoted_values(self):
        p = parse_search_query('tag:"alpha beta" col:"My Stuff" type:link hello')
        self.assertEqual(p.tag, "alpha beta")
        self.assertEqual(p.col, "My Stuff")
        self.assertEqual(p.type, "link")
        self.assertEqual(p.query, "hello")

    def test_parses_is_tokens(self):
        p = parse_search_query("is:bookmark foo")
        self.assertTrue(p.is_bookmark)
        self.assertIsNone(p.is_pinned)
        self.assertEqual(p.query, "foo")

        p2 = parse_search_query("is:pinned")
        self.assertTrue(p2.is_pinned)
        self.assertEqual(p2.query, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)

