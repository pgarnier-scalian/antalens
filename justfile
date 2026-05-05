# List available recipes
default:
    @just --list

# Install all deps including dev
install:
    uv sync --all-extras

# Run tests with coverage
test:
    uv run pytest

# Skip slow tests
test-fast:
    uv run pytest -m "not slow"

# Run all linters
lint:
    uv run ruff check src tests
    uv run ruff format --check src tests

# Auto-format code
format:
    uv run ruff check --fix src tests
    uv run ruff format src tests

# Type-check
type:
    uv run mypy src/antalens

# Run everything (lint + type + test)
check: lint type test

# Build docs
docs:
    uv run sphinx-build -b html -W docs docs/_build/html

# Serve docs with live reload
docs-serve:
    uv run sphinx-autobuild docs docs/_build/html --port 8000

# Smoke test — import works
smoke:
    uv run python -c "import antalens; print(f'antalens {antalens.__version__} OK')"

# Remove build artifacts
clean:
    uv run python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['dist', 'build', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'docs/_build', 'htmlcov']]"
