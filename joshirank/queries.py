"""Specialized Queries for Joshi Network data.

This module provides high-level query functions for analyzing the Joshi wrestling
database, including gender prediction for missing wrestlers and promotion-based
wrestler discovery.

Gender Prediction Caching:
    Gender predictions for missing wrestlers are automatically cached to
    data/gender_predictions_cache.json to avoid expensive recalculation across
    scrape runs. Cache entries expire after 90 days.

    Functions:
    - guess_gender_of_wrestler(): Returns cached or calculated confidence score
    - clear_gender_cache(): Force recalculation for all wrestlers
    - get_gender_cache_stats(): Get cache statistics
"""

import pathlib
import sqlite3
import time
import typing

from joshirank.joshi_data import joshi_promotions
from joshirank.joshidb import get_promotion_name

if typing.TYPE_CHECKING:
    from joshirank.joshidb import WrestlerDb


class GenderCache:
    """Persistent cache for gender predictions using SQLite for efficient updates.

    Uses SQLite instead of JSON to allow:
    - Single-record updates without rewriting entire file
    - Better concurrent access
    - Efficient queries for stale entries
    - Indexes for fast lookups

    Schema:
        CREATE TABLE gender_predictions (
            wrestler_id INTEGER PRIMARY KEY,
            confidence REAL NOT NULL,
            timestamp REAL NOT NULL,
            version INTEGER NOT NULL
        )

    Staleness policy: Recalculate if cached prediction is >90 days old
    """

    CACHE_VERSION = 1
    STALENESS_HOURS = 8

    def __init__(self, cache_path: pathlib.Path | None = None):
        if cache_path is None:
            cache_path = pathlib.Path("data/gender_predictions_cache.db")
        self.cache_path = cache_path
        self._conn = None
        self._initialize_db()
        self._migrate_from_json_if_needed()

    def _initialize_db(self):
        """Initialize SQLite database and create table if needed."""
        # Ensure directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self.cache_path))
        self._conn.row_factory = sqlite3.Row

        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gender_predictions (
                wrestler_id INTEGER PRIMARY KEY,
                confidence REAL NOT NULL,
                timestamp REAL NOT NULL,
                version INTEGER NOT NULL
            )
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON gender_predictions(timestamp)
        """
        )
        self._conn.commit()

    def _migrate_from_json_if_needed(self):
        """Migrate data from old JSON cache file if it exists."""
        json_path = self.cache_path.parent / "gender_predictions_cache.json"
        if not json_path.exists():
            return

        try:
            import json

            with open(json_path, "r") as f:
                data = json.load(f)

            # Import existing predictions into SQLite
            cursor = self._conn.cursor()
            for wid_str, entry in data.items():
                wrestler_id = int(wid_str)
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO gender_predictions 
                    (wrestler_id, confidence, timestamp, version)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        wrestler_id,
                        entry["confidence"],
                        entry["timestamp"],
                        entry.get("version", 1),
                    ),
                )
            self._conn.commit()

            # Rename old JSON file to .migrated
            json_path.rename(json_path.with_suffix(".json.migrated"))
            print(f"Migrated {len(data)} entries from JSON to SQLite gender cache")
        except Exception as e:
            print(f"Warning: Failed to migrate gender cache from JSON: {e}")

    def get(self, wrestler_id: int) -> float | None:
        """Get cached gender prediction for wrestler.

        Returns:
            Confidence score (0.0-1.0) if cached and fresh, None if stale/missing
        """
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT confidence, timestamp, version 
            FROM gender_predictions 
            WHERE wrestler_id = ?
        """,
            (wrestler_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        # Check version compatibility
        if row["version"] != self.CACHE_VERSION:
            return None

        # Check staleness
        age_hours = (time.time() - row["timestamp"]) / 3600
        if age_hours > self.STALENESS_HOURS:
            return None

        return row["confidence"]

    def set(self, wrestler_id: int, confidence: float):
        """Cache a gender prediction for a wrestler."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO gender_predictions 
            (wrestler_id, confidence, timestamp, version)
            VALUES (?, ?, ?, ?)
        """,
            (wrestler_id, confidence, time.time(), self.CACHE_VERSION),
        )
        self._conn.commit()

    def save(self):
        """Save cache to disk (for compatibility - commits happen on set())."""
        # SQLite auto-commits on each set(), but we commit here for safety
        if self._conn:
            self._conn.commit()

    def clear_stale(self) -> int:
        """Remove stale entries from cache.

        Returns:
            Number of entries removed
        """
        now = time.time()
        stale_threshold = now - (self.STALENESS_HOURS * 3600)

        cursor = self._conn.cursor()
        cursor.execute(
            """
            DELETE FROM gender_predictions 
            WHERE timestamp < ?
        """,
            (stale_threshold,),
        )
        removed = cursor.rowcount
        self._conn.commit()
        return removed

    def __len__(self) -> int:
        """Return the number of cached entries."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM gender_predictions")
        return cursor.fetchone()[0]

    def clear(self):
        """Clear all cached entries."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM gender_predictions")
        self._conn.commit()

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self):
        """Ensure connection is closed when object is destroyed."""
        self.close()


# Global cache instance
_gender_cache = GenderCache()


def clear_gender_cache():
    """Clear all cached gender predictions.

    Useful for forcing recalculation after database updates or for testing.
    """
    global _gender_cache
    _gender_cache.clear()
    _gender_cache.save()


def get_gender_cache_stats() -> dict:
    """Get statistics about the gender prediction cache.

    Returns:
        Dict with cache statistics:
        - total_entries: Number of cached predictions
        - cache_file: Path to cache file
        - exists: Whether cache file exists
    """
    return {
        "total_entries": len(_gender_cache),
        "cache_file": str(_gender_cache.cache_path),
        "exists": _gender_cache.cache_path.exists(),
    }


def all_tjpw_wrestlers(wrestler_db: WrestlerDb) -> set[int]:
    """Return a set of all wrestlers who have ever wrestled for TJPW.

    Uses the promotions_worked field for efficient querying.
    """
    # TJPW promotion ID on CageMatch is 1467
    TJPW_ID = 1467
    tjpw_wrestlers = set()

    for wid in wrestler_db.all_female_wrestlers():
        # Check all available years for this wrestler using promotions_worked
        for year in wrestler_db.match_years_available(wid):
            match_info = wrestler_db.get_match_info(wid, year)
            promotions = match_info.get("promotions_worked", {})
            # promotions_worked maps promotion_id (as string or int) to count
            if str(TJPW_ID) in promotions or TJPW_ID in promotions:
                tjpw_wrestlers.add(wid)
                # having found a set of matches we know included TJPW
                # we should check all the matches in that year to find all
                # the wrestlers in those TJPW matches
                # because those wrestlers may not have TJPW in their promotions_worked
                matches = wrestler_db.get_matches(wid, year)
                for match in matches:
                    if match.get("promotion") == TJPW_ID:
                        for competitor in match.get("wrestlers", []):
                            tjpw_wrestlers.add(competitor)

    # filter out any non-female wrestlers (in case of data errors)
    tjpw_wrestlers = {wid for wid in tjpw_wrestlers if wrestler_db.is_female(wid)}
    return tjpw_wrestlers


def estimate_intergender_probability(match: dict, wrestler_db) -> float:
    """Estimate probability that a match is intergender based on its features.

    Based on analysis of 19,563 intergender and 50,365 female-only matches:
    - Match size: avg 4.35 intergender vs 2.90 female-only
    - Joshi promotions: 6.7% intergender vs 34.3% female-only
    - Year: 30.6% intergender in 2025 vs 0.6% in 1997
    - Country: Japan 24.8% intergender vs USA 36.7%

    Args:
        match: Match dict with wrestlers, promotion, date, country, etc.
        wrestler_db: Database instance for looking up promotion names

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


def guess_gender_of_wrestler(wrestler_db: "WrestlerDb", wrestler_id: int) -> float:
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

    Results are cached to avoid expensive recalculation. Cache expires after 90 days.

    Args:
        wrestler_db: Database instance
        wrestler_id: ID of wrestler to analyze (should be a "missing" wrestler)

    Returns:
        Confidence score (0.0 to 1.0) where:
        - 0.9-1.0: Very confident female (100% precision thresholds)
        - 0.7-0.9: Probably female (high confidence)
        - 0.3-0.7: Uncertain
        - 0.1-0.3: Probably male
        - 0.0-0.1: Very confident male
    """
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
                    intergender_prob = estimate_intergender_probability(
                        match, wrestler_db
                    )
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


if __name__ == "__main__":
    from joshirank.joshidb import wrestler_db

    tjpw_wrestlers = all_tjpw_wrestlers(wrestler_db)
    print(f"Total TJPW wrestlers found: {len(tjpw_wrestlers)}")
    for wid in sorted(tjpw_wrestlers):
        name = wrestler_db.get_name(wid)
        print(f"{wid}: {name}")
