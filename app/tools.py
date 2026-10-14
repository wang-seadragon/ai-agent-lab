"""Deterministic simulated incident tools. MCP integration is milestone 2."""
from langchain_core.tools import tool


@tool
def get_incident_metrics(incident_id: str) -> dict:
    """Get data pipeline metrics for an incident."""
    if incident_id != "INC-1001":
        return {"error": "Incident not found", "incident_id": incident_id}
    return {
        "incident_id": incident_id,
        "pipeline": "daily-orders",
        "ingestion_lag_minutes": 24,
        "normal_lag_minutes": 2,
        "worker_cpu_percent": 96,
    }


@tool
def get_incident_logs(incident_id: str) -> dict:
    """Get recent pipeline logs for an incident."""
    if incident_id != "INC-1001":
        return {"error": "Incident not found", "incident_id": incident_id}
    return {
        "incident_id": incident_id,
        "entries": [
            "WARN executor: repeated task retries",
            "ERROR transform: worker memory pressure",
            "WARN pipeline: consumer lag growing",
        ],
    }


@tool
def get_incident_runbook(incident_id: str) -> dict:
    """Get operational runbook guidance for an incident."""
    if incident_id != "INC-1001":
        return {"error": "Incident not found", "incident_id": incident_id}
    return {
        "incident_id": incident_id,
        "guidance": [
            "Correlate executor resource pressure with ingestion lag.",
            "Inspect recent deployments and input volume changes.",
            "Require human approval before changing capacity.",
        ],
    }
