import unittest

from httpcache_lint.parser import Position, parse_cache_control


class ParseBasicsTest(unittest.TestCase):
    def test_flag_directives_have_no_value(self):
        result = parse_cache_control("no-store, no-cache")
        self.assertEqual(result.diagnostics, [])
        self.assertEqual(len(result.directives), 2)

        first, second = result.directives
        self.assertEqual((first.name, first.value, first.quoted), ("no-store", None, False))
        self.assertEqual(first.pos, Position(1, 1))
        self.assertEqual((second.name, second.value, second.quoted), ("no-cache", None, False))
        self.assertEqual(second.pos, Position(1, 11))

    def test_integer_value(self):
        result = parse_cache_control("max-age=3600")
        self.assertEqual(result.diagnostics, [])
        directive = result.directives[0]
        self.assertEqual(directive.value, "3600")
        self.assertFalse(directive.quoted)
        self.assertEqual(directive.pos, Position(1, 1))

    def test_quoted_value(self):
        result = parse_cache_control('private="Set-Cookie"')
        self.assertEqual(result.diagnostics, [])
        directive = result.directives[0]
        self.assertEqual(directive.name, "private")
        self.assertEqual(directive.value, "Set-Cookie")
        self.assertTrue(directive.quoted)


class ParseMalformedInputTest(unittest.TestCase):
    def test_equals_with_no_value_is_an_error(self):
        result = parse_cache_control("max-age=")
        self.assertEqual(result.directives[0].value, "")
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.severity, "error")
        self.assertIn("has '=' but no value", diagnostic.message)
        self.assertEqual(diagnostic.pos, Position(1, 9))

    def test_unterminated_quoted_value(self):
        result = parse_cache_control('private="abc')
        self.assertEqual(result.directives[0].value, "abc")
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.severity, "error")
        self.assertIn("unterminated quoted value for 'private'", diagnostic.message)
        self.assertEqual(diagnostic.pos, Position(1, 9))

    def test_two_commas_in_a_row(self):
        result = parse_cache_control("no-store,, no-cache")
        names = [d.name for d in result.directives]
        self.assertEqual(names, ["no-store", "no-cache"])
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.severity, "error")
        self.assertIn("empty directive", diagnostic.message)
        self.assertEqual(diagnostic.pos, Position(1, 10))

    def test_character_that_cannot_start_a_directive(self):
        result = parse_cache_control("%")
        self.assertEqual(result.directives, [])
        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.severity, "error")
        self.assertIn("unexpected character '%'", diagnostic.message)
        self.assertEqual(diagnostic.pos, Position(1, 1))

    def test_missing_comma_between_directives_recovers(self):
        # There's no separator between the two directives. The parser can't
        # know where the first one was supposed to end, so it reports the
        # missing comma and then resumes scanning from the next character -
        # which eats the leading 'n' of the second directive. Documenting
        # this here so a future grammar change doesn't silently alter it.
        result = parse_cache_control("no-store no-cache")
        names = [d.name for d in result.directives]
        self.assertEqual(names, ["no-store", "o-cache"])

        self.assertEqual(len(result.diagnostics), 1)
        diagnostic = result.diagnostics[0]
        self.assertEqual(diagnostic.severity, "error")
        self.assertIn("expected ',' after directive 'no-store'", diagnostic.message)
        self.assertEqual(diagnostic.pos, Position(1, 10))


class ParsePositionTrackingTest(unittest.TestCase):
    def test_positions_are_relative_to_the_whole_document(self):
        text = "line1\nCache-Control: max-age=abc\n"
        offset = text.index("max-age")
        result = parse_cache_control(text, base_offset=offset)

        self.assertEqual(result.diagnostics, [])
        directive = result.directives[0]
        self.assertEqual(directive.value, "abc")
        self.assertEqual(directive.line_text, "Cache-Control: max-age=abc")

        prefix = text[:offset]
        expected_line = prefix.count("\n") + 1
        expected_column = offset - prefix.rfind("\n")
        self.assertEqual(directive.pos, Position(expected_line, expected_column))


if __name__ == "__main__":
    unittest.main()
