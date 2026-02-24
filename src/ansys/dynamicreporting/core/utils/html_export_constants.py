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

# This file centralizes constants and file lists used by both the server-based
# and serverless HTML export implementations to avoid code duplication.

from .. import DEFAULT_ANSYS_VERSION as CURRENT_VERSION

# Default Ansys version to use as a fallback.
ANSYS_VERSION_FALLBACK = CURRENT_VERSION

# -----------------------
# Site-level assets
# -----------------------

# CSS/JS normally served from static/website/content or scripts
SITE_ASSETS = [
    # CSS
    "content/fontawesome.min.css",
    "content/solid.min.css",
    "content/bootstrap-slider.min.css",
    "content/bootstrap.min.css",
    "content/bootstrap-select.min.css",
    "content/bootstrap-tagsinput.css",
    "content/bootstrap-callout.css",
    "content/datatables.min.css",
    "content/jquery.loading.min.css",
    "content/noty.min.css",
    "content/site.css",
    "content/dark-site.css",
    "content/adr-web-components.css",
    # JS
    "scripts/jquery.min.js",
    "scripts/datatables.min.js",
    "scripts/bootstrap-tagsinput.js",
    "scripts/plotly.min.js",
    "scripts/geotiff.js",
    "scripts/geotiff_nexus.js",
]

# Favicon
FAVICON = "website/images/favicon.ico"

# -----------------------
# MathJax assets
# -----------------------
MATHJAX_FILES = [
    "website/scripts/mathjax/core.js",
    "website/scripts/mathjax/loader.js",
    "website/scripts/mathjax/startup.js",
    "website/scripts/mathjax/tex-mml-chtml.js", # important: top-level loader
    "website/scripts/mathjax/LICENSE",
    "website/scripts/mathjax/a11y/assistive-mml.js",
    "website/scripts/mathjax/a11y/complexity.js",
    "website/scripts/mathjax/a11y/explorer.js",
    "website/scripts/mathjax/a11y/semantic-enrich.js",
    "website/scripts/mathjax/a11y/speech.js",
    "website/scripts/mathjax/a11y/sre.js",
    "website/scripts/mathjax/input/mml/entities.js",
    "website/scripts/mathjax/input/mml/extensions/mml3.js",
    "website/scripts/mathjax/input/mml/extensions/mml3.sef.json",
    "website/scripts/mathjax/input/tex/extensions/ams.js",
    "website/scripts/mathjax/input/tex/extensions/noerrors.js",
    "website/scripts/mathjax/input/tex/extensions/noundefined.js",
    "website/scripts/mathjax/output/chtml.js",
    "website/scripts/mathjax/output/svg.js",
    "website/scripts/mathjax/sre/mathmaps/af.json",
    "website/scripts/mathjax/sre/mathmaps/base.json",
    "website/scripts/mathjax/sre/mathmaps/ca.json",
    "website/scripts/mathjax/sre/mathmaps/da.json",
    "website/scripts/mathjax/sre/mathmaps/de.json",
    "website/scripts/mathjax/sre/mathmaps/en.json",
    "website/scripts/mathjax/sre/mathmaps/es.json",
    "website/scripts/mathjax/sre/mathmaps/euro.json",
    "website/scripts/mathjax/sre/mathmaps/fr.json",
    "website/scripts/mathjax/sre/mathmaps/hi.json",
    "website/scripts/mathjax/sre/mathmaps/it.json",
    "website/scripts/mathjax/sre/mathmaps/ko.json",
    "website/scripts/mathjax/sre/mathmaps/nb.json",
    "website/scripts/mathjax/sre/mathmaps/nemeth.json",
    "website/scripts/mathjax/sre/mathmaps/nn.json",
    "website/scripts/mathjax/sre/mathmaps/sv.json",
    "website/scripts/mathjax/sre/speech-worker.js",
    "website/scripts/mathjax/ui/lazy.js",
    "website/scripts/mathjax/ui/menu.js",
    "website/scripts/mathjax/ui/no-dark-mode.js",
    "website/scripts/mathjax/ui/safe.js"
]

# -----------------------
# Viewer-related assets
# -----------------------

# Image files for the general Nexus UI.
NEXUS_IMAGES = ["menu_20_gray.png", "menu_20_white.png", "nexus_front_page.png", "nexus_logo.png"]

# Image files for the older WebGL viewer.
VIEWER_IMAGES_OLD = [
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

# JavaScript utility files for the modern viewer.
VIEWER_UTILS = ["js-inflate.js", "js-unzip.js", "jquery.min.js"]

# Core JavaScript files for the modern viewer.
VIEWER_JS = ["ANSYSViewer_min.js", "viewer-loader.js"]

# Files for the context menu used in the viewer.
CONTEXT_MENU_JS = [
    "jquery.contextMenu.min.css",
    "jquery.contextMenu.min.js",
    "jquery.ui.position.min.js",
]

# Core Three.js library files.
THREE_JS = [
    "ArcballControls.js",
    "DRACOLoader.js",
    "GLTFLoader.js",
    "OrbitControls.js",
    "OBJLoader.js",
    "three.js",
    "VRButton.js",
]

# Draco library files for 3D model compression.
DRACO_JS = [
    "draco_decoder.js",
    "draco_decoder.wasm",
    "draco_encoder.js",
    "draco_wasm_wrapper.js",
]

# Font files for icons.
FONTS = [
    "fa-solid-900.eot",
    "fa-solid-900.svg",
    "fa-solid-900.ttf",
    "fa-solid-900.woff",
    "fa-solid-900.woff2",
]
