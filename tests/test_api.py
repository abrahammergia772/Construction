from fastapi.testclient import TestClient

from app.main import app
from app.services.ai import local_answer


def test_health_reports_configuration_without_secrets():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["supabase_configured"] is False


def test_local_copilot_stays_grounded_in_workspace_records():
    workspace = {
        "projects": [{"name": "North Bridge", "project_type": "Bridge", "progress": 42, "days_remaining": 10, "delay_days": 5, "status": "At risk"}],
        "complaints": [{"priority": "High", "category": "Safety", "description": "PPE check is overdue", "status": "Open"}],
        "tasks": [], "employees": [],
        "metrics": {"active_projects": 1, "at_risk_projects": 1, "open_complaints": 1},
    }
    answer, actions = local_answer("Which projects are behind schedule?", workspace)
    assert "North Bridge" in answer
    assert actions
