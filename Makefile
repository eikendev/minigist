UV ?= uv
PYTHON ?= python3
SRC := ./minigist
TESTS := ./tests

.PHONY: default
default: check

.PHONY: install
install:
	$(UV) sync --all-extras --dev

.PHONY: format
format:
	$(UV) run isort $(SRC) $(TESTS)
	$(UV) run ruff --fix $(SRC) $(TESTS)

.PHONY: check
check:
	$(UV) run ruff format --check $(SRC) $(TESTS)
	$(UV) run ruff check $(SRC) $(TESTS)
	$(UV) run isort --check $(SRC) $(TESTS)
	$(UV) run mypy $(SRC) $(TESTS)
	$(UV) run pytest $(TESTS)

.PHONY: clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
