MAIN = flyin
PY = python3
DEFAULT_MAP = maps/default.txt

install:
	@which uv > /dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
	@export PATH="$$HOME/.local/bin:$$PATH" && uv sync

run:
	uv run $(PY) -m $(MAIN) $(DEFAULT_MAP) $(ARGS)

run-map:
ifndef MAP
	$(error MAP is not set. Use: make run-map MAP=path)
endif
	uv run $(PY) -m $(MAIN) $(MAP) $(ARGS)

debug:
ifndef MAP
	$(error MAP is not set. Use: make debug MAP=path)
endif
	uv run $(PY) -m pdb $(MAIN)/__main__.py $(MAP) $(ARGS)

clean:
	find . -name "__pycache__" -print -exec rm -rf {} +
	find . -name ".mypy_cache" -print -exec rm -rf {} +
	find . -name "*.pyc" -print -delete

lint:
	uv run flake8 --exclude=.venv,llm_sdk .
	uv run mypy . --exclude '\.venv|llm_sdk' --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	uv run flake8 --exclude=.venv,llm_sdk .
	uv run mypy . --exclude '\.venv|llm_sdk' --strict

build:
	uv run $(PY) -m build

.PHONY: install run debug clean lint lint-strict build
