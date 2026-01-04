#!/usr/bin/env python3
"""Display comprehensive statistics for a wrestler from the database.

Usage:
    python wrestler_stats.py <wrestler_id>
    python wrestler_stats.py 9462  # Hikaru Shida
"""

import argparse
import sys
from collections import Counter
from datetime import datetime

from tabulate import tabulate

from joshirank.joshidb import get_name, wrestler_db


def format_timestamp(timestamp: float) -> str:
    """Convert epoch timestamp to readable date string."""
    if timestamp == 0:
        return "Never"
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def get_wrestler_stats(wrestler_id: int) -> dict:
    """Gather all statistics for a wrestler."""
    if not wrestler_db.wrestler_exists(wrestler_id):
        return None

    # Basic wrestler info
    wrestler_info = wrestler_db.get_wrestler(wrestler_id)

    # Get match data for all available years
    available_years = wrestler_db.match_years_available(wrestler_id)

    # Aggregate match statistics across all years
    total_matches = 0
    all_opponents = Counter()
    all_countries = Counter()
    all_promotions = Counter()
    match_data_by_year = {}

    for year in sorted(available_years):
        matches = wrestler_db.get_matches(wrestler_id, year)
        match_info = wrestler_db.get_match_info(wrestler_id, year)

        year_match_count = len(matches)
        total_matches += year_match_count

        # Aggregate opponents
        for opp_id in match_info.get("opponents", []):
            all_opponents[opp_id] += 1

        # Aggregate countries and promotions
        for country, count in match_info.get("countries_worked", {}).items():
            all_countries[country] += count
        for promotion, count in match_info.get("promotions_worked", {}).items():
            all_promotions[promotion] += count

        # Store year-specific data
        match_data_by_year[year] = {
            "match_count": year_match_count,
            "last_updated": wrestler_db.get_matches_timestamp(wrestler_id, year),
        }

    # Get all colleagues (opponents across all years)
    all_colleagues = wrestler_db.get_all_colleagues(wrestler_id)

    return {
        "info": wrestler_info,
        "available_years": sorted(available_years),
        "total_matches": total_matches,
        "match_data_by_year": match_data_by_year,
        "top_opponents": all_opponents.most_common(10),
        "countries_worked": all_countries.most_common(),
        "promotions_worked": all_promotions.most_common(),
        "total_opponents": len(all_colleagues),
        "female_colleagues_pct": wrestler_db.percentage_of_female_colleagues(
            wrestler_id
        )
        * 100,
    }


def display_wrestler_stats(wrestler_id: int):
    """Display formatted statistics for a wrestler."""
    stats = get_wrestler_stats(wrestler_id)

    if stats is None:
        print(f"❌ Wrestler ID {wrestler_id} not found in database.")
        return

    info = stats["info"]

    # Header
    print("\n" + "=" * 80)
    print(f"WRESTLER STATISTICS: {info.get('name', 'Unknown')} (ID: {wrestler_id})")
    print("=" * 80)

    # Basic Information
    print("\n📋 BASIC INFORMATION")
    print("-" * 80)
    basic_data = [
        ["Name", info.get("name", "Unknown")],
        ["Gender", "Female" if info.get("is_female") else "Male/Other"],
        ["Promotion", info.get("promotion", "Unknown")],
        ["Location", info.get("location", "Unknown")],
        ["Career Start", info.get("career_start", "Unknown")],
        ["Profile Last Updated", format_timestamp(info.get("timestamp", 0))],
    ]
    print(tabulate(basic_data, tablefmt="plain"))

    # Match Statistics
    print("\n📊 MATCH STATISTICS")
    print("-" * 80)
    print(f"Total Matches (all years): {stats['total_matches']}")
    print(f"Years with data: {len(stats['available_years'])}")
    print(f"Available years: {', '.join(map(str, stats['available_years']))}")

    # Year-by-year breakdown
    if stats["match_data_by_year"]:
        print("\n📅 MATCHES BY YEAR")
        print("-" * 80)
        year_data = []
        for year in sorted(stats["match_data_by_year"].keys(), reverse=True):
            year_info = stats["match_data_by_year"][year]
            year_data.append(
                [
                    year,
                    year_info["match_count"],
                    format_timestamp(year_info["last_updated"]),
                ]
            )
        print(
            tabulate(
                year_data,
                headers=["Year", "Matches", "Last Updated"],
                tablefmt="simple",
            )
        )

    # Opponents
    print("\n🤼 OPPONENT STATISTICS")
    print("-" * 80)
    print(f"Total unique opponents: {stats['total_opponents']}")
    print(f"Female colleagues: {stats['female_colleagues_pct']:.1f}%")

    if stats["top_opponents"]:
        print("\nTop 10 Most Frequent Opponents:")
        opp_data = []
        for opp_id, count in stats["top_opponents"]:
            opp_name = get_name(opp_id)
            is_female = "♀" if wrestler_db.is_female(opp_id) else "♂"
            opp_data.append([opp_name, is_female, count])
        print(
            tabulate(opp_data, headers=["Opponent", "", "Matches"], tablefmt="simple")
        )

    # Geographic Statistics
    if stats["countries_worked"]:
        print("\n🌍 COUNTRIES WORKED")
        print("-" * 80)
        country_data = []
        for country, count in stats["countries_worked"][:10]:
            country_data.append([country, count])
        print(tabulate(country_data, headers=["Country", "Matches"], tablefmt="simple"))
        if len(stats["countries_worked"]) > 10:
            print(f"... and {len(stats['countries_worked']) - 10} more countries")

    # Promotion Statistics
    if stats["promotions_worked"]:
        print("\n🏢 PROMOTIONS WORKED")
        print("-" * 80)
        promo_data = []
        for promotion, count in stats["promotions_worked"][:10]:
            promo_data.append([promotion, count])
        print(tabulate(promo_data, headers=["Promotion", "Matches"], tablefmt="simple"))
        if len(stats["promotions_worked"]) > 10:
            print(f"... and {len(stats['promotions_worked']) - 10} more promotions")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Display comprehensive statistics for a wrestler from the database."
    )
    parser.add_argument("wrestler_id", type=int, help="CageMatch wrestler ID")

    args = parser.parse_args()

    display_wrestler_stats(args.wrestler_id)


if __name__ == "__main__":
    main()
