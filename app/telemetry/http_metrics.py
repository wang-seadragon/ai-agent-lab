"""Read-only HTTP telemetry adapter. No simulated fallback.

Expected JSON: incident_id, pipeline, ingestion_lag_minutes.
Provider must independently enforce authorization and incident-to-entity scope.
"""
import json
import math
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, quote
from urllib.request import Request, urlopen


def fetch_telemetry_metrics(incident_id, *, url=None, token=None,
                            timeout_seconds=5.0, opener=urlopen):
    """Return provider evidence or an error marker; never fabricate metrics."""
    url = url if url is not None else os.getenv("TELEMETRY_METRICS_URL", "")
    token = token if token is not None else os.getenv("TELEMETRY_API_TOKEN", "")
    if not incident_id or not url or not token:
        return {"error": "telemetry_not_configured", "incident_id": incident_id}
    if url.count("{incident_id}") != 1:
        return {"error": "telemetry_url_template_required", "incident_id": incident_id}
    url = url.replace("{incident_id}", quote(incident_id, safe=""))
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return {"error": "telemetry_requires_https", "incident_id": incident_id}
    if not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        return {"error": "invalid_timeout", "incident_id": incident_id}
    request = Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            payload = response.read(65537)
        if len(payload) > 65536:
            return {"error": "telemetry_response_too_large", "incident_id": incident_id}
        data = json.loads(payload)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeError):
        return {"error": "telemetry_unavailable", "incident_id": incident_id}
    if not isinstance(data, dict) or data.get("error"):
        return {"error": "invalid_telemetry", "incident_id": incident_id}
    if data.get("incident_id") != incident_id or not isinstance(data.get("pipeline"), str) or not data["pipeline"]:
        return {"error": "telemetry_identity_mismatch", "incident_id": incident_id}
    lag = data.get("ingestion_lag_minutes")
    if type(lag) not in (int, float) or not math.isfinite(lag) or lag < 0:
        return {"error": "invalid_telemetry", "incident_id": incident_id}
    return {"incident_id": incident_id, "pipeline": data["pipeline"],
            "ingestion_lag_minutes": lag}
