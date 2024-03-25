"""
All constants go here.
"""

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
