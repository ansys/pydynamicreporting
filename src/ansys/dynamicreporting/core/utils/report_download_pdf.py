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

from functools import partial
import os

try:
    from qtpy import QtWebEngineWidgets
    from qtpy.QtCore import QFile, QFileInfo, QIODevice, QMarginsF, QSizeF, QTimer, QUrl
    from qtpy.QtGui import QPageLayout, QPageSize

    BaseQWebEnginePage = getattr(QtWebEngineWidgets, "QWebEnginePage", object)
    QWebEngineView = getattr(QtWebEngineWidgets, "QWebEngineView")

    # Classes for saving PDF representation
    # pagedef = {width}X{height}X{0=port|1=land}X{left}X{right}X{top}X{bottom} all in mm

    has_qt = hasattr(QtWebEngineWidgets, "QWebEnginePage") and hasattr(
        QtWebEngineWidgets, "QWebEngineView"
    )
except Exception:
    BaseQWebEnginePage = object
    has_qt = False


if has_qt:  # pragma: no cover

    class NexusPDFPage(BaseQWebEnginePage):
        def __init__(self):
            super().__init__()

        def javaScriptConsoleMessage(self, level, message, line_number, source_id):
            pass

    class NexusPDFSave:
        def __init__(self, app, parent=None):
            self._app = app
            self._parent = parent
            self._web_engine_view = None
            self._web_page = None
            self._html_dirname = None
            self._pdf_filename = None
            self._result = None
            self._page = [
                210,
                297,
                0,
                10,
                10,
                10,
                10,
            ]  # A4 page (210mmx297mm) in portrait with 10mm margins
            # print delay with a one-shot timer
            self._print_delay = int(
                os.environ.get("CEI_NEXUS_PDF_EXPORT_DELAY", "5000")
            )  # time(ms)
            self._print_timer = QTimer()
            self._print_timer.setSingleShot(True)

        def _wait_for_completion(self):
            # wait in the QtApplication loop until the operation is finished
            while self._result is None:
                self._app.processEvents()

        # Interface to the web engine/web page instances
        def webengine(self):
            if self._web_engine_view is None:
                screen = self._app.primaryScreen()
                dpi = screen.logicalDotsPerInch()
                in_per_mm = 0.0393701
                self._web_engine_view = QWebEngineView(self._parent)
                self._web_page = NexusPDFPage()
                self._web_engine_view.setPage(self._web_page)
                self._web_page.loadFinished.connect(self.load_finished)
                dx = self._page[0] * in_per_mm * dpi
                dy = self._page[1] * in_per_mm * dpi
                self._web_engine_view.resize(int(dx), int(dy))
            return self._web_engine_view

        def webpage(self):
            _ = self.webengine()
            return self._web_page

        # Callback whenever a load has completed
        def load_finished(self, ok):
            if ok:
                pagesize = QPageSize(
                    QSizeF(self._page[0], self._page[1]),
                    QPageSize.Millimeter,
                    "",
                    QPageSize.ExactMatch,
                )
                layout = QPageLayout.Portrait
                if self._page[2]:
                    layout = QPageLayout.Landscape
                margins = QMarginsF(self._page[3], self._page[4], self._page[5], self._page[6])
                page = QPageLayout(pagesize, layout, margins, QPageLayout.Millimeter)
                # print with a delay
                self._print_timer.timeout.connect(
                    partial(self.webpage().printToPdf, self.pdf_callback, page)
                )
                self._print_timer.start(self._print_delay)
            else:
                self._result = "failure"

        def save_page_pdf(self, url, filename, page=None, delay=None):
            self._pdf_filename = QFileInfo(filename)
            if len(self._pdf_filename.suffix()) < 1:
                self._pdf_filename.setFile(filename + ".pdf")
            if page is not None:
                self._page = page
            if isinstance(delay, int):
                self._print_delay = delay
            we = self.webengine()
            we.load(QUrl(url))
            self._wait_for_completion()
            return self._result

        def pdf_callback(self, data):
            # its a one-shot timer, this is not really required,
            # but we want to make sure it is dead once print is done.
            if self._print_timer.isActive():
                self._print_timer.stop()
            # finish the pdf save
            if self._pdf_filename is None:
                self._result = "failure"
                return
            f = QFile(self._pdf_filename.absoluteFilePath())
            if f.open(QIODevice.WriteOnly):
                f.write(data)
                f.close()
                self._result = "ok"
            else:
                self._result = "failure"
            self._pdf_filename = None
