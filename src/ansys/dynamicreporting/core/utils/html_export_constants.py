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
    "website/scripts/mathjax/jax/input/TeX/config.js",
    "website/scripts/mathjax/jax/input/MathML/config.js",
    "website/scripts/mathjax/jax/input/AsciiMath/config.js",
    "website/scripts/mathjax/extensions/tex2jax.js",
    "website/scripts/mathjax/extensions/mml2jax.js",
    "website/scripts/mathjax/extensions/asciimath2jax.js",
    "website/scripts/mathjax/extensions/MathZoom.js",
    "website/scripts/mathjax/extensions/MathMenu.js",
    "website/scripts/mathjax/extensions/MathEvents.js",
    "website/scripts/mathjax/jax/element/mml/jax.js",
    "website/scripts/mathjax/jax/input/TeX/jax.js",
    "website/scripts/mathjax/extensions/TeX/AMSmath.js",
    "website/scripts/mathjax/extensions/TeX/AMSsymbols.js",
    "website/scripts/mathjax/extensions/TeX/noErrors.js",
    "website/scripts/mathjax/extensions/TeX/noUndefined.js",
    "website/scripts/mathjax/config/TeX-AMS-MML_SVG.js",
    "website/scripts/mathjax/jax/output/SVG/jax.js",
    "website/scripts/mathjax/jax/output/SVG/fonts/TeX/fontdata.js",
    "website/scripts/mathjax/jax/output/SVG/fonts/TeX/Main/Regular/BasicLatin.js",
    "website/scripts/mathjax/jax/output/SVG/fonts/TeX/Size1/Regular/Main.js",
    "website/images/MenuArrow-15.png",
    "website/scripts/mathjax/MathJax.js",
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
