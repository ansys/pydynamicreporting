# PyDynamicReporting

[![PyAnsys](https://img.shields.io/badge/Py-Ansys-ffc107.svg?labelColor=black&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAABDklEQVQ4jWNgoDfg5mD8vE7q/3bpVyskbW0sMRUwofHD7Dh5OBkZGBgW7/3W2tZpa2tLQEOyOzeEsfumlK2tbVpaGj4N6jIs1lpsDAwMJ278sveMY2BgCA0NFRISwqkhyQ1q/Nyd3zg4OBgYGNjZ2ePi4rB5loGBhZnhxTLJ/9ulv26Q4uVk1NXV/f///////69du4Zdg78lx//t0v+3S88rFISInD59GqIH2esIJ8G9O2/XVwhjzpw5EAam1xkkBJn/bJX+v1365hxxuCAfH9+3b9/+////48cPuNehNsS7cDEzMTAwMMzb+Q2u4dOnT2vWrMHu9ZtzxP9vl/69RVpCkBlZ3N7enoDXBwEAAA+YYitOilMVAAAAAElFTkSuQmCC)](https://docs.pyansys.com/) [![Python](https://img.shields.io/pypi/pyversions/ansys-dynamicreporting-core?logo=pypi)](https://pypi.org/project/ansys-dynamicreporting-core/) [![PyPI](https://img.shields.io/pypi/v/ansys-dynamicreporting-core.svg?logo=python&logoColor=white)](https://pypi.org/project/ansys-dynamicreporting-core) [![GH-CI](https://github.com/ansys/pydynamicreporting/actions/workflows/ci_cd.yml/badge.svg?branch=main)](https://github.com/ansys/pydynamicreporting/actions?query=branch%3Amain) [![codecov](https://codecov.io/gh/ansys/pydynamicreporting/graph/badge.svg?token=WCAK7QRLR3)](https://codecov.io/gh/ansys/pydynamicreporting) [![MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat)](https://github.com/psf/black)

## Overview

PyDynamicReporting is the Python client library for Ansys Dynamic Reporting, previously documented as [Nexus]. Ansys Dynamic Reporting is a service for pushing items of many types, including images, text, 3D scenes, and tables, into a database, where you can keep them organized and create dynamic reports from them. When you use PyDynamicReporting to connect to an instance of Ansys Dynamic Reporting, you have a Pythonic way of accessing all capabilities of Ansys Dynamic Reporting.

## Documentation and issues

Documentation for the latest stable release of PyDynamicReporting is hosted at [PyDynamicReporting documentation](https://dynamicreporting.docs.pyansys.com/version/stable/).

In the upper right corner of the documentation's title bar, there is an option for switching from viewing the documentation for the latest stable release to viewing the documentation for the development version or previously released versions.

You can also [view](https://cheatsheets.docs.pyansys.com/pydynamicreporting_cheat_sheet.png) or [download](https://cheatsheets.docs.pyansys.com/pydynamicreporting_cheat_sheet.pdf) the PyDynamicReporting cheat sheet. This one-page reference provides syntax rules and commands for using PyDynamicReporting.

On the [PyDynamicReporting Issues](https://github.com/ansys/pydynamicreporting/issues) page, you can create issues to report bugs and request new features. On the [Discussions](https://discuss.ansys.com/) page on the Ansys Developer portal, you can post questions, share ideas, and get community feedback.

To reach the project support team, email [pyansys.core@ansys.com](mailto:pyansys.core@ansys.com).

## Installation

The `pydynamicreporting` package supports Python 3.10 through 3.13 on Windows and Linux. It is currently available on the PyPi [repository](https://pypi.org/project/ansys-dynamicreporting-core/).

To install the package, simply run:

```
pip install ansys-dynamicreporting-core
```

### Developer installation

To clone and install the `pydynamicreporting` package in development mode, run this code:

```
git clone https://github.com/ansys/pydynamicreporting
cd pydynamicreporting
pip install uv
uv sync
source .venv/bin/activate  # (.\.venv\Scripts\activate for Windows shell)
make install  # install pydynamicreporting in editable mode
```

The preceding code creates an "editable" installation that lets you develop and test PyDynamicReporting at the same time.

To build using make, you must have `make` installed on your system.  
If you are on Linux or macOS, you probably already have it installed.  
If you are on Windows, you can use the [chocolatey](https://chocolatey.org/install) package manager to install it:

```
choco install make  # install make on Windows
make clean  # clean
make build   # build
pip install dist/*.whl
# this replaces the editable installation done previously. If you don't want to replace,
# switch your virtual environments to test the new install separately.
```

### Local GitHub Actions

To run GitHub Actions on your local desktop (recommended), install the [act](https://github.com/nektos/act#readme) package:

```
choco install act-cli
```

To run a job, such as the `style` job from the `ci_cd.yml` file, use this command, where `style` is the job name:

```
act -W '.github/workflows/ci_cd.yml' -j style --bind
```

Deploy and upload steps **must always** be ignored.  
If they are not ignored, before running GitHub Actions locally, add `if: ${{ !env.ACT }}` to the workflow step and commit this change if required.

## Creating a Release

- Before creating a new branch, make sure your local repository is up to date:

  ```
  git pull
  ```

- Create a new branch for the release, based on the main branch:

  ```
  git checkout -b release/0.10
  ```

  **Important:**  
  The release branch must only include the **major** and **minor** version numbers.  
  Do not include the patch version.  
  For example, use `release/0.10`, not `release/0.10.0`.

- If creating a **patch release**, do not create a new branch.  
  Instead, reuse the existing `release/0.10` branch.

- Version bumps are automatically handled by the `hatch-vcs` build system based on the latest git tag.  
  **Please do not manually change the version number in the code.**

- Use `make version` to check the current version number.

- Make sure the changelog at [CHANGELOG.md](./CHANGELOG.md) is up to date.

- Then push the branch:

  ```
  git push --set-upstream origin release/0.10
  ```

- Create a tag for the release:

  ```
  make tag
  ```
  Note that this command will create a tag with the full **major.minor.patch** version number, such as `v0.10.0`, and push it to the remote repository.
  If there has been any commits since the last tag, the `make tag` command will automatically bump the patch version number.
  If you want to create a tag for a **minor** or **major** release, look at the make target and do it manually.

  **Important:**  
  GitHub release tags must always include the full **major.minor.patch** version number.  
  Always include the `v` prefix.  
  For example, use `v0.10.0`, not `v0.10`.

- Creating and pushing the tag automatically triggers the release workflow in GitHub Actions and also creates a draft release in the GitHub repository.

- After the workflow completes successfully, you can review the draft release and publish it, which will make the release available to users and also upload the release artifacts to PyPI.

## Dependencies

To use PyDynamicReporting, you must have a locally installed and licensed copy of Ansys 2023 R2 or later.

To use PyDynamicReporting Serverless (`ansys.dynamicreporting.core.serverless`), you must have a locally installed and licensed copy of Ansys 2025 R1 or later.

## Basic usage

```
>>> import ansys.dynamicreporting.core as adr
>>> adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
>>> ret = adr_service.connect()
>>> my_img = adr_service.create_item()
>>> my_img.item_image = "image.png"
>>> adr_service.visualize_report()
```

## License and acknowledgements

PyDynamicReporting is licensed under the MIT license.

PyDynamicReporting makes no commercial claim over Ansys whatsoever.  
This library extends the functionality of Ansys Dynamic Reporting by adding a Python interface to Ansys Dynamic Reporting without changing the core behavior or license of the original software.  
The use of PyDynamicReporting requires a legally licensed copy of an Ansys product that supports Ansys Dynamic Reporting.

To get a copy of Ansys, visit the [Ansys](https://www.ansys.com/) website.

[Nexus]: https://nexusdemo.ensight.com/docs/html/Nexus.html
