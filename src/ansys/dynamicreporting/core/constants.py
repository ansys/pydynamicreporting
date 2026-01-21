DOCKER_REPO_URL = "ghcr.io/ansys-internal/nexus"
DOCKER_DEV_REPO_URL = "ghcr.io/ansys-internal/nexus_dev"
DOCKER_DEFAULT_PORT = 8000

LAYOUT_TYPES = (
    "Layout:basic",
    "Layout:panel",
    "Layout:box",
    "Layout:tabs",
    "Layout:carousel",
    "Layout:slider",
    "Layout:footer",
    "Layout:header",
    "Layout:iterator",
    "Layout:tagprops",
    "Layout:toc",
    "Layout:reportlink",
    "Layout:userdefined",
    "Layout:datafilter",
    "Layout:pptx",
    "Layout:pptxslide",
)

GENERATOR_TYPES = (
    "Generator:tablemerge",
    "Generator:tablereduce",
    "Generator:tablemap",
    "Generator:tablerowcolumnfilter",
    "Generator:tablevaluefilter",
    "Generator:tablesortfilter",
    "Generator:sqlquery",
    "Generator:treemerge",
    "Generator:itemscomparison",
    "Generator:statistical",
    # "Generator:iterator",
)

REPORT_TYPES = LAYOUT_TYPES + GENERATOR_TYPES

JSON_ATTR_KEYS = ("name", "report_type", "tags", "item_filter")
JSON_NECESSARY_KEYS = ("name", "report_type", "parent", "children")
JSON_UNNECESSARY_KEYS = ("tags", "params", "sort_selection", "item_filter")
JSON_TEMPLATE_KEYS = JSON_NECESSARY_KEYS + JSON_UNNECESSARY_KEYS
