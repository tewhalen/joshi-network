"""Parse CageMatch match data.

Match Data Structure
====================

Each match is represented as a dictionary with the following structure:

Core Fields (always present):
------------------------------
- version (int): Data format version (see Data Versioning section below)
- date (str): ISO format date string (YYYY-MM-DD) or "Unknown"
- country (str): Country where match took place, or "Unknown"
- wrestlers (list[int]): All wrestler IDs participating in the match
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
from typing import Generator

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


def parse_match(match: BeautifulSoup) -> dict:
    """Turn match soup into a dictionary"""
    wrestlers = []

    result = parse_match_results(match)
    if len(result) == 3:
        # Two-sided match (backwards compatible)
        side_a, side_b, is_victory = result
        # Create sides structure for consistency
        # For draws (is_victory=False), both sides have is_winner=False
        sides = [
            {"wrestlers": side_a, "is_winner": is_victory},
            {"wrestlers": side_b, "is_winner": False},
        ]
        is_multi_sided = False
    else:
        # Multi-sided match (3+ sides) - sides is list of dicts
        sides, is_victory = result
        # Extract wrestlers from dict-based sides for backward compatibility
        side_a = sides[0]["wrestlers"] if sides else tuple()
        side_b = (
            tuple(w for side in sides[1:] for w in side["wrestlers"])
            if len(sides) > 1
            else tuple()
        )
        is_multi_sided = True

    wrestlers = list(side_a) + list(side_b)
    d = m_date(match)
    if d == "Unknown":
        logger.warning("Match with unknown date: {}", str(match))

    match_dict = {
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
    }

    # Add multi-sided flag if applicable
    if is_multi_sided:
        match_dict["is_multi_sided"] = True

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
    elif vs_split:
        splitter = vs_split
        is_victory = False
    else:
        # no recognizable result
        return [], [], False

    # Get the full text of the match card
    match_card = match.find(class_="MatchCard")
    if not match_card:
        return [], [], False

    match_text = match_card.get_text()

    # Split into winner(s) and loser(s) sections
    if splitter.text in match_text:
        winner_text, loser_text = match_text.split(splitter.text, 1)
    else:
        return [], [], False

    # Check if this is a multi-sided match by looking for " and " separators
    # between teams in the loser section (not within teams, which use "&")
    # Pattern: "A defeats B and C" or "A & B defeat C & D and E & F"
    # Pass the HTML string, not plain text
    match_card_html = str(match_card)
    is_multi_sided = _is_multi_sided_match(match_card_html, splitter.text)

    if is_multi_sided:
        return _parse_multi_sided_match(match, splitter, is_victory)
    else:
        return _parse_two_sided_match(match, splitter, is_victory)


def _is_multi_sided_match(match_card_html: str, splitter_text: str) -> bool:
    """Detect if match has 3+ sides by looking for 'and' between teams.

    Returns True if there are multiple " and " separators that indicate
    separate sides (not just list items within a team).

    Args:
        match_card_html: HTML string of the MatchCard element
        splitter_text: The text of the splitter ("defeats" or "vs.")
    """
    # Split the HTML to get only the losers section
    if splitter_text not in match_card_html:
        return False

    _, losers_html = match_card_html.split(splitter_text, 1)

    # Look for pattern: ">Name</a> and <a" which indicates separate wrestlers/teams
    and_between_links = re.findall(r"</a>\s+and\s+<a", losers_html)

    # If we find 1+ occurrences of "and" between separate wrestler links,
    # this is likely a multi-way match
    return len(and_between_links) >= 1


def _parse_two_sided_match(match: BeautifulSoup, splitter, is_victory: bool) -> tuple:
    """Parse a traditional two-sided match."""
    # these searches only find wrestler IDs (hopefully)
    side_a_raw = splitter.find_previous_siblings("a", href=wrestler_id_href)
    side_b_raw = splitter.find_next_siblings("a", href=wrestler_id_href)

    side_a = tuple(sorted(extract_wrestler_id(x) for x in side_a_raw))
    side_b = tuple(sorted(extract_wrestler_id(x) for x in side_b_raw))

    # sanity check - if any wrestlers are on both sides, that's wrong
    for w in side_a:
        if w in side_b:
            logger.warning(
                "Wrestler {} found on both sides of match: {} / {}", w, side_a, side_b
            )

    match_text = match.get_text()
    side_a_txt, side_b_txt = match_text.split(splitter.text, maxsplit=1)

    if check_missing(side_a_txt):
        # prepend a -1 to indicate missing wrestler
        side_a = (-1,) + side_a
    if check_missing(side_b_txt):
        side_b = (-1,) + side_b

    return side_a, side_b, is_victory


def _parse_multi_sided_match(match: BeautifulSoup, splitter, is_victory: bool) -> tuple:
    """Parse a multi-sided match (3+ sides).

    Returns (sides_list, is_victory) where sides_list is a list of tuples,
    each representing one side/team in the match.
    """
    match_card = match.find(class_="MatchCard")
    if not match_card:
        return ([], False)

    # Get all wrestler links
    all_links = match_card.find_all("a", href=wrestler_id_href)

    # Find the splitter position in the HTML
    splitter_parent = splitter.parent

    # Separate winners from losers based on splitter position
    winners = []
    losers_groups = []

    current_group = []
    found_splitter = False
    in_losers = False

    # Walk through all elements in MatchCard
    for element in match_card.descendants:
        if element == splitter:
            found_splitter = True
            if current_group:
                winners = current_group
                current_group = []
            in_losers = True
            continue

        # Check if it's a wrestler link
        if (
            hasattr(element, "name")
            and element.name == "a"
            and element.has_attr("href")
        ):
            href = element.get("href", "")
            if wrestler_id_href.search(href):
                wrestler_id = extract_wrestler_id(element)
                current_group.append(wrestler_id)

        # Check for " and " text nodes that separate sides
        if isinstance(element, str) and in_losers:
            if " and " in element and current_group:
                # This "and" separates sides
                losers_groups.append(tuple(sorted(current_group)))
                current_group = []

    # Add the final group
    if current_group and in_losers:
        losers_groups.append(tuple(sorted(current_group)))

    # Build the final sides list as dict: [{wrestlers, is_winner}, ...]
    # Winner is first, then all losing sides
    sides = [{"wrestlers": tuple(sorted(winners)), "is_winner": is_victory}]
    sides.extend([{"wrestlers": side, "is_winner": False} for side in losers_groups])

    # Check for missing wrestlers
    match_text = match.get_text()
    if check_missing(match_text):
        # For now, add -1 to the first side where we detect missing wrestlers
        # This is a simplification
        if sides and check_missing(match_text.split(splitter.text)[0]):
            sides[0]["wrestlers"] = (-1,) + sides[0]["wrestlers"]

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
