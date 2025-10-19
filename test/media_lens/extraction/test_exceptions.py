import pytest

from src.media_lens.extraction.exceptions import (
    ArticleExtractionError,
    ExtractionError,
    JSONParsingError,
)


def test_extraction_error_base_class():
    """Test that ExtractionError is a proper base exception class."""
    error = ExtractionError("Base error message")

    # Verify it's an Exception
    assert isinstance(error, Exception)
    assert str(error) == "Base error message"


def test_extraction_error_inheritance():
    """Test that all custom exceptions inherit from ExtractionError."""
    article_error = ArticleExtractionError("www.cnn.com", 5, 2)
    json_error = JSONParsingError("invalid json", "parse error")

    # Both should inherit from ExtractionError
    assert isinstance(article_error, ExtractionError)
    assert isinstance(json_error, ExtractionError)

    # And from Exception
    assert isinstance(article_error, Exception)
    assert isinstance(json_error, Exception)


def test_article_extraction_error_creation():
    """Test ArticleExtractionError creation with all parameters."""
    error = ArticleExtractionError(site="www.cnn.com", expected=5, actual=2)

    # Verify attributes
    assert error.site == "www.cnn.com"
    assert error.expected == 5
    assert error.actual == 2


def test_article_extraction_error_default_message():
    """Test ArticleExtractionError default message format."""
    error = ArticleExtractionError(site="www.bbc.com", expected=5, actual=3)

    # Verify default message format
    error_msg = str(error)
    assert "www.bbc.com" in error_msg
    assert "3/5" in error_msg
    assert "extracted" in error_msg


def test_article_extraction_error_custom_message():
    """Test ArticleExtractionError with custom message."""
    custom_msg = "Custom validation error occurred"
    error = ArticleExtractionError(site="www.foxnews.com", expected=5, actual=1, message=custom_msg)

    # Verify custom message is used
    assert str(error) == custom_msg

    # Attributes should still be set
    assert error.site == "www.foxnews.com"
    assert error.expected == 5
    assert error.actual == 1


def test_article_extraction_error_multiple_sites():
    """Test ArticleExtractionError for multiple sites."""
    error = ArticleExtractionError(
        site="multiple",
        expected=5,
        actual=0,
        message="Extraction validation failed: www.cnn.com extracted 2/5 articles; www.bbc.com extracted 1/5 articles",
    )

    # Verify multiple site handling
    assert error.site == "multiple"
    error_msg = str(error)
    assert "www.cnn.com" in error_msg
    assert "www.bbc.com" in error_msg


def test_article_extraction_error_zero_articles():
    """Test ArticleExtractionError when no articles extracted."""
    error = ArticleExtractionError(site="www.cnn.com", expected=5, actual=0)

    # Verify zero handling
    assert error.actual == 0
    assert "0/5" in str(error)


def test_article_extraction_error_boundary_cases():
    """Test ArticleExtractionError with boundary values."""
    # Exactly one less than minimum
    error1 = ArticleExtractionError("www.cnn.com", 5, 4)
    assert "4/5" in str(error1)

    # Very large numbers
    error2 = ArticleExtractionError("www.bbc.com", 100, 50)
    assert "50/100" in str(error2)

    # Negative (edge case, shouldn't happen but test anyway)
    error3 = ArticleExtractionError("www.foxnews.com", 5, -1)
    assert error3.actual == -1


def test_json_parsing_error_creation():
    """Test JSONParsingError creation with all parameters."""
    raw_response = '{"stories": [{"title": "News 1"} invalid json'
    parse_error = "Expecting ',' delimiter: line 1 column 35 (char 34)"

    error = JSONParsingError(raw_response, parse_error)

    # Verify attributes
    assert error.raw_response == raw_response
    assert error.parse_error == parse_error


def test_json_parsing_error_message():
    """Test JSONParsingError message format."""
    raw_response = '{"invalid": json}'
    parse_error = "Expecting value: line 1 column 13 (char 12)"

    error = JSONParsingError(raw_response, parse_error)

    # Verify message includes parse error
    error_msg = str(error)
    assert "JSON parsing failed" in error_msg
    assert parse_error in error_msg


def test_json_parsing_error_with_long_response():
    """Test JSONParsingError with long raw response."""
    # Create a very long response
    raw_response = '{"stories": [' + ('{"title": "News"},') * 100 + "]}"
    parse_error = "Trailing comma error"

    error = JSONParsingError(raw_response, parse_error)

    # Verify attributes store full response
    assert error.raw_response == raw_response
    assert len(error.raw_response) > 1000


def test_json_parsing_error_with_empty_response():
    """Test JSONParsingError with empty response."""
    raw_response = ""
    parse_error = "Expecting value: line 1 column 1 (char 0)"

    error = JSONParsingError(raw_response, parse_error)

    # Verify empty response is handled
    assert error.raw_response == ""
    assert "JSON parsing failed" in str(error)


def test_json_parsing_error_with_schema_wrapper():
    """Test JSONParsingError with JSON Schema wrapper format."""
    raw_response = (
        '{"properties": {"stories": [{"title": "News 1"}]}, "additionalProperties": false}'
    )
    parse_error = "Extra data after JSON object"

    error = JSONParsingError(raw_response, parse_error)

    # Verify schema format is captured
    assert "properties" in error.raw_response
    assert error.parse_error == parse_error


def test_exception_catching_by_base_class():
    """Test that all custom exceptions can be caught using ExtractionError."""
    errors = [
        ArticleExtractionError("www.cnn.com", 5, 2),
        JSONParsingError("invalid", "parse error"),
    ]

    # All should be catchable with ExtractionError
    for error in errors:
        try:
            raise error
        except ExtractionError as e:
            # Should catch the error
            assert isinstance(e, ExtractionError)


def test_exception_raising_and_catching():
    """Test raising and catching custom exceptions."""
    # Test ArticleExtractionError
    with pytest.raises(ArticleExtractionError) as exc_info:
        raise ArticleExtractionError("www.cnn.com", 5, 3)

    assert exc_info.value.site == "www.cnn.com"
    assert exc_info.value.expected == 5
    assert exc_info.value.actual == 3

    # Test JSONParsingError
    with pytest.raises(JSONParsingError) as exc_info:
        raise JSONParsingError("bad json", "parse error")

    assert exc_info.value.raw_response == "bad json"
    assert exc_info.value.parse_error == "parse error"


def test_exception_string_representation():
    """Test string representation of custom exceptions."""
    # ArticleExtractionError
    article_error = ArticleExtractionError("www.bbc.com", 5, 2)
    assert "www.bbc.com" in str(article_error)
    assert "2/5" in str(article_error)
    assert repr(article_error)  # Should have repr

    # JSONParsingError
    json_error = JSONParsingError("invalid", "error message")
    assert "JSON parsing failed" in str(json_error)
    assert "error message" in str(json_error)
    assert repr(json_error)  # Should have repr


def test_exception_equality():
    """Test exception equality (for testing purposes)."""
    error1 = ArticleExtractionError("www.cnn.com", 5, 2)
    error2 = ArticleExtractionError("www.cnn.com", 5, 2)

    # Exceptions are not equal by default (different instances)
    assert error1 is not error2

    # But they have the same attributes
    assert error1.site == error2.site
    assert error1.expected == error2.expected
    assert error1.actual == error2.actual
