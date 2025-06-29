SHELL := bash
.SHELLFLAGS := -e -x -c

# Cross-platform Bash
ifeq ($(OS),Windows_NT)
BASH := "C:/Program Files/Git/bin/bash.exe"
else
BASH := bash
endif

.PHONY: install
install: ## 🚀 Set up environment and install project
	@echo "🚀 Syncing dependencies with uv..."
	uv sync --frozen --all-extras
	@echo "🔧 Installing project in editable mode..."
	uv pip install -e .

.PHONY: check-version
check-version:
	@echo "🔍 Checking if a Git tag exists..."
	@if git describe --tags --abbrev=0 >/dev/null 2>&1; then \
	    VERSION=$$(git describe --tags --abbrev=0); \
	    echo "✅ Git tag found: $$VERSION"; \
	else \
	    echo "❌ No Git tag found. Please create one with: git tag v0.1.0"; \
	    exit 1; \
	fi

.PHONY: check
check: ## Run all code quality checks
	@echo "🚀 Checking lock file consistency"
	uv lock --locked
	@echo "🚀 Running pre-commit hooks"
	uv run pre-commit run --all-files

.PHONY: test
test: ## Run tests using tox
	@echo "🚀 Testing code: Running tox across Python versions"
	tox

.PHONY: test-local
test-local: ## Run tests in current Python environment using uv
	@echo "🚀 Testing code locally"
	uv run python -m pytest -rvx tests --cov=ansys.dynamicreporting.core --cov-config=pyproject.toml --cov-report term --cov-report xml:coverage.xml

.PHONY: build
build: clean ## Build package using uv
	@echo "🚀 Building project"
	uv build

.PHONY: version
version: ## Print the current project version
	uv run hatch version

.PHONY: tag
tag: ## 🏷 Tag the current release version (fixes changelog and pushes tag)
	$(BASH) scripts/tag_release.sh

.PHONY: check-dist
check-dist: ## Validate dist/ artifacts (long description, format)
	@echo "🔍 Validating dist/ artifacts..."
	uv run twine check dist/*

.PHONY: publish
publish-test: ## Publish to Azure Private PyPI
	@echo "🚀 Publishing to Azure PyPI"
	UV_PUBLISH_TOKEN=$(AZURE_PYPI_TOKEN) uv publish --publish-url=$(AZURE_PYPI_URL) --no-cache

build-nightly: build

.PHONY: pull-docker
pull-docker:
	bash scripts/pull_adr_image.sh

.PHONY: smoketest
smoketest:
	uv run python tests/smoketest.py

.PHONY: clean
clean: ## Clean build artifacts
	@echo "🚀 Removing build artifacts"
	rm -rf dist build
	rm -rf **/*.egg-info
	rm -f src/ansys/dynamicreporting/core/adr_item.py
	rm -f src/ansys/dynamicreporting/core/adr_utils.py
	rm -f src/ansys/dynamicreporting/core/build_info.py
	rm -rf .coverage coverage-html coverage.xml .pytest_cache
	find . -name '*.pyc' -delete

.PHONY: test-clean
test-clean:
	uv run python scripts/test_cleanup.py

docs:
	$(MAKE) -C doc html

docs-clean:
	$(MAKE) -C doc clean

.PHONY: help
help:
	uv run python -c "import re; \
	[[print(f'\033[36m{m[0]:<20}\033[0m {m[1]}') for m in re.findall(r'^([a-zA-Z_-]+):.*?## (.*)$$', open(makefile).read(), re.M)] for makefile in ('$(MAKEFILE_LIST)').strip().split()]"

.DEFAULT_GOAL := help
