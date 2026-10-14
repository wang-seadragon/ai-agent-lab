from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_investigation_request_validation():
    response = client.post("/investigate", json={"incident_id": "", "question": ""})
    assert response.status_code == 422
