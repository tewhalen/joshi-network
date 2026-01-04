"""Purge empty match-year records for inactive wrestlers.

Removes match-year records that are:
1. Empty (no matches)
2. Recently scraped (confirming no activity)
3. After the wrestler's last known active year

This prevents wasting scraping resources on wrestlers who have retired.

Example: A wrestler last active in 2021, with recently-scraped empty records for 2024-2026,
should have those empty records purged since we've confirmed they're inactive.
"""

import time

from loguru import logger

from joshirank.joshidb import reopen_rw

CURRENT_YEAR = time.localtime().tm_year
RECENT_SCRAPE_THRESHOLD_DAYS = 90  # Consider a scrape "recent" if within 90 days


def get_active_year_range(db, wrestler_id: int) -> tuple[int | None, int | None]:
    """Get the earliest and latest years with actual matches for a wrestler.

    Returns:
        (earliest_year, latest_year) or (None, None) if no matches found
    """
    years_with_matches = []

    for year in db.match_years_available(wrestler_id):
        matches = db.get_matches(wrestler_id, year)
        if matches:  # Has actual matches
            years_with_matches.append(year)

    if not years_with_matches:
        return None, None

    return min(years_with_matches), max(years_with_matches)


def should_purge_empty_year(
    year: int,
    timestamp: float,
    earliest_active: int | None,
    latest_active: int | None,
    current_year: int = CURRENT_YEAR,
) -> bool:
    """Determine if an empty match-year record should be purged.

    Logic:
    - If no active years known: keep (wrestler might be newly discovered)
    - If wrestler was active in 2025: keep all records (might still be active)
    - If wrestler NOT active in 2025: purge all empty years after last activity (if recently scraped)

    Examples:
        - Latest active: 2025 → Don't purge anything (current year)
        - Latest active: 2024 → Purge 2025, 2026 (if recently scraped)
        - Latest active: 2023 → Purge 2024+ (if recently scraped)
        - Latest active: 2021 → Purge 2022+ (if recently scraped)

    Args:
        year: The year to check
        timestamp: When this match-year was last scraped (epoch time)
        earliest_active: Earliest year with matches (or None)
        latest_active: Latest year with matches (or None)
        current_year: Current year

    Returns:
        True if this empty year should be purged
    """
    if earliest_active is None or latest_active is None:
        # No known matches - keep the stubs in case they're newly discovered
        return False

    # If wrestler was active in 2025, don't purge anything
    if latest_active >= 2025:
        return False

    # Keep empty records for years during or before known activity
    if year <= latest_active:
        return False

    # For years after latest activity, check if we've recently confirmed emptiness
    current_time = time.time()
    days_since_scrape = (current_time - timestamp) / 86400  # Convert seconds to days

    is_recently_scraped = days_since_scrape <= RECENT_SCRAPE_THRESHOLD_DAYS

    # Purge if: year is after known activity AND we recently confirmed it's empty
    if is_recently_scraped:
        return True

    # Keep if: not recently checked (we should verify the emptiness)
    return False


def purge_inactive_empty_matches(dry_run: bool = True):
    """Remove empty match-year records for inactive wrestlers.

    Args:
        dry_run: If True, only report what would be deleted without actually deleting
    """
    with reopen_rw() as db:
        cursor = db.sqldb.cursor()
        cursor.execute("SELECT DISTINCT wrestler_id FROM matches")
        wrestler_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()

        logger.info("Analyzing {} wrestlers", len(wrestler_ids))

        total_checked = 0
        total_purged = 0
        wrestlers_affected = 0

        for wid in wrestler_ids:
            earliest, latest = get_active_year_range(db, wid)
            available_years = db.match_years_available(wid)

            years_to_purge = []

            for year in available_years:
                matches = db.get_matches(wid, year)
                timestamp = db.get_matches_timestamp(wid, year)
                total_checked += 1

                # Only consider empty records
                if not matches:
                    if should_purge_empty_year(
                        year, timestamp, earliest, latest, CURRENT_YEAR
                    ):
                        years_to_purge.append(year)

            if years_to_purge:
                name = db.get_name(wid)
                active_range = f"{earliest}-{latest}" if earliest else "unknown"

                logger.info(
                    "Wrestler {} ({}): active {}, purging empty years: {}",
                    wid,
                    name,
                    active_range,
                    sorted(years_to_purge),
                )

                if not dry_run:
                    cursor = db.sqldb.cursor()
                    for year in years_to_purge:
                        cursor.execute(
                            "DELETE FROM matches WHERE wrestler_id=? AND year=?",
                            (wid, year),
                        )
                        total_purged += 1
                    db.sqldb.commit()
                    cursor.close()
                else:
                    total_purged += len(years_to_purge)

                wrestlers_affected += 1

        mode = "Would purge" if dry_run else "Purged"
        logger.success(
            "{} {} empty match-years from {} wrestlers (checked {} total records)",
            mode,
            total_purged,
            wrestlers_affected,
            total_checked,
        )

        if dry_run:
            logger.info("Run with dry_run=False to actually delete records")


if __name__ == "__main__":
    import sys

    dry_run = "--execute" not in sys.argv

    if dry_run:
        logger.info("DRY RUN MODE - no changes will be made")
        logger.info("Run with --execute to actually delete records")
    else:
        logger.warning("EXECUTE MODE - records will be deleted!")

    purge_inactive_empty_matches(dry_run=dry_run)
