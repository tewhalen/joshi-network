"""Parser for CageMatch website wrestler data."""

import re

from bs4 import BeautifulSoup
from loguru import logger

from joshirank.cagematch.util import parse_cm_date

date_re = re.compile(r"([0-9][0-9])\.([0-9][0-9])\.([0-9][0-9][0-9][0-9])")
id_href = re.compile("nr=([0-9]+)")
tag_href = re.compile("[?]id=(28|29)")
event_href = re.compile("[?]id=1")


def parse_wrestler_profile_page(html_data: str) -> dict:
    """Parse wrestler profile page HTML and return wrestler data as a dictionary."""

    soup = BeautifulSoup(html_data, "html.parser")

    wrestler_data = {}

    page_header = soup.find("h1", class_="TextHeader")
    if page_header:
        wrestler_data["_name"] = page_header.text.strip()
    info_pairs = soup.findAll("div", class_="InformationBoxRow")
    for pair in info_pairs:
        label = pair.find("div", class_="InformationBoxTitle").text.strip().strip(":")
        value = pair.find("div", class_="InformationBoxContents")
        if date_re.match(value.text.strip()):
            try:
                value = parse_cm_date(value.text.strip()).isoformat()
            except ValueError:
                pass
        elif value.stripped_strings and len(list(value.stripped_strings)) > 1:
            # multiple strings, make a list
            value = [s.strip() for s in value.stripped_strings]
        else:
            value = value.text.strip()
        wrestler_data[label] = value

    return wrestler_data
