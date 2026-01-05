"""
Docstring for scripts.analysis.tjpw_combinations

A script which analyses all TJPW wrestler combinations based on match data
in the joshi wrestler database.

Based on the population of wrestlers who have wrestled at least n matches in TJPW,
this script determines all possible combinations of 2 and 3 wrestlers and
searches the database to count the number of times that combination appeared as one
side of a TJPW match.
"""

import time
from collections import Counter, defaultdict
from itertools import combinations

from joshirank.analysis.promotion import all_tjpw_wrestlers
from joshirank.joshidb import get_name, wrestler_db

THIS_YEAR = time.localtime().tm_year

TJPW_PROMO_ID = "1467"


def get_active_tjpw_wrestlers(min_matches=10, year_window=2) -> set[int]:
    """Returns set of wrestlers who have, in the last two years,
    wrestled 10 or more matches in TJPW"""

    tjpw_wrestlers = all_tjpw_wrestlers()
    print(f"Total TJPW wrestlers: {len(tjpw_wrestlers)}")

    valid_years = set(range(THIS_YEAR - year_window, THIS_YEAR + 1))

    # Filter wrestlers with at least min_matches in TJPW across their entire career
    active_tjpw_wrestlers = set()
    for wid in tjpw_wrestlers:
        # Sum TJPW matches across all years
        tjpw_match_count = 0
        available_years = wrestler_db.match_years_available(wid)
        for year in valid_years:
            if year in available_years:
                match_info = wrestler_db.get_match_info(wid, year)
                tjpw_match_count += match_info.get("promotions_worked", {}).get(
                    TJPW_PROMO_ID, 0
                )

        if tjpw_match_count >= min_matches:
            active_tjpw_wrestlers.add(wid)

    active_tjpw_wrestlers.discard(-1)  # remove unknown wrestler ID if present
    return active_tjpw_wrestlers


def match_signature(match: dict) -> tuple:
    """Create a unique signature for a match to enable deduplication."""
    # Sort participants to ensure same match from different perspectives has same signature
    side_a = tuple(sorted(match.get("side_a", [])))
    side_b = tuple(sorted(match.get("side_b", [])))
    # Note that side_a indicates the victor if applicable
    # so we keep the order for that reason
    sides = (side_a, side_b)
    return (match.get("date"), match.get("promotion"), sides)


def get_deduplicated_matches(
    wrestler_ids: set[int], years: set[int] | None = None
) -> list[dict]:
    """Collect all unique matches for a set of wrestlers across specified years.

    Args:
        wrestler_ids: Set of wrestler IDs to collect matches for
        years: Optional set of years to filter. If None, uses all available years.

    Returns:
        List of unique match dictionaries
    """
    seen_signatures = set()
    unique_matches = []

    # Sort wrestlers by match count (descending) to find common matches early
    sorted_wrestlers = sorted(
        wrestler_ids,
        key=lambda w: sum(
            len(wrestler_db.get_matches(w, y))
            for y in wrestler_db.match_years_available(w)
            if years is None or y in years
        ),
        reverse=True,
    )

    for wid in sorted_wrestlers:
        available_years = wrestler_db.match_years_available(wid)
        years_to_check = available_years if years is None else (available_years & years)

        for year in years_to_check:
            matches = wrestler_db.get_matches(wid, year)

            for match in matches:
                sig = match_signature(match)
                if sig in seen_signatures:
                    continue  # Skip already processed match

                seen_signatures.add(sig)
                unique_matches.append(match)

    return unique_matches


def filter_matches_by_promotion_and_participants(
    matches: list[dict],
    promotion_id: int | None = None,
    participant_set: set[int] | None = None,
) -> list[dict]:
    """Filter matches by promotion and/or participant requirements.

    Args:
        matches: List of match dictionaries
        promotion_id: Optional promotion ID to filter by
        participant_set: Optional set of wrestler IDs - if provided, only include matches
                        where all participants on at least one side are in this set

    Returns:
        Filtered list of matches
    """
    filtered = []

    for match in matches:
        # Filter by promotion
        if promotion_id is not None and match.get("promotion") != promotion_id:
            continue

        # Filter by participants
        if participant_set is not None:
            side_a = set(match.get("side_a", []))
            side_b = set(match.get("side_b", []))

            # At least one side must have all participants in the participant_set
            if not (
                side_a.issubset(participant_set) or side_b.issubset(participant_set)
            ):
                continue

        filtered.append(match)

    return filtered


def possible_combinations(wrestler_set):
    """Generate all possible combinations of 2 to 3 wrestlers from the given set."""
    all_combos = []
    for n in range(2, 4):
        combos = combinations(sorted(wrestler_set), n)
        all_combos.extend(combos)
    return all_combos


def tjpw_combinations(min_matches=20):
    """Analyze TJPW wrestler combinations in matches."""
    active_tjpw_wrestlers = get_active_tjpw_wrestlers(min_matches)

    print("=" * 80)
    print(f"TJPW WRESTLER COMBINATION ANALYSIS")
    print("=" * 80)
    print(f"Active wrestlers (≥{min_matches} matches): {len(active_tjpw_wrestlers)}")

    potential_combos = possible_combinations(active_tjpw_wrestlers)
    print(f"Potential combinations to examine: {len(potential_combos):,}")

    # Pass 1: Get all deduplicated matches for these wrestlers
    years_to_check = {THIS_YEAR, THIS_YEAR - 1, THIS_YEAR - 2}
    all_matches = get_deduplicated_matches(active_tjpw_wrestlers)
    print(f"Total unique matches found: {len(all_matches):,}")

    # Pass 2: Filter to TJPW matches
    tjpw_matches = filter_matches_by_promotion_and_participants(
        all_matches, promotion_id=int(TJPW_PROMO_ID), participant_set=None
    )
    print(f"TJPW matches: {len(tjpw_matches):,}")
    print("=" * 80)

    # Count combinations
    combination_counts = {n: Counter() for n in range(2, 4)}
    for match in tjpw_matches:
        side_a = tuple(sorted(match.get("side_a", [])))
        side_b = tuple(sorted(match.get("side_b", [])))

        if len(side_a) != len(side_b):
            continue  # uneven sides, skip
        if len(side_a) < 2 or len(side_a) > 3:
            continue  # only interested in 2 or 3 wrestler sides
        for side in (side_a, side_b):
            combination_counts[len(side)][side] += 1

    # now count partner participations
    partner_participation = {
        n: Counter({j: 0 for j in active_tjpw_wrestlers}) for n in active_tjpw_wrestlers
    }
    for n in range(2, 4):
        for combo, count in combination_counts[n].items():
            # everyone in the combo participated with the others count times
            for wid in combo:
                if wid not in active_tjpw_wrestlers:
                    continue
                for other_wid in combo:
                    if other_wid in active_tjpw_wrestlers and other_wid != wid:
                        partner_participation[wid][other_wid] += count

    # Print partner participation analysis
    print("\n" + "=" * 80)
    print("PARTNER PARTICIPATION ANALYSIS")
    print("=" * 80)

    for wid in sorted(active_tjpw_wrestlers, key=lambda w: get_name(w)):
        participation = partner_participation[wid]
        partners = sum(1 for cnt in participation.values() if cnt > 0)
        total_team_appearances = sum(participation.values())

        print(f"\n{get_name(wid).upper()}")
        print(f"  Unique partners: {partners}/{len(active_tjpw_wrestlers) - 1}")
        print(f"  Total team match appearances: {total_team_appearances:,}")

        print(f"  Top 5 partners:")
        for i, (partner_id, count) in enumerate(participation.most_common(5), 1):
            print(f"    {i}. {get_name(partner_id):<30} {count:>4} matches")

        never_partners = [
            partner_id
            for partner_id, count in participation.items()
            if count == 0 and partner_id != wid
        ]
        if never_partners:
            print(f"  Never teamed with ({len(never_partners)}):")
            never_names = sorted(get_name(p) for p in never_partners)
            print(f"    {', '.join(never_names)}")

    # Print combination statistics
    for n in range(2, 4):
        print("\n" + "=" * 80)
        print(f"TOP {n}-WRESTLER TEAMS")
        print("=" * 80)

        for i, (combo, count) in enumerate(combination_counts[n].most_common(10), 1):
            names = [get_name(wid) for wid in combo]
            print(f"{i:2}. {' & '.join(names):<50} {count:>4} matches")

        print("\n" + "-" * 80)
        print(f"LEAST COMMON {n}-WRESTLER COMBINATIONS")
        print("-" * 80)

        bottom_combos = combination_counts[n].most_common()[:-11:-1]
        for i, (combo, count) in enumerate(bottom_combos, 1):
            names = [get_name(wid) for wid in combo]
            print(f"{i:2}. {' & '.join(names):<50} {count:>4} matches")

        total_combos = len(combination_counts[n])
        total_matches = sum(combination_counts[n].values())
        print(f"\nTotal unique {n}-wrestler combinations: {total_combos:,}")
        print(f"Total {n}-wrestler match appearances: {total_matches:,}")
        if total_combos > 0:
            avg = total_matches / total_combos
            print(f"Average appearances per combination: {avg:.1f}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    tjpw_combinations()
