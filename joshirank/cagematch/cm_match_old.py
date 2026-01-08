def _old_parse_match(match: BeautifulSoup) -> MatchDict:
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

    wrestlers = sorted(wrestlers)

    d = extract_date(match)
    if d == "Unknown":
        logger.warning("Match with unknown date: {}", str(match))

    match_dict: MatchDict = {
        "version": 2,  # Format version - see docstring for version history
        "date": d,
        "country": extract_country(match),
        "wrestlers": wrestlers,
        "side_a": side_a,
        "side_b": side_b,
        "is_victory": is_victory,
        "promotion": extract_promotion(match),
        "raw_html": str(match),
        "match_type": extract_matchtype(match),
        "sides": sides,  # Always present for all matches
    }

    return match_dict


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
