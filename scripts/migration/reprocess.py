"""Script to reprocess profiles and matches without scraping."""

import pprint

from bs4 import BeautifulSoup
from loguru import logger

from joshirank.cagematch.cm_match import parse_match
from joshirank.joshidb import wrestler_db

WEEK = 60 * 60 * 24 * 7

LOAD_COUNT = 0


def refresh_wrestler(wrestler_id: int) -> dict:
    """Reload wrestler profile and matches from CageMatch.net if older than a week."""
    wrestler_db.update_wrestler_from_profile(wrestler_id)
    reprocess_matches_for_wrestler(wrestler_id)


def reprocess_matches_for_wrestler(wrestler_id: int) -> None:
    """Reprocess matches for a wrestler."""
    matches = list(wrestler_db.get_matches(wrestler_id))
    new_matches = []
    # pprint.pprint(matches)
    if not matches:
        return
    # print(f"Reprocessing {len(matches)} matches for wrestler {wrestler_id}")
    # print(list(range(len(matches))))

    for match_index in range(len(matches)):
        match = matches[match_index]

        match_soup = BeautifulSoup(match["raw_html"], "lxml")

        parsed_match = parse_match(match_soup)

        new_matches.append(parsed_match)

    wrestler_db.save_matches_for_wrestler(wrestler_id, new_matches)
    if new_matches:
        wrestler_db.update_matches_from_matches(wrestler_id)
        wrestler_db.update_wrestler_from_matches(wrestler_id)


def copy_and_recreate_matches_table() -> None:
    """Copy matches to a temp table, drop and recreate matches table, copy back."""
    wrestler_db._execute_and_commit(
        """
     ALTER TABLE matches RENAME TO matches_old;
     """,
        tuple(),
    )
    wrestler_db._create_matches_table()
    wrestler_db._execute_and_commit(
        """
     INSERT INTO matches (wrestler_id, cm_matches_json, year)
     SELECT wrestler_id, cm_matches_json, year
     FROM matches_old;
     """,
        tuple(),
    )
    wrestler_db._execute_and_commit(
        """
     DROP TABLE matches_old;
    """,
        tuple(),
    )


def set_year_to_2025_where_missing() -> None:
    """Set year to 2025 where missing in matches table."""

    # first find any wrestlers with both a NULL and a 2025 entry
    wrestler_rows = wrestler_db._select_and_fetchall(
        """
    SELECT DISTINCT wrestler_id
    FROM matches
    WHERE wrestler_id IN (
        SELECT wrestler_id
        FROM matches
        WHERE year IS NULL
    ) AND wrestler_id IN (
        SELECT wrestler_id
        FROM matches
        WHERE year=2025
    );
    """,
        tuple(),
    )
    # delete the NULL entries for those wrestlers
    for (wrestler_id,) in wrestler_rows:
        wrestler_db._execute_and_commit(
            """
        DELETE FROM matches
        WHERE wrestler_id=? AND year IS NULL;
        """,
            (wrestler_id,),
        )
    wrestler_db._execute_and_commit(
        """
    UPDATE matches
    SET year=2025
    WHERE year IS NULL;
    """,
        tuple(),
    )


def remove_unreferenced_wrestlers():
    """Remove wrestlers from wrestlers table and matches table if they're not in anyone else's matches."""
    referenced_wrestlers = set()
    all_wrestler_ids = set(int(wid) for wid in wrestler_db.all_wrestler_ids())
    for wrestler_id in all_wrestler_ids:
        matches = wrestler_db.get_matches(int(wrestler_id))
        for match in matches:
            referenced_wrestlers.update(match["wrestlers"])

    unreferenced_wrestlers = all_wrestler_ids.difference(referenced_wrestlers)
    print(f"Removing {len(unreferenced_wrestlers)} unreferenced wrestlers")
    for wrestler_id in unreferenced_wrestlers:
        wrestler_db._execute_and_commit(
            """
        DELETE FROM wrestlers
        WHERE wrestler_id=?;
        """,
            (wrestler_id,),
        )
        wrestler_db._execute_and_commit(
            """
        DELETE FROM matches
        WHERE wrestler_id=?;
        """,
            (wrestler_id,),
        )


if __name__ == "__main__":
    # copy_and_recreate_matches_table()
    # set_year_to_2025_where_missing()
    # sys.exit()
    logger.info("Starting reprocess...")
    remove_unreferenced_wrestlers()

    # refresh_wrestler(32844)
    # sys.exit()
    for i, wrestler_id in enumerate(wrestler_db.all_female_wrestlers(), start=1):
        refresh_wrestler(int(wrestler_id))

    wrestler_db.close()
    logger.info("Reprocess complete.")
