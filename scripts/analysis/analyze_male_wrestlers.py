#!/usr/bin/env python
"""Analyze male wrestlers referenced in female wrestler match data."""

from collections import Counter, defaultdict
from datetime import datetime

from joshirank.joshidb import wrestler_db


def male_wrestler_statistics():
    """Report statistics about male wrestlers in the database."""
    print("=" * 70)
    print("MALE WRESTLER STATISTICS")
    print("=" * 70)

    all_ids = set(wrestler_db.all_wrestler_ids())
    female_ids = set(wrestler_db.all_female_wrestlers())
    male_ids = all_ids - female_ids

    print(f"\nTotal wrestlers in database: {len(all_ids)}")
    print(
        f"  Female wrestlers: {len(female_ids)} ({100 * len(female_ids) / len(all_ids):.1f}%)"
    )
    print(
        f"  Male/other wrestlers: {len(male_ids)} ({100 * len(male_ids) / len(all_ids):.1f}%)"
    )

    # Gender diverse among males
    gender_diverse_ids = set(wrestler_db.gender_diverse_wrestlers())
    gender_diverse_male = gender_diverse_ids - female_ids

    if gender_diverse_male:
        print(
            f"  Gender-diverse (not classified as female): {len(gender_diverse_male)}"
        )

    # Male wrestlers by promotion
    promotions = Counter()
    locations = Counter()
    for wid in male_ids:
        info = wrestler_db.get_wrestler(wid)
        promo = info.get("promotion", "Unknown")
        loc = info.get("location", "Unknown")
        promotions[promo] += 1
        locations[loc] += 1

    print(f"\nTop 15 promotions (male wrestlers):")
    for promo, count in promotions.most_common(15):
        print(f"  {promo:40} {count:4d} wrestlers")

    print(f"\nTop 10 locations (male wrestlers):")
    for loc, count in locations.most_common(10):
        loc_str = loc if loc else "Unknown"
        print(f"  {loc_str:30} {count:4d} wrestlers")


def male_wrestlers_in_female_matches():
    """Analyze male wrestlers who appear in female wrestlers' matches."""
    print("\n" + "=" * 70)
    print("MALE WRESTLERS IN FEMALE MATCHES")
    print("=" * 70)

    male_appearances = Counter()  # male_id -> appearance count
    female_opponents = defaultdict(set)  # male_id -> set of female wrestler_ids

    print("\nScanning female wrestlers' matches for male opponents...")

    for female_id in wrestler_db.all_female_wrestlers():
        colleagues = wrestler_db.get_all_colleagues(female_id)
        for colleague_id in colleagues:
            if not wrestler_db.is_female(colleague_id):
                male_appearances[colleague_id] += 1
                female_opponents[colleague_id].add(female_id)

    print(
        f"\nFound {len(male_appearances)} male wrestlers in female wrestler match data"
    )
    print(f"Total appearances: {sum(male_appearances.values())}")

    # Top male wrestlers by appearances
    print(f"\nTop 30 male wrestlers by appearances in female matches:")
    for i, (male_id, count) in enumerate(male_appearances.most_common(30), 1):
        name = wrestler_db.get_name(male_id)
        n_opponents = len(female_opponents[male_id])
        info = wrestler_db.get_wrestler(male_id)
        promo = info.get("promotion", "Unknown")[:25]
        print(
            f"  {i:2d}. {name:30} {count:4d} matches, {n_opponents:3d} opponents ({promo})"
        )

    # Statistics by appearance frequency
    frequency_buckets = Counter()
    for count in male_appearances.values():
        if count == 1:
            frequency_buckets["1 appearance"] += 1
        elif count <= 5:
            frequency_buckets["2-5 appearances"] += 1
        elif count <= 10:
            frequency_buckets["6-10 appearances"] += 1
        elif count <= 20:
            frequency_buckets["11-20 appearances"] += 1
        elif count <= 50:
            frequency_buckets["21-50 appearances"] += 1
        else:
            frequency_buckets["50+ appearances"] += 1

    print(f"\nMale wrestlers by appearance frequency:")
    for bucket in [
        "1 appearance",
        "2-5 appearances",
        "6-10 appearances",
        "11-20 appearances",
        "21-50 appearances",
        "50+ appearances",
    ]:
        if bucket in frequency_buckets:
            print(f"  {bucket:20s}: {frequency_buckets[bucket]:4d} wrestlers")


def intergender_matches_analysis():
    """Analyze intergender matches (male vs female)."""
    print("\n" + "=" * 70)
    print("INTERGENDER MATCHES ANALYSIS")
    print("=" * 70)

    female_with_male_opponents = []

    print("\nScanning for female wrestlers with male opponents...")

    for female_id in wrestler_db.all_female_wrestlers():
        colleagues = wrestler_db.get_all_colleagues(female_id)
        male_colleagues = [c for c in colleagues if not wrestler_db.is_female(c)]

        if male_colleagues:
            name = wrestler_db.get_name(female_id)
            female_with_male_opponents.append(
                {
                    "id": female_id,
                    "name": name,
                    "male_opponents": len(male_colleagues),
                    "total_colleagues": len(colleagues),
                    "percentage": 100 * len(male_colleagues) / len(colleagues)
                    if colleagues
                    else 0,
                }
            )

    female_with_male_opponents.sort(key=lambda x: x["male_opponents"], reverse=True)

    print(
        f"\nFemale wrestlers who have faced male opponents: {len(female_with_male_opponents)}"
    )

    if female_with_male_opponents:
        print(f"\nTop 30 female wrestlers by number of male opponents:")
        for i, wrestler in enumerate(female_with_male_opponents[:30], 1):
            print(
                f"  {i:2d}. {wrestler['name']:30} {wrestler['male_opponents']:3d} male opponents ({wrestler['percentage']:4.1f}% of total)"
            )

        # Statistics
        total_female = len(list(wrestler_db.all_female_wrestlers()))
        with_intergender = len(female_with_male_opponents)
        avg_male_opponents = sum(
            w["male_opponents"] for w in female_with_male_opponents
        ) / len(female_with_male_opponents)

        print(f"\nIntergender statistics:")
        print(
            f"  Female wrestlers with intergender matches: {with_intergender}/{total_female} ({100 * with_intergender / total_female:.1f}%)"
        )
        print(f"  Average male opponents per wrestler: {avg_male_opponents:.1f}")

        # Wrestlers with high percentage of male opponents
        high_percentage = [
            w
            for w in female_with_male_opponents
            if w["percentage"] > 50 and w["total_colleagues"] >= 10
        ]
        if high_percentage:
            print(f"\nFemale wrestlers with >50% male opponents (min 10 colleagues):")
            for i, wrestler in enumerate(high_percentage[:15], 1):
                print(
                    f"  {i:2d}. {wrestler['name']:30} {wrestler['male_opponents']:3d}/{wrestler['total_colleagues']:3d} colleagues ({wrestler['percentage']:4.1f}%)"
                )


def male_wrestler_data_quality():
    """Check data quality for male wrestlers."""
    print("\n" + "=" * 70)
    print("MALE WRESTLER DATA QUALITY")
    print("=" * 70)

    all_ids = set(wrestler_db.all_wrestler_ids())
    female_ids = set(wrestler_db.all_female_wrestlers())
    male_ids = all_ids - female_ids

    # Check how many have match data
    male_with_matches = 0
    male_without_matches = 0

    for wid in male_ids:
        years = wrestler_db.match_years_available(wid)
        if years:
            male_with_matches += 1
        else:
            male_without_matches += 1

    print(
        f"\nMale wrestlers with match data: {male_with_matches}/{len(male_ids)} ({100 * male_with_matches / len(male_ids):.1f}%)"
    )
    print(
        f"Male wrestlers without match data: {male_without_matches}/{len(male_ids)} ({100 * male_without_matches / len(male_ids):.1f}%)"
    )

    # Check profile data completeness
    with_promotion = 0
    with_location = 0
    with_career_start = 0

    for wid in male_ids:
        info = wrestler_db.get_wrestler(wid)
        if info.get("promotion"):
            with_promotion += 1
        if info.get("location"):
            with_location += 1
        if info.get("career_start"):
            with_career_start += 1

    print(f"\nMale wrestler profile completeness:")
    print(
        f"  With promotion data: {with_promotion}/{len(male_ids)} ({100 * with_promotion / len(male_ids):.1f}%)"
    )
    print(
        f"  With location data: {with_location}/{len(male_ids)} ({100 * with_location / len(male_ids):.1f}%)"
    )
    print(
        f"  With career_start data: {with_career_start}/{len(male_ids)} ({100 * with_career_start / len(male_ids):.1f}%)"
    )


def main():
    """Run all analysis functions."""
    print(f"\nMale Wrestler Analysis Report")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Database: {wrestler_db.path}")

    male_wrestler_statistics()
    male_wrestlers_in_female_matches()
    intergender_matches_analysis()
    male_wrestler_data_quality()

    print("\n" + "=" * 70)
    print("Analysis complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
