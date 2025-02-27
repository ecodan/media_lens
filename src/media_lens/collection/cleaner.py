import asyncio
import json
import logging
import time
from abc import abstractmethod
from pathlib import Path

from bs4 import BeautifulSoup

from src.media_lens.common import LOGGER_NAME, get_project_root

logger = logging.getLogger(LOGGER_NAME)

TEXT_ELEMENTS: set[str] = {'span', 'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}

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

        :param page: HTML content to clean
        :type page: BeautifulSoup
        :return: The cleaned HTML containing only matching elements and their ancestors
        :rtype: BeautifulSoup
        """
        """
        SLOW VERSION
        """
        # Start timer
        start_time = time.time()

        # Find all elements matching any of the patterns
        matching_elements = []
        for pattern in self.patterns:
            matching_elements.extend(page.select(pattern))

        for element in page.find_all():
            if not (element in matching_elements or
                    any(element in match.descendants or
                        element in match.parents for match in matching_elements)):
                element.decompose()

        # Calculate and log elapsed time
        elapsed_time = time.time() - start_time
        logger.debug(f"Pattern matching took {elapsed_time:.2f} seconds")
        return page

class CNNCleaner(PatternBasedCleaner):
    def __init__(self):
        super().__init__([f'[class*="{pattern}"]' for pattern in ["headline"]])

class BBCCleaner(PatternBasedCleaner):
    def __init__(self):
        super().__init__([f'h2[data-testid*="{pattern}"]' for pattern in ["headline"]])

class FoxNewsCleaner(PatternBasedCleaner):
    def __init__(self):
        super().__init__([f'{pattern}' for pattern in ["article"]])


class CleanerConfig:
    SITE_PATTERNS = {
        "www.cnn.com": ['[class*="headline"]'],
        "www.bbc.com": ['h2[data-testid*="headline"]'],
        "www.foxnews.com": ["article"]
    }


def cleaner_for_site(site: str) -> SiteSpecificCleaner:
    site_key = next((k for k in CleanerConfig.SITE_PATTERNS if k in site), None)
    if site_key:
        return PatternBasedCleaner([f'{p}' for p in CleanerConfig.SITE_PATTERNS[site_key]])
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
        soup = BeautifulSoup(html_content, 'html.parser')

        # nuke HEAD
        if soup.head:
            soup.head.clear()

        # Remove unnecessary elements while preserving structure
        elements_to_remove = [
            'script', 'style', 'iframe', 'noscript',  # Technical elements
            'form', 'button', 'input',  # Interactive elements
            'svg', 'path', 'img'  # Decorative elements
        ]
        for element in soup.find_all(elements_to_remove):
            element.decompose()

        soup = self.site_cleaner.clean_page(soup)

        return str(soup)

    @staticmethod
    def filter_text_elements(html_content):
        """Filter HTML to keep only elements that have text display field descendants.

        :param html_content: Input HTML content
        :type html_content: str
        :return: Filtered HTML content
        :rtype: str
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Define text display tags
        text_tags = TEXT_ELEMENTS

        # Find all elements that don't have text display descendants
        elements_to_remove = []
        for element in soup.find_all():
            # Skip if element itself is a text display tag
            if element.name in text_tags:
                continue

            # Check if element has any text display descendants
            has_text_descendant = any(descendant.name in text_tags
                                    for descendant in element.find_all())

            if not has_text_descendant:
                elements_to_remove.append(element)

        # Remove elements that don't have text display descendants
        for element in elements_to_remove:
            if element.parent:  # Check if element hasn't already been removed
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
        soup = BeautifulSoup(html_content, 'html.parser')
        results = []

        for tag in soup.find_all(TEXT_ELEMENTS):
            text = ' '.join(s.strip() for s in tag.strings
                            if s.strip() and not s.strip().startswith('<!--'))
            if not text:
                continue

            url = next((p.get('href') for p in tag.parents
                        if p.name == 'a' and p.get('href')), None)

            results.append({
                "path": WebpageCleaner._build_xpath(tag),
                "text": text,
                "url": url
            })

        return results

    @staticmethod
    def _build_xpath(element) -> str:
        path = []
        while element and element.name:
            attr_str = element.name
            if element.get('class'):
                attr_str += '[@class="{}"]'.format(' '.join(element.get('class')))
            elif element.get('id'):
                attr_str += '[@id="{}"]'.format(element.get('id'))
            path.insert(0, attr_str)
            element = element.parent
        return '//' + '/'.join(path)

############################################################
# TESTING
def load_test_file(file_path: Path) -> str:
    with open(file_path, "r") as file:
        content = file.read()
    return content

async def main(working_dir: Path, fname: str, cleaner: SiteSpecificCleaner):
    fpath: Path = working_dir / fname
    content: str = load_test_file(fpath)
    logger.debug(f"raw content len: {len(content)} bytes")

    cleaner = WebpageCleaner(cleaner)
    cleaned = cleaner.clean_html(content)
    logger.debug(f"cleaned content len: {len(cleaned)} bytes")

    text_elements = cleaner.extract_text_elements(cleaned)
    logger.debug(f"extracted text elements len: {len(json.dumps(text_elements))} bytes")
    with open(working_dir / f"{fpath.stem}-cleaned.html", "w") as file:
        file.write(cleaned)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    # asyncio.run(main(Path(get_project_root() / "working/out/test"), "www.bbc.com.html", BBCCleaner()))
    asyncio.run(main(Path(get_project_root() / "working/out/test"), "www.cnn.com.html", CNNCleaner()))