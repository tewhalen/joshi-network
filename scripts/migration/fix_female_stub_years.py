"""Fix stub match records for female wrestlers by using career start data.

Replaces stub records for female wrestlers who have no actual matches
with stubs based on their career start year (if available).
"""

import time

from loguru import logger

from joshirank.cagematch.profile import CMProfile
from joshirank.joshidb import reopen_rw

YEAR = time.localtime().tm_year


def guess_likely_match_year(profile_data: dict) -> int:
    """Guess which year is most likely to have matches for a wrestler.

    Uses career start date to start scraping from the beginning:
    - If career start year is available: use that year (to find earliest matches)
    - If no career start data: use previous year (safest bet for active wrestlers)

    Args:
        profile_data: Dict with profile data from database

    Returns:
        Year (int) most likely to have match data
    """
    # Parse profile as CMProfile to get career_start
    cm_profile = CMProfile.from_dict(0, profile_data)  # wrestler_id doesn't matter here
    career_start = cm_profile.career_start()

    if career_start:
        # Extract year from career_start (could be YYYY-MM-DD or just YYYY)
        try:
            if len(career_start) == 4:  # Just year "YYYY"
                start_year = int(career_start)
            else:  # Full date "YYYY-MM-DD"
                start_year = int(career_start.split("-")[0])

            logger.debug("Career started in {}, using that year", start_year)
            return start_year
        except (ValueError, AttributeError) as e:
            logger.debug("Could not parse career start '{}': {}", career_start, e)

    # Fallback: previous year is safest bet for active wrestlers
    logger.debug("No career start data, defaulting to previous year")
    return YEAR - 1


def find_female_stub_only_wrestlers(db):
    """Find female wrestlers who have no matches but only stub records from 2025/2026."""
    stub_only_wrestlers = []

    for wrestler_id in db.all_female_wrestlers():
        # Get all years available
        years = db.match_years_available(wrestler_id)

        if not years:
            continue

        # Check if any year has actual matches
        has_any_matches = False
        for year in years:
            matches = db.get_matches(wrestler_id, year)
            if matches:  # Has actual matches
                has_any_matches = True
                break

        # If no matches at all, and only has 2025/2026 stub records
        if not has_any_matches and years.issubset({2025, 2026}):
            stub_only_wrestlers.append(wrestler_id)

    return stub_only_wrestlers


def fix_stub_years(dry_run: bool = True):
    """Fix stub years for female wrestlers with no actual matches.

    Args:
        dry_run: If True, only report what would be changed without actually changing
    """
    with reopen_rw() as db:
        stub_wrestlers = find_female_stub_only_wrestlers(db)

        logger.info("Found {} female wrestlers with stub-only records", len(stub_wrestlers))

        changes = []
        for wid in stub_wrestlers:
            name = db.get_name(wid)
            current_years = sorted(db.match_years_available(wid))
            profile_data = db.get_cm_profile_for_wrestler(wid)

            # Calculate better year guess
            better_year = guess_likely_match_year(profile_data)

            # Only change if it's actually different
            if better_year not in current_years:
                changes.append((wid, name, current_years, better_year))

        if not changes:
            logger.success("No changes needed - all stubs already use optimal years")
            return

        logger.info("Would update {} wrestlers with better stub years", len(changes))

        for wid, name, old_years, new_year in changes:
            logger.info(
                "  {} ({}): {} -> {}",
                name,
                wid,
                old_years,
                [new_year],
            )

        if dry_run:
            logger.info("DRY RUN MODE - no changes made")
            logger.info("Run with --execute to actually update records")
        else:
            logger.info("Updating stub years...")
            for wid, name, old_years, new_year in changes:
                # Delete old stubs
                for year in old_years:
                    db._execute_and_commit(
                        "DELETE FROM matches WHERE wrestler_id=? AND year=?",
                        (wid, year),
                    )

                # Create new stub with better year
                db.create_stale_match_stubs(wid, {new_year})

                logger.debug("Updated {} ({}): {} -> {}", name, wid, old_years, new_year)

            logger.success("Updated {} wrestlers", len(changes))


if __name__ == "__main__":
    import sys

    dry_run = "--execute" not in sys.argv

    if dry_run:
        logger.info("DRY RUN MODE - no changes will be made")
        logger.info("Run with --execute to actually update records")

    fix_stub_years(dry_run=dry_run)
