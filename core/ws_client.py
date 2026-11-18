"""
WebSocket Client Worker for KCSM Print Service.
Runs as a PyQt6 QThread with auto-reconnection, heartbeat, and job dispatching.
"""

import asyncio
import json
import time
import urllib.parse
from PyQt6.QtCore import QThread, pyqtSignal
import websockets

class WebSocketWorker(QThread):
    connected_signal = pyqtSignal(dict)
    disconnected_signal = pyqtSignal(str)
    job_received_signal = pyqtSignal(dict)
    log_signal = pyqtSignal(str, str)  # (level, message)

    def __init__(self, server_url: str, device_code: str, secret_key: str = ""):
        super().__init__()
        self.server_url = server_url
        self.device_code = device_code
        self.secret_key = secret_key
        self.running = True
        self.loop = None
        self.ws = None
        self.send_queue = None

    def update_credentials(self, server_url: str, device_code: str, secret_key: str = ""):
        self.server_url = server_url
        self.device_code = device_code
        self.secret_key = secret_key

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.send_queue = asyncio.Queue()
        self.loop.run_until_complete(self._main_loop())

    async def _main_loop(self):
        reconnect_delay = 3
        while self.running:
            clean_url = self.server_url.strip()
            if clean_url.startswith("http://"):
                clean_url = "ws://" + clean_url[7:]
            elif clean_url.startswith("https://"):
                clean_url = "wss://" + clean_url[8:]
            elif not clean_url.startswith("ws://") and not clean_url.startswith("wss://"):
                clean_url = "ws://" + clean_url

            # Normalize device code (e.g. "DEV 0002" or "dev_0002" -> "DEV-0002")
            clean_code = self.device_code.strip().replace(" ", "-").replace("_", "-").upper()
            sep = "&" if "?" in clean_url else "?"
            target_url = f"{clean_url}{sep}device_code={urllib.parse.quote(clean_code)}"
            if self.secret_key:
                target_url += f"&secret_key={urllib.parse.quote(self.secret_key)}"

            self.log_signal.emit("INFO", f"Connecting to WebSocket: {clean_url} (Device: {clean_code})...")

            try:
                async with websockets.connect(target_url, ping_interval=20, ping_timeout=15) as ws:
                    self.ws = ws
                    self.log_signal.emit("SUCCESS", f"Connected to KCSM Print Server as {clean_code}!")
                    reconnect_delay = 3  # reset backoff

                    # Start sender and receiver concurrently
                    send_task = asyncio.create_task(self._sender_loop(ws))
                    recv_task = asyncio.create_task(self._receiver_loop(ws))
                    ping_task = asyncio.create_task(self._heartbeat_loop(ws))

                    done, pending = await asyncio.wait(
                        [send_task, recv_task, ping_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in pending:
                        task.cancel()

            except Exception as e:
                self.log_signal.emit("WARN", f"Connection error: {e}")
                self.disconnected_signal.emit(str(e))
            finally:
                self.ws = None

            if not self.running:
                break

            self.log_signal.emit("INFO", f"Reconnecting in {reconnect_delay}s...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(30, reconnect_delay * 1.5)

    async def _sender_loop(self, ws):
        while self.running:
            msg = await self.send_queue.get()
            try:
                await ws.send(json.dumps(msg))
            except Exception as e:
                self.log_signal.emit("ERROR", f"Failed to send WS message: {e}")
                break

    async def _heartbeat_loop(self, ws):
        while self.running:
            await asyncio.sleep(25)
            try:
                await ws.send(json.dumps({"event": "PING"}))
            except Exception:
                break

    async def _receiver_loop(self, ws):
        async for raw in ws:
            try:
                data = json.loads(raw)
                event = data.get("event")

                if event == "AUTHENTICATED":
                    self.connected_signal.emit(data)
                    self.log_signal.emit("SUCCESS", f"Device authenticated: {data.get('device_name')} ({data.get('device_code')})")

                elif event == "PRINT_JOB_DISPATCH":
                    job = data.get("job")
                    if job:
                        self.log_signal.emit("JOB", f"Incoming Print Job #{job.get('id', '')[:8]} - {job.get('product_name')}")
                        self.job_received_signal.emit(job)

                elif event == "PONG":
                    pass

                elif event == "ERROR":
                    self.log_signal.emit("ERROR", f"Server error: {data.get('error')}")

            except json.JSONDecodeError:
                self.log_signal.emit("WARN", f"Malformed payload from server: {raw}")

    def send_status_update(self, job_id: str, status: str, start_time: str = None, end_time: str = None, error_message: str = None, printed_copies: int = 0):
        """Thread-safe enqueue of job status back to the server."""
        payload = {
            "event": "JOB_STATUS_UPDATE",
            "job_id": job_id,
            "status": status,
            "job_start_time": start_time,
            "job_end_time": end_time,
            "error_message": error_message,
            "printed_copies": printed_copies
        }
        if self.loop and self.send_queue:
            asyncio.run_coroutine_threadsafe(self.send_queue.put(payload), self.loop)

    def request_pending_jobs(self):
        """Asks server to re-stream any pending jobs in the queue."""
        if self.loop and self.send_queue:
            asyncio.run_coroutine_threadsafe(self.send_queue.put({"event": "REQUEST_PENDING_JOBS"}), self.loop)

    def stop(self):
        self.running = False
        if self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)
        self.wait(2000)
