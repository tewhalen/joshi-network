"""Extract embedded data from inside match data, like tag team particiption, names, and the gimmick names used
by wrestlers in the matches."""

import re
import urllib.parse

from bs4 import BeautifulSoup

import joshirank.cagematch.util as util
from joshirank.cagematch.data import country_map

date_re = re.compile(r"([0-9]{2})\.([0-9]{2})\.([0-9]{4})")


def extract_promotion(match: BeautifulSoup) -> int | None:
    """Get the promotion id from a match html"""
    for link in match.find_all("a"):
        if link["href"].startswith("?"):
            parsed = urllib.parse.parse_qs(link["href"][1:])
            if parsed["id"][0] == "8":
                # promotion
                if "nr" in parsed:
                    return int(parsed["nr"][0])
    return None


def extract_date(match: BeautifulSoup) -> str | None:
    """Get the date from a match html"""
    for cell in match.find_all("td"):
        m = date_re.search(cell.text)
        if m:
            date = util.parse_cm_date(m.group(0))
            return date.isoformat()
    return "Unknown"


def extract_matchtype(match: BeautifulSoup) -> str:
    m = match.find(class_="MatchType")
    if m:
        return util.remove_colon(m.text)
    else:
        return ""


def extract_team_info(match: BeautifulSoup) -> dict[tuple, dict]:
    """Extract team information from match HTML.

    Returns a dict mapping wrestler tuples to team info:
    {(wrestler_a, wrestler_b): {"team_id": 123, "team_name": "Team Name", "team_type": "tag_team"}}

    Only extracts teams when they represent exactly 2 wrestlers (strict approach).
    Team links use id=28 for tag teams, id=29 for stables.
    """
    team_map = {}

    match_card = match.find(class_="MatchCard")
    if not match_card:
        return team_map

    # Pattern to find team links: <a href="?id=28&nr=123">Team Name</a>
    team_link_pattern = re.compile(
        r'<a href="\?id=(28|29)&amp;nr=(\d+)[^"]*">([^<]+)</a>'
    )
    html_str = str(match_card)

    for match_obj in team_link_pattern.finditer(html_str):
        team_type_id = match_obj.group(1)
        team_id = int(match_obj.group(2))
        team_name = match_obj.group(3)
        team_type = "tag_team" if team_type_id == "28" else "stable"

        # Find the wrestler links immediately after this team link
        # Pattern: Team Name</a> (Wrestler1 & Wrestler2)
        # We need to find the section after the team link up to the next logical break
        start_pos = match_obj.end()
        section = html_str[start_pos : start_pos + 300]

        # Look for wrestler links in parentheses after team name
        # Pattern: (Wrestler1 & Wrestler2) or (Wrestler1, Wrestler2 & Wrestler3)
        paren_match = re.search(r"\(([^)]+)\)", section)
        if paren_match:
            paren_content = paren_match.group(1)
            # Find wrestler IDs within the parentheses
            wrestler_links = re.findall(r"id=2&amp;nr=(\d+)", paren_content)
            wrestler_ids = tuple(sorted(int(wid) for wid in wrestler_links))

            # Only add if exactly 2 wrestlers (strict approach)
            if len(wrestler_ids) == 2:
                team_map[wrestler_ids] = {
                    "team_id": team_id,
                    "team_name": team_name,
                    "team_type": team_type,
                }

    return team_map


def extract_country(match_soup: BeautifulSoup) -> str:
    """Guess the country of a match based on its HTML content."""
    eventline = match_soup.find("div", class_="MatchEventLine")
    # print(eventline)
    if eventline:
        text = eventline.get_text()
        # Simple regex to find country names (this is just an example)
        country_match = re.search(
            r"(Event|Online Stream|TV-Show|Pay Per View|Dark Match|House Show) @ (.*)$",
            text,
        )
        if country_match:
            best_guess = country_match.group(2).split(",")[-1].strip().strip(".")

            return country_map.get(best_guess, best_guess)

    # Placeholder for actual country guessing logic
    return "Unknown"
