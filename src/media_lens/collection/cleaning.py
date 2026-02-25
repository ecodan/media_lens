import asyncio
import logging
import time
from abc import abstractmethod
from pathlib import Path
from typing import ClassVar

from bs4 import BeautifulSoup

from src.media_lens.common import LOGGER_NAME, get_project_root

logger = logging.getLogger(LOGGER_NAME)

TEXT_ELEMENTS: set[str] = {"span", "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "header", "a"}


class SiteSpecificCleaner:
    @abstractmethod
    def clean_page(self, page: BeautifulSoup) -> BeautifulSoup:
        pass


class PatternBasedCleaner(SiteSpecificCleaner):
    def __init__(self, patterns: list[str]):
        super().__init__()
        self.patterns = patterns

    def clean_page(self, page: BeautifulSoup) -> BeautifulSoup:
        """Keep only elements that match or are related to any of the provided patterns.
        This is a linear-time (O(N)) implementation of the filtering logic.

        :param page: HTML content to clean
        :type page: BeautifulSoup
        :return: The cleaned HTML containing only matching elements and their ancestors/descendants
        :rtype: BeautifulSoup
        """
        # Start timer
        start_time = time.time()

        # Find all elements matching any of the patterns
        matching_elements = set()
        for pattern in self.patterns:
            matching_elements.update(page.select(pattern))

        # 1. Identify all nodes that must be kept (matches, ancestors, and descendants)
        keep_set = set()
        for element in matching_elements:
            # Add ancestors
            curr = element
            while curr and curr not in keep_set:
                keep_set.add(curr)
                curr = curr.parent

            # Add descendants
            # BS4 descendants is an iterator. Adding to a set is O(1).
            for desc in element.descendants:
                keep_set.add(desc)

        # 2. Decompose any element not in the keep_set
        for element in page.find_all():
            if element not in keep_set:
                element.decompose()

        # Calculate and log elapsed time
        elapsed_time = time.time() - start_time
        logger.debug(f"Pattern matching took {elapsed_time:.2f} seconds (optimized O(N))")
        return page


class CNNCleaner(PatternBasedCleaner):
    def __init__(self):
        super().__init__(CleanerConfig.SITE_PATTERNS["www.cnn.com"])


class BBCCleaner(PatternBasedCleaner):
    def __init__(self):
        super().__init__(CleanerConfig.SITE_PATTERNS["www.bbc.com"])


class FoxNewsCleaner(PatternBasedCleaner):
    def __init__(self):
        super().__init__(CleanerConfig.SITE_PATTERNS["www.foxnews.com"])


class CleanerConfig:
    SITE_PATTERNS: ClassVar[dict] = {
        "www.cnn.com": ['[class*="headline"]', '[class*="title"]'],
        "www.bbc.com": ['h2[data-testid*="headline"]'],
        "www.foxnews.com": ["article", "[class*='info']"],
    }


def cleaner_for_site(site: str) -> SiteSpecificCleaner:
    site_key = next((k for k in CleanerConfig.SITE_PATTERNS if k in site), None)
    if site_key:
        return PatternBasedCleaner(CleanerConfig.SITE_PATTERNS[site_key])
    raise ValueError(f"Unsupported site: {site}")


class WebpageCleaner:
    def __init__(self, site_cleaner: SiteSpecificCleaner):
        super().__init__()
        self.site_cleaner = site_cleaner

    def clean_html(self, html_content: str) -> str:
        """Clean HTML content while preserving important structural information.

        :param html_content: HTML content to clean
        :type html_content: str
        :return: Cleaned HTML content with preserved hierarchy
        :rtype: str
        """
        import re

        # Pre-strip non-content tags to reduce size before parsing
        # (This drastically reduces N for the subsequent O(N^2) cleaning)
        html_content = re.sub(r"<script.*?>.*?</script>", "", html_content, flags=re.S | re.I)
        html_content = re.sub(r"<style.*?>.*?</style>", "", html_content, flags=re.S | re.I)
        html_content = re.sub(r"<svg.*?>.*?</svg>", "", html_content, flags=re.S | re.I)

        # Safe Cut: Truncate massive pages after stripping scripts/styles.
        # Now that we've removed scripts, 10MB is more than enough for pure HTML.
        # This prevents the truncation from cutting off actual content.
        max_html_size = 10 * 1024 * 1024
        if len(html_content) > max_html_size:
            html_content = html_content[:max_html_size]

        soup = BeautifulSoup(html_content, "html.parser")

        # nuke HEAD
        if soup.head:
            soup.head.clear()

        # Remove unnecessary elements while preserving structure
        elements_to_remove = [
            "script",
            "style",
            "iframe",
            "noscript",  # Technical elements
            "form",
            "button",
            "input",  # Interactive elements
            "svg",
            "path",
            "img",  # Decorative elements
        ]
        for element in soup.find_all(elements_to_remove):
            element.decompose()

        soup = self.site_cleaner.clean_page(soup)

        return str(soup)

    @staticmethod
    def filter_text_elements(html_content):
        """Filter HTML to keep only elements that have text display field descendants.
        This is a linear-time (O(N)) implementation of the filtering logic.

        :param html_content: Input HTML content
        :type html_content: str
        :return: Filtered HTML content
        :rtype: str
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Define text display tags
        text_tags = set(TEXT_ELEMENTS)

        # 1. Identify all nodes that must be kept (text tags and their ancestors)
        keep_set = set()
        for element in soup.find_all(text_tags):
            curr = element
            while curr and curr not in keep_set:
                keep_set.add(curr)
                curr = curr.parent

        # 2. Decompose any element not in the keep_set
        # We must collect them first to avoid modifying the tree while iterating
        for element in soup.find_all():
            if element not in keep_set:
                element.decompose()

        return str(soup)

    @staticmethod
    def extract_text_elements(html_content) -> list[dict]:
        """Extract text elements from HTML within specified tags.

        :param html_content: Input HTML content
        :type html_content: str
        :return: List of text elements with path and URL info
        :rtype: list[dict]
        """
        soup = BeautifulSoup(html_content, "html.parser")
        results = []

        for tag in soup.find_all(TEXT_ELEMENTS):
            text = " ".join(
                s.strip() for s in tag.strings if s.strip() and not s.strip().startswith("<!--")
            )
            if not text:
                continue

            url = next(
                (p.get("href") for p in tag.parents if p.name == "a" and p.get("href")), None
            )

            results.append({"path": WebpageCleaner._build_xpath(tag), "text": text, "url": url})

        return results

    @staticmethod
    def _build_xpath(element) -> str:
        path = []
        while element and element.name:
            attr_str = element.name
            if element.get("class"):
                attr_str += '[@class="{}"]'.format(" ".join(element.get("class")))
            elif element.get("id"):
                attr_str += '[@id="{}"]'.format(element.get("id"))
            path.insert(0, attr_str)
            element = element.parent
        return "//" + "/".join(path)


############################################################
# TESTING
def load_test_file(file_path: Path) -> str:
    with open(file_path) as file:
        content = file.read()
    return content


async def main(working_dir: Path, fname: str, cleaner: SiteSpecificCleaner):
    fpath: Path = working_dir / fname
    content: str = load_test_file(fpath)
    logger.debug(f"raw content len: {len(content)} bytes")

    cleaner = WebpageCleaner(cleaner)
    cleaned = cleaner.clean_html(content)
    logger.debug(f"cleaned content len: {len(cleaned)} bytes")
    cleaned = cleaner.filter_text_elements(content)
    logger.debug(f"cleaned content len (post text elements): {len(cleaned)} bytes")

    # text_elements = cleaner.extract_text_elements(cleaned)
    # logger.debug(f"extracted text elements len: {len(json.dumps(text_elements))} bytes")

    with open(working_dir / f"{fpath.stem}-clean.html", "w") as file:
        file.write(cleaned)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # asyncio.run(main(Path(get_project_root() / "working/out/test"), "www.bbc.com.html", BBCCleaner()))
    asyncio.run(
        main(
            Path(get_project_root() / "working/out/test"), "www.foxnews.com.html", FoxNewsCleaner()
        )
    )
