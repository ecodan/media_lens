import asyncio
import json
import logging
import re
from abc import abstractmethod
from logging import Logger
from pathlib import Path

import trafilatura
from bs4 import BeautifulSoup
from trafilatura.settings import use_config

from src.media_lens.collection.scraper import WebpageScraper
from src.media_lens.common import LOGGER_NAME

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
        """
        Keep only elements that match or are related to any of the provided patterns.

        Args:
            html_content: str, the HTML to clean
            patterns: list of str, CSS patterns to match (e.g. ['[class*="headline"]', '[class*="title"]'])

        Returns:
            str: The cleaned HTML containing only matching elements and their ancestors
        """

        # Find all elements matching any of the patterns
        matching_elements = []
        for pattern in self.patterns:
            matching_elements.extend(page.select(pattern))

        # Mark elements for removal
        elements_to_remove = []
        for element in page.find_all():
            should_remove = True

            # Check if this element matches or contains/is contained by a match
            for match in matching_elements:
                if (element == match or
                        # match in element.descendants or
                        element in match.descendants or
                        element in match.parents):
                    should_remove = False
                    break

            if should_remove:
                elements_to_remove.append(element)

        # Remove marked elements
        for element in elements_to_remove:
            element.decompose()

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


def cleaner_for_site(site: str) -> SiteSpecificCleaner:
    if site.find("cnn") >= 0:
        return CNNCleaner()
    elif site.find("bbc") >= 0:
        return BBCCleaner()
    elif site.find("foxnews") >= 0:
        return FoxNewsCleaner()
    else:
        raise ValueError(f"{site} is not a valid site")

class WebpageCleaner:

    def __init__(self, site_cleaner: SiteSpecificCleaner):
        super().__init__()
        self.site_cleaner = site_cleaner

    def clean_html(self, html_content: str) -> str:
        """
        Clean HTML content while preserving important structural information.
        :param html_content: HTML content
        :returns Cleaned HTML content with preserved hierarchy
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
        """
        Filter HTML to keep only elements that have text display field descendants.

        Args:
            html_content (str): Input HTML content

        Returns:
            str: Filtered HTML content
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
        """
        Extract text elements from HTML specifically within span, p, or div tags.

        Args:
            html_content (str): Input HTML content

        Returns:
            list: List of dictionaries containing path, text, and URL for each text element
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Define valid text containers
        valid_tags = TEXT_ELEMENTS
        results = []

        # Find all text elements within valid tags
        for tag in soup.find_all(valid_tags):
            # Get direct text content, excluding nested tag text
            direct_text = ''.join(child.strip() for child in tag.children if isinstance(child, str) and not child.strip().startswith('<!--'))

            # Skip if no direct text content
            if not direct_text.strip():
                continue

            # Build XPath
            current = tag
            attrs = []
            while current and current.name:
                attr_str = current.name
                if current.get('class'):
                    attr_str += '[@class="{}"]'.format(' '.join(current.get('class')))
                elif current.get('id'):
                    attr_str += '[@id="{}"]'.format(current.get('id'))
                attrs.insert(0, attr_str)
                current = current.parent

            xpath = '//' + '/'.join(attrs)

            # Find closest parent with href
            url = None
            parent = tag.parent
            while parent:
                if parent.name == 'a' and parent.get('href'):
                    url = parent.get('href')
                    break
                parent = parent.parent

            # Create result entry
            result = {
                "path": xpath,
                "text": direct_text.strip(),
                "url": url
            }

            results.append(result)

        return results


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
    # logger.debug(f"cleaned content: {cleaned}")

    # cleaned = cleaner.filter_text_elements(cleaned)
    # logger.debug(f"cleaned and filtered content len: {len(cleaned)} bytes")
    # logger.debug(f"cleaned and filtered content: {cleaned}")

    text_elements = cleaner.extract_text_elements(cleaned)
    logger.debug(f"extracted text elements len: {len(json.dumps(text_elements))} bytes")
    # logger.debug(f"extracted text elements: {json.dumps(text_elements)}")
    with open(working_dir / f"{fpath.stem}-cleaned.html", "w") as file:
        file.write(cleaned)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main(Path("/Users/dan/dev/code/projects/python/media_lens/working/out/test"), "www.bbc.com.html", BBCCleaner()))
    # asyncio.run(main(load_test_file("cnn-mob.html"), BBCCleaner()))
    # asyncio.run(main(load_test_file("foxnews-mob.html"), BBCCleaner()))
