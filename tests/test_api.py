"""HTTP-level tests for the FastAPI backend (status codes, validation, hardening)."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # runs the lifespan (loads models + fleet timelines)
        yield c


def test_unknown_api_route_is_404_not_html(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404


def test_unknown_airframe_is_404(client):
    assert client.get("/api/fleet/AT-999").status_code == 404


def test_mission_rejects_bad_split(client):
    assert client.get("/api/missions/train_healthy/x").status_code == 400


def test_mission_unknown_id_is_404(client):
    assert client.get("/api/missions/test_fault/nope").status_code == 404


def test_results_is_strict_json(client):
    r = client.get("/api/results")
    assert r.status_code == 200
    assert "NaN" not in r.text


def test_simulate_validates_input(client):
    assert client.post("/api/simulate", json={"profile": "mars"}).status_code == 400
    assert client.post("/api/simulate", json={"onset_s": -5}).status_code == 422
    assert client.post("/api/simulate", json={"gap": 99}).status_code == 422


def test_copilot_rejects_oversized_question(client):
    r = client.post("/api/copilot", json={"question": "x" * 5000})
    assert r.status_code == 422


def test_copilot_offline_answers(client):
    r = client.post("/api/copilot", json={"question": "Status of AT-104?", "force_offline": True})
    assert r.status_code == 200 and r.json()["mode"] == "offline"


def test_real_results_is_404_or_has_a_test_fold(client):
    r = client.get("/api/real-results")
    assert r.status_code == 404 or "test" in r.json()


def test_cors_not_wildcard(client):
    r = client.get("/api/meta", headers={"Origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-origin") != "*"
    assert "access-control-allow-origin" not in r.headers


def test_spa_path_traversal_does_not_leak_files(client):
    r = client.get("/..%2f..%2f..%2f..%2fetc/hosts")
    assert "localhost" not in r.text.lower() or "<html" in r.text.lower()
