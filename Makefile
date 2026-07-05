SHELL := /bin/bash

UV_PYTHON ?= 3.11
PORT ?= 8000
ENDPOINT ?= http://127.0.0.1:$(PORT)
IMAGE ?= mood-radio-mcp:local
SMOKE_PORT ?= 8766
SMOKE_CONTAINER ?= mood-radio-mcp-smoke
SMOKE_VOLUME ?= mood-radio-mcp-smoke-data

.PHONY: help install run test audit bundle preflight docker-build docker-smoke clean clean-all

help:
	@printf '%s\n' \
		'Targets:' \
		'  install       Install local dev dependencies with uv' \
		'  run           Run the MCP server on PORT, default 8000' \
		'  test          Run pytest' \
		'  audit         Run py_compile and submission audit' \
		'  bundle        Build dist tarball and checksum manifest' \
		'  preflight     Check ENDPOINT /, /health, and /mcp' \
		'  docker-build  Build local Docker image' \
		'  docker-smoke  Build, run, preflight, and clean a test container' \
		'  clean         Remove local caches and data' \
		'  clean-all     Remove caches, data, and dist'

install:
	uv sync --python $(UV_PYTHON) --extra dev

run:
	PORT=$(PORT) uv run --python $(UV_PYTHON) mood-radio-mcp

test:
	uv run --python $(UV_PYTHON) pytest

audit:
	uv run --python $(UV_PYTHON) python -m py_compile mood_radio_mcp/*.py scripts/*.py tests/*.py
	uv run --python $(UV_PYTHON) python scripts/submission_audit.py

bundle: audit
	uv run --python $(UV_PYTHON) python scripts/build_release_bundle.py

preflight:
	uv run --python $(UV_PYTHON) python scripts/preflight_endpoint.py $(ENDPOINT)

docker-build:
	docker build -t $(IMAGE) .

docker-smoke: docker-build
	@set -euo pipefail; \
	docker rm -f $(SMOKE_CONTAINER) >/dev/null 2>&1 || true; \
	docker volume rm $(SMOKE_VOLUME) >/dev/null 2>&1 || true; \
	docker run -d --name $(SMOKE_CONTAINER) -p $(SMOKE_PORT):8000 -v $(SMOKE_VOLUME):/data $(IMAGE); \
	cleanup() { docker rm -f $(SMOKE_CONTAINER) >/dev/null 2>&1 || true; docker volume rm $(SMOKE_VOLUME) >/dev/null 2>&1 || true; }; \
	trap cleanup EXIT; \
	for _ in $$(seq 1 30); do \
		if curl -fsS http://127.0.0.1:$(SMOKE_PORT)/health >/dev/null 2>&1; then \
			break; \
		fi; \
		sleep 1; \
	done; \
	curl -fsS http://127.0.0.1:$(SMOKE_PORT)/health >/dev/null; \
	uv run --python $(UV_PYTHON) python scripts/preflight_endpoint.py http://127.0.0.1:$(SMOKE_PORT); \
	test "$$(docker exec $(SMOKE_CONTAINER) id -u)" = "1000"; \
	docker exec $(SMOKE_CONTAINER) test -w /data

clean:
	rm -rf .pytest_cache mood_radio_mcp/__pycache__ scripts/__pycache__ tests/__pycache__ data

clean-all: clean
	rm -rf dist
