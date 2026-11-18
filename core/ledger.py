"""
Job Ledger & Power-Cut Recovery Manager.
Maintains persistent audit of every processed job to prevent duplicate prints
and ensure clean recovery if power cuts off midway.
"""

import json
import os
import time
from .config import get_app_dir

def get_ledger_path() -> str:
    return os.path.join(get_app_dir(), "ledger.json")

class JobLedger:
    def __init__(self):
        self.path = get_ledger_path()
        self.data = self._load()
        # On initialization, check if any job was left in IN_PROGRESS when app stopped
        self._reconcile_interrupted_jobs()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            initial = {
                "jobs": {},
                "metrics": {
                    "total_processed": 0,
                    "completed": 0,
                    "failed": 0,
                    "interrupted": 0,
                    "total_labels_printed": 0
                }
            }
            self._save(initial)
            return initial
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"jobs": {}, "metrics": {"total_processed": 0, "completed": 0, "failed": 0, "interrupted": 0, "total_labels_printed": 0}}

    def _save(self, data: dict = None):
        if data is None:
            data = self.data
        try:
            # Bound memory and disk usage: retain latest 2,000 jobs in local ledger
            if len(data.get("jobs", {})) > 2500:
                sorted_keys = sorted(
                    data["jobs"].keys(),
                    key=lambda k: data["jobs"][k].get("start_time") or data["jobs"][k].get("end_time") or "",
                    reverse=True
                )
                keep_keys = set(sorted_keys[:2000])
                data["jobs"] = {k: data["jobs"][k] for k in keep_keys}

            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Ledger] Failed to save ledger: {e}")

    def _reconcile_interrupted_jobs(self):
        """Finds any job left IN_PROGRESS (e.g. power cut) and marks it INTERRUPTED so it's not reprinted."""
        changed = False
        for job_id, info in self.data.get("jobs", {}).items():
            if info.get("status") == "IN_PROGRESS":
                info["status"] = "INTERRUPTED"
                info["interrupted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                info["notes"] = "Power outage or shutdown detected during printing. Skipped to prevent re-print."
                self.data["metrics"]["interrupted"] = self.data["metrics"].get("interrupted", 0) + 1
                changed = True
                print(f"[Ledger] Power-cut recovery: Marked job {job_id} as INTERRUPTED")
        if changed:
            self._save()

    def is_processed(self, job_id: str) -> bool:
        """Returns True if the job was already completed or marked interrupted/failed."""
        info = self.data.get("jobs", {}).get(job_id)
        if not info:
            return False
        # If it was completed, failed, or interrupted, do NOT print again
        return info.get("status") in ("COMPLETED", "FAILED", "INTERRUPTED")

    def get_job_status(self, job_id: str) -> str:
        info = self.data.get("jobs", {}).get(job_id)
        if info:
            return info.get("status", "UNKNOWN")
        return "NEW"

    def start_job(
        self,
        job_id: str,
        product_name: str,
        barcode: str,
        quantity: int,
        created_by_name: str = "",
        print_mrp: float = 0.0,
        print_sale_rate: float = 0.0,
    ):
        """Records job beginning execution."""
        self.data["jobs"][job_id] = {
            "id": job_id,
            "job_id": job_id,
            "product_name": product_name,
            "print_name": product_name,
            "barcode": barcode,
            "quantity": quantity,
            "created_by_name": created_by_name or "ERP User",
            "print_mrp": float(print_mrp or 0.0),
            "print_sale_rate": float(print_sale_rate or 0.0),
            "status": "IN_PROGRESS",
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "printed_copies": 0
        }
        self.data["metrics"]["total_processed"] = self.data["metrics"].get("total_processed", 0) + 1
        self._save()

    def complete_job(self, job_id: str, printed_copies: int):
        """Marks job as successfully finished and updates label counters."""
        if job_id in self.data["jobs"]:
            job = self.data["jobs"][job_id]
            job["status"] = "COMPLETED"
            job["end_time"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            job["printed_copies"] = printed_copies
        else:
            self.data["jobs"][job_id] = {
                "job_id": job_id,
                "status": "COMPLETED",
                "end_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "printed_copies": printed_copies
            }
        self.data["metrics"]["completed"] = self.data["metrics"].get("completed", 0) + 1
        self.data["metrics"]["total_labels_printed"] = self.data["metrics"].get("total_labels_printed", 0) + printed_copies
        self._save()

    def fail_job(self, job_id: str, error_msg: str):
        """Marks job as failed with reason."""
        if job_id in self.data["jobs"]:
            job = self.data["jobs"][job_id]
            job["status"] = "FAILED"
            job["error_message"] = error_msg
            job["end_time"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        else:
            self.data["jobs"][job_id] = {
                "job_id": job_id,
                "status": "FAILED",
                "error_message": error_msg,
                "end_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        self.data["metrics"]["failed"] = self.data["metrics"].get("failed", 0) + 1
        self._save()

    def get_metrics(self) -> dict:
        return self.data.get("metrics", {
            "total_processed": 0,
            "completed": 0,
            "failed": 0,
            "interrupted": 0,
            "total_labels_printed": 0
        })

    def get_recent_jobs(self, limit: int = 50) -> list:
        """Returns list of recent jobs sorted by recency."""
        jobs_dict = self.data.get("jobs", {})
        sorted_jobs = sorted(
            jobs_dict.values(),
            key=lambda x: x.get("start_time") or x.get("end_time") or "",
            reverse=True
        )
        return sorted_jobs[:limit]
