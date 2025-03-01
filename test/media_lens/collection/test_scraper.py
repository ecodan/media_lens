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
        mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.content.return_value = "<html><body>Test Content</body></html>"
        
        # Call function with desktop browser type
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
        mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.content.return_value = "<html><body>Mobile Test Content</body></html>"
        
        # Call function with mobile browser type
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
        mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser
        mock_browser.new_context.side_effect = Exception("Network error")
        
        # Check that the exception is propagated
        with pytest.raises(Exception, match="Network error"):
            await WebpageScraper.get_page_content(
                "https://example.com", 
                WebpageScraper.BrowserType.DESKTOP
            )


@pytest.mark.asyncio
async def test_unknown_browser_type():
    """Test handling of invalid browser type."""
    # Create an invalid browser type
    invalid_browser_type = MagicMock()
    
    # Check that ValueError is raised
    with pytest.raises(ValueError, match="Unknown browser type"):
        await WebpageScraper.get_page_content(
            "https://example.com", 
            invalid_browser_type
        )