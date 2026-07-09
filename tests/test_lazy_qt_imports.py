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


def test_report_download_pdf_module_import_stays_headless():
    probe = _run_import_probe(
        """
        import json
        import sys

        import ansys.dynamicreporting.core.utils.report_download_pdf as report_download_pdf

        print(
            json.dumps(
                {
                    "module": report_download_pdf.__name__,
                    "qtpy": "qtpy" in sys.modules,
                    "PySide6": "PySide6" in sys.modules,
                    "shiboken6": "shiboken6" in sys.modules,
                }
            )
        )
        """
    )

    assert probe == {
        "module": "ansys.dynamicreporting.core.utils.report_download_pdf",
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


def test_set_payload_image_runtime_stays_headless_for_png_bytes():
    probe = _run_import_probe(
        """
        import base64
        import io
        import json
        import sys

        from PIL import Image
        from ansys.dynamicreporting.core.utils.report_objects import ItemREST

        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z4XcAAAAASUVORK5CYII="
        )
        item = ItemREST()
        item.set_payload_image(png_bytes)
        image = Image.open(io.BytesIO(item.image_data))

        print(
            json.dumps(
                {
                    "qtpy": "qtpy" in sys.modules,
                    "PySide6": "PySide6" in sys.modules,
                    "shiboken6": "shiboken6" in sys.modules,
                    "width": item.width,
                    "height": item.height,
                    "fileurl": item.fileurl,
                    "guid": str(item.guid),
                    "guid_text": image.text.get("CEI_NEXUS_GUID"),
                }
            )
        )
        """
    )

    assert probe["qtpy"] is False
    assert probe["PySide6"] is False
    assert probe["shiboken6"] is False
    assert probe["width"] == 1
    assert probe["height"] == 1
    assert probe["fileurl"] == "image.png"
    assert probe["guid_text"] == probe["guid"]


def test_set_payload_image_runtime_stays_headless_for_pillow_image():
    probe = _run_import_probe(
        """
        import io
        import json
        import sys

        from PIL import Image
        from ansys.dynamicreporting.core.utils.report_objects import ItemREST

        item = ItemREST()
        item.set_payload_image(Image.new("RGB", (2, 3), color="red"))
        image = Image.open(io.BytesIO(item.image_data))

        print(
            json.dumps(
                {
                    "qtpy": "qtpy" in sys.modules,
                    "PySide6": "PySide6" in sys.modules,
                    "shiboken6": "shiboken6" in sys.modules,
                    "width": item.width,
                    "height": item.height,
                    "fileurl": item.fileurl,
                    "guid": str(item.guid),
                    "guid_text": image.text.get("CEI_NEXUS_GUID"),
                }
            )
        )
        """
    )

    assert probe["qtpy"] is False
    assert probe["PySide6"] is False
    assert probe["shiboken6"] is False
    assert probe["width"] == 2
    assert probe["height"] == 3
    assert probe["fileurl"] == "image.png"
    assert probe["guid_text"] == probe["guid"]


def test_qimage_like_payload_fails_cleanly_without_touching_qt():
    probe = _run_import_probe(
        """
        import json
        import sys

        from ansys.dynamicreporting.core.utils.report_objects import ItemREST

        QImage = type("QImage", (), {"__module__": "PySide6.QtGui"})
        item = ItemREST()

        try:
            item.set_payload_image(QImage())
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "qtpy": "qtpy" in sys.modules,
                        "PySide6": "PySide6" in sys.modules,
                        "shiboken6": "shiboken6" in sys.modules,
                        "exception_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
            )
        else:
            raise AssertionError("Expected QImage-like payload to fail without Qt support.")
        """
    )

    assert probe == {
        "qtpy": False,
        "PySide6": False,
        "shiboken6": False,
        "exception_type": "TypeError",
        "message": "QImage payloads require Qt image support to be available.",
    }


def test_copy_items_runtime_stays_headless_with_progress_qt_enabled():
    probe = _run_import_probe(
        """
        import json
        import sys

        from ansys.dynamicreporting.core.utils import report_objects
        from ansys.dynamicreporting.core.utils.report_remote_server import Server

        class FakeSource:
            def __init__(self):
                self.dataset = report_objects.DatasetREST()
                self.session = report_objects.SessionREST()
                self.item = report_objects.ItemREST()
                self.item.dataset = self.dataset.guid
                self.item.session = self.session.guid

            def get_objects(self, objtype=None, query=None):
                return [self.item]

            def get_object_from_guid(self, guid, objtype=None):
                if objtype is report_objects.DatasetREST and guid == self.dataset.guid:
                    return self.dataset
                if objtype is report_objects.SessionREST and guid == self.session.guid:
                    return self.session
                return None

        class FakeProgress:
            def __init__(self):
                self.labels = []

            def setLabelText(self, text):
                self.labels.append(text)

            def setMaximum(self, value):
                pass

            def setValue(self, value):
                pass

            def wasCanceled(self):
                return False

        server = Server()
        server.put_objects = lambda objects: 200
        progress = FakeProgress()
        success = server.copy_items(FakeSource(), obj_type="item", progress=progress, progress_qt=True)

        print(
            json.dumps(
                {
                    "qtpy": "qtpy" in sys.modules,
                    "PySide6": "PySide6" in sys.modules,
                    "shiboken6": "shiboken6" in sys.modules,
                    "success": success,
                    "labels": progress.labels,
                }
            )
        )
        """
    )

    assert probe == {
        "qtpy": False,
        "PySide6": False,
        "shiboken6": False,
        "success": True,
        "labels": ["Scanning datasets...", "Scanning sessions...", "Importing: item"],
    }


def test_export_report_as_pdf_runtime_stays_headless_even_with_parent():
    probe = _run_import_probe(
        """
        import json
        import sys

        from ansys.dynamicreporting.core.utils import report_remote_server
        from ansys.dynamicreporting.core.utils.report_remote_server import Server

        captured = {}

        def fake_run_nexus_utility(cmd, use_software_gl=False, exec_basis=None, ansys_version=None):
            captured["cmd"] = cmd
            captured["use_software_gl"] = use_software_gl
            captured["exec_basis"] = exec_basis
            captured["ansys_version"] = ansys_version

        report_remote_server.run_nexus_utility = fake_run_nexus_utility

        server = Server(url="http://example.com")
        server.build_url_with_query = lambda report_guid, query, item_filter=None: (
            "http://example.com/reports/report_display/?view=test-guid&print=pdf"
        )

        server.export_report_as_pdf("test-guid", "out.pdf", parent=object())

        print(
            json.dumps(
                {
                    "qtpy": "qtpy" in sys.modules,
                    "PySide6": "PySide6" in sys.modules,
                    "shiboken6": "shiboken6" in sys.modules,
                    "cmd": captured["cmd"],
                    "use_software_gl": captured["use_software_gl"],
                }
            )
        )
        """
    )

    assert probe["qtpy"] is False
    assert probe["PySide6"] is False
    assert probe["shiboken6"] is False
    assert probe["cmd"][0] == "report_save_pdf"
    assert probe["cmd"][1].startswith("b64:")
    assert probe["cmd"][2].endswith("out.pdf")
    assert probe["use_software_gl"] is True
