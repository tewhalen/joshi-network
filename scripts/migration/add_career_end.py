#!/usr/bin/env python
"""Migration: reprocess all stored match data

Updates all the derived columns, and theoretically doesn't change the timestamps.

This script performs a write operation on the default database via WrestlerDb.
"""

import json
from collections import Counter

from bs4 import BeautifulSoup
from loguru import logger

from joshirank.cagematch.cm_match import parse_match
from joshirank.joshidb import wrestler_db


def column_exists(table: str, column: str) -> bool:
    rows = wrestler_db._select_and_fetchall(
        f"PRAGMA table_info({table})",
        (),
    )
    for row in rows:
        # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
        if len(row) >= 2 and row[1] == column:
            return True
    return False


def add_column_if_missing():
    if column_exists("matches", "names_used"):
        logger.info("Column 'names_used' already exists; skipping ALTER TABLE.")
        return False

    logger.info("Adding column 'names_used' (TEXT) to matches table...")
    with wrestler_db.writable():
        wrestler_db._execute_and_commit(
            "ALTER TABLE matches ADD COLUMN names_used TEXT",
            (),
        )
    logger.success("Added column 'names_used'.")
    return True


def populate_names_used():
    rows = wrestler_db._select_and_fetchall(
        """
        SELECT wrestler_id, year, cm_matches_json
        FROM matches
        WHERE cm_matches_json IS NOT NULL AND cm_matches_json != '[]'
        """,
        (),
    )

    total = len(rows)
    fixed = 0
    errors = 0

    logger.info("Populating names_used for {} wrestler-years...", total)

    with wrestler_db.writable():
        i = 0
        for wrestler_id, year, json_str in rows:
            i += 1
            try:
                data = json.loads(json_str)
                match_data = []
                names_used = Counter()
                for old_match_data in data:
                    match_soup = BeautifulSoup(
                        old_match_data["raw_html"], "html.parser"
                    )
                    new_match_data = parse_match(match_soup)
                    match_data.append(new_match_data)
                    # nothing is lost, we hope
                    assert new_match_data["raw_html"] == old_match_data["raw_html"], (
                        "Raw HTML mismatch after reparsing"
                    )
                opponents, countries_worked, promotions_worked, names_used = (
                    wrestler_db._extract_data_from_match_data(wrestler_id, match_data)
                )

                wrestler_db._execute(
                    """
                    UPDATE matches
                    SET cm_matches_json = ?, opponents = ?, names_used = ?, countries_worked = ?,
                    promotions_worked = ?
                    WHERE wrestler_id = ? AND year = ?
                    """,
                    (
                        json.dumps(match_data),
                        json.dumps([x[0] for x in opponents.most_common()]),
                        json.dumps(dict(names_used)),
                        json.dumps(dict(countries_worked)),
                        json.dumps(dict(promotions_worked)),
                        wrestler_id,
                        year,
                    ),
                )
                fixed += 1

            except Exception as e:
                logger.error("Error updating {}: {}", wrestler_id, e)
                errors += 1
            if i % 100 == 0:
                logger.info(
                    "Processed {}/{} wrestler-years ({} updated, {} errors)",
                    i,
                    total,
                    fixed,
                    errors,
                )
    logger.success("Populated names_used: {} updated, {} errors", fixed, errors)


def main():
    added = add_column_if_missing()
    populate_names_used()
    if added:
        logger.info("Migration completed: column added and values populated.")
    else:
        logger.info("Migration completed: values populated for existing column.")


if __name__ == "__main__":
    main()
