import unittest

from httpcache_lint.headers import check_age, check_vary
from httpcache_lint.parser import Position


class AgeHeaderTest(unittest.TestCase):
    def test_valid_delta_seconds(self):
        self.assertEqual(check_age("3600", 0), [])

    def test_zero_is_valid(self):
        self.assertEqual(check_age("0", 0), [])

    def test_empty_value_is_an_error(self):
        diagnostics = check_age("", 0)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertIn("empty value", diagnostics[0].message)

    def test_negative_number_is_an_error(self):
        diagnostics = check_age("-1", 0)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertIn("not a non-negative integer", diagnostics[0].message)

    def test_non_numeric_value_is_an_error(self):
        diagnostics = check_age("soon", 0)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertIn("'soon'", diagnostics[0].message)

    def test_position_is_relative_to_whole_document(self):
        text = "Age: 12x\n"
        offset = text.index("12x")
        diagnostics = check_age(text, offset)
        self.assertEqual(diagnostics[0].pos, Position(1, 6))


class VaryHeaderTest(unittest.TestCase):
    def test_single_field_name(self):
        self.assertEqual(check_vary("Accept-Encoding", 0), [])

    def test_list_of_field_names(self):
        self.assertEqual(check_vary("Accept-Encoding, User-Agent", 0), [])

    def test_bare_star_is_valid(self):
        self.assertEqual(check_vary("*", 0), [])

    def test_empty_value_is_a_warning(self):
        diagnostics = check_vary("", 0)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertIn("empty value", diagnostics[0].message)

    def test_two_commas_in_a_row_is_an_error(self):
        diagnostics = check_vary("Accept,, User-Agent", 0)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertIn("empty member", diagnostics[0].message)

    def test_invalid_field_name_characters(self):
        diagnostics = check_vary("Accept/Encoding", 0)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertIn("not a valid field-name", diagnostics[0].message)

    def test_repeated_field_name_is_a_warning(self):
        diagnostics = check_vary("Accept, accept", 0)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertIn("repeated", diagnostics[0].message)

    def test_star_combined_with_other_members_is_an_error(self):
        diagnostics = check_vary("*, Accept", 0)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertIn("must appear alone", diagnostics[0].message)


if __name__ == "__main__":
    unittest.main()
