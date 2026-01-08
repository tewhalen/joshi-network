#!/usr/bin/env python
"""Analyze what features predict whether a missing wrestler is female.

IMPORTANT CONSTRAINT: We only scrape match data for female/gender-diverse wrestlers.
This means when we see a "missing wrestler" in the database, they ONLY appear in
matches of female wrestlers. We never see them through male wrestlers' matches.

Therefore:
- opponent_ids will ONLY be female wrestlers
- "female_opponent_ratio" is meaningless (always ~1.0)
- The KEY signal is HOW MANY female wrestlers faced them and WHERE they wrestled
"""

from collections import Counter

from joshirank.joshi_data import joshi_promotions
from joshirank.joshidb import wrestler_db


def estimate_intergender_probability(match: dict) -> float:
    """Estimate probability that a match is intergender based on its features.

    Based on analysis of 19,563 intergender and 50,365 female-only matches,
    we know certain features predict intergender likelihood:
    - Match size (avg 4.35 intergender vs 2.90 female-only)
    - Non-Joshi promotions (6.7% intergender vs 34.3% female-only)
    - Year (30.6% intergender in 2025 vs 0.6% in 1997)
    - Country (Japan 24.8% intergender vs USA 36.7%)

    Returns: Estimated probability this match is intergender (0.0 to 1.0)
    """
    # Base rate: 28% of all matches in dataset are intergender
    prob = 0.28

    # Match size is strongest predictor
    num_wrestlers = len(match.get("wrestlers", []))
    if num_wrestlers == 2:
        prob *= 0.6  # Singles: 33.3% of intergender vs 56.2% female-only
    elif num_wrestlers >= 5:
        prob *= 1.8  # 5+ wrestlers: much more likely intergender

    # Joshi promotion strongly predicts female-only
    promotion_id = match.get("promotion")
    if promotion_id:
        promo_name = wrestler_db.get_promotion_name(promotion_id)
        if promo_name in joshi_promotions:
            prob *= 0.2  # Only 6.7% of intergender vs 34.3% female-only

    # Year trend
    date_str = match.get("date", "2020-01-01")
    if date_str and date_str != "Unknown":
        year = int(date_str[:4])
        if year >= 2023:
            prob *= 1.1  # Recent years ~28-30% intergender
        elif year >= 2010:
            prob *= 1.0  # 2010s steady ~24-27%
        elif year >= 2000:
            prob *= 0.7  # 2000s lower ~15-21%
        else:
            prob *= 0.3  # Pre-2000 very low ~1-11%

    # Country
    country = match.get("country", "")
    if country == "Japan":
        prob *= 0.85  # Japan: 24.8% intergender (below average)
    elif country in ("UK", "Canada", "Australia"):
        prob *= 1.2  # These regions: higher intergender rates

    # Multi-sided matches
    if match.get("is_multi_sided", False):
        prob *= 1.3  # 3+ sides: 6.5% intergender vs 2.5% female-only

    # Cap at reasonable bounds
    return min(max(prob, 0.01), 0.99)


def get_missing_wrestler_features(
    wrestler_id: int, female_opponent_ids: set[int]
) -> dict:
    """Extract features about a missing wrestler from female opponents' match data.

    CRITICAL: Since we only scrape female wrestlers' matches, opponent_ids will
    ONLY contain female wrestlers. This means:
    - We can't calculate meaningful "female opponent ratio" (always ~1.0)
    - The NUMBER of female opponents matters (more = likely female themselves)
    - Country/promotion patterns matter (Japan/Joshi = likely female)
    - Match size matters (inter-gender matches may be larger multi-person matches)

    NEW: We now estimate intergender probability for each match and use it
    to weight our gender prediction. Matches with high intergender probability
    suggest the missing wrestler might be male.

    Args:
        wrestler_id: ID of the missing wrestler
        female_opponent_ids: Set of FEMALE wrestler IDs who faced this missing wrestler

    Returns:
        Dict of features that can be used to predict gender
    """
    promotions = Counter()
    countries = Counter()
    match_sizes = []  # Track number of wrestlers per match
    total_matches_seen = 0

    # NEW: Track weighted statistics based on intergender probability
    intergender_probability_sum = 0.0
    female_only_probability_sum = 0.0

    # Scan through female opponents' matches to find appearances of this wrestler
    for opponent_id in female_opponent_ids:
        # Scan their matches across recent years
        for year in range(2020, 2027):
            matches = wrestler_db.get_matches(opponent_id, year)
            for match in matches:
                # Check if our missing wrestler appears in this match
                if wrestler_id in match.get("wrestlers", []):
                    total_matches_seen += 1

                    # Track match size
                    num_wrestlers = len(match.get("wrestlers", []))
                    match_sizes.append(num_wrestlers)

                    # Extract match features
                    country = match.get("country", "")
                    if country:
                        countries[country] += 1

                    if "promotion" in match and match["promotion"]:
                        promo_name = wrestler_db.get_promotion_name(match["promotion"])
                        promotions[promo_name] += 1

                    # NEW: Calculate intergender probability for this match
                    intergender_prob = estimate_intergender_probability(match)
                    intergender_probability_sum += intergender_prob
                    female_only_probability_sum += 1.0 - intergender_prob

    # Calculate feature ratios
    total_opponents = len(female_opponent_ids)
    japan_matches = countries.get("Japan", 0)
    joshi_matches = sum(
        cnt for promo, cnt in promotions.items() if promo in joshi_promotions
    )

    # Match size statistics
    avg_match_size = sum(match_sizes) / len(match_sizes) if match_sizes else 0
    singles_matches = sum(1 for size in match_sizes if size == 2)
    multi_person_matches = sum(1 for size in match_sizes if size > 2)
    multi_person_ratio = multi_person_matches / len(match_sizes) if match_sizes else 0

    # NEW: Calculate average intergender probability across all their matches
    avg_intergender_prob = (
        intergender_probability_sum / total_matches_seen
        if total_matches_seen > 0
        else 0.0
    )
    avg_female_only_prob = (
        female_only_probability_sum / total_matches_seen
        if total_matches_seen > 0
        else 0.0
    )

    return {
        "total_female_opponents": total_opponents,  # How many female wrestlers faced them
        "total_matches_seen": total_matches_seen,
        "japan_matches": japan_matches,
        "japan_ratio": japan_matches / total_matches_seen
        if total_matches_seen > 0
        else 0,
        "joshi_matches": joshi_matches,
        "joshi_ratio": joshi_matches / total_matches_seen
        if total_matches_seen > 0
        else 0,
        "unique_countries": len(countries),
        "unique_promotions": len(promotions),
        "matches_per_opponent": total_matches_seen / total_opponents
        if total_opponents > 0
        else 0,
        "avg_match_size": avg_match_size,
        "singles_matches": singles_matches,
        "multi_person_matches": multi_person_matches,
        "multi_person_ratio": multi_person_ratio,
        "top_country": countries.most_common(1)[0][0] if countries else None,
        "top_promotion": promotions.most_common(1)[0][0] if promotions else None,
        # NEW: Probabilistic features
        "avg_intergender_prob": avg_intergender_prob,
        "avg_female_only_prob": avg_female_only_prob,
        "intergender_likelihood_ratio": avg_intergender_prob / avg_female_only_prob
        if avg_female_only_prob > 0
        else 0,
    }


def main():
    print("Analyzing predictors for missing wrestler gender...")
    print("=" * 70)
    print("NOTE: We only see missing wrestlers through FEMALE wrestlers' matches")
    print("=" * 70)
    print()

    # Get only female wrestlers (since they're the only ones with match data)
    female_wrestlers = list(wrestler_db.all_female_wrestlers())

    # Sample for faster analysis
    import random

    random.seed(42)
    sample_size = min(1000, len(female_wrestlers))
    sampled_wrestlers = random.sample(female_wrestlers, sample_size)

    # We'll also analyze some male wrestlers who DO have matches
    # (to see what differentiates them when seen through female opponents)
    male_wrestlers_with_matches = []
    for wid in wrestler_db.all_wrestler_ids():
        if not wrestler_db.is_female(wid):
            # Check if they have any match data
            colleagues = wrestler_db.get_all_colleagues(wid)
            if colleagues:
                male_wrestlers_with_matches.append(wid)
                if len(male_wrestlers_with_matches) >= 200:
                    break

    female_features = []
    male_features = []

    print(f"Analyzing {len(sampled_wrestlers)} female wrestlers...")
    print(
        f"Analyzing {len(male_wrestlers_with_matches)} male wrestlers with match data..."
    )
    print()

    for i, wid in enumerate(sampled_wrestlers + male_wrestlers_with_matches):
        if i % 100 == 0:
            print(
                f"  Progress: {i}/{len(sampled_wrestlers) + len(male_wrestlers_with_matches)}..."
            )

        # Get ground truth gender
        is_female = wrestler_db.is_female(wid)

        # Get their colleagues (wrestlers they've faced)
        # For simulation: these represent the female wrestlers who would "see" them if they were missing
        colleagues = wrestler_db.get_all_colleagues(wid)

        if not colleagues:
            continue

        # Extract features as if this wrestler was missing
        features = get_missing_wrestler_features(wid, colleagues)

        if features["total_matches_seen"] == 0:
            continue

        if is_female:
            female_features.append(features)
        else:
            male_features.append(features)

    print(
        f"\nAnalyzed {len(female_features)} female wrestlers, {len(male_features)} male wrestlers"
    )
    print()

    # Calculate statistics
    def calc_stats(data, feature_name):
        values = [d[feature_name] for d in data if d[feature_name] is not None]
        if not values:
            return 0, 0, 0
        avg = sum(values) / len(values)
        median = sorted(values)[len(values) // 2]
        nonzero_pct = len([v for v in values if v > 0]) / len(values) * 100
        return avg, median, nonzero_pct

    print("Feature correlation analysis:")
    print("-" * 70)

    numeric_features = [
        "total_female_opponents",  # Key signal: how many female wrestlers faced them
        "japan_ratio",  # Strong signal: wrestling in Japan
        "joshi_ratio",  # Strongest signal: wrestling for Joshi promotions
        "total_matches_seen",  # Volume of matches
        "matches_per_opponent",  # How often they face same opponents
        "avg_match_size",  # Average number of wrestlers per match
        "multi_person_ratio",  # Percentage of matches with 3+ wrestlers
        "unique_countries",
        "unique_promotions",
        "avg_intergender_prob",  # NEW: Average probability matches are intergender
        "intergender_likelihood_ratio",  # NEW: Ratio of intergender to female-only probability
    ]

    for feature in numeric_features:
        f_avg, f_median, f_nonzero = calc_stats(female_features, feature)
        m_avg, m_median, m_nonzero = calc_stats(male_features, feature)
        ratio = f_avg / m_avg if m_avg > 0 else float("inf")

        print(f"{feature:25s}:")
        print(
            f"  Female: avg={f_avg:.3f}, median={f_median:.3f}, {f_nonzero:.0f}% non-zero"
        )
        print(
            f"  Male:   avg={m_avg:.3f}, median={m_median:.3f}, {m_nonzero:.0f}% non-zero"
        )
        print(f"  Ratio (F/M): {ratio:.2f}x {'←' if ratio > 1.5 else ''}")
        print()

    # Test different threshold combinations
    print("\nPrediction accuracy for different thresholds:")
    print("-" * 70)

    thresholds = [
        ("total_female_opponents >= 5", lambda f: f["total_female_opponents"] >= 5),
        ("total_female_opponents >= 10", lambda f: f["total_female_opponents"] >= 10),
        ("total_female_opponents >= 20", lambda f: f["total_female_opponents"] >= 20),
        ("japan_ratio >= 0.3", lambda f: f["japan_ratio"] >= 0.3),
        ("japan_ratio >= 0.5", lambda f: f["japan_ratio"] >= 0.5),
        ("joshi_ratio >= 0.1", lambda f: f["joshi_ratio"] >= 0.1),
        ("joshi_ratio >= 0.3", lambda f: f["joshi_ratio"] >= 0.3),
        ("multi_person_ratio < 0.5", lambda f: f["multi_person_ratio"] < 0.5),
        ("multi_person_ratio >= 0.7", lambda f: f["multi_person_ratio"] >= 0.7),
        ("avg_match_size < 3.0", lambda f: f["avg_match_size"] < 3.0),
        (
            "japan_ratio >= 0.3 OR joshi_ratio >= 0.1",
            lambda f: f["japan_ratio"] >= 0.3 or f["joshi_ratio"] >= 0.1,
        ),
        ("total_female_opponents >= 3", lambda f: f["total_female_opponents"] >= 3),
        (
            "total_female_opponents >= 3 AND (japan >= 0.3 OR joshi >= 0.1)",
            lambda f: f["total_female_opponents"] >= 3
            and (f["japan_ratio"] >= 0.3 or f["joshi_ratio"] >= 0.1),
        ),
        (
            "total_female_opponents >= 5 AND multi_person_ratio < 0.6",
            lambda f: f["total_female_opponents"] >= 5
            and f["multi_person_ratio"] < 0.6,
        ),
        # NEW: Probabilistic thresholds
        ("avg_intergender_prob < 0.20", lambda f: f["avg_intergender_prob"] < 0.20),
        ("avg_intergender_prob < 0.15", lambda f: f["avg_intergender_prob"] < 0.15),
        (
            "intergender_likelihood_ratio < 0.25",
            lambda f: f["intergender_likelihood_ratio"] < 0.25,
        ),
        (
            "avg_intergender_prob < 0.20 AND (japan >= 0.3 OR joshi >= 0.1)",
            lambda f: f["avg_intergender_prob"] < 0.20
            and (f["japan_ratio"] >= 0.3 or f["joshi_ratio"] >= 0.1),
        ),
    ]

    for name, condition in thresholds:
        female_match = sum(1 for f in female_features if condition(f))
        male_match = sum(1 for f in male_features if condition(f))

        total_match = female_match + male_match
        if total_match == 0:
            continue

        precision = female_match / total_match * 100
        recall = female_match / len(female_features) * 100

        print(f"{name:50s}:")
        print(f"  Precision: {precision:.1f}% ({female_match}F / {total_match} total)")
        print(
            f"  Recall: {recall:.1f}% (covers {female_match}/{len(female_features)} females)"
        )
        print(f"  False positives: {male_match} males")
        print()


if __name__ == "__main__":
    main()
