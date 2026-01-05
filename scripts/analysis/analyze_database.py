#!/usr/bin/env python
"""Analyze database contents and report interesting statistics."""

import time
from collections import Counter, defaultdict
from datetime import datetime

from joshirank.joshidb import wrestler_db


def format_age(timestamp: float) -> str:
    """Format timestamp age in human-readable format."""
    if timestamp == 0:
        return "never"
    age = time.time() - timestamp
    days = age / 86400
    if days < 1:
        return f"{int(age / 3600)}h ago"
    elif days < 30:
        return f"{int(days)}d ago"
    elif days < 365:
        return f"{int(days / 30)}mo ago"
    else:
        return f"{days / 365:.1f}y ago"


def wrestler_statistics():
    """Report statistics about wrestlers in the database."""
    print("=" * 70)
    print("WRESTLER STATISTICS")
    print("=" * 70)

    all_ids = wrestler_db.all_wrestler_ids()
    female_ids = list(wrestler_db.all_female_wrestlers())
    gender_diverse_ids = list(wrestler_db.gender_diverse_wrestlers())

    print(f"\nTotal wrestlers: {len(all_ids)}")
    print(
        f"  Female wrestlers: {len(female_ids)} ({100 * len(female_ids) / len(all_ids):.1f}%)"
    )
    print(f"  Gender-diverse wrestlers: {len(gender_diverse_ids)}")
    print(f"  Other wrestlers: {len(all_ids) - len(female_ids)}")

    # Wrestlers by promotion
    promotions = Counter()
    locations = Counter()
    for wid in female_ids:
        info = wrestler_db.get_wrestler(wid)
        promo = info.get("promotion", "Unknown")
        loc = info.get("location", "Unknown")
        promotions[promo] += 1
        locations[loc] += 1

    print(f"\nTop 15 promotions (female wrestlers):")
    for promo, count in promotions.most_common(15):
        print(f"  {promo:40} {count:4d} wrestlers")

    print(f"\nTop 10 locations (female wrestlers):")
    for loc, count in locations.most_common(10):
        loc_str = loc if loc else "Unknown"
        print(f"  {loc_str:30} {count:4d} wrestlers")


def match_statistics():
    """Report statistics about match data."""
    print("\n" + "=" * 70)
    print("MATCH DATA STATISTICS")
    print("=" * 70)

    # Matches by year
    years = defaultdict(lambda: {"wrestlers": 0, "total_matches": 0})

    for wid in wrestler_db.all_female_wrestlers():
        available_years = wrestler_db.match_years_available(wid)
        for year in available_years:
            info = wrestler_db.get_match_info(wid, year)
            years[year]["wrestlers"] += 1
            years[year]["total_matches"] += info.get("match_count", 0)

    print(f"\nMatch data by year:")
    for year in sorted(years.keys(), reverse=True):
        data = years[year]
        avg_matches = (
            data["total_matches"] / data["wrestlers"] if data["wrestlers"] > 0 else 0
        )
        print(
            f"  {year}: {data['wrestlers']:4d} wrestlers, {data['total_matches']:6d} total matches, {avg_matches:.1f} avg/wrestler"
        )

    # Most active wrestlers (2024-2025)
    print(f"\nTop 20 most active wrestlers (2024-2025):")
    activity = []
    for wid in wrestler_db.all_female_wrestlers():
        total = 0
        for year in [2024, 2025]:
            info = wrestler_db.get_match_info(wid, year)
            total += info.get("match_count", 0)
        if total > 0:
            name = wrestler_db.get_name(wid)
            activity.append((name, total, wid))

    activity.sort(key=lambda x: x[1], reverse=True)
    for i, (name, count, wid) in enumerate(activity[:20], 1):
        info = wrestler_db.get_wrestler(wid)
        promo = info.get("promotion", "Unknown")[:30]
        print(f"  {i:2d}. {name:30} {count:3d} matches ({promo})")


def freshness_statistics():
    """Report statistics about data freshness."""
    print("\n" + "=" * 70)
    print("DATA FRESHNESS STATISTICS")
    print("=" * 70)

    # Profile freshness
    profile_ages = []
    for wid in wrestler_db.all_female_wrestlers():
        info = wrestler_db.get_wrestler(wid)
        timestamp = info.get("timestamp", 0)
        if timestamp > 0:
            profile_ages.append(time.time() - timestamp)

    if profile_ages:
        profile_ages.sort()
        avg_age = sum(profile_ages) / len(profile_ages)
        median_age = profile_ages[len(profile_ages) // 2]

        print(f"\nFemale wrestler profiles:")
        print(f"  Total profiles: {len(profile_ages)}")
        print(f"  Average age: {avg_age / 86400:.1f} days")
        print(f"  Median age: {median_age / 86400:.1f} days")
        print(f"  Oldest: {max(profile_ages) / 86400:.1f} days")
        print(f"  Newest: {min(profile_ages) / 86400:.1f} days")

    # Match data freshness by year
    print(f"\nMatch data freshness:")
    for year in [2026, 2025, 2024, 2023]:
        timestamps = []
        for wid in wrestler_db.all_female_wrestlers():
            if year in wrestler_db.match_years_available(wid):
                ts = wrestler_db.get_matches_timestamp(wid, year)
                if ts > 0:
                    timestamps.append(ts)

        if timestamps:
            avg_ts = sum(timestamps) / len(timestamps)
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            print(
                f"  {year}: {len(timestamps):4d} datasets, avg: {format_age(avg_ts):10s}, oldest: {format_age(min_ts):10s}, newest: {format_age(max_ts):10s}"
            )


def coverage_statistics():
    """Report statistics about data coverage."""
    print("\n" + "=" * 70)
    print("DATA COVERAGE STATISTICS")
    print("=" * 70)

    # Year coverage
    year_coverage = Counter()
    for wid in wrestler_db.all_female_wrestlers():
        years = wrestler_db.match_years_available(wid)
        for year in years:
            year_coverage[year] += 1

    print(f"\nYear coverage (female wrestlers with match data):")
    for year in sorted(year_coverage.keys(), reverse=True):
        if year >= 2020:  # Only show recent years
            count = year_coverage[year]
            total_female = len(list(wrestler_db.all_female_wrestlers()))
            pct = 100 * count / total_female
            print(f"  {year}: {count:4d} wrestlers ({pct:5.1f}%)")

    # Missing data
    missing_2026 = 0
    missing_2025 = 0
    active_count = 0

    for wid in wrestler_db.all_female_wrestlers():
        years = wrestler_db.match_years_available(wid)
        # Check if active (has 2024 or 2025 data)
        if 2024 in years or 2025 in years:
            active_count += 1
            if 2026 not in years:
                missing_2026 += 1
        if 2025 not in years:
            missing_2025 += 1

    print(f"\nMissing recent year data:")
    print(f"  Active wrestlers (have 2024/2025 data): {active_count}")
    print(
        f"  Active wrestlers missing 2026 data: {missing_2026} ({100 * missing_2026 / active_count:.1f}%)"
    )
    print(f"  All female wrestlers missing 2025 data: {missing_2025}")

    # Countries worked
    all_countries = Counter()
    for wid in wrestler_db.all_female_wrestlers():
        for year in [2024, 2025]:
            info = wrestler_db.get_match_info(wid, year)
            countries = info.get("countries_worked", {})
            for country, count in countries.items():
                all_countries[country] += count

    print(f"\nTop 10 countries by match count (2024-2025):")
    for country, count in all_countries.most_common(10):
        print(f"  {country:30} {count:5d} matches")


def historical_coverage_statistics():
    """Report statistics about historical data coverage."""
    print("\n" + "=" * 70)
    print("HISTORICAL COVERAGE ANALYSIS")
    print("=" * 70)

    # Career start statistics
    wrestlers_with_career_start = 0
    career_start_years = []

    for wid in wrestler_db.all_female_wrestlers():
        info = wrestler_db.get_wrestler(wid)
        career_start = info.get("career_start")
        if career_start:
            wrestlers_with_career_start += 1
            # Extract year from career_start (may be YYYY or YYYY-MM-DD)
            year_str = str(career_start)[:4]
            if year_str.isdigit():
                career_start_years.append(int(year_str))

    total_female = len(list(wrestler_db.all_female_wrestlers()))
    print(f"\nCareer start data availability:")
    print(
        f"  Female wrestlers with career_start: {wrestlers_with_career_start}/{total_female} ({100 * wrestlers_with_career_start / total_female:.1f}%)"
    )

    if career_start_years:
        from collections import Counter

        decades = Counter()
        for year in career_start_years:
            decade = (year // 10) * 10
            decades[decade] += 1

        print(f"  Career starts by decade:")
        for decade in sorted(decades.keys()):
            print(f"    {decade}s: {decades[decade]:4d} wrestlers")

    # Analyze incomplete scraping - wrestlers with stub years not yet filled
    print(f"\n{'=' * 70}")
    print("INCOMPLETE SCRAPING ANALYSIS")
    print(f"{'=' * 70}")

    import time

    YEAR_IN_SECONDS = 365 * 86400
    single_stub_wrestlers = []
    multi_stub_wrestlers = []

    for wid in wrestler_db.all_female_wrestlers():
        info = wrestler_db.get_wrestler(wid)
        career_start = info.get("career_start")
        years = wrestler_db.match_years_available(wid)

        if not years:
            continue

        # Get career length
        career_start_year = None
        if career_start:
            year_str = str(career_start)[:4]
            if year_str.isdigit():
                career_start_year = int(year_str)

        # Check each year for stub status (0 matches AND stale = stub)
        stub_years = []
        populated_years = []
        for year in years:
            match_info = wrestler_db.get_match_info(wid, year)
            match_count = match_info.get("match_count", 0)
            timestamp = wrestler_db.get_matches_timestamp(wid, year)

            # A year is a stub if it has no matches AND data is over a year old
            age = time.time() - timestamp if timestamp > 0 else float("inf")
            is_stale = age > YEAR_IN_SECONDS

            if match_count == 0 and is_stale:
                stub_years.append(year)
            elif match_count > 0:
                populated_years.append(year)

        # Case 1: Only one populated year but has a long career
        if len(populated_years) == 1 and career_start_year:
            career_length = 2026 - career_start_year
            if career_length >= 3:  # At least 3 year career
                total_matches = sum(
                    wrestler_db.get_match_info(wid, year).get("match_count", 0)
                    for year in populated_years
                )
                single_stub_wrestlers.append(
                    {
                        "id": wid,
                        "name": wrestler_db.get_name(wid),
                        "career_start_year": career_start_year,
                        "career_length": career_length,
                        "populated_year": populated_years[0],
                        "total_matches": total_matches,
                        "stub_count": len(stub_years),
                    }
                )

        # Case 2: Multiple stub years (need to be scraped)
        if len(stub_years) >= 3:  # At least 3 stubs
            total_matches = sum(
                wrestler_db.get_match_info(wid, year).get("match_count", 0)
                for year in populated_years
            )
            multi_stub_wrestlers.append(
                {
                    "id": wid,
                    "name": wrestler_db.get_name(wid),
                    "career_start_year": career_start_year,
                    "stub_count": len(stub_years),
                    "stub_years": sorted(stub_years),
                    "populated_count": len(populated_years),
                    "total_matches": total_matches,
                }
            )

    # Sort and display single stub wrestlers (longest careers first)
    single_stub_wrestlers.sort(key=lambda x: x["career_length"], reverse=True)

    print(
        f"\nWrestlers with single populated year but long careers: {len(single_stub_wrestlers)}"
    )
    print("(These need initial scraping to discover all active years)")
    if single_stub_wrestlers:
        print(f"\nTop 20 wrestlers needing discovery scraping:")
        for i, w in enumerate(single_stub_wrestlers[:20], 1):
            print(
                f"  {i:2d}. {w['name']:30} Career: {w['career_start_year']}-present ({w['career_length']:2d} years), "
                f"{w['total_matches']:3d} matches in {w['populated_year']}, {w['stub_count']} stubs"
            )

    # Sort and display multi stub wrestlers (most stubs first)
    multi_stub_wrestlers.sort(key=lambda x: x["stub_count"], reverse=True)

    print(f"\nWrestlers with multiple stub years: {len(multi_stub_wrestlers)}")
    print("(These have discovered years but need data to be filled in)")
    if multi_stub_wrestlers:
        print(f"\nTop 20 wrestlers with most stub years needing data:")
        for i, w in enumerate(multi_stub_wrestlers[:20], 1):
            recent_stubs = [y for y in w["stub_years"] if y >= 2020]
            stub_info = (
                f"{len(recent_stubs)} recent (2020+)"
                if recent_stubs
                else f"all pre-2020"
            )
            career_info = (
                f"debut: {w['career_start_year']}"
                if w["career_start_year"]
                else "unknown debut"
            )
            print(
                f"  {i:2d}. {w['name']:30} {w['stub_count']:2d} stubs ({stub_info}), "
                f"{w['populated_count']:2d} populated, {career_info}"
            )

    # Check for data quality issues (matches before career start)
    data_quality_issues = []
    for wid in wrestler_db.all_female_wrestlers():
        years = wrestler_db.match_years_available(wid)
        if not years:
            continue

        info = wrestler_db.get_wrestler(wid)
        career_start = info.get("career_start")
        career_start_year = None

        if career_start:
            year_str = str(career_start)[:4]
            if year_str.isdigit():
                career_start_year = int(year_str)

        min_year = min(years)

        # Check for data quality issues (matches before career start)
        if career_start_year and min_year < career_start_year:
            data_quality_issues.append(
                {
                    "id": wid,
                    "name": wrestler_db.get_name(wid),
                    "career_start_year": career_start_year,
                    "first_match_year": min_year,
                    "years_early": career_start_year - min_year,
                }
            )

    if data_quality_issues:
        data_quality_issues.sort(key=lambda x: x["years_early"], reverse=True)
        print(
            f"\n⚠️  Data quality issues (matches before career start): {len(data_quality_issues)}"
        )
        print(f"Top 10 wrestlers with matches before their listed career start:")
        for i, issue in enumerate(data_quality_issues[:10], 1):
            print(
                f"  {i:2d}. {issue['name']:30} Career start: {issue['career_start_year']}, First match: {issue['first_match_year']} ({issue['years_early']} years early)"
            )


def missing_wrestlers_report():
    """Report on wrestlers referenced in matches but not in the database."""
    print("\n" + "=" * 70)
    print("MISSING WRESTLERS ANALYSIS")
    print("=" * 70)

    # Find all wrestler IDs referenced in matches
    appearance_counter = Counter()
    opponent_tracker = defaultdict(set)

    print("\nScanning all match data for missing wrestler references...")

    for wrestler_id in wrestler_db.all_wrestler_ids():
        colleagues = wrestler_db.get_all_colleagues(wrestler_id)
        for wid in colleagues:
            if not wrestler_db.wrestler_exists(wid):
                appearance_counter[wid] += 1
                opponent_tracker[wid].add(wrestler_id)

    if not appearance_counter:
        print(
            "✅ No missing wrestlers found - all referenced wrestlers are in the database!"
        )
        return

    print(
        f"\n⚠️  Found {len(appearance_counter)} missing wrestlers (referenced but not in database)"
    )
    print(f"Total appearances: {sum(appearance_counter.values())}")

    # Sort by appearance count
    missing_list = [
        (wid, count, opponent_tracker[wid])
        for wid, count in appearance_counter.most_common()
    ]

    print(f"\nTop 20 missing wrestlers by appearances:")
    for i, (wid, count, opponents) in enumerate(missing_list[:20], 1):
        # Show a few example wrestlers they've worked with
        opponent_names = [wrestler_db.get_name(oid) for oid in list(opponents)[:3]]
        opponent_str = ", ".join(opponent_names)
        if len(opponents) > 3:
            opponent_str += f" ... ({len(opponents)} total)"

        print(f"  {i:2d}. Wrestler ID {wid:6d}: {count:3d} appearances")
        print(f"      Worked with: {opponent_str}")

    # Statistics
    avg_appearances = sum(appearance_counter.values()) / len(appearance_counter)
    print(f"\nMissing wrestler statistics:")
    print(f"  Average appearances per missing wrestler: {avg_appearances:.1f}")
    print(f"  Most appearances: {max(appearance_counter.values())}")
    print(f"  Least appearances: {min(appearance_counter.values())}")

    # Count by appearance frequency
    frequency_buckets = Counter()
    for count in appearance_counter.values():
        if count == 1:
            frequency_buckets["1 appearance"] += 1
        elif count <= 5:
            frequency_buckets["2-5 appearances"] += 1
        elif count <= 10:
            frequency_buckets["6-10 appearances"] += 1
        elif count <= 20:
            frequency_buckets["11-20 appearances"] += 1
        else:
            frequency_buckets["20+ appearances"] += 1

    print(f"\nMissing wrestlers by appearance frequency:")
    for bucket in [
        "1 appearance",
        "2-5 appearances",
        "6-10 appearances",
        "11-20 appearances",
        "20+ appearances",
    ]:
        if bucket in frequency_buckets:
            print(f"  {bucket:20s}: {frequency_buckets[bucket]:4d} wrestlers")


def main():
    """Run all analysis functions."""
    print(f"\nDatabase Analysis Report")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Database: {wrestler_db.path}")

    wrestler_statistics()
    match_statistics()
    freshness_statistics()
    coverage_statistics()
    historical_coverage_statistics()
    missing_wrestlers_report()

    print("\n" + "=" * 70)
    print("Analysis complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
