from unittest.mock import MagicMock, patch

import pytest

from src.media_lens.collection.harvester import Harvester


@pytest.mark.asyncio
async def test_clean_sites_memory_tracking():
    """Test that memory tracking works correctly during site cleaning."""
    # Mock storage adapter
    mock_storage = MagicMock()
    mock_storage.file_exists.return_value = True
    mock_storage.read_text.return_value = "<html><body>Test Content</body></html>"
    mock_storage.write_text = MagicMock()

    # Mock psutil to simulate memory changes
    mock_process = MagicMock()
    # First call (before cleaning): 500MB
    # Second call (after cleanup): 400MB
    mock_process.memory_info.return_value.rss = 500 * 1024 * 1024

    with patch("src.media_lens.collection.harvester.psutil.Process", return_value=mock_process):
        with patch("src.media_lens.collection.harvester.WebpageCleaner") as mock_cleaner_class:
            with patch(
                "src.media_lens.collection.harvester.cleaner_for_site"
            ) as mock_cleaner_for_site:
                # Setup cleaner mocks
                mock_cleaner_instance = MagicMock()
                mock_cleaner_instance.clean_html.return_value = "<html>Cleaned</html>"
                mock_cleaner_instance.filter_text_elements.return_value = "<html>Filtered</html>"
                mock_cleaner_class.return_value = mock_cleaner_instance
                mock_cleaner_for_site.return_value = MagicMock()

                # Simulate memory change: first call 500MB, second call 400MB
                mock_process.memory_info.side_effect = [
                    MagicMock(rss=500 * 1024 * 1024),  # Before cleaning
                    MagicMock(rss=400 * 1024 * 1024),  # After cleanup
                ]

                # Create harvester and run clean_sites
                harvester = Harvester()
                harvester.storage = mock_storage

                await harvester.clean_sites(
                    job_dir="jobs/2025/01/01/120000", sites=["www.example.com"]
                )

                # Verify storage operations
                mock_storage.file_exists.assert_called_once_with(
                    "jobs/2025/01/01/120000/www.example.com.html"
                )
                mock_storage.read_text.assert_called_once_with(
                    "jobs/2025/01/01/120000/www.example.com.html"
                )
                mock_storage.write_text.assert_called_once_with(
                    "jobs/2025/01/01/120000/www.example.com-clean.html",
                    "<html>Filtered</html>",
                    encoding="utf-8",
                )

                # Verify cleaning was called
                mock_cleaner_instance.clean_html.assert_called_once()
                mock_cleaner_instance.filter_text_elements.assert_called_once()

                # Verify memory info was called twice (before and after)
                assert mock_process.memory_info.call_count == 2


@pytest.mark.asyncio
async def test_clean_sites_multiple_sites():
    """Test cleaning multiple sites with memory tracking."""
    mock_storage = MagicMock()
    mock_storage.file_exists.return_value = True
    mock_storage.read_text.return_value = "<html><body>Test</body></html>"
    mock_storage.write_text = MagicMock()

    mock_process = MagicMock()
    # Simulate memory changes for 3 sites
    mock_process.memory_info.side_effect = [
        MagicMock(rss=500 * 1024 * 1024),  # Site 1 before
        MagicMock(rss=450 * 1024 * 1024),  # Site 1 after
        MagicMock(rss=450 * 1024 * 1024),  # Site 2 before
        MagicMock(rss=400 * 1024 * 1024),  # Site 2 after
        MagicMock(rss=400 * 1024 * 1024),  # Site 3 before
        MagicMock(rss=380 * 1024 * 1024),  # Site 3 after
    ]

    with patch("src.media_lens.collection.harvester.psutil.Process", return_value=mock_process):
        with patch("src.media_lens.collection.harvester.WebpageCleaner") as mock_cleaner_class:
            with patch(
                "src.media_lens.collection.harvester.cleaner_for_site"
            ) as mock_cleaner_for_site:
                mock_cleaner_instance = MagicMock()
                mock_cleaner_instance.clean_html.return_value = "<html>Clean</html>"
                mock_cleaner_instance.filter_text_elements.return_value = "<html>Filtered</html>"
                mock_cleaner_class.return_value = mock_cleaner_instance
                mock_cleaner_for_site.return_value = MagicMock()

                harvester = Harvester()
                harvester.storage = mock_storage

                sites = ["www.cnn.com", "www.bbc.com", "www.foxnews.com"]
                await harvester.clean_sites(job_dir="jobs/2025/01/01/120000", sites=sites)

                # Verify all sites were processed
                assert mock_storage.file_exists.call_count == 3
                assert mock_storage.read_text.call_count == 3
                assert mock_storage.write_text.call_count == 3

                # Verify memory tracking for all sites (2 calls per site = 6 total)
                assert mock_process.memory_info.call_count == 6


@pytest.mark.asyncio
async def test_clean_sites_missing_file():
    """Test handling of missing scraped content file."""
    mock_storage = MagicMock()
    mock_storage.file_exists.return_value = False

    mock_process = MagicMock()

    with patch("src.media_lens.collection.harvester.psutil.Process", return_value=mock_process):
        harvester = Harvester()
        harvester.storage = mock_storage

        await harvester.clean_sites(job_dir="jobs/2025/01/01/120000", sites=["www.missing.com"])

        # File doesn't exist, so should not call read_text or write_text
        mock_storage.read_text.assert_not_called()
        mock_storage.write_text.assert_not_called()

        # Memory tracking should not be called for missing files
        mock_process.memory_info.assert_not_called()


@pytest.mark.asyncio
async def test_clean_site_memory_cleanup():
    """Test that _clean_site properly cleans up memory."""
    mock_storage = MagicMock()
    mock_storage.write_text = MagicMock()

    with patch("src.media_lens.collection.harvester.WebpageCleaner") as mock_cleaner_class:
        with patch("src.media_lens.collection.harvester.cleaner_for_site") as mock_cleaner_for_site:
            mock_cleaner_instance = MagicMock()
            mock_cleaner_instance.clean_html.return_value = "<html>Cleaned</html>"
            mock_cleaner_instance.filter_text_elements.return_value = "<html>Filtered</html>"
            mock_cleaner_class.return_value = mock_cleaner_instance
            mock_cleaner_for_site.return_value = MagicMock()

            harvester = Harvester()
            harvester.storage = mock_storage

            content = "<html><body>Original Content</body></html>"

            await harvester._clean_site(
                directory_path="jobs/2025/01/01/120000", content=content, site="www.example.com"
            )

            # Verify cleaning occurred
            mock_cleaner_instance.clean_html.assert_called_once_with(content)
            mock_cleaner_instance.filter_text_elements.assert_called_once_with(
                "<html>Cleaned</html>"
            )

            # Verify write occurred
            mock_storage.write_text.assert_called_once_with(
                "jobs/2025/01/01/120000/www.example.com-clean.html",
                "<html>Filtered</html>",
                encoding="utf-8",
            )


@pytest.mark.asyncio
async def test_clean_sites_exception_handling():
    """Test that exceptions in cleaning one site don't stop processing others."""
    mock_storage = MagicMock()
    mock_storage.file_exists.return_value = True

    # First site will raise exception, second will succeed
    mock_storage.read_text.side_effect = [Exception("Read error"), "<html>Success</html>"]

    mock_process = MagicMock()
    mock_process.memory_info.side_effect = [
        MagicMock(rss=500 * 1024 * 1024),  # Site 1 before (will fail after this)
        MagicMock(rss=400 * 1024 * 1024),  # Site 2 before
        MagicMock(rss=350 * 1024 * 1024),  # Site 2 after
    ]

    with patch("src.media_lens.collection.harvester.psutil.Process", return_value=mock_process):
        with patch("src.media_lens.collection.harvester.WebpageCleaner") as mock_cleaner_class:
            with patch(
                "src.media_lens.collection.harvester.cleaner_for_site"
            ) as mock_cleaner_for_site:
                mock_cleaner_instance = MagicMock()
                mock_cleaner_instance.clean_html.return_value = "<html>Clean</html>"
                mock_cleaner_instance.filter_text_elements.return_value = "<html>Filtered</html>"
                mock_cleaner_class.return_value = mock_cleaner_instance
                mock_cleaner_for_site.return_value = MagicMock()

                harvester = Harvester()
                harvester.storage = mock_storage

                sites = ["www.error.com", "www.success.com"]
                await harvester.clean_sites(job_dir="jobs/2025/01/01/120000", sites=sites)

                # Both sites should be attempted
                assert mock_storage.file_exists.call_count == 2
                assert mock_storage.read_text.call_count == 2

                # Only the successful site should write
                assert mock_storage.write_text.call_count == 1

                # Memory tracking: 1 call for failed site (before only), 2 calls for successful site (before+after) = 3 total
                assert mock_process.memory_info.call_count == 3
