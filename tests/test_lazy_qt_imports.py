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

import json
import subprocess
import sys
import textwrap


def _run_import_probe(source: str) -> dict[str, object]:
    """
    Execute a small import probe in a fresh interpreter (must use a subprocess to start free from previous runs).
    sys.executable uses the same Python interpreter as the test runner.
    "-c" tells Python to execute the following source string
    textwrap.dedent(source) removes indentation from the triple-quoted embedded script before execution.
    """
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        capture_output=True,
        check=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_report_remote_server_import_stays_headless():
    probe = _run_import_probe(
        """
        import json
        import sys

        from ansys.dynamicreporting.core.utils import report_remote_server

        print(
            json.dumps(
                {
                    "module": report_remote_server.__name__,
                    "qtpy": "qtpy" in sys.modules,
                    "PySide6": "PySide6" in sys.modules,
                    "shiboken6": "shiboken6" in sys.modules,
                }
            )
        )
        """
    )

    assert probe == {
        "module": "ansys.dynamicreporting.core.utils.report_remote_server",
        "qtpy": False,
        "PySide6": False,
        "shiboken6": False,
    }


def test_service_import_stays_headless_while_loading_service_modules():
    probe = _run_import_probe(
        """
        import json
        import sys

        from ansys.dynamicreporting.core import Service

        print(
            json.dumps(
                {
                    "module": Service.__module__,
                    "report_objects_loaded": (
                        "ansys.dynamicreporting.core.utils.report_objects" in sys.modules
                    ),
                    "report_remote_server_loaded": (
                        "ansys.dynamicreporting.core.utils.report_remote_server" in sys.modules
                    ),
                    "qtpy": "qtpy" in sys.modules,
                    "PySide6": "PySide6" in sys.modules,
                    "shiboken6": "shiboken6" in sys.modules,
                }
            )
        )
        """
    )

    assert probe == {
        "module": "ansys.dynamicreporting.core.adr_service",
        "report_objects_loaded": True,
        "report_remote_server_loaded": True,
        "qtpy": False,
        "PySide6": False,
        "shiboken6": False,
    }
