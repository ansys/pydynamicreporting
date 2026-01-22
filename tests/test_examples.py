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

import pytest

import ansys.dynamicreporting.core.examples as examples


@pytest.mark.ado_test
def test_download_image(adr_service_create, request) -> None:
    filter_str = "A|i_type|cont|image"
    img_items = adr_service_create.query(query_type="Item", item_filter=filter_str)
    my_img = adr_service_create.create_item()
    my_img.item_image = examples.download_file("enthalpy_001.png", "input_data")
    new_img_items = adr_service_create.query(query_type="Item", item_filter=filter_str)
    assert len(new_img_items) == (len(img_items) + 1)


@pytest.mark.ado_test
def test_download_error(adr_service_create, request) -> None:
    my_img = adr_service_create.create_item()
    success = False
    try:
        my_img.item_image = examples.download_file("does_not_exist.png", "input_data")
    except examples.RemoteFileNotFoundError:
        success = True
    assert success


@pytest.mark.ado_test
def test_download_image_newdir(adr_service_create, request) -> None:
    filter_str = "A|i_type|cont|image"
    img_items = adr_service_create.query(query_type="Item", item_filter=filter_str)
    my_img = adr_service_create.create_item()
    my_img.item_image = examples.download_file("enthalpy_001.png", "input_data", "new_dir")
    new_img_items = adr_service_create.query(query_type="Item", item_filter=filter_str)
    assert len(new_img_items) == (len(img_items) + 1)


@pytest.mark.ado_test
def test_url_validation() -> None:
    is_valid = examples.downloads.uri_validator("http://google.com")
    is_not_valid = examples.downloads.uri_validator("google.com")
    assert is_valid and (not is_not_valid)
