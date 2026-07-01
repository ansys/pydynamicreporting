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

# Keep utility submodules opt-in. Importing this package should not pull in
# service-mode helpers such as ``report_objects`` and their optional Qt stack.

__all__ = ["geofile_processing", "report_objects", "report_remote_server"]


def __getattr__(name):
    """Resolve the historical utility package exports only when requested."""
    if name == "geofile_processing":
        from importlib import import_module

        geofile_processing = import_module("ansys.dynamicreporting.core.utils.geofile_processing")

        globals()[name] = geofile_processing
        return geofile_processing
    if name == "report_objects":
        from importlib import import_module

        report_objects = import_module("ansys.dynamicreporting.core.utils.report_objects")

        globals()[name] = report_objects
        return report_objects
    if name == "report_remote_server":
        from importlib import import_module

        report_remote_server = import_module("ansys.dynamicreporting.core.utils.report_remote_server")

        globals()[name] = report_remote_server
        return report_remote_server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
