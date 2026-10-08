.PHONY: help dev dev-agent dev-backend test install

PYTHON ?= python3

help:
	@echo "TerraCortex LangGraph Agent Commands:"
	@echo " make dev-agent    : Run FastAPI microservice (port 8000)"
	@echo " make dev-backend  : Alias for make dev-agent"
	@echo " make test         : Run local multi-agent diagnostic test"
	@echo " make install      : Install requirements.txt"

dev:
	$(PYTHON) main.py

dev-agent: dev
dev-backend: dev

test:
	$(PYTHON) tests/test_agent_local.py

install:
	$(PYTHON) -m pip install -r requirements.txt
