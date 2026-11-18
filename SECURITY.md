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

Update certifi to 2026.10.19 or later, which removes trust in the CA used by the
compromised eMudhra intermediates. Other trust stores in your environment need
separate updates:

- **Python:** use CPython 3.11.18+, 3.12.16+, 3.13.18+, or 3.14.10+. See the
  [Python security announcement](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576).
- **System and product:** refresh OS and container certificate stores, and check
  explicit CA-file overrides. ADR's bundled browser and Qt runtime have their own
  trust stores; get updates for those from the product vendor.
