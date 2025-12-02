"""Parse CageMatch match data."""

import re
import urllib.parse
from typing import Generator

from bs4 import BeautifulSoup, Tag

import joshirank.cagematch.cm_parse as cm_parse
import joshirank.cagematch.util as util
from joshirank.cagematch.data import country_map

date_re = re.compile(r"\(([0-9]+)\.([0-9]+)\.([0-9]+)\)")

id_href = re.compile("nr=([0-9]+)")
tag_href = re.compile("[?]id=(28|29)")
event_href = re.compile("[?]id=1")


def extract_match_data_from_match_page(content: str) -> Generator[dict, None, None]:
    """Extract match data from a CageMatch match page HTML content."""
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
            date = util.parse_cm_date(m.group(0))
            return date.isoformat()
    return None


def get_matchtype(match: Tag):
    m = match.find(class_="MatchType")
    if m:
        return util.remove_colon(m.text)
    else:
        return ""


def extract_wrestler_id(wrestler: Tag) -> int:
    """Get the id number from an a tag"""
    return int(id_href.search(wrestler["href"]).group(1))


def parse_match(match: BeautifulSoup) -> dict:
    """Turn match soup into a dictionary"""
    wrestlers = []

    side_a, side_b, is_victory = parse_match_results(match)
    wrestlers = side_a + side_b

    for link in match.find_all("a"):
        # print(link["href"])
        if link["href"].startswith("?"):
            parsed = urllib.parse.parse_qs(link["href"][1:])
            if parsed["id"][0] == "2":
                if "nr" in parsed:
                    wrestlers.append(int(parsed["nr"][0]))

    return {
        "date": m_date(match),
        "country": _guess_country_of_match_soup(match),
        "wrestlers": wrestlers,
        "side_a": side_a,
        "side_b": side_b,
        "is_victory": is_victory,
        "promotion": m_promotion(match),
        "raw_html": str(match),
        "match_type": get_matchtype(match),
    }


def parse_match_results(match: BeautifulSoup) -> tuple:
    """Extract match results (side_a, side_b, is_victory) from match html.

    Results are returned as a tuple of (side_a, side_b, is_victory).
    If is_victory is True, side_a defeated side_b. If is_victory is False, neither side won (draw).

    Each side is represented as a list of wrestler IDs. This means that if there are any wrestlers
    without a CageMatch ID, they will be omitted from the results.
    """
    d_split = match.find(string=re.compile("defeat[s]?"))
    vs_split = match.find(string=re.compile("vs[.]"))  # indicates draw
    if d_split:

        winners = d_split.find_previous_siblings("a")
        losers = d_split.find_next_siblings("a")

        side_a = list(sorted(extract_wrestler_id(x) for x in winners))
        side_b = list(sorted(extract_wrestler_id(x) for x in losers))
        return side_a, side_b, True

    elif vs_split:
        # draw?

        side_one = [
            extract_wrestler_id(x) for x in vs_split.find_previous_siblings("a")
        ]
        side_two = [extract_wrestler_id(x) for x in vs_split.find_next_siblings("a")]

        return side_one, side_two, False


def guess_country_of_match(html_content):
    """Guess the country of a match based on its HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")
    return _guess_country_of_match_soup(soup)


def _guess_country_of_match_soup(soup: BeautifulSoup) -> str:
    eventline = soup.find("div", class_="MatchEventLine")
    # print(eventline)
    if eventline:
        text = eventline.get_text()
        # Simple regex to find country names (this is just an example)
        country_match = re.search(
            r"(Event|Online Stream|TV-Show|Pay Per View|House Show) @ (.*)$", text
        )
        if country_match:
            best_guess = country_match.group(2).split(",")[-1].strip().strip(".")

            return country_map.get(best_guess, best_guess)

    # Placeholder for actual country guessing logic
    return "Unknown"
