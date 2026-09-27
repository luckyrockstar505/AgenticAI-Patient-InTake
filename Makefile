.DEFAULT_GOAL := help
COMPOSE := docker compose
UV := uv

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
.PHONY: help
help:
	@echo ""
	@echo "Claims Intake Agent — available targets"
	@echo "  make up               Build images and start all four services"
	@echo "  make down             Stop and remove containers (keeps volumes)"
	@echo "  make test             Run unit tests with pytest"
	@echo "  make test-integration Run integration tests with pytest"
	@echo "  make test-all         Run unit + integration tests"
	@echo "  make eval             Run the eval suite (exits 0 even with no scenarios)"
	@echo "  make lint             Run ruff + mypy"
	@echo "  make migrate          Run Alembic migrations (alembic upgrade head)"
	@echo "  make seed             Seed the database with synthetic member data"
	@echo "  make logs             Tail logs for all running containers"
	@echo "  make lock             Regenerate uv.lock from pyproject.toml"
	@echo ""

# ---------------------------------------------------------------------------
# Local Docker stack
# ---------------------------------------------------------------------------
.PHONY: up
up: .env
	$(COMPOSE) up --build -d
	@echo ""
	@echo "  Services starting…  run 'make logs' to watch or"
	@echo "  curl http://localhost:8000/healthz to verify."
	@echo ""

.PHONY: down
down:
	$(COMPOSE) down

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------
.PHONY: test
test:
	$(UV) run pytest tests/unit -v

.PHONY: test-integration
test-integration:
	$(UV) run pytest tests/integration tests/contracts -v

.PHONY: test-all
test-all: test test-integration

.PHONY: eval
eval:
	$(UV) run python -m evals.runner

.PHONY: lint
lint:
	$(UV) run ruff check .
	$(UV) run mypy .

.PHONY: migrate
migrate:
	$(UV) run alembic -c mcp_tools/db/migrations/alembic.ini upgrade head

.PHONY: seed
seed:
	$(UV) run python scripts/seed.py

.PHONY: logs
logs:
	$(COMPOSE) logs -f

# ---------------------------------------------------------------------------
# Dependency management
# ---------------------------------------------------------------------------
.PHONY: lock
lock:
	$(UV) lock

.PHONY: install
install: uv.lock
	$(UV) sync

uv.lock: pyproject.toml
	$(UV) lock

# ---------------------------------------------------------------------------
# .env guard — remind the developer to copy .env.example if .env is missing
# ---------------------------------------------------------------------------
.env:
	@echo ""
	@echo "  .env not found.  Creating it from .env.example…"
	cp .env.example .env
	@echo "  Edit .env if you need custom values, then re-run 'make up'."
	@echo ""
