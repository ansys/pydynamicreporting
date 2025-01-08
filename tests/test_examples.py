import pytest

import ansys.dynamicreporting.core.examples as examples


@pytest.mark.ado_test
def test_download_image(adr_service_create, request) -> None:
    filter_str = "A|i_type|cont|image"
    img_items = adr_service_create.query(query_type="Item", filter=filter_str)
    my_img = adr_service_create.create_item()
    my_img.item_image = examples.download_file("enthalpy_001.png", "input_data")
    new_img_items = adr_service_create.query(query_type="Item", filter=filter_str)
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
    img_items = adr_service_create.query(query_type="Item", filter=filter_str)
    my_img = adr_service_create.create_item()
    my_img.item_image = examples.download_file("enthalpy_001.png", "input_data", "new_dir")
    new_img_items = adr_service_create.query(query_type="Item", filter=filter_str)
    assert len(new_img_items) == (len(img_items) + 1)


@pytest.mark.ado_test
def test_url_validation() -> None:
    is_valid = examples.downloads.uri_validator("http://google.com")
    is_not_valid = examples.downloads.uri_validator("google.com")
    assert is_valid and (not is_not_valid)
