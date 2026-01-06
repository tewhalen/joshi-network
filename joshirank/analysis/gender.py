"""Gender analysis functions for wrestlers.

Functions for analyzing wrestler gender classification based on match patterns,
colleague analysis, and profile data.
"""

from loguru import logger

from joshirank.joshi_data import considered_female, joshi_promotions
from joshirank.joshidb import get_promotion_name, wrestler_db


def percentage_of_female_colleagues(wrestler_id: int) -> float:
    """Return the percentage of colleagues known to be female.

    Args:
        wrestler_id: ID of wrestler to analyze

    Returns:
        Percentage of female colleagues (0.0 to 1.0)
    """
    colleagues = wrestler_db.get_all_colleagues(wrestler_id)
    if not colleagues:
        return 0.0
    female_count = sum(1 for c in colleagues if wrestler_db.is_female(c))
    return female_count / len(colleagues)


def is_gender_diverse(wrestler_id: int) -> bool:
    """Return True if the wrestler is considered gender-diverse.

    Checks the wrestler's CageMatch profile for Gender="diverse".

    Args:
        wrestler_id: ID of wrestler to check

    Returns:
        True if gender-diverse, False otherwise
    """
    profile = wrestler_db.get_cm_profile_for_wrestler(wrestler_id)
    g = profile.get("Gender")
    return g == "diverse"


def gender_diverse_wrestlers():
    """Yield wrestler IDs considered gender-diverse.

    Scans all wrestlers in the database and yields those with Gender="diverse"
    in their profiles.

    Yields:
        int: Wrestler IDs that are gender-diverse
    """
    for wrestler_id in wrestler_db.all_wrestler_ids():
        if is_gender_diverse(wrestler_id):
            yield wrestler_id


def update_gender_diverse_classification(wrestler_id: int) -> bool:
    """Update gender classification for a gender-diverse wrestler based on colleagues.

    For wrestlers marked as gender-diverse, this function analyzes their match
    patterns to determine if they should be classified as female. Wrestlers who
    work primarily with female colleagues (>50%) are classified as female.

    Wrestlers manually marked in joshi_data.considered_female are skipped.

    Args:
        wrestler_id: ID of gender-diverse wrestler to classify

    Returns:
        True if classification was updated, False if skipped
    """
    if not is_gender_diverse(wrestler_id):
        return False

    # Check if this wrestler is manually marked as female

    if wrestler_id in considered_female:
        # Skip colleague-based reclassification for manually marked wrestlers
        logger.debug(
            "Gender-diverse {} manually marked as female, skipping colleague check",
            wrestler_id,
        )
        return False

    # Set is_female if the majority of colleagues are female
    if percentage_of_female_colleagues(wrestler_id) > 0.5:
        logger.info("Gender-diverse {} -> female", wrestler_id)
        wrestler_db._execute_and_commit(
            """
            UPDATE wrestlers
            SET is_female=1
            WHERE wrestler_id=?
            """,
            (wrestler_id,),
        )
        return True
    else:
        logger.info("Gender-diverse {} -> not female", wrestler_id)
        wrestler_db._execute_and_commit(
            """
            UPDATE wrestlers
            SET is_female=0
            WHERE wrestler_id=?
            """,
            (wrestler_id,),
        )
        return True


def estimate_intergender_probability(match: dict) -> float:
    """Estimate probability that a match is intergender based on its features.

    Based on analysis of 19,563 intergender and 50,365 female-only matches:
    - Match size: avg 4.35 intergender vs 2.90 female-only
    - Joshi promotions: 6.7% intergender vs 34.3% female-only
    - Year: 30.6% intergender in 2025 vs 0.6% in 1997
    - Country: Japan 24.8% intergender vs USA 36.7%

    Args:
        match: Match dict with wrestlers, promotion, date, country, etc.

    Returns:
        Estimated probability this match is intergender (0.0 to 1.0)
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
        promo_name = get_promotion_name(promotion_id)
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


def guess_gender_of_wrestler(wrestler_id: int) -> float:
    """Guess the gender of a wrestler based on data about their opponents.

    IMPORTANT: This function is designed for "missing" wrestlers who don't have
    their own match data in the database - we can only see them through the matches
    of female wrestlers who faced them. For wrestlers with their own match data,
    use wrestler_db.is_female() instead.

    Uses statistical analysis of match patterns to predict whether a missing
    wrestler is likely to be female or male. Key predictors:

    1. Intergender probability: Aggregate probability that their matches are
       intergender based on match size, promotion, year, country
    2. Japan ratio: Percentage of matches in Japan (female wrestlers much higher)
    3. Joshi ratio: Percentage of matches in Joshi promotions (100% precision signal)
    4. Match volume: Female wrestlers seen in more matches

    Analysis of 652 female and 29 male wrestlers shows:
    - avg_intergender_prob < 0.15: 100% precision for female
    - japan_ratio >= 0.3: 100% precision for female
    - joshi_ratio >= 0.1: 100% precision for female

    Results are cached to avoid expensive recalculation. Cache expires after 2 hours.

    Args:
        wrestler_id: ID of wrestler to analyze (should be a "missing" wrestler)

    Returns:
        Confidence score (0.0 to 1.0) where:
        - 0.9-1.0: Very confident female (100% precision thresholds)
        - 0.7-0.9: Probably female (high confidence)
        - 0.3-0.7: Uncertain
        - 0.1-0.3: Probably male
        - 0.0-0.1: Very confident male
    """
    # Import cache inside function to allow monkeypatching in tests
    from joshirank.analysis.gender_cache import _gender_cache

    # Check cache first
    cached_confidence = _gender_cache.get(wrestler_id)
    if cached_confidence is not None:
        return cached_confidence

    # Get all female wrestlers who have faced this wrestler
    female_opponents = wrestler_db.get_all_inverse_colleagues(wrestler_id)

    if not female_opponents:
        # No data - return neutral
        confidence = 0.5
        _gender_cache.set(wrestler_id, confidence)
        _gender_cache.save()
        return confidence

    # Scan matches to gather features
    total_matches = 0
    japan_matches = 0
    joshi_matches = 0
    intergender_prob_sum = 0.0

    # Performance optimization: Limit how many opponents we scan if we have a lot
    # After 50 opponents with sufficient data, we likely have enough signal
    max_opponents_to_scan = 50
    opponents_scanned = 0

    for opponent_id in female_opponents:
        # Performance: Only scan years where this opponent actually has matches
        available_years = wrestler_db.match_years_available(opponent_id)

        if not available_years:
            continue

        opponents_scanned += 1

        for year in available_years:
            matches = wrestler_db.get_matches(opponent_id, year)
            for match in matches:
                # Check if our wrestler appears in this match
                if wrestler_id in match.get("wrestlers", []):
                    total_matches += 1

                    # Track Japan matches
                    if match.get("country") == "Japan":
                        japan_matches += 1

                    # Track Joshi promotion matches
                    promotion_id = match.get("promotion")
                    if promotion_id:
                        promo_name = get_promotion_name(promotion_id)
                        if promo_name in joshi_promotions:
                            joshi_matches += 1

                    # Calculate intergender probability
                    intergender_prob = estimate_intergender_probability(match)
                    intergender_prob_sum += intergender_prob

        # Early exit: If we have high confidence after scanning some opponents, we can stop
        # This is safe because all our high-confidence rules require significant signal
        if opponents_scanned >= max_opponents_to_scan and total_matches >= 20:
            break

    if total_matches == 0:
        confidence = 0.5
        _gender_cache.set(wrestler_id, confidence)
        _gender_cache.save()
        return confidence

    # Calculate ratios
    japan_ratio = japan_matches / total_matches
    joshi_ratio = joshi_matches / total_matches
    avg_intergender_prob = intergender_prob_sum / total_matches

    # Apply prediction rules based on analysis
    # Rules with 100% precision for female:
    confidence = None

    if joshi_ratio >= 0.1:
        # 100% precision (155F/0M) - wrestles in Joshi promotions
        confidence = 0.95
    elif japan_ratio >= 0.3:
        # 100% precision (158F/0M) - frequently wrestles in Japan
        confidence = 0.95
    elif avg_intergender_prob < 0.15:
        # 100% precision (108F/0M) - very low intergender probability
        confidence = 0.95
    elif avg_intergender_prob < 0.20 and (japan_ratio >= 0.3 or joshi_ratio >= 0.05):
        # 100% precision (129F/0M) - combined rule
        confidence = 0.95
    # High confidence female thresholds (98%+ precision):
    elif avg_intergender_prob < 0.20:
        # 98.7% precision (156F/2M)
        confidence = 0.85
    elif japan_ratio >= 0.2:
        # High japan ratio is strong signal
        confidence = 0.80
    elif total_matches >= 50 and avg_intergender_prob < 0.30:
        # Volume + reasonable intergender probability
        confidence = 0.75
    # Moderate confidence based on intergender probability
    # Female wrestlers avg 0.309, male wrestlers avg 0.426
    elif avg_intergender_prob < 0.25:
        confidence = 0.70
    elif avg_intergender_prob < 0.35:
        confidence = 0.55
    # Likely male thresholds
    elif avg_intergender_prob > 0.50:
        # High intergender probability suggests male
        confidence = 0.20
    elif avg_intergender_prob > 0.45 and japan_ratio < 0.1:
        # High intergender prob + not in Japan = probably male
        confidence = 0.15
    elif avg_intergender_prob > 0.55:
        # Very high intergender probability
        confidence = 0.10

    # If we matched an early rule, cache and return
    if confidence is not None:
        _gender_cache.set(wrestler_id, confidence)
        _gender_cache.save()
        return confidence

    # Default: use linear interpolation based on avg_intergender_prob
    # Female avg: 0.309, Male avg: 0.426
    # Map 0.309 -> 0.5, 0.426 -> 0.3
    if avg_intergender_prob <= 0.309:
        confidence = 0.5 + (0.309 - avg_intergender_prob) * 0.5  # 0.5-0.65
    elif avg_intergender_prob <= 0.426:
        confidence = 0.5 - (avg_intergender_prob - 0.309) * (0.2 / 0.117)  # 0.3-0.5
    else:
        confidence = max(0.3 - (avg_intergender_prob - 0.426) * 0.5, 0.05)  # <0.3

    # Cache the result before returning
    _gender_cache.set(wrestler_id, confidence)
    _gender_cache.save()

    return confidence
