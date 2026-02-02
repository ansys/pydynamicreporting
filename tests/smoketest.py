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

# version
# ADR service core
from ansys.dynamicreporting.core import Item, Report, Service, __version__

# ADR serverless core
from ansys.dynamicreporting.core.serverless import (
    ADR,
    HTML,
    Animation,
    BasicLayout,
    BoxLayout,
    CarouselLayout,
    DataFilterLayout,
    Dataset,
    File,
    FooterLayout,
    HeaderLayout,
    Image,
)
from ansys.dynamicreporting.core.serverless import (
    ItemsComparisonGenerator,
    IteratorGenerator,
    IteratorLayout,
    PanelLayout,
    PPTXLayout,
    PPTXSlideLayout,
    ReportLinkLayout,
    Scene,
    Session,
    SliderLayout,
    SQLQueryGenerator,
    StatisticalGenerator,
    String,
    TabLayout,
    Table,
    TableMapGenerator,
    TableMergeGenerator,
    TableMergeRCFilterGenerator,
    TableMergeValueFilterGenerator,
    TableReduceGenerator,
    TableSortFilterGenerator,
    TagPropertyLayout,
    Template,
    TOCLayout,
    Tree,
    TreeMergeGenerator,
    UserDefinedLayout,
)
from ansys.dynamicreporting.core.serverless import Item as ServerlessItem

print(__version__)
