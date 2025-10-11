"""Custom exceptions for the extraction module."""


class ExtractionError(Exception):
    """Base exception for extraction-related errors."""
    pass


class ArticleExtractionError(ExtractionError):
    """Raised when article extraction fails validation."""

    def __init__(self, site: str, expected: int, actual: int, message: str = None):
        """
        Initialize ArticleExtractionError.

        Args:
            site: The site that failed extraction
            expected: Expected number of articles
            actual: Actual number of articles extracted
            message: Optional custom error message
        """
        self.site = site
        self.expected = expected
        self.actual = actual
        default_msg = f"Site {site} extracted {actual}/{expected} articles"
        super().__init__(message or default_msg)


class JSONParsingError(ExtractionError):
    """Raised when LLM returns invalid or unparseable JSON."""

    def __init__(self, raw_response: str, parse_error: str):
        """
        Initialize JSONParsingError.

        Args:
            raw_response: The raw LLM response that failed to parse
            parse_error: The parsing error message
        """
        self.raw_response = raw_response
        self.parse_error = parse_error
        super().__init__(f"JSON parsing failed: {parse_error}")
