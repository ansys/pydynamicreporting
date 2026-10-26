# Security Policy

## Reporting a vulnerability

> [!CAUTION]
> Do not use GitHub issues to report any security vulnerabilities.

If you detect a vulnerability, contact the [PyAnsys Core team](mailto:pyansys-core@synopsys.com),
mentioning the repository and the details of your finding. The team will address it as soon as possible.

Provide the PyAnsys Core team with this information:

- Any specific configuration settings needed to reproduce the problem
- Step-by-step guidance to reproduce the problem
- The exact location of the problematic source code, including tag, branch, commit, or a direct URL
- The potential consequences of the vulnerability, along with a description of how an attacker could take advantage of the issue

## TLS security after the eMudhra incident

The `stable/27.1` package remains compatible with Python 3.10 through 3.14.
For the interpreter's compromised-key protection, use CPython 3.11.18+, 3.12.16+,
3.13.18+, or 3.14.10+ within the package's supported range. Python 3.10 is
end-of-life and has no upstream fix for this incident. Deployments retaining
3.10 need a maintained vendor backport or an independently verified trust-store
mitigation; package compatibility does not establish that protection. See the
[Python security announcement](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576).

Use certifi 2026.10.19+, pip 26.2.2+, uv 0.13.5+, and virtualenv 21.14.13+.
Each tool can carry its own CA bundle or environment seeds. Updating the
project's certifi alone does not update those copies. Bootstrap from official
artifacts with independently checked hashes, update existing environments, and
recreate hook environments using `uv run pre-commit run --all-files`. The hook
dependency floors in this branch invalidate the affected cached environments.
The [virtualenv release notes](https://virtualenv.pypa.io/en/latest/changelog.html)
describe the corrected pip seed; the
[uv release notes](https://github.com/astral-sh/uv/releases/tag/0.13.5)
describe compromised-intermediate key rejection.

CI uses patched interpreters on Windows and Linux without changing the package's
Python requirement. `.github/python-downloads.json` pins eight x86-64 builds
from the official
[python-build-standalone 20261026 release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261026).
The entries come from
[uv download metadata at 69e574e](https://github.com/astral-sh/uv/blob/69e574e368d31145692b3e22e59285316566e6d7/crates/uv-python-managed/download-metadata.json),
with SHA-256 values checked against the release assets. uv verifies these hashes
before installation, and `scripts/check_ci_python.py` checks the selected
interpreter. Keep the metadata, matrices, and guard in sync when updating CI.

Deployment owners must also refresh OS certificate stores and rebuild container
images without cached layers. Preserve required enterprise CAs while removing
compromised trust. Inspect the stores used by the running process, including
explicit CA-file overrides, PostgreSQL/libpq configuration, and ADR's bundled
Chromium or Qt runtime. PyDynamicReporting cannot replace these external stores
or vendor binaries. Validate the deployed ADR browser when updating Playwright;
its embedded Node runtime and the product browser have separate trust stores.
The gRPC/DPF certificate store remains a separate remediation.
