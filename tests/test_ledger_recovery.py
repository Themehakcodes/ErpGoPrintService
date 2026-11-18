"""
Tests for Power-Cut Recovery and Duplicate Prevention in JobLedger.
"""

import os
import tempfile
import json
import unittest

from core.ledger import JobLedger

class TestLedgerPowerCutRecovery(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ledger_file = os.path.join(self.temp_dir.name, "ledger.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normal_completion(self):
        # Point ledger to temp path
        ledger = JobLedger()
        ledger.path = self.ledger_file
        ledger.data = ledger._load()

        job_id = "test-job-001"
        self.assertFalse(ledger.is_processed(job_id))

        ledger.start_job(job_id, "Test Milk 500ml", "890123456", 2)
        self.assertFalse(ledger.is_processed(job_id))
        self.assertEqual(ledger.get_job_status(job_id), "IN_PROGRESS")

        ledger.complete_job(job_id, 2)
        self.assertTrue(ledger.is_processed(job_id))
        self.assertEqual(ledger.get_job_status(job_id), "COMPLETED")
        self.assertEqual(ledger.get_metrics()["completed"], 1)
        self.assertEqual(ledger.get_metrics()["total_labels_printed"], 2)

    def test_power_cut_recovery_reconciliation(self):
        # 1. Simulate a job being printed when power cuts out
        crash_data = {
            "jobs": {
                "cut-job-001": {
                    "job_id": "cut-job-001",
                    "product_name": "Sugar 5KG",
                    "barcode": "999888777",
                    "quantity": 10,
                    "status": "IN_PROGRESS",
                    "start_time": "2026-11-17T12:00:00Z",
                    "printed_copies": 0
                }
            },
            "metrics": {
                "total_processed": 1,
                "completed": 0,
                "failed": 0,
                "interrupted": 0,
                "total_labels_printed": 0
            }
        }
        with open(self.ledger_file, "w", encoding="utf-8") as f:
            json.dump(crash_data, f)

        # 2. Simulate app restarting after power restored
        ledger = JobLedger()
        ledger.path = self.ledger_file
        ledger.data = ledger._load()
        ledger._reconcile_interrupted_jobs()

        # 3. Verify it was marked INTERRUPTED
        self.assertEqual(ledger.get_job_status("cut-job-001"), "INTERRUPTED")
        # 4. Crucial: is_processed must return True so it does NOT reprint
        self.assertTrue(ledger.is_processed("cut-job-001"))
        self.assertEqual(ledger.get_metrics()["interrupted"], 1)

    def test_failed_job_not_reprinted(self):
        ledger = JobLedger()
        ledger.path = self.ledger_file
        ledger.data = ledger._load()

        job_id = "fail-job-002"
        ledger.start_job(job_id, "Bad Item", "000000", 1)
        ledger.fail_job(job_id, "Out of paper")

        self.assertTrue(ledger.is_processed(job_id))
        self.assertEqual(ledger.get_job_status(job_id), "FAILED")

if __name__ == "__main__":
    unittest.main()
