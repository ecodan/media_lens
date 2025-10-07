import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.media_lens.collection.scraper import WebpageScraper


@pytest.mark.asyncio
async def test_get_page_content_desktop():
    """Test scraping with desktop browser configuration."""
    with patch('src.media_lens.collection.scraper.async_playwright') as mock_playwright:
        # Set up mock context
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_browser = AsyncMock()

        # Create a proper async mock for async_playwright()
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.stop = AsyncMock()

        # Mock the async_playwright() call chain
        mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.is_connected = MagicMock(return_value=True)
        mock_browser.close = AsyncMock()

        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_page.content = AsyncMock(return_value="<html><body>Test Content</body></html>")
        mock_page.goto = AsyncMock()
        mock_page.set_extra_http_headers = AsyncMock()
        mock_page.is_closed = MagicMock(return_value=False)
        mock_page.close = AsyncMock()

        # Call function with desktop browser type
        with patch('src.media_lens.collection.scraper.stealth_async', new_callable=AsyncMock):
            result = await WebpageScraper.get_page_content(
                "https://example.com",
                WebpageScraper.BrowserType.DESKTOP
            )

        # Check results
        assert result == "<html><body>Test Content</body></html>"

        # Verify desktop configuration was used
        mock_browser.new_context.assert_called_once()
        context_args = mock_browser.new_context.call_args[1]
        assert context_args['viewport']['width'] == 1920
        assert 'Windows' in context_args['user_agent']
        assert 'is_mobile' not in context_args


@pytest.mark.asyncio
async def test_get_page_content_mobile():
    """Test scraping with mobile browser configuration."""
    with patch('src.media_lens.collection.scraper.async_playwright') as mock_playwright:
        # Set up mock context
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_browser = AsyncMock()

        # Create a proper async mock for async_playwright()
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.stop = AsyncMock()

        # Mock the async_playwright() call chain
        mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.is_connected = MagicMock(return_value=True)
        mock_browser.close = AsyncMock()

        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_page.content = AsyncMock(return_value="<html><body>Mobile Test Content</body></html>")
        mock_page.goto = AsyncMock()
        mock_page.set_extra_http_headers = AsyncMock()
        mock_page.is_closed = MagicMock(return_value=False)
        mock_page.close = AsyncMock()

        # Call function with mobile browser type
        with patch('src.media_lens.collection.scraper.stealth_async', new_callable=AsyncMock):
            result = await WebpageScraper.get_page_content(
                "https://example.com",
                WebpageScraper.BrowserType.MOBILE
            )

        # Check results
        assert result == "<html><body>Mobile Test Content</body></html>"

        # Verify mobile configuration was used
        mock_browser.new_context.assert_called_once()
        context_args = mock_browser.new_context.call_args[1]
        assert context_args['viewport']['width'] == 375
        assert 'iPhone' in context_args['user_agent']
        assert context_args['is_mobile'] is True
        assert context_args['has_touch'] is True


@pytest.mark.asyncio
async def test_get_page_content_error_handling():
    """Test error handling during page scraping."""
    with patch('src.media_lens.collection.scraper.async_playwright') as mock_playwright:
        # Make the browser.new_context raise an exception
        mock_browser = AsyncMock()

        # Create a proper async mock for async_playwright()
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.stop = AsyncMock()

        # Mock the async_playwright() call chain
        mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

        mock_browser.new_context = AsyncMock(side_effect=Exception("Network error"))
        mock_browser.is_connected = MagicMock(return_value=True)
        mock_browser.close = AsyncMock()

        # The function catches exceptions and returns None
        with patch('src.media_lens.collection.scraper.stealth_async', new_callable=AsyncMock):
            result = await WebpageScraper.get_page_content(
                "https://example.com",
                WebpageScraper.BrowserType.DESKTOP
            )

        # Verify that the error was caught and None was returned
        assert result is None


@pytest.mark.asyncio
async def test_unknown_browser_type():
    """Test handling of invalid browser type."""
    with patch('src.media_lens.collection.scraper.async_playwright') as mock_playwright:
        # Create an invalid browser type
        invalid_browser_type = MagicMock()

        # Create a proper async mock for async_playwright()
        mock_browser = AsyncMock()
        mock_pw_instance = AsyncMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw_instance.stop = AsyncMock()

        # Mock the async_playwright() call chain
        mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)

        mock_browser.is_connected = MagicMock(return_value=True)
        mock_browser.close = AsyncMock()

        # The function catches exceptions and returns None
        with patch('src.media_lens.collection.scraper.stealth_async', new_callable=AsyncMock):
            result = await WebpageScraper.get_page_content(
                "https://example.com",
                invalid_browser_type
            )

        # Verify that the error was caught and None was returned
        assert result is None