"""FastAPI application exposing the orchestrator to the frontend.

Endpoints:
    GET  /api/health              liveness probe
    GET  /api/backends            all registered backends with live mode
    GET  /api/algorithms          algorithm catalog with parameter schemas
    POST /api/jobs                submit a benchmark job
    GET  /api/jobs                recent jobs
    GET  /api/jobs/{id}           job status + result
    GET  /api/jobs/{id}/events    Server-Sent Events progress stream
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import qsolace
from qsolace.algorithms import ALGORITHMS
from qsolace.backends.factory import create_default_registry
from qsolace.orchestrator import JobManager

app = FastAPI(
    title="Quantum of Solace",
    version=qsolace.__version__,
    description="Hybrid quantum-classical workflow orchestration.",
)

# The Vite dev server (localhost:5173) proxies /api, but allow direct calls too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = create_default_registry()
jobs = JobManager(registry)


class JobRequest(BaseModel):
    algorithm_id: str = Field(..., examples=["maxcut-qaoa"])
    backend_id: str = Field(default="local-simulator")
    params: dict[str, Any] = Field(default_factory=dict)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": qsolace.__version__}


@app.get("/api/backends")
def list_backends() -> list[dict[str, Any]]:
    return [backend.info().to_dict() for backend in registry.list()]


@app.get("/api/algorithms")
def list_algorithms() -> list[dict[str, Any]]:
    return ALGORITHMS


@app.post("/api/jobs", status_code=201)
def submit_job(request: JobRequest) -> dict[str, Any]:
    if not any(a["id"] == request.algorithm_id for a in ALGORITHMS):
        raise HTTPException(status_code=404, detail=f"unknown algorithm '{request.algorithm_id}'")
    try:
        job = jobs.submit(request.algorithm_id, request.backend_id, request.params)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return job.to_dict(include_result=False)


@app.get("/api/jobs")
def list_jobs() -> list[dict[str, Any]]:
    return [job.to_dict(include_result=False) for job in jobs.list()[:50]]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    try:
        return jobs.get(job_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/jobs/{job_id}/events")
def stream_job_events(job_id: str) -> StreamingResponse:
    try:
        subscription = jobs.subscribe(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    def event_stream():
        while True:
            event = subscription.get()
            if event is None:
                yield "event: end\ndata: {}\n\n"
                return
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
