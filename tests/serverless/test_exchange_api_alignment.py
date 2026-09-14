from ansys.dynamicreporting.core.utils.exchange import ExchangeImporter, ItemType, TemplateType


def test_exchange_api_exports_expected_names():
    assert ExchangeImporter is not None
    assert ItemType.TEXT.value == "text"
    assert TemplateType.BASIC.value == "basic"
