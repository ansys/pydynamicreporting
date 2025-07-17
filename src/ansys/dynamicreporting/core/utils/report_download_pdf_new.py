import os
import os.path
import urllib.parse

import requests

ANSYS_VERSION_FALLBACK = "242"


class ReportDownloadPDF:
    def __init__(
        self,
        url=None,
        debug=False,
        filename="index.pdf",
        ansys_version=None,
    ):
        # Make sure that the print query has been specified.  Set it to pdf if not set
        if url:
            parsed = urllib.parse.urlparse(url)
            query = parsed.query
            if "print=" not in query:
                if query:
                    query += "&print=pdf"
                else:
                    query = "print=pdf"
                parsed._replace(query=query)
                url = urllib.parse.urlunparse(parsed)
        self._ansys_version = str(ANSYS_VERSION_FALLBACK)
        if ansys_version:
            self._ansys_version = str(ansys_version)
            if int(self._ansys_version) < 242:
                self._ansys_version = ""
        self._url = url
        self._filename = filename
        self._debug = debug

    def download(self, url: str | None = None, directory: str | None = None) -> None:
        if url is not None:
            self._url = url
        if directory is not None:
            self._directory = directory
        self._download()

    def _download(self):
        self._filemap = dict()
        if self._url is None:
            raise ValueError("No URL specified")
        # get the webpage html source
        resp = requests.get(self._url)
        if resp.status_code != requests.codes.ok:
            raise RuntimeError(f"Unable to access {self._url} ({resp.status_code})")
        # debugging...
        if self._debug:
            with open(os.path.join(self._directory, "index.raw"), "wb") as f:
                f.write(resp.text.encode("utf8"))
        pdf = resp.text
        # save the results
        with open(self._filename, "wb") as f:
            f.write(pdf.encode("utf8"))
