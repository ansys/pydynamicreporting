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

from types import SimpleNamespace
from unittest.mock import Mock


def test_item_visualization_renders_display_ready_iframe(monkeypatch):
    from ansys.dynamicreporting.core.serverless import item as item_module
    from ansys.dynamicreporting.core.serverless.item import Item, ItemType

    request = object()
    render = Mock(return_value='<p title="quoted">A &amp; B</p>')
    item = SimpleNamespace(type=ItemType.SCENE, render=render)

    iframe = Item.get_iframe(item, context={"plotly": 1}, request=request)

    render.assert_called_once_with(context={"plotly": 1}, request=request)
    assert 'width="1000" height="800"' in iframe
    assert 'srcdoc="&lt;p title=&quot;quoted&quot;&gt;A &amp;amp; B&lt;/p&gt;"' in iframe
    assert 'sandbox="allow-downloads allow-forms allow-modals allow-popups allow-scripts"' in iframe
    assert iframe._repr_html_() == str(iframe)

    item.get_iframe = Mock(return_value=iframe)
    display_iframe = Mock()
    monkeypatch.setattr(item_module, "_display_iframe", display_iframe)

    assert Item.visualize(item, width=640, height=480) is None
    item.get_iframe.assert_called_once_with(width=640, height=480, context=None, request=None)
    display_iframe.assert_called_once_with(iframe)


def test_report_visualization_forwards_render_options(monkeypatch):
    from ansys.dynamicreporting.core.serverless import template as template_module
    from ansys.dynamicreporting.core.serverless.template import Template

    request = object()
    render = Mock(return_value="<main>Report</main>")
    report = SimpleNamespace(render=render)

    iframe = Template.get_iframe(
        report,
        width=720,
        height=540,
        context={"plotly": 1},
        item_filter="A|i_name|cont|result;",
        embed_scene_data=True,
        request=request,
    )

    render.assert_called_once_with(
        context={"plotly": 1},
        item_filter="A|i_name|cont|result;",
        embed_scene_data=True,
        request=request,
    )
    assert 'width="720" height="540"' in iframe
    assert 'srcdoc="&lt;main&gt;Report&lt;/main&gt;"' in iframe

    report.get_iframe = Mock(return_value=iframe)
    display_iframe = Mock()
    monkeypatch.setattr(template_module, "_display_iframe", display_iframe)

    assert Template.visualize(report, item_filter="A|i_tags|cont|section=summary;") is None
    report.get_iframe.assert_called_once_with(
        width=1000,
        height=800,
        context=None,
        item_filter="A|i_tags|cont|section=summary;",
        embed_scene_data=False,
        request=None,
    )
    display_iframe.assert_called_once_with(iframe)
