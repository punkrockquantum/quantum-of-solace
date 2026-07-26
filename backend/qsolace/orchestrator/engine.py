"""Hybrid workflow orchestrator.

Runs benchmark jobs on worker threads, buffers progress events, and lets any
number of SSE subscribers replay + follow a job's event stream. In a lab
deployment the same job model fans out to HPC schedulers; here a thread pool
is plenty for interactive use.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from qsolace.comparison import run_benchmark
from qsolace.core.registry import BackendRegistry

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    algorithm_id: str
    backend_id: str
    params: dict[str, Any]
    status: JobStatus = JobStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    result: dict[str, Any] | None = None
    error: str | None = None
    #: full ordered event history (replayed to late SSE subscribers)
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, include_result: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "algorithm_id": self.algorithm_id,
            "backend_id": self.backend_id,
            "params": self.params,
            "status": self.status.value,
            "created_at": self.created_at,
            "error": self.error,
        }
        if include_result:
            payload["result"] = self.result
        return payload


class JobManager:
    def __init__(self, registry: BackendRegistry, max_workers: int = 2) -> None:
        self._registry = registry
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="qsolace-job")
        self._jobs: dict[str, Job] = {}
        self._subscribers: dict[str, list[queue.Queue]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def submit(self, algorithm_id: str, backend_id: str, params: dict[str, Any]) -> Job:
        # validate backend id eagerly so submission fails fast
        self._registry.get(backend_id)
        job = Job(id=uuid.uuid4().hex[:12], algorithm_id=algorithm_id, backend_id=backend_id, params=params)
        with self._lock:
            self._jobs[job.id] = job
            self._subscribers[job.id] = []
        self._executor.submit(self._run, job)
        return job

    def get(self, job_id: str) -> Job:
        try:
            return self._jobs[job_id]
        except KeyError:
            raise KeyError(f"unknown job '{job_id}'") from None

    def list(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    # ------------------------------------------------------------------
    # Event streaming
    # ------------------------------------------------------------------
    def subscribe(self, job_id: str) -> queue.Queue:
        """Queue that replays the job's history, then follows live events.

        A ``None`` item marks the end of the stream.
        """
        job = self.get(job_id)
        q: queue.Queue = queue.Queue()
        with self._lock:
            for event in job.events:
                q.put(event)
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                q.put(None)
            else:
                self._subscribers[job_id].append(q)
        return q

    def _publish(self, job: Job, event: dict[str, Any]) -> None:
        event = {**event, "ts": time.time()}
        with self._lock:
            job.events.append(event)
            subscribers = list(self._subscribers.get(job.id, []))
        for q in subscribers:
            q.put(event)

    def _finish(self, job: Job) -> None:
        with self._lock:
            subscribers = self._subscribers.pop(job.id, [])
        for q in subscribers:
            q.put(None)

    # ------------------------------------------------------------------
    def _run(self, job: Job) -> None:
        job.status = JobStatus.RUNNING
        self._publish(job, {"type": "status", "status": job.status.value})
        try:
            backend = self._registry.get(job.backend_id)

            def progress(event: dict[str, Any]) -> None:
                self._publish(job, {"type": "progress", **event})

            job.result = run_benchmark(job.algorithm_id, job.params, backend, progress)
            job.status = JobStatus.COMPLETED
            self._publish(job, {"type": "status", "status": job.status.value})
        except Exception as exc:  # noqa: BLE001 - surface any failure to the client
            logger.exception("job %s failed", job.id)
            job.error = str(exc)
            job.status = JobStatus.FAILED
            self._publish(job, {"type": "status", "status": job.status.value, "error": job.error})
        finally:
            self._finish(job)
