import unittest

from httpcache_lint.parser import parse_cache_control
from httpcache_lint.rules import check_directives


def _diagnostics(value):
    result = parse_cache_control(value)
    return check_directives(result)


class UnknownAndRepeatedTest(unittest.TestCase):
    def test_unknown_directive_is_a_warning(self):
        diagnostics = _diagnostics("foo-bar")
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertIn("unknown directive 'foo-bar'", diagnostics[0].message)

    def test_repeated_directive_is_flagged_once(self):
        diagnostics = _diagnostics("no-store, no-store")
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertIn("'no-store' repeated", diagnostics[0].message)


class ValueRequirementsTest(unittest.TestCase):
    def test_missing_required_value_is_an_error(self):
        diagnostics = _diagnostics("max-age")
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertIn("requires a value", diagnostics[0].message)

    def test_non_integer_value_is_an_error(self):
        diagnostics = _diagnostics("max-age=abc")
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertIn("expects a non-negative integer, got 'abc'", diagnostics[0].message)

    def test_value_on_a_directive_that_takes_none_is_an_error(self):
        diagnostics = _diagnostics("no-store=1")
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertIn("'no-store' does not take a value", diagnostics[0].message)

    def test_optional_value_directive_is_fine_bare_or_with_an_integer(self):
        self.assertEqual(_diagnostics("max-stale"), [])
        self.assertEqual(_diagnostics("max-stale=10"), [])

        diagnostics = _diagnostics("max-stale=abc")
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")

    def test_empty_value_is_left_to_the_parser_to_report(self):
        # parse_cache_control already emits a diagnostic for "max-age=";
        # check_directives should not pile on a second one for the same spot.
        result = parse_cache_control("max-age=")
        self.assertEqual(check_directives(result), [])


class ValidInputTest(unittest.TestCase):
    def test_well_formed_directives_produce_no_diagnostics(self):
        self.assertEqual(_diagnostics("max-age=60, no-cache, immutable"), [])


if __name__ == "__main__":
    unittest.main()
