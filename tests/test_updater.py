import unittest
from core.updater import parse_version, is_newer_version


class TestUpdaterVersionComparison(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("1.10.0"), (1, 10, 0))
        self.assertEqual(parse_version("v2.0"), (2, 0, 0))
        self.assertEqual(parse_version(""), (0, 0, 0))

    def test_is_newer_version(self):
        self.assertTrue(is_newer_version("v1.2.0", "1.1.0"))
        self.assertTrue(is_newer_version("v2.0.0", "1.9.9"))
        self.assertFalse(is_newer_version("v1.1.0", "1.1.0"))
        self.assertFalse(is_newer_version("v1.0.9", "1.1.0"))


if __name__ == "__main__":
    unittest.main()
