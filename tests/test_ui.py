"""
Test MainWindow initialization and headless lifecycle.
"""

import sys
import unittest
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow

class TestMainWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create QApplication if not already exists
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_window_init(self):
        win = MainWindow()
        self.assertIsNotNone(win)
        self.assertIn("KCSM Print Service — Desktop Agent", win.windowTitle())
        self.assertIsNotNone(win.printer_combo)
        self.assertIsNotNone(win.table)
        self.assertEqual(win.table.columnCount(), 9)
        self.assertEqual(win.table.horizontalHeaderItem(7).text(), "Printed By")
        self.assertIsNotNone(win.printer_progress_bar)
        self.assertIsNotNone(win.status_pill)
        # Check printer enumeration
        self.assertGreater(win.printer_combo.count(), 0)
        win.close()

if __name__ == "__main__":
    unittest.main()
