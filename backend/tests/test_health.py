from careflow.main import HealthResponse, app
from fastapi.testclient import TestClient


def test_health_reports_process_liveness() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert HealthResponse.model_validate(response.json()).status == "ok"
