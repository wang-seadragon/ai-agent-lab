"""Local-only pipeline simulator. All observations are synthetic lab measurements."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ.get("LAB_CONTROL_TOKEN", "local-lab-only")
ENTITY = "lab-orders"
INCIDENT = "LAB-INC-1"
lock = threading.Lock()
state = {"mode": "normal", "lag": 0.0, "processed": 0, "errors": 0}
MODES = {"normal", "lag", "failure"}


def tick():
    while True:
        with lock:
            mode = state["mode"]
            if mode == "normal":
                state["lag"] = max(0.0, state["lag"] - 0.5)
                state["processed"] += 1
            elif mode == "lag":
                state["lag"] += 1.0
                state["processed"] += 1
            else:
                state["errors"] += 1
                state["lag"] += 1.0
        time.sleep(1)


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, content_type="application/json"):
        raw = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        with lock:
            snapshot = dict(state)
        if self.path == "/health":
            self.reply(200, json.dumps({"status": "ok", "environment": "lab"}))
        elif self.path == "/metrics":
            metrics = (
                "# HELP lab_ingestion_lag_minutes Simulated pipeline ingestion lag\n"
                "# TYPE lab_ingestion_lag_minutes gauge\n"
                f'lab_ingestion_lag_minutes{{pipeline="{ENTITY}",incident_id="{INCIDENT}"}} {snapshot["lag"]}\n'
                "# TYPE lab_processed_total counter\n"
                f'lab_processed_total{{pipeline="{ENTITY}"}} {snapshot["processed"]}\n'
                "# TYPE lab_worker_errors_total counter\n"
                f'lab_worker_errors_total{{pipeline="{ENTITY}"}} {snapshot["errors"]}\n'
            )
            self.reply(200, metrics, "text/plain; version=0.0.4")
        else:
            self.reply(404, json.dumps({"error": "not_found"}))

    def do_POST(self):
        if self.path != "/scenario" or self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self.reply(403, json.dumps({"error": "forbidden"}))
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size < 1024:
                raise ValueError("invalid size")
            mode = json.loads(self.rfile.read(size))["mode"]
            if mode not in MODES:
                raise ValueError("invalid mode")
        except (ValueError, KeyError, TypeError):
            self.reply(400, json.dumps({"error": "invalid_scenario"}))
            return
        with lock:
            state["mode"] = mode
            if mode == "normal":
                state["lag"] = 0.0
        self.reply(200, json.dumps({"mode": mode, "environment": "lab"}))


if __name__ == "__main__":
    threading.Thread(target=tick, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8090), Handler).serve_forever()
