"""Local-only Prometheus query adapter; lab data is never production evidence."""
import json
import math
import os
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

LAB_INCIDENT = "LAB-INC-1"
LAB_ENTITY = "lab-orders"


def fetch_lab_metrics(incident_id, *, endpoint=None, opener=urlopen):
    if incident_id != LAB_INCIDENT:
        return {"error": "lab_incident_not_found", "incident_id": incident_id}
    endpoint = endpoint or os.getenv("LAB_PROMETHEUS_URL", "http://127.0.0.1:9090")
    parsed = urlsplit(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1") or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        return {"error": "invalid_lab_endpoint", "incident_id": incident_id}
    query = 'lab_ingestion_lag_minutes{pipeline="lab-orders",incident_id="LAB-INC-1"}'
    url = endpoint.rstrip("/") + "/api/v1/query?" + urlencode({"query": query})
    try:
        with opener(url, timeout=5.0) as response:
            payload = response.read(65537)
        if len(payload) > 65536:
            raise ValueError("oversized")
        data = json.loads(payload)
        if data.get("status") != "success" or data["data"]["resultType"] != "vector":
            raise ValueError("invalid response")
        series = data["data"]["result"]
        if len(series) != 1:
            raise ValueError("missing or ambiguous series")
        metric = series[0]["metric"]
        if metric.get("pipeline") != LAB_ENTITY or metric.get("incident_id") != LAB_INCIDENT:
            raise ValueError("identity mismatch")
        lag = float(series[0]["value"][1])
        if not math.isfinite(lag) or lag < 0:
            raise ValueError("invalid lag")
        return {"incident_id": incident_id, "pipeline": LAB_ENTITY,
                "ingestion_lag_minutes": lag, "environment": "lab"}
    except (OSError, URLError, HTTPError, ValueError, TypeError, KeyError, IndexError):
        return {"error": "lab_metrics_unavailable", "incident_id": incident_id}
