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

_LAZY_MODULES = {
    "encoders": "ansys.dynamicreporting.core.utils.encoders",
    "enhanced_images": "ansys.dynamicreporting.core.utils.enhanced_images",
    "exceptions": "ansys.dynamicreporting.core.utils.exceptions",
    "extremely_ugly_hacks": "ansys.dynamicreporting.core.utils.extremely_ugly_hacks",
    "filelock": "ansys.dynamicreporting.core.utils.filelock",
    "geofile_processing": "ansys.dynamicreporting.core.utils.geofile_processing",
    "pdf_utils": "ansys.dynamicreporting.core.utils.pdf_utils",
    "report_download_html": "ansys.dynamicreporting.core.utils.report_download_html",
    "report_download_pdf": "ansys.dynamicreporting.core.utils.report_download_pdf",
    "report_objects": "ansys.dynamicreporting.core.utils.report_objects",
    "report_remote_server": "ansys.dynamicreporting.core.utils.report_remote_server",
    "report_utils": "ansys.dynamicreporting.core.utils.report_utils",
}

__all__ = sorted(_LAZY_MODULES)


def __getattr__(name):
    """Load utility submodules only when requested."""
    if name in _LAZY_MODULES:
        from importlib import import_module

        module = import_module(_LAZY_MODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
