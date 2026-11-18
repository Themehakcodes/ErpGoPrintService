import os
import unittest
from core.updater import parse_version, is_newer_version, _clean_spawn_env


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

    def test_clean_spawn_env_strips_pyinstaller_vars(self):
        os.environ["_MEIPASS2"] = "C:\\Temp\\_MEI9999"
        os.environ["QT_PLUGIN_PATH"] = "C:\\Temp\\_MEI9999\\PyQt6"
        try:
            cleaned = _clean_spawn_env()
            self.assertNotIn("_MEIPASS2", cleaned)
            self.assertNotIn("QT_PLUGIN_PATH", cleaned)
        finally:
            os.environ.pop("_MEIPASS2", None)
            os.environ.pop("QT_PLUGIN_PATH", None)


if __name__ == "__main__":
    unittest.main()
