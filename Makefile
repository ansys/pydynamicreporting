SHELL := bash
.SHELLFLAGS := -e -x -c

# Cross-platform Bash
ifeq ($(OS),Windows_NT)
BASH := "C:/Program Files/Git/bin/bash.exe"
else
BASH := bash
endif

TEST_FILE ?= "tests\test_service.py"

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

.PHONY: typecheck
typecheck: ## Run ty type checker
	uv run ty check src

.PHONY: version
version: ## Print the current project version
	uv run hatch version

pull-docker:
	bash scripts/pull_adr_image.sh

test:
	uv run python -m pip install -e .[test]
	uv run python -m pytest \
		-rvx --setup-show \
		--cov=ansys.dynamicreporting.core \
		--cov-report html:coverage-html \
		--cov-report term \
		--cov-report xml:coverage.xml

smoketest:
	uv run python tests/smoketest.py

.PHONY: build
build: clean ## Build package using uv
	@echo "🚀 Building project"
	uv build

.PHONY: install
install: ## 🚀 Set up environment and install project
	@echo "🚀 Syncing dependencies with uv..."
	uv sync --frozen --all-extras
	@echo "🔧 Installing project in editable mode..."
	uv run python -m pip install -e .

.PHONY: check-dist
check-dist: ## Validate dist/ artifacts (long description, format)
	@echo "🔍 Validating dist/ artifacts..."
	ls -la dist
	test -e dist/*.whl || (echo "No wheel found in dist/"; exit 1)
	test -e dist/*.tar.gz || (echo "No sdist found in dist/"; exit 1)
	uv run twine check dist/*

.PHONY: tag
tag: ## 🏷 Tag the current release version (fixes changelog and pushes tag)
	$(BASH) scripts/tag_release.sh

.PHONY: publish
publish-test: ## Publish to Azure Private PyPI
	@echo "🚀 Publishing to Azure PyPI"
	UV_PUBLISH_TOKEN=$(AZURE_PYPI_TOKEN) uv publish --publish-url=$(AZURE_PYPI_URL) --no-cache

.PHONY: publish-azure
publish-azure: ## Publish to Azure Private PyPI
	@echo "🚀 Publishing to Azure PyPI"
	@test -n "$(AZURE_PYPI_TOKEN)" || (echo "AZURE_PYPI_TOKEN is required"; exit 1)
	@test -n "$(AZURE_PYPI_URL)" || (echo "AZURE_PYPI_URL is required"; exit 1)
	UV_PUBLISH_TOKEN="$(AZURE_PYPI_TOKEN)" uv publish --publish-url="$(AZURE_PYPI_URL)" --no-cache

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
