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

from joshirank.joshidb import get_name, get_promotion_name, wrestler_db
from joshirank.queries import guess_gender_of_wrestler


def format_timestamp(timestamp: float) -> str:
    """Convert epoch timestamp to readable date string."""
    if timestamp == 0:
        return "Never"
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def get_missing_wrestler_stats(wrestler_id: int) -> dict:
    """Gather statistics for a missing wrestler from inverse colleague data."""
    # Find wrestlers who faced this missing wrestler
    inverse_colleagues = wrestler_db.get_all_inverse_colleagues(wrestler_id)

    if not inverse_colleagues:
        return None

    # Analyze matches where this wrestler appeared
    all_promotions = Counter()
    all_countries = Counter()
    match_years = set()
    matches_analyzed = 0

    for colleague_id in inverse_colleagues:
        available_years = wrestler_db.match_years_available(colleague_id)

        for year in available_years:
            matches = wrestler_db.get_matches(colleague_id, year)

            for match in matches:
                # Check if missing wrestler appears in this match
                if wrestler_id in match.get("wrestlers", []):
                    matches_analyzed += 1
                    match_years.add(year)

                    # Track promotion
                    if match.get("promotion"):
                        all_promotions[match["promotion"]] += 1

                    # Track country
                    if match.get("country"):
                        all_countries[match["country"]] += 1

    # Get gender prediction
    gender_confidence = guess_gender_of_wrestler(wrestler_db, wrestler_id)

    return {
        "is_missing": True,
        "total_matches_found": matches_analyzed,
        "inverse_colleagues": list(inverse_colleagues),
        "total_inverse_colleagues": len(inverse_colleagues),
        "promotions_worked": all_promotions.most_common(),
        "countries_worked": all_countries.most_common(),
        "years_active": sorted(match_years),
        "gender_confidence": gender_confidence,
    }


def get_wrestler_stats(wrestler_id: int) -> dict:
    """Gather all statistics for a wrestler."""
    if not wrestler_db.wrestler_exists(wrestler_id):
        # Try to get stats from inverse colleagues
        return get_missing_wrestler_stats(wrestler_id)

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

    # Get inverse colleagues (wrestlers who had this wrestler as a colleague)
    inverse_colleagues = wrestler_db.get_all_inverse_colleagues(wrestler_id)

    # percentage of female inverse colleagues
    pct_of_inverse_female = (
        sum(1 for cid in inverse_colleagues if wrestler_db.is_female(cid))
        / len(inverse_colleagues)
        if inverse_colleagues
        else 0
    )

    return {
        "info": wrestler_info,
        "available_years": sorted(available_years),
        "total_matches": total_matches,
        "match_data_by_year": match_data_by_year,
        "top_opponents": all_opponents.most_common(10),
        "countries_worked": all_countries.most_common(),
        "promotions_worked": all_promotions.most_common(),
        "total_opponents": len(all_colleagues),
        "total_inverse_colleagues": len(inverse_colleagues),
        "female_colleagues_pct": wrestler_db.percentage_of_female_colleagues(
            wrestler_id,
        ),
        "inverse_female_colleagues_pct": pct_of_inverse_female * 100,
        "gender_confidence": guess_gender_of_wrestler(wrestler_db, wrestler_id),
    }


def display_missing_wrestler_stats(wrestler_id: int, stats: dict):
    """Display statistics for a missing wrestler based on inverse colleague data."""
    print("\n" + "=" * 80)
    print(f"MISSING WRESTLER ANALYSIS: ID {wrestler_id} (No Profile Data)")
    print("=" * 80)
    print("\n⚠️  This wrestler has no profile in the database.")
    print(
        "The following statistics are inferred from their appearances in other wrestlers' matches."
    )

    # Gender prediction
    print("\n🔍 GENDER PREDICTION")
    print("-" * 80)
    confidence = stats["gender_confidence"]
    if confidence >= 0.95:
        gender_str = "Very likely Female (95%+ confidence)"
    elif confidence >= 0.75:
        gender_str = f"Likely Female ({confidence * 100:.0f}% confidence)"
    elif confidence >= 0.5:
        gender_str = f"Possibly Female ({confidence * 100:.0f}% confidence)"
    elif confidence >= 0.3:
        gender_str = f"Possibly Male ({(1 - confidence) * 100:.0f}% confidence)"
    else:
        gender_str = f"Likely Male ({(1 - confidence) * 100:.0f}% confidence)"

    print(f"Gender: {gender_str}")
    print(f"Confidence score: {confidence:.3f}")

    # Match statistics
    print("\n📊 MATCH APPEARANCES")
    print("-" * 80)
    print(f"Total matches found: {stats['total_matches_found']}")
    print(f"Years active: {', '.join(map(str, stats['years_active']))}")
    print(f"Wrestlers who faced this wrestler: {stats['total_inverse_colleagues']}")

    # Show some of the wrestlers they faced
    if stats["inverse_colleagues"]:
        print("\n🤼 OPPONENTS (wrestlers who faced this wrestler)")
        print("-" * 80)
        # Show up to 15 opponents
        opponents_to_show = stats["inverse_colleagues"][:15]
        opp_data = []
        for opp_id in opponents_to_show:
            opp_name = get_name(opp_id)
            is_female = "♀" if wrestler_db.is_female(opp_id) else "♂"
            opp_data.append([opp_name, is_female, opp_id])
        print(tabulate(opp_data, headers=["Opponent", "", "ID"], tablefmt="simple"))
        if len(stats["inverse_colleagues"]) > 15:
            print(f"... and {len(stats['inverse_colleagues']) - 15} more opponents")

    # Promotions
    if stats["promotions_worked"]:
        print("\n🏢 PROMOTIONS (where matches occurred)")
        print("-" * 80)
        promo_data = []
        for promotion_id, count in stats["promotions_worked"][:10]:
            promo_name = get_promotion_name(int(promotion_id))
            promo_data.append([promo_name, count])
        print(tabulate(promo_data, headers=["Promotion", "Matches"], tablefmt="simple"))
        if len(stats["promotions_worked"]) > 10:
            print(f"... and {len(stats['promotions_worked']) - 10} more promotions")

    # Countries
    if stats["countries_worked"]:
        print("\n🌍 COUNTRIES (where matches occurred)")
        print("-" * 80)
        country_data = []
        for country, count in stats["countries_worked"][:10]:
            country_data.append([country, count])
        print(tabulate(country_data, headers=["Country", "Matches"], tablefmt="simple"))
        if len(stats["countries_worked"]) > 10:
            print(f"... and {len(stats['countries_worked']) - 10} more countries")

    print("\n" + "=" * 80)
    print("💡 Note: This wrestler likely doesn't have a CageMatch profile page.")
    print("   They appear in match listings but lack their own wrestler entry.")
    print("=" * 80)


def display_wrestler_stats(wrestler_id: int):
    """Display formatted statistics for a wrestler."""
    stats = get_wrestler_stats(wrestler_id)

    if stats is None:
        print(f"❌ Wrestler ID {wrestler_id} not found in database.")
        print("   No profile data and no appearances in other wrestlers' matches.")
        return

    # Check if this is a missing wrestler
    if stats.get("is_missing"):
        display_missing_wrestler_stats(wrestler_id, stats)
        return

    info = stats["info"]

    # Header
    print("\n" + "=" * 80)
    print(f"WRESTLER STATISTICS: {info.get('name', 'Unknown')} (ID: {wrestler_id})")
    print("=" * 80)

    # Basic Information
    print("\n📋 BASIC INFORMATION")
    print("-" * 80)
    confidence = stats["gender_confidence"]
    if confidence >= 0.95:
        gender_str = f"Very likely Female ({confidence * 100:.0f}% confidence)"
    elif confidence >= 0.75:
        gender_str = f"Likely Female ({confidence * 100:.0f}% confidence)"
    elif confidence >= 0.5:
        gender_str = f"Possibly Female ({confidence * 100:.0f}% confidence)"
    elif confidence >= 0.3:
        gender_str = f"Possibly Male ({(1 - confidence) * 100:.0f}% confidence)"
    else:
        gender_str = f"Likely Male ({(1 - confidence) * 100:.0f}% confidence)"
    basic_data = [
        ["Name", info.get("name", "Unknown")],
        ["Gender", "Female" if info.get("is_female") else "Male/Other"],
        ["Gender Prediction", gender_str],
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
    print(f"Total unique inverse colleagues: {stats['total_inverse_colleagues']}")
    print(f"Inverse female colleagues: {stats['inverse_female_colleagues_pct']:.1f}%")

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
        for promotion_id, count in stats["promotions_worked"][:10]:
            # Try to get promotion name, fall back to ID if not available
            promo_name = get_promotion_name(int(promotion_id))
            promo_data.append([promo_name, count])
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
