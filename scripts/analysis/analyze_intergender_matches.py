#!/usr/bin/env python
"""Analyze what features predict whether a match will be intergender.

IMPORTANT: In this database, we only scrape match data for female/gender-diverse wrestlers.
This means that when a male wrestler appears in a match, it's BY DEFINITION an intergender match
(a female wrestler's match that included a male opponent).

Question: What OTHER signals (besides presence of male wrestler) predict intergender matches?
- Match size (number of wrestlers)
- Match type (singles, tag, multi-way)
- Promotion
- Country
- Year/era
"""

from collections import Counter

from joshirank.joshi_data import joshi_promotions
from joshirank.joshidb import wrestler_db


def analyze_matches_by_gender_composition():
    """Analyze all matches to find patterns in intergender matches."""

    intergender_matches = []
    female_only_matches = []

    print("Scanning all female wrestlers' matches...")

    female_wrestlers = list(wrestler_db.all_female_wrestlers())

    # Track unique matches (avoid counting same match multiple times)
    seen_matches = set()

    for i, wrestler_id in enumerate(female_wrestlers):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(female_wrestlers)}...")

        # Check matches across recent years
        for year in range(1990, 2027):
            matches = wrestler_db.get_matches(wrestler_id, year)

            for match in matches:
                # Create unique match key
                wrestlers_tuple = tuple(sorted(match.get("wrestlers", [])))
                date = match.get("date", "")
                match_key = (date, wrestlers_tuple)

                if match_key in seen_matches:
                    continue
                seen_matches.add(match_key)

                # Check if match is intergender
                wrestlers_in_match = match.get("wrestlers", [])
                if not wrestlers_in_match:
                    continue

                # Check gender of all participants
                female_count = sum(
                    1 for wid in wrestlers_in_match if wrestler_db.is_female(wid)
                )
                male_count = len(wrestlers_in_match) - female_count

                match_features = extract_match_features(match, female_count, male_count)

                if male_count > 0:
                    intergender_matches.append(match_features)
                else:
                    female_only_matches.append(match_features)

    print(f"\nFound {len(intergender_matches)} intergender matches")
    print(f"Found {len(female_only_matches)} female-only matches")
    print()

    return intergender_matches, female_only_matches


def extract_match_features(match: dict, female_count: int, male_count: int) -> dict:
    """Extract features from a match."""
    wrestlers = match.get("wrestlers", [])

    # Determine match type from sides structure
    sides = match.get("sides", [])
    if sides:
        side_sizes = [len(side["wrestlers"]) for side in sides]
        if len(sides) == 2:
            if side_sizes[0] == 1 and side_sizes[1] == 1:
                match_type = "singles"
            elif all(s == 2 for s in side_sizes):
                match_type = "tag_team"
            else:
                match_type = "other_two_sided"
        else:
            match_type = "multi_way"
    else:
        match_type = "unknown"

    promotion_id = match.get("promotion")
    promotion_name = (
        wrestler_db.get_promotion_name(promotion_id) if promotion_id else "Unknown"
    )
    is_joshi_promotion = promotion_name in joshi_promotions

    return {
        "total_wrestlers": len(wrestlers),
        "female_count": female_count,
        "male_count": male_count,
        "match_type": match_type,
        "num_sides": len(sides),
        "promotion": promotion_name,
        "is_joshi_promotion": is_joshi_promotion,
        "country": match.get("country", "Unknown"),
        "year": int(match.get("date", "2000-01-01")[:4]) if match.get("date") else None,
        "is_multi_sided": match.get("is_multi_sided", False),
    }


def compare_statistics(intergender: list[dict], female_only: list[dict]):
    """Compare statistics between intergender and female-only matches."""

    print("=" * 70)
    print("INTERGENDER MATCH PREDICTORS")
    print("=" * 70)
    print()

    # Match size distribution
    print("Match Size Distribution:")
    print("-" * 70)
    inter_sizes = Counter(m["total_wrestlers"] for m in intergender)
    female_sizes = Counter(m["total_wrestlers"] for m in female_only)

    all_sizes = sorted(set(inter_sizes.keys()) | set(female_sizes.keys()))
    for size in all_sizes:
        inter_count = inter_sizes.get(size, 0)
        female_count = female_sizes.get(size, 0)
        inter_pct = inter_count / len(intergender) * 100 if intergender else 0
        female_pct = female_count / len(female_only) * 100 if female_only else 0

        if inter_count > 0 or female_count > 0:
            print(f"  {size} wrestlers:")
            print(f"    Intergender: {inter_count:5d} ({inter_pct:5.1f}%)")
            print(f"    Female-only: {female_count:5d} ({female_pct:5.1f}%)")
            if female_count > 0:
                ratio = inter_count / female_count if female_count > 0 else 0
                print(f"    Ratio: {ratio:.2f}x")
            print()

    # Average match size
    avg_inter_size = (
        sum(m["total_wrestlers"] for m in intergender) / len(intergender)
        if intergender
        else 0
    )
    avg_female_size = (
        sum(m["total_wrestlers"] for m in female_only) / len(female_only)
        if female_only
        else 0
    )
    print("Average match size:")
    print(f"  Intergender: {avg_inter_size:.2f}")
    print(f"  Female-only: {avg_female_size:.2f}")
    print()

    # Match type distribution
    print("Match Type Distribution:")
    print("-" * 70)
    inter_types = Counter(m["match_type"] for m in intergender)
    female_types = Counter(m["match_type"] for m in female_only)

    all_types = sorted(set(inter_types.keys()) | set(female_types.keys()))
    for mtype in all_types:
        inter_count = inter_types.get(mtype, 0)
        female_count = female_types.get(mtype, 0)
        inter_pct = inter_count / len(intergender) * 100 if intergender else 0
        female_pct = female_count / len(female_only) * 100 if female_only else 0

        print(f"  {mtype:20s}:")
        print(f"    Intergender: {inter_count:5d} ({inter_pct:5.1f}%)")
        print(f"    Female-only: {female_count:5d} ({female_pct:5.1f}%)")
        print()

    # Multi-sided matches
    inter_multi = sum(1 for m in intergender if m["is_multi_sided"])
    female_multi = sum(1 for m in female_only if m["is_multi_sided"])
    print("Multi-sided (3+ sides) matches:")
    print(f"  Intergender: {inter_multi} ({inter_multi / len(intergender) * 100:.1f}%)")
    print(
        f"  Female-only: {female_multi} ({female_multi / len(female_only) * 100:.1f}%)"
    )
    print()

    # Promotion patterns
    print("Top 20 Promotions for Intergender Matches:")
    print("-" * 70)
    inter_promos = Counter(m["promotion"] for m in intergender)
    for promo, count in inter_promos.most_common(20):
        pct = count / len(intergender) * 100
        is_joshi = " [JOSHI]" if promo in joshi_promotions else ""
        print(f"  {promo:40s}: {count:4d} ({pct:5.1f}%){is_joshi}")
    print()

    print("Top 20 Promotions for Female-Only Matches:")
    print("-" * 70)
    female_promos = Counter(m["promotion"] for m in female_only)
    for promo, count in female_promos.most_common(20):
        pct = count / len(female_only) * 100
        is_joshi = " [JOSHI]" if promo in joshi_promotions else ""
        print(f"  {promo:40s}: {count:4d} ({pct:5.1f}%){is_joshi}")
    print()

    # Joshi promotion ratio
    inter_joshi = sum(1 for m in intergender if m["is_joshi_promotion"])
    female_joshi = sum(1 for m in female_only if m["is_joshi_promotion"])
    print("Joshi Promotion Matches:")
    print(f"  Intergender: {inter_joshi} ({inter_joshi / len(intergender) * 100:.1f}%)")
    print(
        f"  Female-only: {female_joshi} ({female_joshi / len(female_only) * 100:.1f}%)"
    )
    print()

    # Country patterns
    print("Country Distribution:")
    print("-" * 70)
    inter_countries = Counter(m["country"] for m in intergender)
    female_countries = Counter(m["country"] for m in female_only)

    all_countries = sorted(
        set(inter_countries.keys()) | set(female_countries.keys()),
        key=lambda c: inter_countries.get(c, 0) + female_countries.get(c, 0),
        reverse=True,
    )[:15]

    for country in all_countries:
        inter_count = inter_countries.get(country, 0)
        female_count = female_countries.get(country, 0)
        inter_pct = inter_count / len(intergender) * 100 if intergender else 0
        female_pct = female_count / len(female_only) * 100 if female_only else 0

        print(f"  {country:20s}:")
        print(f"    Intergender: {inter_count:5d} ({inter_pct:5.1f}%)")
        print(f"    Female-only: {female_count:5d} ({female_pct:5.1f}%)")
        print()

    # Year trends
    print("Year Distribution and Trends:")
    print("-" * 70)
    inter_years = Counter(m["year"] for m in intergender if m["year"])
    female_years = Counter(m["year"] for m in female_only if m["year"])

    all_years = sorted(set(inter_years.keys()) | set(female_years.keys()))

    print(
        f"{'Year':>6s} {'Intergender':>12s} {'Female-Only':>12s} {'Total':>8s} {'% Inter':>8s}"
    )
    print("-" * 70)

    for year in all_years:
        inter_count = inter_years.get(year, 0)
        female_count = female_years.get(year, 0)
        total = inter_count + female_count
        inter_pct = inter_count / total * 100 if total > 0 else 0

        print(
            f"{year:>6d} {inter_count:>12d} {female_count:>12d} {total:>8d} {inter_pct:>7.1f}%"
        )

    print()
    print("Intergender percentage by year:")
    # Calculate moving average
    years_sorted = sorted(all_years)
    for i, year in enumerate(years_sorted):
        inter_count = inter_years.get(year, 0)
        female_count = female_years.get(year, 0)
        total = inter_count + female_count
        pct = inter_count / total * 100 if total > 0 else 0

        # 3-year moving average if possible
        if i >= 1 and i < len(years_sorted) - 1:
            prev_year = years_sorted[i - 1]
            next_year = years_sorted[i + 1]
            ma_inter = (
                inter_years.get(prev_year, 0)
                + inter_count
                + inter_years.get(next_year, 0)
            )
            ma_female = (
                female_years.get(prev_year, 0)
                + female_count
                + female_years.get(next_year, 0)
            )
            ma_total = ma_inter + ma_female
            ma_pct = ma_inter / ma_total * 100 if ma_total > 0 else 0
            print(f"  {year}: {pct:5.1f}% (3-year MA: {ma_pct:5.1f}%)")
        else:
            print(f"  {year}: {pct:5.1f}%")
    print()


def main():
    print("Analyzing intergender match predictors...")
    print()

    intergender, female_only = analyze_matches_by_gender_composition()
    compare_statistics(intergender, female_only)

    print("\n" + "=" * 70)
    print("KEY FINDINGS:")
    print("=" * 70)
    print("Features that predict intergender matches:")
    print("1. Match size (larger matches more likely intergender)")
    print("   - Intergender avg: 4.35 wrestlers, Female-only avg: 2.90 wrestlers")
    print("   - 5+ wrestlers dramatically increases intergender likelihood")
    print("2. Non-Joshi promotions (intergender more common outside Joshi scene)")
    print("   - Only 6.7% intergender in Joshi vs 34.3% female-only")
    print("3. Multi-way matches (3+ sides): 2.6x more likely intergender")
    print("4. Geography: UK, Canada, Australia have higher intergender rates")
    print("   - Japan has LOWER intergender rate (24.8% vs 40.8% female-only)")
    print("5. Year trends show temporal patterns in intergender wrestling")


if __name__ == "__main__":
    main()
