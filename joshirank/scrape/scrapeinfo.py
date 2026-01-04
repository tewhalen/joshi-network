import random
import time
from collections import Counter, defaultdict

import joshirank.cagematch.data as cm_data
from joshirank.joshidb import WrestlerDb
from joshirank.scrape.staleness import StalenessPolicy

WEEK = 60 * 60 * 24 * 7


class WrestlerScrapeInfo:
    """Interface to check wrestler profile freshness and existence."""

    wrestler_db: WrestlerDb
    staleness_policy: StalenessPolicy

    def __init__(self, wrestler_db: WrestlerDb, current_year: int = 2026):
        self.wrestler_db = wrestler_db
        self.staleness_policy = StalenessPolicy(current_year=current_year)
        self.current_year = current_year

    def wrestler_info_is_stale(self, wrestler_id: int) -> bool:
        """Return True if the wrestler profile should be refreshed.

        Uses different thresholds based on gender:
        - Female wrestlers: 90 days
        - Non-female wrestlers: 365 days
        """
        wrestler_info = self.wrestler_db.get_wrestler(wrestler_id)
        timestamp = wrestler_info.get("timestamp", 0)
        is_female = self.wrestler_db.is_female(wrestler_id)
        return self.staleness_policy.profile_is_stale(timestamp, is_female)

    def wrestler_profile_missing(self, wrestler_id: int) -> bool:
        """Return True if the wrestler profile is missing."""
        if wrestler_id in cm_data.missing_profiles:
            return False  # we know this profile is missing, don't try to reload it
        try:
            wrestler_info = self.wrestler_db.get_wrestler(wrestler_id)
        except KeyError:
            # wrestler not in DB, definitely refresh
            return True

        if not wrestler_info:
            # wrestler in DB but no info, definitely refresh
            return True
        return False

    def profile_age(self, wrestler_id: int) -> str:
        """Return the age of the wrestler profile in a nice human-readable string."""
        wrestler_info = self.wrestler_db.get_wrestler(wrestler_id)
        if not wrestler_info or "last_updated" not in wrestler_info:
            return "never"
        age_seconds = max(0, time.time() - wrestler_info["timestamp"])
        if age_seconds < 60:
            return f"{int(age_seconds)} seconds"
        elif age_seconds < 3600:
            return f"{int(age_seconds / 60)} minutes"
        elif age_seconds < 86400:
            return f"{int(age_seconds / 3600)} hours"
        else:
            return f"{int(age_seconds / 86400)} days"

    def find_missing_wrestlers(self):
        """Yield all wrestlers present in matches but missing from the database."""
        appearance_counter = Counter()
        opponent_tracker = defaultdict(set)
        for wrestler_id in self.wrestler_db.all_wrestler_ids():
            colleagues = self.wrestler_db.get_all_colleagues(wrestler_id)
            for wid in colleagues:
                if not self.wrestler_db.wrestler_exists(wid):
                    appearance_counter[wid] += 1
                    opponent_tracker[wid].add(wrestler_id)
        for wid, count in appearance_counter.most_common():
            yield wid, count, opponent_tracker[wid]

    def random_wrestlers(self, count: int, year: int):
        all_wrestler_ids = self.wrestler_db.all_wrestler_ids()
        random_ids = random.sample(all_wrestler_ids, count)
        return random_ids

    def wrestlers_without_profiles(self):
        """Yield all wrestler ids that have matches but no profile."""

        for wrestler_id in self.wrestler_db.all_wrestler_ids():
            wrestler_info = self.wrestler_db.get_cm_profile_for_wrestler(wrestler_id)

            if not wrestler_info:
                yield wrestler_id

    def wrestler_should_be_refreshed(
        self, wrestler_id: int, skip_gender_check=False
    ) -> bool:
        """Return True if the wrestler should be refreshed.

        Wrestlers with missing profiles, or female wrestlers with stale info, are refreshed."""
        if self.wrestler_profile_missing(wrestler_id):
            return True
        elif self.wrestler_info_is_stale(wrestler_id):
            if skip_gender_check:
                return True
            elif self.wrestler_db.is_female(wrestler_id):
                return True
        return False

    def is_recently_active(self, wrestler_id: int) -> bool:
        """Check if wrestler had matches in the previous 1-2 years.

        Used to determine if we should check current year matches.
        Inactive wrestlers (no matches in recent years) are skipped for current year.
        """
        available_years = self.wrestler_db.match_years_available(wrestler_id)

        # Check if they have matches in previous 2 years
        recent_years = {self.current_year - 1, self.current_year - 2}
        return bool(available_years & recent_years)

    def matches_need_refresh(
        self, wrestler_id: int, year: int, is_gender_diverse: bool = False
    ) -> bool:
        """Return True if matches for a specific year need refreshing.

        Uses year-based thresholds:
        - Current year (2026): 14 days for recently active female wrestlers
        - Previous year (2025): 90 days for female wrestlers
        - Historical (2024-): 180 days for female wrestlers (365 days if inactive)
        - Non-female wrestlers: never refresh matches

        Args:
            wrestler_id: The wrestler to check
            year: The year of match data to check
            is_gender_diverse: If True, bypass is_female check and treat as active female
        """
        is_female = self.wrestler_db.is_female(wrestler_id)
        if not is_female and not is_gender_diverse:
            return False

        timestamp = self.wrestler_db.get_matches_timestamp(wrestler_id, year)
        is_active = self.is_recently_active(wrestler_id) or is_gender_diverse

        return self.staleness_policy.matches_are_stale(
            timestamp, year, is_female or is_gender_diverse, is_active
        )

    def get_stale_match_years(self, wrestler_id: int) -> list[tuple[int, int]]:
        """Return list of (year, priority) tuples for years needing refresh.

        Returns in priority order (lower priority number = higher urgency).
        """
        is_female = self.wrestler_db.is_female(wrestler_id)
        if not is_female:
            return []

        available_years = self.wrestler_db.match_years_available(wrestler_id)
        stale_years = []
        is_active = self.is_recently_active(wrestler_id)

        for year in available_years:
            if self.matches_need_refresh(wrestler_id, year):
                priority = self.staleness_policy.match_priority(
                    year, is_female, is_active
                )
                stale_years.append((year, priority))

        # Sort by priority (lower number = higher priority)
        stale_years.sort(key=lambda x: x[1])
        return stale_years

    def calculate_importance(self, wrestler_id: int) -> float:
        """Calculate wrestler importance based on recent activity.

        Returns a score from 0 (least important) to 1 (most important).
        Based on matches and unique opponents in the past 2 years.
        """
        total_matches = 0
        unique_opponents = set()

        # Check last 2 years of data
        for year in [self.current_year - 1, self.current_year - 2]:
            match_info = self.wrestler_db.get_match_info(wrestler_id, year)
            total_matches += match_info.get("match_count", 0)
            unique_opponents.update(match_info.get("opponents", []))

        # Normalize scores (cap at reasonable maxima)
        match_score = min(total_matches / 100.0, 1.0)  # 100+ matches = max
        opponent_score = min(len(unique_opponents) / 50.0, 1.0)  # 50+ opponents = max

        # Combine scores (weight matches slightly more than opponent diversity)
        importance = (match_score * 0.6) + (opponent_score * 0.4)
        return importance
