default: test

# Install dependencies, pre-commit hooks, and the playwright chromium browser.
setup:
    uv sync
    uv run pre-commit install
    uv run playwright install chromium

# Run the app locally on http://localhost:8080 (auto-reloads on change).
# OpenHost sets OPENHOST_SQLITE_MAIN in production; locally the presets live under .local/.
run:
    OPENHOST_SQLITE_MAIN=.local/sqlite/main.db uv run hypercorn server.app:app --bind 0.0.0.0:8080 --reload

# Run the fast suite: scheduling logic and the API, in process.
test-fast:
    uv run pytest tests/test_schedule.py tests/test_api.py

# Run the whole suite, including the containerized browser tests (needs podman).
test:
    uv run pytest -x

# Lint, format, and typecheck (same checks as the pre-commit hooks).
check:
    uv run ruff check --fix .
    uv run ruff format .
    uv run mypy

# Build the container image.
build:
    docker build -t meditation-timer .
