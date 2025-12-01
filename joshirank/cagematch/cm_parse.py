"""Parser for CageMatch website wrestler/match data."""

import datetime
import re
import urllib
from typing import Generator

from bs4 import BeautifulSoup, Tag
from loguru import logger

date_re = re.compile(r"([0-9][0-9])\.([0-9][0-9])\.([0-9][0-9][0-9][0-9])")
id_href = re.compile("nr=([0-9]+)")
tag_href = re.compile("[?]id=(28|29)")
event_href = re.compile("[?]id=1")


def parse_cm_date(date_str: str) -> datetime.date:
    """Parse a CageMatch date string (DD.MM.YYYY) into a datetime.date object."""

    return datetime.datetime.strptime(date_str, "%d.%m.%Y").date()


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


def parse_matches(content: str) -> Generator[dict, None, None]:
    soup = BeautifulSoup(content, "html.parser")
    # print(soup)
    for match in soup.find_all("tr", ["TRow1", "TRow2"]):
        # print(match)
        yield parse_match(match)


def m_promotion(match: BeautifulSoup) -> int | None:
    """Get the promotion id from a match html"""
    for link in match.find_all("a"):
        if link["href"].startswith("?"):
            parsed = urllib.parse.parse_qs(link["href"][1:])
            if parsed["id"][0] == "8":
                # promotion
                if "nr" in parsed:
                    return int(parsed["nr"][0])
    return None


def m_date(match: BeautifulSoup) -> str | None:
    """Get the date from a match html"""
    for cell in match.find_all("td"):
        m = date_re.search(cell.text)
        if m:
            date = parse_cm_date(m.group(0))
            return date.isoformat()
    return None


def parse_match(match: BeautifulSoup) -> dict:
    """Turn match html into a dictionary"""
    wrestlers = []
    promotion = m_promotion(match)
    date = m_date(match)

    for link in match.find_all("a"):
        # print(link["href"])
        if link["href"].startswith("?"):
            parsed = urllib.parse.parse_qs(link["href"][1:])
            if parsed["id"][0] == "2":
                if "nr" in parsed:
                    wrestlers.append(int(parsed["nr"][0]))

    return {
        "date": date,
        "wrestlers": wrestlers,
        "promotion": promotion,
        "raw_html": str(match),
    }


def parse_event(event: Tag) -> list[dict]:
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
