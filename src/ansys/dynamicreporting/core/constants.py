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

DOCKER_REPO_URL = "ghcr.io/ansys-internal/adr_dev"
DOCKER_DEV_REPO_URL = "ghcr.io/ansys-internal/adr_dev"
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
