"""Purge stub match records for non-female wrestlers.

Removes match-year stub records for non-female wrestlers that have:
1. Only stub records from 2025/2026
2. No actual match data

These records are useless since we don't scrape matches for non-female wrestlers.
"""

import sys

from loguru import logger

from joshirank.joshidb import reopen_rw, wrestler_db


def find_purgeable_stubs() -> list[tuple[int, str, set[int]]]:
    """Find non-female wrestlers with only empty stub records from 2025/2026.

    Returns:
        List of (wrestler_id, name, years) tuples
    """
    purgeable = []

    for wrestler_id in wrestler_db.all_wrestler_ids():
        # Only process non-female wrestlers
        if wrestler_db.is_female(wrestler_id):
            continue

        # Get all years available
        years = wrestler_db.match_years_available(wrestler_id)

        if not years:
            continue

        # Check if any year has actual matches
        has_any_matches = False
        for year in years:
            matches = wrestler_db.get_matches(wrestler_id, year)
            if matches:  # Has actual matches
                has_any_matches = True
                break

        # If no matches at all, and only has 2025/2026 stub records
        if not has_any_matches:
            if years.issubset({2025, 2026}):
                name = wrestler_db.get_name(wrestler_id)
                purgeable.append((wrestler_id, name, years))

    return purgeable


def purge_stub_matches(dry_run: bool = True) -> tuple[int, int]:
    """Purge empty stub match records for non-female wrestlers.

    Args:
        dry_run: If True, only report what would be deleted

    Returns:
        Tuple of (total_records_purged, wrestlers_affected)
    """
    purgeable = find_purgeable_stubs()

    if not purgeable:
        logger.info("No purgeable stub records found")
        return 0, 0

    total_records = 0

    if dry_run:
        logger.info("DRY RUN - no changes will be made")
        for wid, name, years in sorted(purgeable):
            logger.info(
                "Would purge {} stub records for wrestler {} ({}): {}",
                len(years),
                wid,
                name,
                sorted(years),
            )
            total_records += len(years)
    else:
        logger.info("DELETING stub records...")
        with reopen_rw() as db:
            for wid, name, years in sorted(purgeable):
                logger.info(
                    "Purging {} stub records for wrestler {} ({}): {}",
                    len(years),
                    wid,
                    name,
                    sorted(years),
                )
                for year in years:
                    cursor = db.sqldb.cursor()
                    cursor.execute(
                        """DELETE FROM matches WHERE wrestler_id=? AND year=?""",
                        (wid, year),
                    )
                    total_records += cursor.rowcount
                    cursor.close()

            db.sqldb.commit()
            logger.success(
                "Purged {} stub records from {} wrestlers",
                total_records,
                len(purgeable),
            )

    return total_records, len(purgeable)


if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv

    if dry_run:
        logger.info("Running in DRY RUN mode (use --execute to actually delete)")

    total_records, num_wrestlers = purge_stub_matches(dry_run=dry_run)

    if dry_run:
        logger.success(
            "Would purge {} stub records from {} non-female wrestlers",
            total_records,
            num_wrestlers,
        )
        logger.info("Run with --execute to actually delete records")
    else:
        logger.success(
            "Purged {} stub records from {} non-female wrestlers",
            total_records,
            num_wrestlers,
        )
