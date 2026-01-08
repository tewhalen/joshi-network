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

from collections.abc import Generator

from bs4 import BeautifulSoup

from joshirank.cagematch.cm_match_token import MatchDict, parse_match


def extract_match_data_from_match_page(
    content: str,
) -> Generator[MatchDict]:
    """Extract match data from a CageMatch match page HTML content."""
    soup = BeautifulSoup(content, "html.parser")
    # print(soup)
    for match in soup.find_all("tr", class_=["TRow1", "TRow2"]):
        # print(match)
        yield parse_match(match)


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
