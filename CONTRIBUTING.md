# Contributing

We absolutely welcome any code contributions and we hope that this
guide will facilitate an understanding of the `pydynamicreporting` code
repository. It is important to note that while the `pydynamicreporting`
software package is maintained by ANSYS and any submissions will be
reviewed thoroughly before merging, we still seek to foster a community
that can support user questions and develop new features to make this
software a useful tool for all users. As such, we welcome and encourage
any questions or submissions to this repository.

Overall guidance on contributing to a PyAnsys library appears in the
[Contributing](https://dev.docs.pyansys.com/how-to/contributing.html) topic
in the *PyAnsys Developer's Guide*. Please reference the
[PyAnsys Developer's Guide](https://dev.docs.pyansys.com/) for the full
documentation regarding contributing to the `pydynamicreporting` project.

Ensure that you are thoroughly familiar with this guide before attempting to
contribute to PyDynamicReporting.

## Branch Conventions

This project does not allow for direct commits into the main branch. The use
of branches is required for any new feature, bug fix or change. We do
encourage the use of the following branch naming convention:

- **`fix`** - any bug fixes, patches, or experimental changes that are minor
- **`feat`** - any changes that introduce a new feature or significant addition
- **`junk`** - for any experimental changes that can be deleted if gone stale
- **`maint`** - for general maintenance of the repository or CI routines
- **`doc`** - for any changes only pertaining to documentation
- **`no-ci`** - for low-impact activity that should not trigger the CI routines
- **`testing`** - improvements or changes to testing
- **`release`** - releases

## Forward-Porting Compatibility Changes

When forward-porting maintenance-line compatibility work into `main`, do not
assume that version constants, install defaults, or dependency floors should
come across unchanged. Recheck the following items explicitly:

- `src/ansys/dynamicreporting/core/compatibility.py`:
  `DEFAULT_ANSYS_INSTALL_RELEASE`, `DEFAULT_ANSYS_INSTALL_VERSION`, and
  `AUTO_DETECT_INSTALL_VERSIONS`
- `src/ansys/dynamicreporting/core/__init__.py`:
  `DEFAULT_ANSYS_VERSION`, `ansys_version`, `__ansys_version__`, and
  `__ansys_version_str__`
- `src/ansys/dynamicreporting/core/common_utils.py`:
  default install probe order and fallback assumptions
- `src/ansys/dynamicreporting/core/serverless/_compat.py`:
  any release-specific compatibility shims that should remain scoped to the
  maintenance branch
- `pyproject.toml`:
  Django, `django-guardian`, and other dependency floors that may have been
  widened to support an older product line
- `tests/test_compatibility.py` and `tests/serverless/test_common_utils.py`:
  expectations tied to the target bundled release and implicit install
  discovery order

Before merging a forward-port PR into `main`, confirm that:

- the default install version and public version constants match the intended
  `main`-line product release
- the implicit install probe order prefers the intended `main`-line bundled
  release
- maintenance-line dependency floor changes are either reverted or explicitly
  accepted for `main`
- compatibility tests and smoketest output reflect the intended `main`-line
  release family
