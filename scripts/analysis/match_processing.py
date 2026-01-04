"""Takes a look at how well cagematch match data is processed.

The main goal is to identify HTML scraping issues or other problems
that lead to missing, incomplete, or corrupted match data. Addtionally,
identifying opportunities for improving data quality or coverage is useful.

This script can also reprocess match data from the database using the
current parsing logic to identify differences and validate improvements.
"""

import json

from bs4 import BeautifulSoup

from joshirank.cagematch.cm_match import parse_match
from joshirank.joshidb import WrestlerDb, wrestler_db


def investigate_wrestler_duplication(sampled_matches: list[list[dict]]):
    """Find and investigate matches where a wrestler appears on both sides."""

    duplication_cases = []

    for match_set in sampled_matches:
        for old_match in match_set:
            raw_html = old_match.get("raw_html", "")
            if not raw_html:
                continue

            try:
                soup = BeautifulSoup(raw_html, "html.parser")
                match_row = soup.find("tr")
                if not match_row:
                    continue

                new_match = parse_match(match_row)

                # Check for duplicates in new parse
                side_a = set(new_match.get("side_a", []))
                side_b = set(new_match.get("side_b", []))
                duplicates = side_a & side_b

                if duplicates:
                    # Get readable HTML snippet
                    match_card = match_row.find(class_="MatchCard")
                    if match_card:
                        card_text = match_card.get_text()
                    else:
                        card_text = match_row.get_text()[:200]

                    duplication_cases.append(
                        {
                            "duplicate_wrestlers": list(duplicates),
                            "side_a": new_match.get("side_a"),
                            "side_b": new_match.get("side_b"),
                            "sides": new_match.get("sides"),
                            "is_victory": new_match.get("is_victory"),
                            "is_multi_sided": new_match.get("is_multi_sided"),
                            "match_type": new_match.get("match_type"),
                            "card_text": card_text,
                            "raw_html": raw_html,
                        }
                    )
            except Exception as e:
                pass

    # Print detailed report
    print("\n" + "=" * 80)
    print("WRESTLER DUPLICATION INVESTIGATION")
    print("=" * 80)
    print(f"Found {len(duplication_cases)} matches with wrestler duplication\n")

    for i, case in enumerate(duplication_cases, 1):
        print(f"\nCase {i}:")
        print(f"  Duplicate wrestler(s): {case['duplicate_wrestlers']}")
        print(f"  Match type: {case['match_type']}")
        print(f"  Is victory: {case['is_victory']}")
        print(f"  Is multi-sided: {case['is_multi_sided']}")
        print(f"  Side A: {case['side_a']}")
        print(f"  Side B: {case['side_b']}")
        if case["sides"]:
            print(f"  Sides structure:")
            for j, side in enumerate(case["sides"]):
                print(f"    Side {j}: {side}")
        print(f"  Card text: {case['card_text'][:200]}")
        print(f"  Raw HTML snippet:")
        html_snippet = case["raw_html"]
        # Find MatchCard section
        if "MatchCard" in html_snippet:
            start = html_snippet.find("MatchCard")
            end = html_snippet.find("</span>", start) + 7
            print(f"    {html_snippet[start:end][:500]}")
        else:
            print(f"    {html_snippet[:300]}")
        print()

    return duplication_cases


def analyze_tag_team_extraction(sampled_matches: list[list[dict]]):
    """Analyze options for extracting tag team information from match data."""

    team_data = {
        "matches_with_team_links": [],  # Matches with id=28 or id=29 links
        "matches_with_team_names": [],  # Matches with named teams in parentheses
        "tag_matches": [],  # All tag team matches (2+ wrestlers per side)
        "team_link_examples": [],
        "team_name_examples": [],
    }

    stats = {
        "total_matches": 0,
        "tag_matches_count": 0,
        "matches_with_team_links": 0,
        "matches_with_team_names": 0,
        "team_ids_found": set(),
    }

    import re

    for match_set in sampled_matches:
        for match in match_set:
            stats["total_matches"] += 1
            raw_html = match.get("raw_html", "")
            side_a = match.get("side_a", [])
            side_b = match.get("side_b", [])

            # Check if it's a tag match
            is_tag = len(side_a) >= 2 or len(side_b) >= 2
            if is_tag:
                stats["tag_matches_count"] += 1
                team_data["tag_matches"].append(match)

            if not raw_html:
                continue

            # Look for team links (id=28 for tag teams, id=29 for stables)
            team_link_pattern = re.compile(
                r'<a href="\?id=(28|29)&amp;nr=(\d+)[^"]*">([^<]+)</a>'
            )
            team_links = team_link_pattern.findall(raw_html)

            if team_links:
                stats["matches_with_team_links"] += 1
                for link_type, team_id, team_name in team_links:
                    stats["team_ids_found"].add(int(team_id))

                if len(team_data["team_link_examples"]) < 10:
                    team_data["team_link_examples"].append(
                        {
                            "side_a": side_a,
                            "side_b": side_b,
                            "team_links": team_links,
                            "html_snippet": raw_html[
                                raw_html.find("MatchCard") : raw_html.find("MatchCard")
                                + 400
                            ]
                            if "MatchCard" in raw_html
                            else raw_html[:400],
                        }
                    )

            # Look for team names in parentheses pattern: "Team Name (Wrestler1 & Wrestler2)"
            team_name_pattern = re.compile(r">([^<(]+)\s*\((?:[^)]+&[^)]+)\)")
            team_names = team_name_pattern.findall(raw_html)

            if team_names and is_tag:
                stats["matches_with_team_names"] += 1
                if len(team_data["team_name_examples"]) < 10:
                    soup = BeautifulSoup(raw_html, "html.parser")
                    match_card = soup.find(class_="MatchCard")
                    card_text = match_card.get_text() if match_card else ""

                    team_data["team_name_examples"].append(
                        {
                            "side_a": side_a,
                            "side_b": side_b,
                            "team_names": team_names,
                            "card_text": card_text,
                            "html_snippet": raw_html[
                                raw_html.find("MatchCard") : raw_html.find("MatchCard")
                                + 400
                            ]
                            if "MatchCard" in raw_html
                            else raw_html[:400],
                        }
                    )

    # Print report
    print("\n" + "=" * 80)
    print("TAG TEAM EXTRACTION ANALYSIS")
    print("=" * 80)
    print(f"Total matches analyzed: {stats['total_matches']:,}")
    print(
        f"Tag matches (2+ per side): {stats['tag_matches_count']:,} ({100 * stats['tag_matches_count'] / stats['total_matches']:.1f}%)"
    )
    print(f"Matches with team links (id=28/29): {stats['matches_with_team_links']:,}")
    print(f"Matches with team name patterns: {stats['matches_with_team_names']:,}")
    print(f"Unique team IDs found: {len(stats['team_ids_found'])}")
    print()

    # Show examples of team links
    if team_data["team_link_examples"]:
        print("\n" + "-" * 80)
        print("EXAMPLES OF TEAM LINKS (id=28 or id=29)")
        print("-" * 80)
        for i, ex in enumerate(team_data["team_link_examples"][:5], 1):
            print(f"\nExample {i}:")
            print(f"  Side A: {ex['side_a']}")
            print(f"  Side B: {ex['side_b']}")
            print(f"  Team links found:")
            for link_type, team_id, team_name in ex["team_links"]:
                link_type_name = "Tag Team" if link_type == "28" else "Stable"
                print(f"    {link_type_name} ID {team_id}: {team_name}")
            print(f"  HTML snippet:")
            print(f"    {ex['html_snippet'][:300]}...")

    # Show examples of team name patterns
    if team_data["team_name_examples"]:
        print("\n" + "-" * 80)
        print("EXAMPLES OF TEAM NAME PATTERNS")
        print("-" * 80)
        for i, ex in enumerate(team_data["team_name_examples"][:5], 1):
            print(f"\nExample {i}:")
            print(f"  Side A: {ex['side_a']}")
            print(f"  Side B: {ex['side_b']}")
            print(f"  Team names found: {ex['team_names']}")
            print(f"  Card text: {ex['card_text'][:200]}")
            print(f"  HTML snippet:")
            print(f"    {ex['html_snippet'][:300]}...")

    # Analysis summary
    print("\n" + "=" * 80)
    print("EXTRACTION OPTIONS ANALYSIS")
    print("=" * 80)
    print("\nOption 1: Extract team links (id=28 for tag teams, id=29 for stables)")
    print(
        f"  Coverage: {stats['matches_with_team_links']} matches ({100 * stats['matches_with_team_links'] / stats['tag_matches_count']:.1f}% of tag matches)"
    )
    print(f"  Pros: Provides team IDs and names directly")
    print(f"  Cons: Only available when teams are linked in HTML")

    print("\nOption 2: Extract team names from text patterns")
    print(
        f"  Coverage: {stats['matches_with_team_names']} matches ({100 * stats['matches_with_team_names'] / stats['tag_matches_count']:.1f}% of tag matches)"
    )
    print(f"  Pros: Can capture team names even without IDs")
    print(f"  Cons: Requires pattern matching, may have false positives")

    print("\nOption 3: No extraction (current approach)")
    print(f"  Coverage: All matches")
    print(f"  Pros: Simple, no parsing errors")
    print(f"  Cons: Loses team information")

    return team_data


def sample_matches(wrestler_db: WrestlerDb, sample_size: int) -> list[dict]:
    """Sample matches from the database to analyze data quality.

    Args:
        wrestler_db: WrestlerDb instance
        sample_size: Number of non-empty match rows to sample

    Returns:
        List of match arrays (each containing one or more match dicts)
    """
    # Select only rows with non-empty match arrays
    sql = """
    SELECT cm_matches_json FROM matches 
    WHERE json_array_length(cm_matches_json) > 0
    ORDER BY RANDOM() 
    LIMIT ?
    """
    match_rows = wrestler_db._select_and_fetchall(sql, (sample_size,))
    # deserialize JSON data
    matches = [json.loads(row[0]) for row in match_rows]
    return matches


def analyze_data_quality(sampled_matches: list[list[dict]]):
    """Analyze data quality focusing on winner detection, missing wrestlers, and side accuracy."""

    issues = {
        "missing_wrestler_sentinel": [],  # matches with -1 wrestler ID
        "suspicious_sides": [],  # sides that don't make sense
        "unclear_winner": [],  # can't determine winner from HTML
        "side_mismatch": [],  # wrestlers list doesn't match sides
    }

    stats = {
        "multi_sided_matches": 0,  # Properly detected multi-sided matches
        "two_sided_matches": 0,  # Traditional two-sided matches
    }

    total_matches = 0

    for match_set in sampled_matches:
        for match in match_set:
            total_matches += 1
            html = match.get("raw_html", "")
            wrestlers = match.get("wrestlers", [])
            side_a = match.get("side_a", [])
            side_b = match.get("side_b", [])
            is_victory = match.get("is_victory", False)
            is_multi_sided = match.get("is_multi_sided", False)
            sides = match.get("sides", None)

            # Track multi-sided matches
            if is_multi_sided:
                stats["multi_sided_matches"] += 1
            else:
                stats["two_sided_matches"] += 1

            # Check for -1 sentinel
            if -1 in wrestlers or -1 in side_a or -1 in side_b:
                issues["missing_wrestler_sentinel"].append(
                    {
                        "wrestlers": wrestlers,
                        "side_a": side_a,
                        "side_b": side_b,
                        "sides": sides,
                        "is_multi_sided": is_multi_sided,
                        "html_snippet": html[
                            html.find("MatchCard") : html.find("MatchCard") + 300
                        ]
                        if "MatchCard" in html
                        else html[:300],
                    }
                )

            # Check that wrestlers = side_a + side_b
            combined_sides = set(side_a + side_b)
            wrestlers_set = set(wrestlers)
            if combined_sides != wrestlers_set:
                issues["side_mismatch"].append(
                    {
                        "wrestlers": wrestlers,
                        "side_a": side_a,
                        "side_b": side_b,
                        "sides": sides,
                        "is_multi_sided": is_multi_sided,
                        "missing_from_sides": wrestlers_set - combined_sides,
                        "extra_in_sides": combined_sides - wrestlers_set,
                    }
                )

            # Check for suspicious side configurations
            if len(side_a) == 0 or len(side_b) == 0:
                issues["suspicious_sides"].append(
                    {
                        "side_a": side_a,
                        "side_b": side_b,
                        "sides": sides,
                        "is_multi_sided": is_multi_sided,
                        "html_snippet": html[
                            html.find("MatchCard") : html.find("MatchCard") + 200
                        ]
                        if "MatchCard" in html
                        else html[:200],
                    }
                )

            # Check if we can verify the winner from HTML
            if is_victory:
                # Should have "defeats" or "defeat" in HTML
                if (
                    "defeat" not in html.lower()
                    and "Referee" not in html
                    and "DQ" not in html
                ):
                    issues["unclear_winner"].append(
                        {
                            "side_a": side_a,
                            "side_b": side_b,
                            "is_victory": is_victory,
                            "html_snippet": html[
                                html.find("MatchCard") : html.find("MatchCard") + 250
                            ]
                            if "MatchCard" in html
                            else html[:250],
                        }
                    )

    # Print report
    print("=" * 80)
    print("DATA QUALITY ANALYSIS REPORT")
    print("=" * 80)
    print(f"Total matches analyzed: {total_matches:,}")
    print(f"Multi-sided matches: {stats['multi_sided_matches']:,}")
    print(f"Two-sided matches: {stats['two_sided_matches']:,}")
    print()

    for issue_type, issue_list in issues.items():
        if issue_list:
            print(f"\n{issue_type.upper().replace('_', ' ')}: {len(issue_list)} issues")
            print("-" * 80)
            # Show first 3 examples
            for i, example in enumerate(issue_list[:3], 1):
                print(f"\nExample {i}:")
                for key, value in example.items():
                    if key == "html_snippet":
                        print(f"  {key}: {value[:200]}...")
                    else:
                        print(f"  {key}: {value}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for issue_type, issue_list in issues.items():
        pct = 100 * len(issue_list) / total_matches if total_matches > 0 else 0
        status = "✓" if len(issue_list) == 0 else "⚠" if pct < 1 else "✗"
        print(
            f"{status} {issue_type.replace('_', ' ').title():<35} {len(issue_list):>6} ({pct:>5.2f}%)"
        )


def reprocess_matches(sampled_matches: list[list[dict]]):
    """Reprocess match HTML using current parsing logic and compare with stored data."""

    comparison = {
        "total_matches": 0,
        "successfully_reparsed": 0,
        "parse_errors": [],
        "version_changes": [],
        "new_multi_sided": [],  # Old data didn't detect as multi-sided, new does
        "side_differences": [],  # Different side composition
        "missing_sides_field": 0,  # Old data missing sides field
    }

    for match_set in sampled_matches:
        for old_match in match_set:
            comparison["total_matches"] += 1

            # Check if old data has sides field
            if "sides" not in old_match:
                comparison["missing_sides_field"] += 1

            raw_html = old_match.get("raw_html", "")
            if not raw_html:
                comparison["parse_errors"].append(
                    {"error": "No raw_html in stored match", "old_match": old_match}
                )
                continue

            try:
                # Reparse the HTML
                soup = BeautifulSoup(raw_html, "html.parser")
                match_row = soup.find("tr")
                if not match_row:
                    comparison["parse_errors"].append(
                        {
                            "error": "No tr element found in HTML",
                            "html_snippet": raw_html[:200],
                        }
                    )
                    continue

                new_match = parse_match(match_row)
                comparison["successfully_reparsed"] += 1

                # Compare versions
                old_version = old_match.get("version", 1)
                new_version = new_match.get("version", 1)
                if old_version != new_version:
                    comparison["version_changes"].append(
                        {
                            "old_version": old_version,
                            "new_version": new_version,
                            "old_has_sides": "sides" in old_match,
                            "new_has_sides": "sides" in new_match,
                        }
                    )

                # Check for newly detected multi-sided matches
                old_multi = old_match.get("is_multi_sided", False)
                new_multi = new_match.get("is_multi_sided", False)
                if new_multi and not old_multi:
                    comparison["new_multi_sided"].append(
                        {
                            "old_side_a": old_match.get("side_a"),
                            "old_side_b": old_match.get("side_b"),
                            "new_sides": new_match.get("sides"),
                            "match_type": new_match.get("match_type"),
                            "html_snippet": raw_html[
                                raw_html.find("MatchCard") : raw_html.find("MatchCard")
                                + 300
                            ]
                            if "MatchCard" in raw_html
                            else raw_html[:300],
                        }
                    )

                # Compare side compositions
                old_side_a = set(old_match.get("side_a", []))
                old_side_b = set(old_match.get("side_b", []))
                new_side_a = set(new_match.get("side_a", []))
                new_side_b = set(new_match.get("side_b", []))

                if old_side_a != new_side_a or old_side_b != new_side_b:
                    comparison["side_differences"].append(
                        {
                            "old_side_a": sorted(old_side_a),
                            "old_side_b": sorted(old_side_b),
                            "new_side_a": sorted(new_side_a),
                            "new_side_b": sorted(new_side_b),
                            "old_sides": old_match.get("sides"),
                            "new_sides": new_match.get("sides"),
                            "match_type": new_match.get("match_type"),
                        }
                    )

            except Exception as e:
                comparison["parse_errors"].append(
                    {
                        "error": str(e),
                        "html_snippet": raw_html[:200] if raw_html else "No HTML",
                    }
                )

    # Print report
    print("\n" + "=" * 80)
    print("REPROCESSING COMPARISON REPORT")
    print("=" * 80)
    print(f"Total matches: {comparison['total_matches']:,}")
    print(f"Successfully reparsed: {comparison['successfully_reparsed']:,}")
    print(f"Parse errors: {len(comparison['parse_errors']):,}")
    print(f"Missing sides field (old data): {comparison['missing_sides_field']:,}")
    print()

    if comparison["version_changes"]:
        print(f"\nVERSION CHANGES: {len(comparison['version_changes'])} matches")
        print("-" * 80)
        v1_to_v2 = sum(
            1
            for x in comparison["version_changes"]
            if x["old_version"] == 1 and x["new_version"] == 2
        )
        print(f"  Version 1 → 2: {v1_to_v2}")
        if len(comparison["version_changes"]) > 0:
            print(f"\nExample:")
            ex = comparison["version_changes"][0]
            for key, value in ex.items():
                print(f"    {key}: {value}")

    if comparison["new_multi_sided"]:
        print(
            f"\nNEWLY DETECTED MULTI-SIDED MATCHES: {len(comparison['new_multi_sided'])} matches"
        )
        print("-" * 80)
        for i, ex in enumerate(comparison["new_multi_sided"][:3], 1):
            print(f"\nExample {i}:")
            print(f"  match_type: {ex['match_type']}")
            print(f"  old_side_a: {ex['old_side_a']}")
            print(f"  old_side_b: {ex['old_side_b']}")
            print(f"  new_sides: {ex['new_sides']}")
            print(f"  html: {ex['html_snippet'][:150]}...")

    if comparison["side_differences"]:
        print(
            f"\nSIDE COMPOSITION DIFFERENCES: {len(comparison['side_differences'])} matches"
        )
        print("-" * 80)
        for i, ex in enumerate(comparison["side_differences"][:3], 1):
            print(f"\nExample {i}:")
            print(f"  match_type: {ex['match_type']}")
            print(f"  old_side_a: {ex['old_side_a']}")
            print(f"  old_side_b: {ex['old_side_b']}")
            print(f"  new_side_a: {ex['new_side_a']}")
            print(f"  new_side_b: {ex['new_side_b']}")
            if ex["new_sides"]:
                print(f"  new_sides: {ex['new_sides']}")

    if comparison["parse_errors"]:
        print(f"\nPARSE ERRORS: {len(comparison['parse_errors'])} errors")
        print("-" * 80)
        for i, ex in enumerate(comparison["parse_errors"][:3], 1):
            print(f"\nError {i}:")
            print(f"  error: {ex['error']}")
            if "html_snippet" in ex:
                print(f"  html: {ex['html_snippet'][:150]}...")

    return comparison


if __name__ == "__main__":
    db = wrestler_db
    sampled_matches = sample_matches(db, sample_size=1000)
    print(f"Sampled {len(sampled_matches)} match rows from the database.")

    # Output sampled matches to a JSON file for analysis
    with open("sampled_matches.json", "w", encoding="utf-8") as f:
        json.dump(sampled_matches, f, indent=2, ensure_ascii=False)
    print("Sampled matches written to sampled_matches.json\n")

    # Run data quality analysis on original data
    print("\n" + "=" * 80)
    print("ANALYZING ORIGINAL DATABASE DATA")
    print("=" * 80)
    analyze_data_quality(sampled_matches)

    # Reprocess matches and compare
    print("\n" + "=" * 80)
    print("REPROCESSING WITH CURRENT PARSING LOGIC")
    print("=" * 80)
    reprocess_matches(sampled_matches)

    # Investigate wrestler duplication cases
    investigate_wrestler_duplication(sampled_matches)

    # Analyze tag team extraction options
    analyze_tag_team_extraction(sampled_matches)
