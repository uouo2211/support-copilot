COMPOSE ?= docker compose
PYTHON ?= python3

.PHONY: init up seed test eval down config requirements

# Every target is opt-in. None is executed merely by opening this repository.
init:
	$(PYTHON) scripts/init_env.py
	$(COMPOSE) build

config:
	$(COMPOSE) config --quiet

up:
	$(COMPOSE) up -d --wait db
	$(COMPOSE) run --rm --no-deps web alembic upgrade head
	$(COMPOSE) up -d --wait web worker

seed:
	$(COMPOSE) run --rm --no-deps web python -m scripts.seed

# Install test dependencies into an ephemeral container-owned directory.
test:
	$(COMPOSE) run --rm --no-deps -e UV_PROJECT_ENVIRONMENT=/tmp/test-venv web uv run --frozen --group dev pytest

eval:
	$(COMPOSE) run --rm --no-deps -e UV_PROJECT_ENVIRONMENT=/tmp/test-venv web uv run --frozen --group dev python -m evals.run

down:
	$(COMPOSE) down

# Generated compatibility exports; uv.lock is the source of truth.
requirements:
	$(COMPOSE) run --rm --no-deps web uv export --frozen --no-dev --no-emit-project --no-hashes > requirements.txt
	$(COMPOSE) run --rm --no-deps web uv export --frozen --all-groups --no-emit-project --no-hashes > requirements-dev.txt
