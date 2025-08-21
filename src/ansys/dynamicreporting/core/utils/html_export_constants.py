# This file centralizes constants and file lists used by both the server-based
# and serverless HTML export implementations to avoid code duplication.

# Default Ansys version to use as a fallback.
ANSYS_VERSION_FALLBACK = "261"

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
