CODESPELL_DIRS ?= ./pydynamicreporting
CODESPELL_SKIP ?= "*.pyc,*.xml,*.txt,*.gif,*.png,*.jpg,*.js,*.html,*.doctree,*.ttf,*.woff,*.woff2,*.eot,*.mp4,*.inv,*.pickle,*.ipynb,flycheck*,./.git/*,./.hypothesis/*,*.yml,./docs/build/*,./docs/images/*,./dist/*,*~,.hypothesis*,./docs/source/examples/*,*cover,*.dat,*.mac,\#*,PKG-INFO,*.mypy_cache/*,*.xml,*.aedt,*.svg"
CODESPELL_IGNORE ?= "ignore_words.txt"

doctest: codespell

codespell:
	echo "Running codespell"
	codespell $(CODESPELL_DIRS) -S $(CODESPELL_SKIP) # -I $(CODESPELL_IGNORE)

build:
	python -m build --wheel
	python codegen/rename_whl.py
	rm -rf build

build-nightly: build

install:
	pip uninstall ansys-dynamicreporting-core -y
	pip install dist/*.whl

install-dev:
	python -m pip install --upgrade pip
	pip uninstall ansys-dynamicreporting-core -y
	pip install -e .[dev]

pull-docker:
	bash .ci/pull_adr_image.sh

test:
	pytest -rvx --setup-show --cov=ansys.dynamicreporting.core \
 	--cov-report html:coverage-html \
	--cov-report term \
	--cov-report xml:coverage.xml

smoketest:
	python -c "from ansys.dynamicreporting.core import __version__; print(__version__)"
	python -c "from ansys.dynamicreporting.core import Service"

clean:
	rm -rf dist build
	rm -f src/ansys/dynamicreporting/core/adr_item.py
	rm -f src/ansys/dynamicreporting/core/adr_utils.py
	rm -f src/ansys/dynamicreporting/core/build_info.py
	rm -rf **/*.egg-info
	rm -rf coverage-html
	rm -rf .pytest_cache
	find . -name \*.pyc -delete

test_clean:
	python test_cleanup.py

all: clean build install