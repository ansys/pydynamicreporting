import pytest

from ansys.dynamicreporting.core.common_utils import validate_html_dictionary


class TestValidateHTMLDictionary:
    """Test suite for validate_html_dictionary and validate_html_list functions."""

    def test_valid_string(self):
        """Test that valid strings pass validation."""
        data = {"field1": "This is plain text", "field2": "Another valid string"}
        validate_html_dictionary(data)  # Should not raise

    def test_valid_nested_dict(self):
        """Test that valid nested dictionaries pass validation."""
        data = {
            "outer": {
                "inner": "plain text",
                "another": "more text"
            }
        }
        validate_html_dictionary(data)  # Should not raise

    def test_valid_list(self):
        """Test that valid lists pass validation."""
        data = {
            "list_field": ["item1", "item2", "item3"]
        }
        validate_html_dictionary(data)  # Should not raise

    def test_html_key_is_exempt(self):
        """Test that HTML key is exempt from validation."""
        data = {
            "HTML": "<div>This is HTML</div>",
            "other": "plain text"
        }
        validate_html_dictionary(data)  # Should not raise

    def test_properties_exempt_keys(self):
        """Test that exempt keys in properties are not validated."""
        data = {
            "properties": {
                "title": "<div>This is HTML</div>",  # title is in PROPERTIES_EXEMPT
                "link_text": "<span>Link</span>",  # link_text is in PROPERTIES_EXEMPT
            }
        }
        validate_html_dictionary(data)  # Should not raise

    def test_invalid_html_in_string(self):
        """Test that HTML content in string raises ValueError with field name and value."""
        data = {"field1": "<div>Bold text</div>"}
        with pytest.raises(ValueError) as exc_info:
            validate_html_dictionary(data)
        assert "field1 contains HTML content." in str(exc_info.value)
        assert "<div>Bold text</div>" in str(exc_info.value)

    def test_invalid_html_in_nested_dict(self):
        """Test that HTML content in nested dict raises ValueError with field name and value."""
        data = {
            "outer": {
                "inner_field": "<script>alert('xss')</script>"
            }
        }
        with pytest.raises(ValueError) as exc_info:
            validate_html_dictionary(data)
        assert "inner_field contains HTML content." in str(exc_info.value)
        assert "<script>alert('xss')</script>" in str(exc_info.value)

    def test_invalid_html_in_list(self):
        """Test that HTML content in list raises ValueError with field name and value."""
        data = {
            "list_field": ["plain", "<div>html</div>", "text"]
        }
        with pytest.raises(ValueError) as exc_info:
            validate_html_dictionary(data)
        assert "list_field contains HTML content." in str(exc_info.value)
        assert "<div>html</div>" in str(exc_info.value)

    def test_invalid_html_in_nested_list(self):
        """Test that HTML content in nested list raises ValueError with field name and value."""
        data = {
            "outer_list": [["plain"], ["<p>paragraph</p>"]]
        }
        with pytest.raises(ValueError) as exc_info:
            validate_html_dictionary(data)
        assert "outer_list contains HTML content." in str(exc_info.value)
        assert "<p>paragraph</p>" in str(exc_info.value)

    def test_invalid_html_in_dict_within_list(self):
        """Test that HTML content in dict within list raises ValueError with field name and value."""
        data = {
            "list_of_dicts": [
                {"field": "plain"},
                {"field": "<span>html</span>"}
            ]
        }
        with pytest.raises(ValueError) as exc_info:
            validate_html_dictionary(data)
        assert "field contains HTML content." in str(exc_info.value)
        assert "<span>html</span>" in str(exc_info.value)

    def test_non_exempt_properties_validated(self):
        """Test that non-exempt keys in properties are validated and include value."""
        data = {
            "properties": {
                "title": "plain text",  # exempt
                "custom_field": "<div>html</div>"  # not exempt, should fail
            }
        }
        with pytest.raises(ValueError) as exc_info:
            validate_html_dictionary(data)
        assert "custom_field contains HTML content." in str(exc_info.value)
        assert "<div>html</div>" in str(exc_info.value)

    def test_mixed_types(self):
        """Test that mixed types are handled correctly."""
        data = {
            "string": "plain text",
            "number": 42,
            "boolean": True,
            "none": None,
            "dict": {"nested": "text"},
            "list": ["item1", "item2"]
        }
        validate_html_dictionary(data)  # Should not raise
