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

from types import MethodType, SimpleNamespace
from unittest.mock import Mock


def test_item_visualization_renders_display_ready_iframe(monkeypatch):
    from IPython import display as ipython_display

    from ansys.dynamicreporting.core.serverless.item import Item, ItemType

    request = object()
    render = Mock(return_value='<p title="quoted">A &amp; B</p>')
    item = SimpleNamespace(type=ItemType.SCENE, render=render)
    item.get_iframe = MethodType(Item.get_iframe, item)
    display = Mock()
    monkeypatch.setattr(ipython_display, "display", display)

    assert Item.visualize(item, context={"plotly": 1}, request=request) is None

    render.assert_called_once_with(context={"plotly": 1}, request=request)
    display.assert_called_once()
    iframe = display.call_args.args[0]
    assert 'width="1000" height="800"' in iframe
    assert 'srcdoc="&lt;p title=&quot;quoted&quot;&gt;A &amp;amp; B&lt;/p&gt;"' in iframe
    assert 'sandbox="allow-downloads allow-forms allow-modals allow-popups allow-scripts"' in iframe
    assert iframe._repr_html_() == str(iframe)


def test_report_visualization_forwards_render_options(monkeypatch):
    from IPython import display as ipython_display

    from ansys.dynamicreporting.core.serverless.template import Template

    request = object()
    render = Mock(return_value="<main>Report</main>")
    report = SimpleNamespace(render=render)
    report.get_iframe = MethodType(Template.get_iframe, report)
    display = Mock()
    monkeypatch.setattr(ipython_display, "display", display)

    assert (
        Template.visualize(
            report,
            width=720,
            height=540,
            context={"plotly": 1},
            item_filter="A|i_name|cont|result;",
            embed_scene_data=True,
            request=request,
        )
        is None
    )

    render.assert_called_once_with(
        context={"plotly": 1},
        item_filter="A|i_name|cont|result;",
        embed_scene_data=True,
        request=request,
    )
    display.assert_called_once()
    iframe = display.call_args.args[0]
    assert 'width="720" height="540"' in iframe
    assert 'srcdoc="&lt;main&gt;Report&lt;/main&gt;"' in iframe
