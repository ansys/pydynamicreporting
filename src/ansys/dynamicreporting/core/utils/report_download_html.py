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

import base64
import os
import os.path
import re
import urllib.parse

import requests

from ..compatibility import DEFAULT_STATIC_ASSET_VERSION as CURRENT_VERSION
from .html_export_constants import (
    MATHJAX_2X_FILES,
    MATHJAX_4X_FILES,
    MATHJAX_OPTIONAL_FILES,
    MATHJAX_VERSION_SENTINELS,
)
from .html_export_mathjax import detect_mathjax_version_from_html

# Default Ansys version to use as a fallback.
# Direct ``ReportDownloadHTML`` callers may not have a service object handy, so
# preserve the historical bundled-product asset namespace until a concrete
# server version is supplied.
ANSYS_VERSION_FALLBACK = CURRENT_VERSION


class ReportDownloadHTML:
    def __init__(
        self,
        url=None,
        directory=None,
        debug=False,
        filename="index.html",
        no_inline_files=False,
        ansys_version=None,
    ):
        # Make sure that the print query has been specified.  Set it to html if not set
        if url:
            parsed = urllib.parse.urlparse(url)
            query = parsed.query
            if "print=" not in query:
                if query:
                    query += "&print=html"
                else:
                    query = "print=html"
                parsed._replace(query=query)
                url = urllib.parse.urlunparse(parsed)
        self._ansys_version = str(ANSYS_VERSION_FALLBACK)
        if ansys_version:
            self._ansys_version = str(ansys_version)
            if int(self._ansys_version) < 242:
                self._ansys_version = ""
        self._url = url
        self._directory = directory
        self._filename = filename
        self._debug = debug
        self._replaced_file_ext = None
        # for each downloaded file, the new "url" to be injected into the re-worked HTML
        self._filemap = dict()
        # Normally we inline content to make it display stand-alone.  If the user requests
        # it, we can download the files instead and the user would need to serve up the
        # local files or work around CORS issues in other ways.
        self._no_inline = no_inline_files
        # Some downloaded filenames come up repeatedly (e.g. prxoy.png).  When we see that
        # the base name has already been used, we prefix with {self._collision_count}_ to
        # make it unique.
        self._collision_count = 0
        # Here we keep track of the size of the embedded data uris in the output.  If
        # the size of the uris exceeds a threshold, we will display some entities using
        # different visuals so that they do not result in excessively large HTML files.
        self._total_data_uri_size = 0
        self._max_inline_size = 1024 * 1024 * 500  # 500MB
        self._inline_size_exception = False  # record this so we can get it externally
        # Cache the rendered report HTML and resolved MathJax version for this
        # downloader instance.  One export should use one stable answer, so
        # repeating the same detection work only adds network I/O.
        self._report_html: str | None = None
        self._mathjax_version: str | None = None

    def _should_use_data_uri(self, size: int) -> bool:
        self._inline_size_exception = False
        if self._no_inline:
            # this is not an exception case, we are simply not allowed to use data uris here
            return False
        if self._total_data_uri_size + size > self._max_inline_size:
            self._inline_size_exception = True
            return False
        self._total_data_uri_size += size
        return True

    def download(self, url: str | None = None, directory: str | None = None) -> None:
        if url is not None:
            self._url = url
        if directory is not None:
            self._directory = directory
        self._download()

    def _replace_files(self, text: str, inline: bool = False, size_check: bool = False) -> str:
        # track the filename extension for the last replacement
        self._replaced_file_ext = None
        # we might have multiple replacements
        current = 0
        while True:
            try:
                idx1 = text.index(f"/static/ansys{self._ansys_version}/", current)
            except ValueError:
                try:
                    idx1 = text.index("/static/", current)
                except ValueError:
                    try:
                        idx1 = text.index("/media/", current)
                    except ValueError:
                        try:
                            idx1 = text.index(f"/ansys{self._ansys_version}/", current)
                        except ValueError:
                            return text
            quote = text[idx1 - 1]
            try:
                idx2 = text.index(quote, idx1)
            except ValueError:
                return text
            path = text[idx1:idx2]
            # We may have a path that includes queries (e.g. /media/filename.png?query...)
            # We need the query for the purposes of the GET operation to download the item,
            # but once saved to disk, we need to drop the query portion of the path.
            # 'simple_path' is the stripped down filename (used in the cache).
            simple_path = path
            if "?" in path:
                tmp = path.index("?")
                simple_path = path[:tmp]
            # Capture the last replaced filename extension.  Needed for the inline situation.
            (_, ext) = os.path.splitext(simple_path)
            self._replaced_file_ext = ext
            # get the actual new file
            new_path = self._get_file(path, simple_path, inline=inline)
            # if we had size checking enabled replacement resulted in a sizing exception,
            # we need to substitute a tag that can be replaced later.
            if size_check and self._inline_size_exception:
                new_path = "__SIZE_EXCEPTION__"
            text = text[:idx1] + new_path + text[idx2:]
            current = idx1 + len(new_path)

    def _download_special_files(self):
        # The remote path resolves the page's MathJax version before downloads
        # begin, so only the matching asset tree needs to be fetched.  Avoiding
        # the other tree keeps the export quiet and removes unnecessary GETs.
        mathjax_version = self._detect_mathjax_version()
        if mathjax_version == "4":
            self._download_mathjax_files(MATHJAX_4X_FILES, silent=False)
        elif mathjax_version == "2":
            self._download_mathjax_files(MATHJAX_2X_FILES, silent=False)
        else:
            # Unknown installs still get a best-effort pass across both trees,
            # but missing files stay silent because neither set is authoritative.
            self._download_mathjax_files(MATHJAX_4X_FILES + MATHJAX_2X_FILES, silent=True)

        # Additional files to be mapped to the media directory
        images = ["menu_20_gray.png", "menu_20_white.png", "nexus_front_page.png", "nexus_logo.png"]
        self._download_static_files(images, "/static/website/images/", "media", "nexus images")

        # The old Ansys Nexus WebGL viewer
        images = [
            "ANSYS_blk_lrg.png",
            "ANSYS_icon.png",
            "ANSYS_wht_lrg.png",
            "back.png",
            "close.png",
            "closed.png",
            "favicon.png",
            "Icons.png",
            "open.png",
            "Point.cur",
        ]
        self._download_static_files(images, "/static/website/images/", "media", "viewer images I")

        # The new Ansys Nexus WebGL viewer
        images = [
            "ANSYS_blk_lrg.png",
            "ANSYS_icon.png",
            "ANSYS_wht_lrg.png",
            "back.png",
            "close.png",
            "closed.png",
            "favicon.png",
            "Icons.png",
            "open.png",
            "Point.cur",
            "proxy_viewer.png",
            "play.png",
        ]
        self._download_static_files(
            images,
            f"/ansys{self._ansys_version}/nexus/images/",
            f"ansys{self._ansys_version}/nexus/images/",
            "viewer images II",
        )
        images = ["js-inflate.js", "js-unzip.js", "jquery.min.js"]
        self._download_static_files(
            images,
            f"/ansys{self._ansys_version}/nexus/utils/",
            f"ansys{self._ansys_version}/nexus/utils/",
            "viewer javascript support",
        )
        images = ["ANSYSViewer_min.js", "viewer-loader.js"]
        self._download_static_files(
            images,
            f"/ansys{self._ansys_version}/nexus/",
            f"ansys{self._ansys_version}/nexus/",
            "ansys-nexus-viewer js",
        )
        images = [
            "jquery.contextMenu.min.css",
            "jquery.contextMenu.min.js",
            "jquery.ui.position.min.js",
        ]
        self._download_static_files(
            images,
            f"/ansys{self._ansys_version}/nexus/novnc/vendor/jQuery-contextMenu/",
            f"ansys{self._ansys_version}/nexus/novnc/vendor/jQuery-contextMenu",
            "ansys-nexus-viewer vnc js",
        )

        image = [
            "ArcballControls.js",
            "DRACOLoader.js",
            "GLTFLoader.js",
            "OrbitControls.js",
            "OBJLoader.js",
            "three.js",
            "VRButton.js",
        ]
        self._download_static_files(
            image,
            f"/ansys{self._ansys_version}/nexus/threejs/",
            f"ansys{self._ansys_version}/nexus/threejs",
            "threejs core",
        )

        image = [
            "draco_decoder.js",
            "draco_decoder.wasm",
            "draco_encoder.js",
            "draco_wasm_wrapper.js",
        ]
        self._download_static_files(
            image,
            f"/ansys{self._ansys_version}/nexus/threejs/libs/draco/",
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco",
            "threejs draco",
        )
        self._download_static_files(
            image,
            f"/ansys{self._ansys_version}/nexus/threejs/libs/draco/gltf/",
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/gltf",
            "threejs draco gltf",
        )

        # Fonts
        fonts = [
            "fa-solid-900.eot",
            "fa-solid-900.svg",
            "fa-solid-900.ttf",
            "fa-solid-900.woff",
            "fa-solid-900.woff2",
        ]
        self._download_static_files(fonts, "/static/website/webfonts/", "webfonts", "fonts")

    @staticmethod
    def fix_viewer_component_paths(filename, data, ansys_version):
        # Special case for AVZ viewer: ANSYSViewer_min.js to set the base path for images
        if filename.endswith("ANSYSViewer_min.js"):
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                data = data.decode("latin-1")
            data = data.replace(
                '"/static/website/images/"',
                r'document.URL.replace(/\\/g, "/").replace("index.html", "media/")',
            )
            data = data.replace(
                f'"/ansys{ansys_version}/nexus/images/', f'"./ansys{ansys_version}//nexus/images/'
            )
            # this one is interesting.  by default, AVZ will throw an error if you attempt to read
            # a "file://" protocol src.  In offline mode, if we are not using data URIs, then we
            # need to lie to the AVZ core and tell it to go ahead and try.
            data = data.replace('"FILE",delegate', '"arraybuffer",delegate')
            data = data.encode("utf-8")
        # Special case for the AVZ viewer web component (loading proxy images and play arrow)
        elif filename.endswith("viewer-loader.js"):
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                data = data.decode("latin-1")
            data = data.replace(
                f'"/ansys{ansys_version}/nexus/images/', f'"./ansys{ansys_version}//nexus/images/'
            )
            data = data.encode("utf-8")
        return data

    @staticmethod
    def _mathjax_media_path(source_rel_path: str) -> str:
        """Map a static MathJax asset path to the exported ``media/`` layout.

        ADR serves MathJax assets from ``website/scripts/mathjax/...``.  The
        offline export keeps only the path segment below ``mathjax/`` and moves
        it under ``media/`` so existing HTML references stay portable.
        """
        relative_path = source_rel_path.split("mathjax/", 1)[1]
        return os.path.join("media", relative_path)

    @staticmethod
    def _write_binary_file(filename: str, data: bytes) -> None:
        """Write a binary payload after ensuring its parent directory exists.

        Several download paths save files under nested directories that may only
        exist for one MathJax major version.  Centralizing the write keeps the
        file-handle handling deterministic and avoids duplicating mkdir logic.
        """
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wb") as file_handle:
            file_handle.write(data)

    def _download_mathjax_files(self, files: tuple[str, ...], *, silent: bool) -> None:
        """Download one MathJax asset set into the offline export tree.

        Parameters
        ----------
        files : tuple[str, ...]
            Static asset paths rooted at ``website/scripts/mathjax``.
        silent : bool
            When ``True``, missing files are ignored because version detection
            failed and neither asset tree can be treated as authoritative.
        """
        tmp = urllib.parse.urlsplit(self._url)
        mathjax_root_url = tmp.scheme + "://" + tmp.netloc + "/static/"

        for source_rel_path in files:
            url = mathjax_root_url + source_rel_path
            resp = requests.get(url, allow_redirects=True)  # nosec B400
            if resp.status_code == requests.codes.ok:
                filename = os.path.join(self._directory, self._mathjax_media_path(source_rel_path))
                try:
                    self._write_binary_file(filename, resp.content)
                except OSError as e:
                    print(f"Unable to download MathJax file: {source_rel_path}\nError {e}")
            elif not (silent or source_rel_path in MATHJAX_OPTIONAL_FILES):
                print(f"Unable to get: {url}")

    def _download_static_files(self, files, source_path, target_path, comment):
        tmp = urllib.parse.urlsplit(self._url)
        for f in files:
            url = tmp.scheme + "://" + tmp.netloc + source_path + f
            resp = requests.get(url, allow_redirects=True)  # nosec B400
            if resp.status_code == requests.codes.ok:
                filename = self._directory + os.sep + target_path + os.sep + f
                filename = os.path.normpath(filename)
                try:
                    data = self.fix_viewer_component_paths(
                        str(filename), resp.content, self._ansys_version
                    )
                    self._write_binary_file(filename, data)
                except Exception as e:
                    print(f"Unable to download {comment}: {f}\nError: {e}")

    def _make_unique_basename(self, name: str) -> str:
        # check to see if the filename has already been used (and hence we are headed toward
        # a naming collision).  If so, use a unique prefix for such files.
        pathname = os.path.join(self._directory, "media", name)
        if not os.path.exists(pathname):
            return name
        self._collision_count += 1
        return f"{str(self._collision_count)}_{name}"

    @staticmethod
    def is_scene_file(name: str) -> bool:
        if name.upper().endswith(".AVZ"):
            return True
        if name.upper().endswith(".SCDOC"):
            return True
        if name.upper().endswith(".SCDOCX"):
            return True
        if name.upper().endswith(".GLB"):
            return True
        return False

    def _get_file(self, path_plus_queries: str, pathname: str, inline: bool = False) -> str:
        if pathname in self._filemap:
            return self._filemap[pathname]
        tmp = urllib.parse.urlsplit(self._url)
        url = tmp.scheme + "://" + tmp.netloc + path_plus_queries
        resp = requests.get(url, allow_redirects=True)  # nosec B400
        results = pathname
        if resp.status_code == requests.codes.ok:
            basename = os.path.basename(pathname)
            # "basename" is used in the media directory, avoid collisions.
            basename = self._make_unique_basename(basename)
            try:
                tmp = resp.content
                # 4/3 is roughly the expansion factor of base64 encoding (3bytes encode to 4)
                # Note: we will also inline any "scene" 3D file.  This can happen when processing
                # a slider view "key_image" array.
                if (inline or self.is_scene_file(pathname)) and self._should_use_data_uri(
                    len(tmp) * (4.0 / 3.0)
                ):
                    # convert to inline data domain URI. Prefix:  'data:application/octet-stream;base64,'
                    results = "data:application/octet-stream;base64," + base64.b64encode(
                        tmp
                    ).decode("utf-8")
                    # for in the field debugging, allow for the data uri sources to be saved
                    if "NEXUS_REPORT_DOWNLOAD_SAVE_DATAURI_SOURCE" in os.environ:
                        filename = os.path.join(self._directory, "media", basename)
                        self._write_binary_file(filename, tmp)
                else:
                    # Special case for Babylon js viewer.  We get here via this link...
                    # <script src="/media/b4bb7a9e-aa4d-11e9-a8ef-44850048bb82_scene/scene.js"></script>
                    # The downloaded file may have binary loader references like this:
                    # load_binary_block('/media/b4bb7a9e-aa4d-11e9-a8ef-44850048bb82_scene/p0_t0_b4_m0.bin', mesh0);
                    if basename.endswith("scene.js"):
                        tmp = tmp.decode("utf-8")
                        tmp = self._replace_blocks(
                            tmp, "load_binary_block(", ");", inline=True
                        ).encode("utf-8")
                        # we need to prefix the .bin file and scene.js file with the GUID
                        basename = f"{os.path.basename(os.path.dirname(pathname))}_{basename}"
                    else:
                        tmp = self.fix_viewer_component_paths(basename, tmp, self._ansys_version)
                    # get the output filename
                    if pathname.startswith(f"/static/ansys{self._ansys_version}/"):
                        # if the content is part of the /ansys/ namespace, we keep the namespace,
                        # but remove the /static prefix
                        local_pathname = os.path.dirname(pathname).replace("/static/", "./")
                        results = f"{local_pathname}/{basename}"
                    else:
                        results = f"./media/{basename}"
                    filename = os.path.join(self._directory, "media", basename)
                    self._write_binary_file(filename, tmp)
            except Exception as e:
                print(f"Unable to write downloaded file: {basename}\nError: {str(e)}")
        else:
            print(f"Unable to read file via URL: {url}")
        self._filemap[pathname] = results
        return self._filemap[pathname]

    @staticmethod
    def find_block(text: str, start: int, prefix: str, suffix: str) -> tuple[int, int, str]:
        """
        Finds a block of text between a prefix and a suffix that contains a valid asset path.

        This method searches for a substring that starts with 'prefix', ends with 'suffix',
        and contains a reference to '/media/', '/static/', or a versioned ansys path
        like '/ansys242/'.

        Args:
            text: The string to search within.
            start: The starting index for the search.
            prefix: The string that marks the beginning of the block.
            suffix: The string that marks the end of the block.

        Returns:
            A tuple containing the start index, end index, and the found block text.
            If no block is found, it returns (-1, -1, "").
        """
        while True:
            try:
                idx1 = text.index(prefix, start)
            except ValueError:
                return -1, -1, ""
            try:
                idx2 = text.index(suffix, idx1 + len(prefix))
            except ValueError:
                return -1, -1, ""
            idx2 += len(suffix)
            block = text[idx1:idx2]
            if (
                ("/media/" in block)
                or ("/static/" in block)
                or (re.match(r"/ansys([0-9]+)", block))
            ):
                return idx1, idx2, text[idx1:idx2]
            start = idx2

    def _replace_blocks(
        self, html: str, prefix: str, suffix: str, inline: bool = False, size_check: bool = False
    ) -> str:
        # track the filename extension for the last replacement
        self._replaced_file_ext = None
        # walk all the matching blocks
        current_pos = 0
        while True:
            start, end, text = self.find_block(html, current_pos, prefix, suffix)
            if start < 0:
                break
            text = self._replace_files(text, inline=inline, size_check=size_check)
            html = html[:start] + text + html[end:]
            current_pos = start + len(text)
        return html

    def _inline_ansys_viewer(self, html: str) -> str:
        #  AVZ component interface
        # <ansys-nexus-viewer proxy_img="/media/ca0845e2-1edd-11ec-8c57-381428170733_scene/proxy.png" active=false
        # ... aspect_ratio="proxy" src="/media/ca0845e2-1edd-11ec-8c57-381428170733_scene/scene.avz"
        # ... id="avz_comp_042395948b40418b81a48f2ffbb7fa2a"></ansys-nexus-viewer>
        current_pos = 0
        while True:
            start, end, text = self.find_block(
                html, current_pos, "<ansys-nexus-viewer", "</ansys-nexus-viewer>"
            )
            if start < 0:
                break
            text = self._replace_blocks(text, 'proxy_img="', '"', inline=True)
            text = self._replace_blocks(text, 'src="', '"', inline=True, size_check=True)
            # handle any size check exception
            if "__SIZE_EXCEPTION__" in text:
                # convert src="__SIZE_EXCEPTION__" to: src="" proxy_only="Hover text"
                msg = "3D geometry too large for stand-alone HTML file"
                text = text.replace("__SIZE_EXCEPTION__", f'" proxy_only="{msg}')
            # if the src was replaced with a data URI, we need to inject the src_ext attribute so
            # that the component knows what the source file format is.
            if self._replaced_file_ext:
                ext = self._replaced_file_ext.replace(".", "").upper()
                text = text.replace("<ansys-nexus-viewer", f'<ansys-nexus-viewer src_ext="{ext}"')
            html = html[:start] + text + html[end:]
            current_pos = start + len(text)
        return html

    @staticmethod
    def _make_dir(subdirs):
        base = None
        for d in subdirs:
            if base is None:
                base = d
            else:
                base = os.path.join(base, d)
            if os.path.exists(base) and os.path.isfile(base):
                raise OSError(f"Directory specified, {base}, is actually an existing file")
            if not os.path.exists(base):
                try:
                    os.makedirs(base, exist_ok=True)
                except Exception as e:
                    raise OSError(f"Unable to create target directory: {base}\nError: {str(e)}")

    def _detect_mathjax_version_from_installation(self) -> str:
        """Probe the ADR server for MathJax when page HTML is inconclusive.

        Checks for the presence of each version's top-level sentinel file:

        * MathJax 4.x: ``/static/website/scripts/mathjax/tex-mml-chtml.js``
        * MathJax 2.x: ``/static/website/scripts/mathjax/MathJax.js``

        Returns
        -------
        str
            ``"4"`` when MathJax 4.x is detected, ``"2"`` when MathJax 2.x is
            detected, or ``"unknown"`` when neither sentinel file is reachable.

        Notes
        -----
        Redirects stay disabled for these sentinel probes. Authentication gates
        and other middleware commonly redirect missing/forbidden asset requests
        to an HTML login page that still returns ``200`` after the redirect
        chain. Treating only the direct HEAD response as authoritative avoids
        false-positive version detection in those deployments.
        """
        tmp = urllib.parse.urlsplit(self._url)
        base = tmp.scheme + "://" + tmp.netloc + "/static/website/scripts/mathjax/"
        for version, sentinel in MATHJAX_VERSION_SENTINELS:
            try:
                resp = requests.head(base + sentinel, allow_redirects=False)  # nosec B400
                if resp.status_code == requests.codes.ok:
                    return version
            except (requests.ConnectionError, requests.Timeout, requests.RequestException):
                # Server unreachable or request failed — skip this sentinel and
                # try the next one.  If all fail, fall through to "unknown".
                continue
        return "unknown"

    def _detect_mathjax_version(self) -> str:
        """Resolve the MathJax major version for the current export.

        The rendered report HTML is the best source of truth because it names
        the loader the page actually references.  If that HTML does not expose
        a recognizable MathJax loader, fall back to the installation probe so
        older report templates and unusual deployments still export cleanly.
        """
        if self._mathjax_version is not None:
            return self._mathjax_version

        if self._report_html is not None:
            html_version = detect_mathjax_version_from_html(self._report_html)
            if html_version != "unknown":
                self._mathjax_version = html_version
                return self._mathjax_version

        self._mathjax_version = self._detect_mathjax_version_from_installation()
        return self._mathjax_version

    def _make_output_dirs(self, mathjax_version: str) -> None:
        """Create the offline export directory tree for one MathJax version.

        Parameters
        ----------
        mathjax_version : str
            Resolved MathJax major version.  ``"4"`` and ``"2"`` create only
            the matching version-specific tree; ``"unknown"`` keeps only the
            common export directories so the later best-effort download pass can
            still write files without leaving dead empty version folders.
        """
        # media/ must always exist - both special-file downloads and rewritten
        # report assets write into it regardless of the MathJax version.
        self._make_dir([self._directory, "media"])

        if mathjax_version == "4":
            self._make_dir([self._directory, "media", "a11y"])
            self._make_dir([self._directory, "media", "input", "mml", "extensions"])
            self._make_dir([self._directory, "media", "input", "tex", "extensions"])
            self._make_dir([self._directory, "media", "output"])
            self._make_dir([self._directory, "media", "sre", "mathmaps"])
            self._make_dir([self._directory, "media", "ui"])
        elif mathjax_version == "2":
            self._make_dir([self._directory, "media", "config"])
            self._make_dir([self._directory, "media", "extensions", "TeX"])
            self._make_dir(
                [
                    self._directory,
                    "media",
                    "jax",
                    "output",
                    "SVG",
                    "fonts",
                    "TeX",
                    "Main",
                    "Regular",
                ]
            )
            self._make_dir(
                [
                    self._directory,
                    "media",
                    "jax",
                    "output",
                    "SVG",
                    "fonts",
                    "TeX",
                    "Size1",
                    "Regular",
                ]
            )
            self._make_dir([self._directory, "media", "jax", "element", "mml"])
            self._make_dir([self._directory, "media", "jax", "input", "TeX"])
            self._make_dir([self._directory, "media", "jax", "input", "MathML"])
            self._make_dir([self._directory, "media", "jax", "input", "AsciiMath"])
            self._make_dir([self._directory, "media", "images"])

        self._make_dir([self._directory, "webfonts"])
        self._make_dir([self._directory, f"ansys{self._ansys_version}", "nexus", "images"])
        self._make_dir([self._directory, f"ansys{self._ansys_version}", "nexus", "utils"])
        self._make_dir(
            [
                self._directory,
                f"ansys{self._ansys_version}",
                "nexus",
                "threejs",
                "libs",
                "draco",
                "gltf",
            ]
        )
        self._make_dir(
            [
                self._directory,
                f"ansys{self._ansys_version}",
                "nexus",
                "novnc",
                "vendor",
                "jQuery-contextMenu",
            ]
        )

    def _download(self):
        self._filemap = dict()
        self._report_html = None
        self._mathjax_version = None
        if self._url is None:
            raise ValueError("No URL specified")
        if self._directory is None:
            raise ValueError("No directory specified")

        # Make sure we are not writing into a Nexus database directory (which has a media
        # directory).  We do not check for a "media" directory as that breaks the use case of
        # exporting repeatedly into the same root directory.
        if os.path.isfile(os.path.join(self._directory, "db.sqlite3")):
            raise ValueError("Cannot export into a Nexus database directory")

        # media/ must always exist — _download_special_files() and _get_file() write into it.
        # Read the rendered report first so MathJax detection can follow the
        # loader the page actually uses instead of guessing from installation
        # layout alone.
        resp = requests.get(self._url)  # nosec B400
        if resp.status_code != requests.codes.ok:
            raise RuntimeError(f"Unable to access {self._url} ({resp.status_code})")
        self._report_html = resp.text

        # Decide the MathJax tree after reading the report HTML so the export
        # follows the loader the page actually references.
        mathjax_version = self._detect_mathjax_version()
        self._make_output_dirs(mathjax_version)
        # debugging...
        if self._debug:
            with open(os.path.join(self._directory, "index.raw"), "wb") as f:
                f.write(self._report_html.encode("utf8"))

        # some files that hide out under some .js
        self._download_special_files()

        # Currently, converting the following snippets:
        # core css
        # <link rel="stylesheet" type="text/css" href="/static/website/content/datatables.min.css" />
        # core scripts (and Babylon js loader)
        # <script src="/static/website/scripts/datatables.min.js"></script>
        # file links
        # <a href="/media/1629297d-2614-11e7-a1c6-109add666335_file.evsn">EnVision File</a>
        # images
        # <img src="/media/7d6838fe-f28d-11e8-a5aa-1c1b0da59167_image.png" class="img-responsive"
        # ... style="margin: 0 auto; display:flex; justify-content:center;"  alt="Image file not found">
        # in viewer-loader.js - this is handled in a special way
        # <img class="ansys-nexus-play" id="proxy-play" src="/ansys###/nexus/images/play.png">
        # video
        # <source src="/media/4a87c6c0-f34b-11e8-871b-1c1b0da59167_movie.mp4" type="video/mp4" />
        # slider template
        # "slider_loader_1162.key_images = {"
        # ['/media/8fa34470-f349-11e8-ae8c-1c1b0da59167_image.png',],
        # "slider_loader_1162.update();"
        #  AVZ viewer
        # <script>
        #  var viewer_bb97d5297dc44d77a4a43c92ee60197a = new GLTFViewer('avz_viewer_bb97d5297dc44d77a4a43c92ee60197a','/media/1782c99a-22b2-11ea-977f-6c2b599f031b_scene.avz','AVZ');
        # </script>
        # Deep pixels handlers
        # async function tiff_image_6ad0cc989c414473a4823bf42b2c4d92_loader() {
        #    const response = await fetch("./media/435491e8-f099-11ea-81f3-28f10e13ffe6_image.tif");
        #    const arrayBuffer = await response.arrayBuffer();
        #    const tiff_promise_6ad0cc989c414473a4823bf42b2c4d92 = GeoTIFF.fromArrayBuffer(arrayBuffer);
        #    tiff_promise_6ad0cc989c414473a4823bf42b2c4d92.then( nexus_image_load_tiff_image.bind(null, "nexus_image_6ad0cc989c414473a4823bf42b2c4d92"), nexus_image_general_error);
        # }

        html = self._report_html
        html = self._replace_blocks(html, "<link", "/>")
        html = self._replace_blocks(html, "<img id='guiicon", ">")
        html = self._replace_blocks(html, "e.src = '", "';")
        html = self._replace_blocks(html, "<script src=", "</script>")
        html = self._replace_blocks(html, "<a href=", ">")
        html = self._replace_blocks(html, "<img src=", ">")
        html = self._replace_blocks(html, "<source src=", ">")
        html = self._replace_blocks(html, ".key_images = {", ".update();")
        html = self._replace_blocks(html, "GLTFViewer", ");", inline=True)
        html = self._inline_ansys_viewer(html)
        html = self._replace_blocks(html, "await fetch(", ");", inline=True)

        # save the results
        with open(os.path.join(self._directory, self._filename), "wb") as f:
            f.write(html.encode("utf8"))
