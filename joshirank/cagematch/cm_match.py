"""Parse CageMatch match data.

Match Data Structure
====================

Each match is represented as a dictionary with the following structure:

Core Fields (always present):
------------------------------
- version (int): Data format version (see Data Versioning section below)
- date (str): ISO format date string (YYYY-MM-DD) or "Unknown"
- country (str): Country where match took place, or "Unknown"
- wrestlers (list[int]): All unique wrestler IDs participating in the match
- is_victory (bool): True if there was a decisive winner, False for draws
- promotion (int | None): CageMatch promotion ID
- raw_html (str): Original HTML for debugging/reprocessing
- match_type (str): Match stipulation/type (e.g., "Singles", "Tag Team", "Triple Threat")
- sides (list[dict]): List of all sides/teams in the match (see structure below)

Two-Sided Match Structure (traditional):
-----------------------------------------
- side_a (tuple[int]): Winning side wrestler IDs (if is_victory=True), or one side for draws
- side_b (tuple[int]): Losing side wrestler IDs (if is_victory=True), or other side for draws
- sides (list[dict]): Two-element list with metadata for each side
  Each side is a dict with:
    - wrestlers (tuple[int]): Wrestler IDs on this side/team
    - is_winner (bool): True if this side won (for draws, first side is arbitrarily True)
    - team_id (int, optional): CageMatch team ID if this is a named team (only when len(wrestlers)==2)
    - team_name (str, optional): Team name if this is a named team (only when len(wrestlers)==2)
    - team_type (str, optional): "tag_team" or "stable" (only when team_id present)

For two-sided matches:
  wrestlers = list(side_a) + list(side_b)
  sides = [{"wrestlers": side_a, "is_winner": is_victory},
           {"wrestlers": side_b, "is_winner": not is_victory}]

Examples:
  Singles victory:
    side_a=(9462,), side_b=(10402,), is_victory=True
    sides=[{"wrestlers": (9462,), "is_winner": True},
           {"wrestlers": (10402,), "is_winner": False}]

  Tag victory:
    side_a=(9462, 10402), side_b=(4629, 9434), is_victory=True
    sides=[{"wrestlers": (9462, 10402), "is_winner": True},
           {"wrestlers": (4629, 9434), "is_winner": False}]

  Draw:
    side_a=(9462,), side_b=(10402,), is_victory=False
    sides=[{"wrestlers": (9462,), "is_winner": False},
           {"wrestlers": (10402,), "is_winner": False}]

Multi-Sided Match Structure (3+ sides):
----------------------------------------
When a match involves 3 or more distinct sides/teams (e.g., triple threat, fatal 4-way):

- is_multi_sided (bool): True for matches with 3+ sides (not present for two-sided matches)
- sides (list[dict]): List of all sides with metadata for each (3+ elements)
  Each side is a dict with:
    - wrestlers (tuple[int]): Wrestler IDs on this side/team
    - is_winner (bool): True if this side won the match

For backwards compatibility, multi-sided matches ALSO include:
  - side_a: Tuple of wrestler IDs from winning side (or first side if draw)
  - side_b: Tuple of all wrestlers from losing sides (flattened)

Examples:
  Triple Threat (1v1v1):
    sides = [
      {"wrestlers": (9462,), "is_winner": True},
      {"wrestlers": (10402,), "is_winner": False},
      {"wrestlers": (4629,), "is_winner": False}
    ]
    side_a = (9462,)
    side_b = (10402, 4629)  # flattened

  Fatal 4-Way (1v1v1v1):
    sides = [
      {"wrestlers": (19353,), "is_winner": True},
      {"wrestlers": (18539,), "is_winner": False},
      {"wrestlers": (14219,), "is_winner": False},
      {"wrestlers": (22930,), "is_winner": False}
    ]
    side_a = (19353,)
    side_b = (18539, 14219, 22930)  # flattened

  Triple Threat Tag (2v2v2):
    sides = [
      {"wrestlers": (9462, 10402), "is_winner": True},
      {"wrestlers": (4629, 9434), "is_winner": False},
      {"wrestlers": (16943, 16997), "is_winner": False}
    ]
    side_a = (9462, 10402)
    side_b = (4629, 9434, 16943, 16997)  # flattened

Special Values:
---------------
- Wrestler ID -1: Sentinel value indicating a wrestler without a CageMatch profile
  (name appeared in match text but no link was present)
- Empty sides: Indicates parsing issues or matches with unlinked wrestlers

Data Versioning:
----------------
Each match includes a "version" field to track the data format:

- **Version 1** (legacy): Only side_a/side_b fields, no sides list
  * Original tuple-based structure
  * No explicit winner marking in multi-way matches
  * Missing version field indicates version 1

- **Version 2** (current): Includes dict-based sides list for all matches
  * sides = [{"wrestlers": tuple, "is_winner": bool}, ...]
  * Consistent structure for two-sided and multi-sided matches
  * Enables rich metadata capture (winner marking, future fields)
  * Maintains backward compatibility with side_a/side_b

Migration example:
```python
if match_data.get("version", 1) < 2:
    # Legacy data - needs to be re-scraped or reprocessed from raw_html
    match_data = reparse_match(match_data["raw_html"])
```

Future Direction:
-----------------
The dict-based "sides" structure is now present for all matches (both two-sided and multi-way).
Potential improvements:

1. **Eliminate side_a/side_b entirely** once all downstream code is migrated:
   Currently maintained for backward compatibility, but sides provides all needed information

2. **Additional metadata fields** could be captured:
   - team_name (str): Named tag team if applicable
   - champion (bool): True if this side has a champion
   - team_id (int): CageMatch team ID if linked
   - Other match-specific metadata

3. **Eliminate side_a/side_b** once all downstream code is migrated:
   - all_matches.py uses side_a/side_b
   - do_rank.py uses side_a/side_b
   - generate_network.py uses side_a/side_b

Current implementation:
- All matches now include version=2 with dict-based "sides" field
- Legacy data (version 1 or missing version) lacks sides field
- side_a/side_b maintained for backward compatibility
- Downstream code (all_matches.py, do_rank.py, generate_network.py) still uses side_a/side_b
"""

import re
import urllib.parse
from typing import Generator, TypedDict

from bs4 import BeautifulSoup, Tag
from loguru import logger

import joshirank.cagematch.util as util
from joshirank.cagematch.data import country_map, missing_wrestlers

date_re = re.compile(r"([0-9]{2})\.([0-9]{2})\.([0-9]{4})")

id_href = re.compile("nr=([0-9]+)")
tag_href = re.compile("[?]id=(28|29)")
event_href = re.compile("[?]id=1")

# only find wrestler links, not tag teams
wrestler_id_href = re.compile(r"id=2&nr=([0-9]+)")


class MatchDict(TypedDict):
    version: int
    sides: list[dict]
    side_a: tuple
    side_b: tuple
    date: str | None
    wrestlers: list[int]
    is_victory: bool
    promotion: int | None
    raw_html: str
    match_type: str
    country: str | None
    is_multi_sided: bool


def extract_match_data_from_match_page(
    content: str,
) -> Generator[MatchDict, None, None]:
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
    return "Unknown"


def get_matchtype(match: Tag):
    m = match.find(class_="MatchType")
    if m:
        return util.remove_colon(m.text)
    else:
        return ""


def extract_wrestler_id(wrestler: Tag) -> int:
    """Get the id number from an a tag"""
    return int(id_href.search(wrestler["href"]).group(1))


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


def parse_match(match: BeautifulSoup) -> MatchDict:
    """Turn match soup into a dictionary"""
    wrestlers = []

    result = parse_match_results(match)
    # sides is list of dicts
    sides, is_victory = result
    # Extract wrestlers from dict-based sides for backward compatibility
    side_a = sides[0]["wrestlers"] if sides else tuple()
    side_b = (
        tuple(w for side in sides[1:] for w in side["wrestlers"])
        if len(sides) > 1
        else tuple()
    )

    # Extract team information (strict: only when team = full side)
    team_map = extract_team_info(match)

    # Add team info to sides where applicable
    for side in sides:
        wrestlers_tuple = side["wrestlers"]
        # Ensure it's a tuple (might be a list if loaded from JSON)
        if isinstance(wrestlers_tuple, list):
            wrestlers_tuple = tuple(wrestlers_tuple)
            side["wrestlers"] = wrestlers_tuple
        team_info = team_map.get(wrestlers_tuple, {})
        side.update(team_info)

    # build wrestlers list out of every wrestlers list in sides
    wrestlers = set()
    for side in sides:
        wrestlers.update(side["wrestlers"])

    wrestlers = list(sorted(wrestlers))

    d = m_date(match)
    if d == "Unknown":
        logger.warning("Match with unknown date: {}", str(match))

    match_dict: MatchDict = {
        "version": 2,  # Format version - see docstring for version history
        "date": d,
        "country": _guess_country_of_match_soup(match),
        "wrestlers": wrestlers,
        "side_a": side_a,
        "side_b": side_b,
        "is_victory": is_victory,
        "promotion": m_promotion(match),
        "raw_html": str(match),
        "match_type": get_matchtype(match),
        "sides": sides,  # Always present for all matches
        "is_multi_sided": len(sides) > 2,
    }

    return match_dict


def check_missing(txt_string):
    """Check if any known missing wrestlers are in the given text string."""

    for name in missing_wrestlers:
        if name in txt_string:
            return True
    return False


def parse_match_results(match: BeautifulSoup) -> tuple:
    """Extract match results from match html.

    For two-sided matches, returns (side_a, side_b, is_victory).
    For multi-sided matches (3+ sides), returns (sides_list, is_victory).

    If is_victory is True, side_a (or sides[0]) won.
    If is_victory is False, it's a draw.

    Each side is represented as a tuple of wrestler IDs. Wrestlers without
    CageMatch IDs are represented with -1.
    """
    d_split = match.find(string=re.compile("defeat[s]?"))
    vs_split = match.find(string=re.compile("vs[.]"))  # indicates draw

    if d_split:
        splitter = d_split
        is_victory = True
        # Extract just the matched word (defeat/defeats) from the text node
        splitter_match = re.search(r"defeat[s]?", d_split)
        splitter_word = splitter_match.group(0) if splitter_match else "defeat"
    elif vs_split:
        splitter = vs_split
        is_victory = False
        # Extract just "vs." from the text node
        splitter_match = re.search(r"vs\.", vs_split)
        splitter_word = splitter_match.group(0) if splitter_match else "vs."
    else:
        # no recognizable result
        return [], [], False

    # Get the full text of the match card
    match_card = match.find(class_="MatchCard")
    if not match_card:
        return [], [], False

    match_text = match_card.get_text()

    # Split into winner(s) and loser(s) sections using just the matched word
    if splitter_word in match_text:
        winner_text, loser_text = match_text.split(splitter_word, 1)
    else:
        return [], [], False

    return _parse_match_results(match, splitter, is_victory, splitter_word)


def is_wrestler_link(element) -> bool:
    if hasattr(element, "name") and element.name == "a" and element.has_attr("href"):
        href = element.get("href", "")
        if wrestler_id_href.search(href):
            return True
    return False


def _parse_match_results(
    match: BeautifulSoup, splitter, is_victory: bool, splitter_word: str
) -> tuple[list[dict], bool]:
    """Parse match results into structured sides data.

    Handles both two-sided and multi-sided matches using a unified algorithm.
    Walks through HTML nodes to collect wrestlers into groups, splitting on
    appropriate separators (" and " for victories, "vs." for draws).

    Args:
        match: BeautifulSoup match row
        splitter: The text node containing the splitter word (for DOM traversal)
        is_victory: True if this is a victory (defeats), False if draw (vs.)
        splitter_word: The actual word to split on ("defeat", "defeats", or "vs.")

    Returns:
        tuple: (sides_list, is_victory) where sides_list is a list of dicts,
               each containing 'wrestlers' (tuple of IDs) and 'is_winner' (bool).
               Unlinked wrestlers are represented with -1 sentinel values.
    """
    match_card = match.find(class_="MatchCard")
    if not match_card:
        return ([], False)

    # Separate winners from losers based on splitter position
    # the first group is "winners", the rest are "losers" groups
    # even if it's a draw, we treat the first group as "winners" for parsing

    all_groups = []
    current_group = []

    # Walk through all elements in MatchCard,
    # breaking into groups using the splitter as the main divider
    for element in match_card.descendants:
        if element == splitter:
            # we found the splitter node, time to start a new group
            # Always append current group (even if empty) to mark that we've seen the splitter
            all_groups.append(current_group)
            current_group = []
            continue

        if is_wrestler_link(element):
            # found a wrestler, add to the current group
            wrestler_id = extract_wrestler_id(element)
            current_group.append(wrestler_id)

        # Check for separators between sides
        if isinstance(element, str) and all_groups:
            # Look for both " and " (battle royals) and "vs." (multi-way matches)
            # Note: vs. might be preceded by ) or other characters
            if (" and " in element or "vs." in element) and current_group:
                # This separates sides
                all_groups.append(current_group)
                current_group = []

    # Add the final group - always append if we saw the splitter
    # (even if empty, unlinked wrestlers will be filled in by text analysis)
    if all_groups:
        all_groups.append(current_group)

    winners = all_groups[0] if all_groups else []
    # Build the final sides list as dict: [{wrestlers, is_winner}, ...]
    # Winner is first, then all losing sides
    sides = [{"wrestlers": tuple(sorted(winners)), "is_winner": is_victory}]
    sides.extend(
        [
            {"wrestlers": tuple(sorted(side)), "is_winner": False}
            for side in all_groups[1:]
        ]
    )

    # Count unlinked wrestlers in each side's text
    match_text = match.get_text()
    text_parts = match_text.split(splitter_word, 1)

    if len(text_parts) == 2:
        winner_text, losers_text = text_parts

        # Process winner side
        if sides:
            winner_separators = winner_text.count(" & ")
            winner_expected = winner_separators + 1
            winner_missing = winner_expected - len(sides[0]["wrestlers"])

            if winner_missing > 0:
                sides[0]["wrestlers"] = (
                    tuple([-1] * winner_missing) + sides[0]["wrestlers"]
                )

        # Process loser sides - split by appropriate separator
        if len(sides) > 1:
            # Determine separator based on whether this is a victory or draw
            # For draws (vs.), split by " vs. "; for victories (defeats), split by " and "
            separator = " vs. " if not is_victory else " and "
            loser_sections = losers_text.split(separator)
            for i, section in enumerate(loser_sections):
                if i + 1 < len(sides):  # Check if we have a corresponding side
                    # In multi-sided matches, wrestlers on same side use "&", different sides use "and" or "vs."
                    side_separators = section.count(" & ")
                    side_expected = side_separators + 1
                    side_missing = side_expected - len(sides[i + 1]["wrestlers"])

                    if side_missing > 0:
                        sides[i + 1]["wrestlers"] = (
                            tuple([-1] * side_missing) + sides[i + 1]["wrestlers"]
                        )

                else:
                    # This is a section without a corresponding linked wrestler (unlinked name only)
                    # Add a new side with just -1
                    # Count how many wrestlers should be in this section
                    section_separators = section.count(" & ")
                    section_expected = section_separators + 1
                    sides.append(
                        {
                            "wrestlers": tuple([-1] * section_expected),
                            "is_winner": False,
                        }
                    )

    return (sides, is_victory)


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


def extract_years_from_match_page(content: str) -> set[int]:
    """Extract all years that matches exist for from a CageMatch match page HTML content."""
    soup = BeautifulSoup(content, "html.parser")
    years = set()
    year_selector = soup.find("select", {"name": "year"})
    if not year_selector:
        return years
    for option in year_selector.find_all("option"):
        if option["value"].isnumeric():
            years.add(int(option["value"]))
    return years
