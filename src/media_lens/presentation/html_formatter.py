import datetime
import json
import logging
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple
from urllib.parse import urlparse

import dotenv
from jinja2 import Environment, FileSystemLoader

from src.media_lens.common import utc_timestamp, UTC_PATTERN, LOGGER_NAME, SITES, get_project_root, timestamp_as_long_date, timestamp_str_as_long_date, LONG_DATE_PATTERN

logger = logging.getLogger(LOGGER_NAME)


def convert_relative_url(url: str, site: str) -> str:
    """
    Process a potentially relative URL, adding https:// and domain if needed.
    :param url: The URL to process
    :param site: Domain name (e.g., 'www.cnn.com')
    :returns str: Processed URL with protocol and domain if needed
    """
    # Check if URL already has a protocol
    parsed_url = urlparse(url)
    if parsed_url.scheme:
        return url

    # Append https:// and domain to the relative URL
    url_path = url[1:] if url.startswith('/') else url
    return f'https://{site}/{url_path}'

def generate_comparison_html(template_dir_path: Path, template_name: str, content: dict):
    """
    Generate an HTML page that displays two lists of dictionaries side by side.
    The expected content format is:
        {
            "report_timestamp": "2020-07-22",
            "runs": [
                {
                    "run_timestamp": "2020-07-22",
                    sites: [],
                    extracted: [{<same as extracted data format>}, ...],
                    interpreted: [{<same as interpreted data format>}, ...]
                }
            ]
        }
    """
    logger.info(f"generating HTML from template {template_name} in {template_dir_path}")
    env = Environment(loader=FileSystemLoader(template_dir_path))
    template = env.get_template(template_name)
    html_output = template.render(**content)
    return html_output

def generate_report(job_dirs: List[Path], sites: list[str], template_dir_path: Path, template_name: str) -> str:
    """
    Generate a report for the given job directories and sites.
    :param job_dirs: list of job directories
    :param sites: media sites
    :param template_dir_path: full path to location of Jinja2 templates
    :param template_name: template name
    :return:
    """
    logger.info(f'Generating report for {len(job_dirs)} jobs and {len(sites)} sites')
    content: Dict = {
        "report_timestamp": timestamp_as_long_date(),
        "runs": []
    }
    for job_dir in job_dirs:
        logger.debug("processing job_dir {}".format(job_dir))
        run: Dict = {
            "run_timestamp": timestamp_str_as_long_date(job_dir.name),
            "sites": sites,
            "extracted": [],
            "interpreted": []
        }
        for site in sites:
            with open(job_dir / f"{site}-clean-extracted.json", "r") as f:
                extracted: Dict = json.load(f)
                stories: List[Dict] = extracted['stories']
                clean_stories: List[Dict] = []
                for story in stories:
                    story['url'] = convert_relative_url(story['url'], site)
                    clean_stories.append(story)
                extracted['stories'] = clean_stories
                run['extracted'].append(extracted)
            with open(job_dir / f"{site}-interpreted.json", "r") as f:
                run['interpreted'].append(json.load(f))
        qna: List[List] = []
        for i in range(len(run['interpreted'][0])):
            sublist: List = []
            for j in range(len(run['interpreted']) + 1):
                if j == 0: # first column
                    sublist.append(run['interpreted'][j][i]['question'])
                else:
                    sublist.append(run['interpreted'][j-1][i]['answer'])
            qna.append(sublist)
        run['interpreted'] = qna
        content['runs'].append(run)
    logger.info("generating html")
    content['runs'] = sorted(content['runs'], key=lambda x: datetime.datetime.strptime(x["run_timestamp"], LONG_DATE_PATTERN), reverse=True)
    html: str = generate_comparison_html(template_dir_path, template_name, content)
    return html

def generate_html_from_path(job_dirs_root: Path, sites: list[str], template_dir_path: Path, template_name: str) -> str:
    """
    Convenience method to generate HTML from a path.
    :param job_dirs_root: the parent dir of all job dirs with UTC dates as names
    :param sites: list of media sites that will be covered
    :param template_dir_path: full path to location of Jinja2 templates
    :param template_name: template name
    :return:
    """
    logger.info(f"Generating HTML for {len(sites)} sites in {job_dirs_root}")
    dirs: List[Path] = []
    for node in job_dirs_root.iterdir():
        if node.is_dir():
            if re.match(UTC_PATTERN, node.name):
                dirs.append(node)
    return generate_report(dirs, sites, template_dir_path, template_name)


#########################################
# TEST
def main(job_dirs_root: Path):
    template_dir_path: Path = Path(get_project_root() / "config/templates")
    template_name: str = "template_01.j2"
    html: str = generate_html_from_path(job_dirs_root, SITES, template_dir_path, template_name)
    with open(job_dirs_root / f"medialens.html", "w") as f:
        f.write(html)

if __name__ == '__main__':
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.INFO)
    main(Path(get_project_root() / "working/out"))
