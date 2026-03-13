# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from ._version import __version__
from .compatibility import (
    BUNDLED_PRODUCT_RELEASE,
    DEFAULT_ANSYS_INSTALL_RELEASE,
    DEFAULT_ANSYS_INSTALL_VERSION,
    SUPPORTED_PRODUCT_LINES,
    SUPPORTED_PRODUCT_RELEASE_POLICY,
    ProductCompatibility,
    get_compatibility_info,
    product_release_to_display_string,
    product_release_to_short_label,
)

VERSION = __version__
# ``DEFAULT_ANSYS_VERSION`` remains the compatibility shim name used across the
# codebase, even though the source of truth now lives in ``compatibility.py``.
DEFAULT_ANSYS_VERSION = DEFAULT_ANSYS_INSTALL_VERSION

ansys_version = product_release_to_short_label(DEFAULT_ANSYS_INSTALL_RELEASE)

# Preserve the historical package surface so existing imports keep resolving
# while callers migrate to the explicit compatibility metadata names.
__ansys_version__ = DEFAULT_ANSYS_VERSION
__ansys_version_str__ = product_release_to_display_string(DEFAULT_ANSYS_INSTALL_RELEASE)

# Ease imports
from ansys.dynamicreporting.core.adr_item import Item
from ansys.dynamicreporting.core.adr_report import Report
from ansys.dynamicreporting.core.adr_service import Service
