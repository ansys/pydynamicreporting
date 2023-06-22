import base64
import os
import os.path
from typing import Optional
import urllib.parse

import requests

# TODO:
#  Improve MathJax download


class ReportDownloadHTML:
    def __init__(
        self, url=None, directory=None, debug=False, filename="index.html", no_inline_files=False
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

    def download(self, url: Optional[str] = None, directory: Optional[str] = None) -> None:
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
                idx1 = text.index("/static/ansys/", current)
            except ValueError:
                try:
                    idx1 = text.index("/static/", current)
                except ValueError:
                    try:
                        idx1 = text.index("/media/", current)
                    except ValueError:
                        try:
                            idx1 = text.index("/ansys/", current)
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
        # MathJax
        files = [
            "media/jax/input/TeX/config.js",
            "media/jax/input/MathML/config.js",
            "media/jax/input/AsciiMath/config.js",
            "media/extensions/tex2jax.js",
            "media/extensions/mml2jax.js",
            "media/extensions/asciimath2jax.js",
            "media/extensions/MathZoom.js",
            "media/extensions/MathEvents.js",
            "media/extensions/MathMenu.js",
            "media/extensions/MathEvents.js",
            "media/jax/element/mml/jax.js",
            "media/jax/input/TeX/jax.js",
            "media/extensions/TeX/AMSmath.js",
            "media/extensions/TeX/AMSsymbols.js",
            "media/extensions/TeX/noErrors.js",
            "media/extensions/TeX/noUndefined.js",
            "media/config/TeX-AMS-MML_SVG.js",
            "media/jax/output/SVG/jax.js",
            "media/jax/output/SVG/fonts/TeX/fontdata.js",
            "media/jax/output/SVG/fonts/TeX/Main/Regular/BasicLatin.js",
            "media/jax/output/SVG/fonts/TeX/Size1/Regular/Main.js",
            "media/images/MenuArrow-15.png",
        ]

        tmp = urllib.parse.urlsplit(self._url)
        for f in files:
            mangled = f.replace("media/", "/static/website/scripts/mathjax/")
            url = tmp.scheme + "://" + tmp.netloc + mangled
            resp = requests.get(url, allow_redirects=True)
            if resp.status_code == requests.codes.ok:
                filename = os.path.join(self._directory, f)
                try:
                    open(filename, "wb").write(resp.content)
                except Exception:
                    print(f"Unable to download MathJax file: {f}")
            else:
                print(f"Unable to get: {url}")

        # Additional files to be mapped to the media directory
        images = ["menu_20_gray.png", "menu_20_white.png", "nexus_front_page.png", "nexus_logo.png"]
        self._download_static_files(images, "/static/website/images/", "media", "image")

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
        self._download_static_files(images, "/static/website/images/", "media", "viewer image")

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
            images, "/ansys/nexus/images/", "ansys/nexus/images/", "viewer image"
        )
        images = ["js-inflate.js", "js-unzip.js", "jquery.min.js"]
        self._download_static_files(
            images, "/ansys/nexus/utils/", "ansys/nexus/utils/", "viewer image"
        )
        images = ["ANSYSViewer_min.js", "viewer-loader.js"]
        self._download_static_files(images, "/ansys/nexus/", "ansys/nexus/", "viewer image")
        images = [
            "jquery.contextMenu.min.css",
            "jquery.contextMenu.min.js",
            "jquery.ui.position.min.js",
        ]
        self._download_static_files(
            images,
            "/ansys/nexus/novnc/vendor/jQuery-contextMenu/",
            "ansys/nexus/novnc/vendor/jQuery-contextMenu",
            "viewer image",
        )

        # Fonts
        fonts = [
            "fa-solid-900.eot",
            "fa-solid-900.svg",
            "fa-solid-900.ttf",
            "fa-solid-900.woff",
            "fa-solid-900.woff2",
        ]
        self._download_static_files(fonts, "/static/website/webfonts/", "webfonts", "font")

    @staticmethod
    def _fix_viewer_component_paths(filename, data):
        # Special case for AVZ viewer: ANSYSViewer_min.js to set the base path for images
        if filename.endswith("ANSYSViewer_min.js"):
            data = data.decode("utf-8")
            data = data.replace(
                '"/static/website/images/"',
                r'document.URL.replace(/\\/g, "/").replace("index.html", "media/")',
            )
            data = data.replace('"/ansys/nexus/images/', '"./ansys/nexus/images/')
            # this one is interesting.  by default, AVZ will throw an error if you attempt to read
            # a "file://" protocol src.  In offline mode, if we are not using data URIs, then we
            # need to lie to the AVZ core and tell it to go ahead and try.
            data = data.replace('"FILE",delegate', '"arraybuffer",delegate')
            data = data.encode("utf-8")
        # Special case for the AVZ viewer web component (loading proxy images and play arrow)
        elif filename.endswith("viewer-loader.js"):
            data = data.decode("utf-8")
            data = data.replace('"/ansys/nexus/images/', '"./ansys/nexus/images/')
            data = data.encode("utf-8")
        return data

    def _download_static_files(self, files, source_path, target_path, comment):
        tmp = urllib.parse.urlsplit(self._url)
        for f in files:
            url = tmp.scheme + "://" + tmp.netloc + source_path + f
            resp = requests.get(url, allow_redirects=True)
            if resp.status_code == requests.codes.ok:
                filename = os.path.join(self._directory, target_path, f)
                try:
                    data = self._fix_viewer_component_paths(filename, resp.content)
                    open(filename, "wb").write(data)
                except Exception:
                    print(f"Unable to download {comment}: {f}")

    def _make_unique_basename(self, name: str) -> str:
        # check to see if the filename has already been used (and hence we are headed toward
        # a naming collision).  If so, use a unique prefix for such files.
        pathname = os.path.join(self._directory, "media", name)
        if not os.path.exists(pathname):
            return name
        self._collision_count += 1
        return f"{str(self._collision_count)}_{name}"

    def _get_file(self, path_plus_queries: str, pathname: str, inline: bool = False) -> str:
        if pathname in self._filemap:
            return self._filemap[pathname]
        tmp = urllib.parse.urlsplit(self._url)
        url = tmp.scheme + "://" + tmp.netloc + path_plus_queries
        resp = requests.get(url, allow_redirects=True)
        results = pathname
        if resp.status_code == requests.codes.ok:
            basename = os.path.basename(pathname)
            # "basename" is used in the media directory, avoid collisions.
            basename = self._make_unique_basename(basename)
            try:
                tmp = resp.content
                # 4/3 is roughly the expansion factor of base64 encoding (3bytes encode to 4)
                if inline and self._should_use_data_uri(len(tmp) * (4.0 / 3.0)):
                    # convert to inline data domain URI. Prefix:  'data:application/octet-stream;base64,'
                    results = "data:application/octet-stream;base64," + base64.b64encode(
                        tmp
                    ).decode("utf-8")
                    # for in the field debugging, allow for the data uri sources to be saved
                    if "NEXUS_REPORT_DOWNLOAD_SAVE_DATAURI_SOURCE" in os.environ:
                        filename = os.path.join(self._directory, "media", basename)
                        open(filename, "wb").write(tmp)
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
                        tmp = self._fix_viewer_component_paths(basename, tmp)
                    # get the output filename
                    if pathname.startswith("/static/ansys/"):
                        # if the content is part of the /ansys/ namespace, we keep the namespace,
                        # but remove the /static prefix
                        local_pathname = os.path.dirname(pathname).replace("/static/", "./")
                        results = f"{local_pathname}/{basename}"
                    else:
                        results = f"./media/{basename}"
                    filename = os.path.join(self._directory, "media", basename)
                    open(filename, "wb").write(tmp)
            except Exception:
                print(f"Unable to write downloaded file: {basename}")
        else:
            print(f"Unable to read file via URL: {url}")
        self._filemap[pathname] = results
        return self._filemap[pathname]

    @staticmethod
    def _find_block(text: str, start: int, prefix: int, suffix: str) -> (int, int, str):
        # Note: the block must contain "/media/", "/ansys/" or "/static/" for it to be valid
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
            if ("/media/" in block) or ("/static/" in block) or ("/ansys/" in block):
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
            start, end, text = self._find_block(html, current_pos, prefix, suffix)
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
            start, end, text = self._find_block(
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
                except Exception:
                    raise OSError(f"Unable to create target directory: {base}")

    def _download(self):
        self._filemap = dict()
        if self._url is None:
            raise ValueError("No URL specified")
        if self._directory is None:
            raise ValueError("No directory specified")

        # Make sure we are not writing into a Nexus database directory (which has a media
        # directory).  We do not check for a "media" directory as that breaks the use case of
        # exporting repeatedly into the same root directory.
        if os.path.isfile(os.path.join(self._directory, "db.sqlite3")):
            raise ValueError("Cannot export into a Nexus database directory")

        self._make_dir([self._directory, "media", "config"])
        self._make_dir([self._directory, "media", "extensions", "TeX"])
        self._make_dir(
            [self._directory, "media", "jax", "output", "SVG", "fonts", "TeX", "Main", "Regular"]
        )
        self._make_dir(
            [self._directory, "media", "jax", "output", "SVG", "fonts", "TeX", "Size1", "Regular"]
        )
        self._make_dir([self._directory, "media", "jax", "element", "mml"])
        self._make_dir([self._directory, "media", "jax", "input", "TeX"])
        self._make_dir([self._directory, "media", "jax", "input", "MathML"])
        self._make_dir([self._directory, "media", "jax", "input", "AsciiMath"])
        self._make_dir([self._directory, "media", "images"])
        self._make_dir([self._directory, "webfonts"])
        self._make_dir([self._directory, "ansys", "nexus", "images"])
        self._make_dir([self._directory, "ansys", "nexus", "utils"])
        self._make_dir([self._directory, "ansys", "nexus", "novnc", "vendor", "jQuery-contextMenu"])

        # get the webpage html source
        resp = requests.get(self._url)
        if resp.status_code != requests.codes.ok:
            raise RuntimeError(f"Unable to access {self._url} ({resp.status_code})")
        # debugging...
        if self._debug:
            with open(os.path.join(self._directory, "index.raw"), "wb") as f:
                f.write(resp.text.encode("utf8"))

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
        # <img class="ansys-nexus-play" id="proxy-play" src="/ansys/nexus/images/play.png">
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

        html = resp.text
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
