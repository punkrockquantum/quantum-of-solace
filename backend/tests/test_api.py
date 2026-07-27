"""End-to-end API tests through the FastAPI test client."""

import time

import pytest
from fastapi.testclient import TestClient

from qsolace.api.app import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_backends_listing() -> None:
    response = client.get("/api/backends")
    assert response.status_code == 200
    backends = response.json()
    assert len(backends) == 11
    local = next(b for b in backends if b["id"] == "local-simulator")
    assert local["mode"] == "connected"


def test_algorithms_listing() -> None:
    response = client.get("/api/algorithms")
    ids = [a["id"] for a in response.json()]
    assert ids == ["maxcut-qaoa", "vqe-ising", "gbs-dense-subgraph", "quantum-monte-carlo", "cfd-vqls"]


def test_submit_unknown_algorithm() -> None:
    response = client.post("/api/jobs", json={"algorithm_id": "nope", "backend_id": "local-simulator"})
    assert response.status_code == 404


def test_submit_unknown_backend() -> None:
    response = client.post("/api/jobs", json={"algorithm_id": "maxcut-qaoa", "backend_id": "nope"})
    assert response.status_code == 404


def test_job_lifecycle_and_result_provenance() -> None:
    response = client.post(
        "/api/jobs",
        json={
            "algorithm_id": "maxcut-qaoa",
            "backend_id": "local-simulator",
            "params": {"num_nodes": 4, "layers": 1, "max_iterations": 15, "shots": 256, "seed": 1},
        },
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    deadline = time.time() + 60
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(0.2)
    else:
        pytest.fail("job did not finish in time")

    assert job["status"] == "completed", job.get("error")
    result = job["result"]
    assert result["paths"]["classical"]["approximation_ratio"] == 1.0
    assert 0.0 <= result["paths"]["hybrid"]["approximation_ratio"] <= 1.0
    # honesty contract: provenance must disclose simulation
    assert result["provenance"]["simulated"] is True
    assert "simulation" in result["provenance"]["statement"].lower() or "exact" in result["provenance"]["statement"].lower()
    # scaling projection is attached and labelled as a model, not a measurement
    assert result["projection"]["is_projection"] is True
    assert "PROJECTION" in result["projection"]["disclaimer"]
    assert len(result["projection"]["curve"]) > 1

    events = client.get(f"/api/jobs/{job_id}/events")
    assert events.status_code == 200
    assert "event: end" in events.text
