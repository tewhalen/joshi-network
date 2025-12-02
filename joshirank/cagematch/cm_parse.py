"""Parser for CageMatch website wrestler data."""

import datetime
import re
import urllib
from typing import Generator

from bs4 import BeautifulSoup, Tag
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
        value = pair.find("div", class_="InformationBoxContents").text.strip()
        if date_re.match(value):
            try:
                value = parse_cm_date(value).isoformat()
            except ValueError:
                pass
        if label == "Alter egos":
            # iterate over each <a> tag and extract the alter ego names
            alter_egos = []
            for a_tag in pair.find("div", class_="InformationBoxContents").find_all(
                "a"
            ):
                alter_egos.append(a_tag.text.strip())
            value = alter_egos

        wrestler_data[label] = value

    return wrestler_data


def parse_event(event: Tag) -> list[dict]:
    # NOT USED
    results = []
    event_header = event.find("div", class_="QuickResultsHeader")
    date_m = date_re.search(event_header.text)
    if not date_m:
        raise SyntaxError("no date found!")
    day, month, year = date_m.groups()
    datestr = f"{year}-{month}-{day}"

    event_name = event_header.a.text

    for match in event.find_all("span", class_="MatchResults"):
        match_res = parse_match(match)
        match_res["date"] = datestr
        match_res["event"] = event_name
        results.append(match_res)
    return results
