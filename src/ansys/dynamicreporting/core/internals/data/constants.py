"""
All constants go here.
"""

# File extension map for uploaded files
# image, anim, string, html, table, scene, file, none, tree
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!WARNING!!!!!!!!!!!!!!!!!!!!!!!!!!
# Adding an extension here will enable support for that in file
# uploads throughout Nexus, so beware.
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!WARNING!!!!!!!!!!!!!!!!!!!!!!!!!!
FILE_EXT_MAP = [
    {"name": "Images", "type": "image", "ext": ["png", "jpg", "tif", "tiff"]},
    {"name": "Movies", "type": "anim", "ext": ["mp4"]},
    {"name": "Tables", "type": "table", "ext": ["csv"]},
    {"name": "Scenes", "type": "scene", "ext": ["stl", "ply", "csf", "avz", "scdoc"]},
    {"name": "Strings", "type": "string", "ext": ["txt"]},
    {"name": "HTML", "type": "html", "ext": ["htm", "html"]},
    # WARNING !! the 'file' item MUST ALWAYS be last !!
    {"name": "File", "type": "file", "ext": ["ens", "enc", "evsn"]},
]

# use positive lookahead to mimic atomic groups in order to match the
# entire string or nothing. Refer ITEM_CATEGORY_NAME_WARNING
# for allowed characters.
ITEM_CATEGORY_NAME_REGEX = r"^(?=((?:[\w\.\-]+[\/ ]?)+))\1$"
ITEM_CATEGORY_NAME_WARNING = "Allowed characters are a-z, A-Z, 0-9, '.', '_', '-'." \
                             " May contain an optional / or space in between."

# constant to store the list of supported encodings for file uploads.
# ascii is a subset of utf-8, so that's fine too. We also support utf-8 with BOM aka utf-8-sig
SUPPORTED_FILE_ENCODINGS = [
    "ascii",
    "utf-8",
    "utf-8-sig",
]

TEXT_FILE_TYPES = ["string", "html", "table"]

PICKLED_TYPES = ["string", "html", "table", "tree", "none"]

# batch size for bulk updates/creates
BULK_QUERY_BATCH_SIZE = 1000
# threshold above which bulk insertions will be activated.
BULK_QUERY_BATCH_THRESHOLD = 2000
