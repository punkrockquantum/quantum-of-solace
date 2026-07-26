SHELL := /bin/bash
PYTHON ?= python3
VENV := backend/.venv
UVICORN := $(VENV)/bin/uvicorn
PYTEST := $(VENV)/bin/pytest

# Load nvm-managed node if present (harmless otherwise).
NVM_LOAD := [ -s "$$HOME/.nvm/nvm.sh" ] && . "$$HOME/.nvm/nvm.sh" >/dev/null 2>&1 || true

.PHONY: install install-backend install-frontend dev dev-backend dev-frontend test build-frontend

install: install-backend install-frontend

install-backend:
	@if command -v uv >/dev/null 2>&1; then \
		uv venv $(VENV) --python 3.12 && \
		uv pip install --python $(VENV)/bin/python -e "backend[dev]"; \
	else \
		$(PYTHON) -m venv $(VENV) && \
		$(VENV)/bin/pip install --upgrade pip && \
		$(VENV)/bin/pip install -e "backend[dev]"; \
	fi

install-frontend:
	@$(NVM_LOAD); cd frontend && npm install

dev:
	@trap 'kill 0' INT TERM; \
	$(MAKE) dev-backend & \
	$(MAKE) dev-frontend & \
	wait

dev-backend:
	$(UVICORN) qsolace.api.app:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

dev-frontend:
	@$(NVM_LOAD); cd frontend && npm run dev

test:
	$(PYTEST) backend/tests -q

build-frontend:
	@$(NVM_LOAD); cd frontend && npm run build
