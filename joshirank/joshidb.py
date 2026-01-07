"""
Docstring for joshirank.joshidb

Handles persistent storage of wrestler data using shelve and sqlite3.

We keep partially-parsed scraped JSON data in a shelve database,
most notably match lists.
We use sqlite3 for efficient querying of derived wrestler metadata.

"""

import datetime
import functools
import json
import pathlib
import sqlite3
from collections import Counter
from contextlib import contextmanager

from loguru import logger

from joshirank.cagematch.profile import CMProfile
from joshirank.db_wrapper import DBWrapper


class WrestlerDb(DBWrapper):
    """Database wrapper for wrestler data storage."""

    ##
    ## Initialization Functions
    ##

    def initialize_sql_db(self):
        """If necessary, create the SQL tables for wrestler metadata."""
        self._create_wrestlers_table()
        self._create_matches_table()
        self._create_promotions_table()
        self._create_opponents_table()
        self._seed_database()

    def _create_wrestlers_table(self):
        cursor = self._rw_cursor()

        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS wrestlers (
            wrestler_id INTEGER,
            is_female BOOLEAN,
            name TEXT,
            promotion TEXT,
            last_updated TIMESTAMP,
            location TEXT,
            cm_profile_json TEXT,
            career_start TEXT,
            career_end TEXT,
           
            PRIMARY KEY (wrestler_id)  
        )
        """
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_wrestler_fem ON wrestlers (is_female)"""
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_wrestler_updated ON wrestlers (last_updated)"""
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_wrestler_promotion ON wrestlers (promotion)"""
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_wrestler_location ON wrestlers (location)"""
        )
        # Only create career_start index if column exists
        try:
            cursor.execute(
                """CREATE INDEX IF NOT EXISTS idx_wrestler_career_start ON wrestlers (career_start)"""
            )
        except sqlite3.OperationalError:
            # Column doesn't exist yet, will be added later
            pass
        cursor.close()

    def _create_matches_table(self):
        """Create the matches table if it does not exist."""
        cursor = self._rw_cursor()
        cursor.execute(
            """ CREATE TABLE IF NOT EXISTS matches (
            wrestler_id INTEGER,
            cm_matches_json TEXT,
            opponents TEXT,
            match_count INTEGER,
            countries_worked TEXT,
            promotions_worked TEXT,
            year INTEGER NOT NULL DEFAULT 2025,
            last_updated TIMESTAMP,
            PRIMARY KEY (wrestler_id, year) 
             ) """
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_matches_year ON matches (year)"""
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_matches_updated ON matches (last_updated)"""
        )
        cursor.close()

    def _create_promotions_table(self):
        """Create the promotions table if it does not exist."""
        cursor = self._rw_cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS promotions (
            promotion_id INTEGER PRIMARY KEY,
            name TEXT,
            founded TEXT,
            country TEXT,
            cm_promotion_json TEXT,
            last_updated TIMESTAMP
            )"""
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_promotion_name ON promotions (name)"""
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_promotion_updated ON promotions (last_updated)"""
        )
        cursor.close()

    def _create_opponents_table(self):
        """Create the normalized opponents table for fast lookups."""
        cursor = self._rw_cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS wrestler_opponents (
            wrestler_id INTEGER,
            opponent_id INTEGER,
            year INTEGER,
            match_count INTEGER DEFAULT 1,
            PRIMARY KEY (wrestler_id, opponent_id, year)
            )"""
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_opponent_lookup 
            ON wrestler_opponents(opponent_id, year)"""
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_wrestler_year 
            ON wrestler_opponents(wrestler_id, year)"""
        )
        cursor.close()

    def is_female(self, wrestler_id: int) -> bool:
        """Return True if the wrestler is considered female."""
        row = self._select_and_fetchone(
            """SELECT is_female FROM wrestlers WHERE wrestler_id=?""", (wrestler_id,)
        )

        if not row:
            return False
        return bool(row[0])

    ##
    ## Saving of Profile and Match data
    ##

    def save_profile_for_wrestler(
        self, wrestler_id: int, profile_data: dict
    ) -> CMProfile:
        """Save the profile data for a wrestler in the database table as JSON.

        Sets the last_updated timestamp to current time.
        Extracts additional derived fields from the profile data, including name,
        is_female, promotion, career_start.

        Does not commit; caller is responsible for committing transaction.

        Will not overwrite existing "location" field.

        Args:
            wrestler_id: ID of the wrestler
            profile_data: Dict of profile data as scraped from CageMatch

        Returns:
            The CMProfile object created from the profile_data.

        """
        cm_profile = CMProfile.from_dict(wrestler_id, profile_data)

        try:
            cm_profile_json = json.dumps(profile_data)
        except:
            logger.error(
                "Could not serialize profile data for wrestler ID {}: {}",
                wrestler_id,
                profile_data,
            )
            raise

        self._execute(
            """
        INSERT OR REPLACE INTO wrestlers
        (is_female, name, promotion, career_start, career_end, wrestler_id, cm_profile_json, last_updated, location)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, COALESCE((SELECT location FROM wrestlers WHERE wrestler_id=?), NULL))
        """,
            (
                cm_profile.is_female(),
                cm_profile.name(),
                cm_profile.promotion(),
                cm_profile.career_start(),
                cm_profile.career_end(),
                wrestler_id,
                cm_profile_json,
                wrestler_id,
            ),
        )
        return cm_profile

    def save_matches_for_wrestler(
        self, wrestler_id: int, match_data: list[dict], year: int
    ):
        """Save the match data for a wrestler in the database table as JSON.

        Also parses out opponents, countries worked, and promotions worked for metadata.
        Sets the last_updated timestamp to current time.
        Args:
            wrestler_id: ID of the wrestler
            match_data: List of match dicts as scraped from CageMatch
            year: Year the matches belong to

        Does not commit; caller is responsible for committing transaction.
        """
        try:
            cm_matches_json = json.dumps(match_data)
        except:
            logger.error(
                "Could not serialize profile data for wrestler ID {}: {}",
                wrestler_id,
                match_data,
            )
            raise

        opponents, countries_worked, promotions_worked = (
            self._extract_data_from_match_data(wrestler_id, match_data)
        )

        self._execute_and_commit(
            """
        INSERT OR REPLACE INTO matches
        (wrestler_id, year, cm_matches_json, last_updated, opponents, match_count, countries_worked, promotions_worked)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
        """,
            (
                wrestler_id,  # wrestler_id + year is the primary key
                year,
                cm_matches_json,
                json.dumps([x[0] for x in opponents.most_common()]),
                len(match_data),
                json.dumps(dict(countries_worked)),
                json.dumps(dict(promotions_worked)),
            ),
        )
        # Update normalized opponents table
        self._update_opponents_table(wrestler_id, year, opponents)

    def _extract_data_from_match_data(
        self, wrestler_id: int, match_data: list[dict]
    ) -> tuple[Counter, Counter, Counter]:
        opponents, countries_worked, promotions_worked = (
            Counter(),
            Counter(),
            Counter(),
        )
        for match in match_data:
            for wid in match["wrestlers"]:
                if wid != wrestler_id:
                    opponents[wid] += 1
            if "country" in match:
                countries_worked[match["country"]] += 1
            if "promotion" in match and match["promotion"] is not None:
                promotions_worked[match["promotion"]] += 1
        return opponents, countries_worked, promotions_worked

    def create_stale_match_stubs(self, wrestler_id: int, years: set[int]):
        """Create stub match entries for years that don't exist yet.

        These stubs are marked as stale (old timestamp) so they'll be picked up
        by the staleness policy in future scraping sessions.
        """
        existing_years = self.match_years_available(wrestler_id)
        new_years = years - existing_years

        if not new_years:
            return

        # Use a timestamp from 2 years ago to ensure they're marked as stale
        stale_timestamp = datetime.datetime.now(
            datetime.timezone.utc
        ) - datetime.timedelta(days=730)
        stale_timestamp_str = stale_timestamp.isoformat()

        for year in new_years:
            self._execute_and_commit(
                """
            INSERT OR IGNORE INTO matches
            (wrestler_id, cm_matches_json, year, last_updated)
            VALUES (?, ?, ?, ?)
            """,
                (wrestler_id, json.dumps([]), year, stale_timestamp_str),
            )

    def update_matches_from_matches(self, wrestler_id: int):
        """Using the stored json matches for the wrestler, update their metadata in the SQL db.

        Deprecated!

        """
        rows = self._select_and_fetchall(
            """SELECT cm_matches_json, year FROM matches WHERE wrestler_id=?""",
            (wrestler_id,),
        )
        for row in rows:
            if row and row[0]:
                year = row[1]
                matches = json.loads(row[0])
                opponents, countries_worked, promotions_worked = (
                    self._extract_data_from_match_data(wrestler_id, matches)
                )

                self._execute_and_commit(
                    """
                UPDATE matches
                SET opponents=?, match_count=?, countries_worked=?, promotions_worked=?
                WHERE wrestler_id=? AND year=?
                """,
                    (
                        json.dumps([x[0] for x in opponents.most_common()]),
                        len(matches),
                        json.dumps(dict(countries_worked)),
                        json.dumps(dict(promotions_worked)),
                        wrestler_id,
                        year,
                    ),
                )

                # Update normalized opponents table
                self._update_opponents_table(wrestler_id, year, opponents)

    def _update_opponents_table(self, wrestler_id: int, year: int, opponents: Counter):
        """Update the normalized opponents table for a wrestler/year."""

        cursor = self._rw_cursor()
        # Delete existing entries for this wrestler/year
        cursor.execute(
            """DELETE FROM wrestler_opponents 
            WHERE wrestler_id = ? AND year = ?""",
            (wrestler_id, year),
        )
        # Insert new entries
        for opponent_id, count in opponents.items():
            cursor.execute(
                """INSERT INTO wrestler_opponents 
                (wrestler_id, opponent_id, year, match_count)
                VALUES (?, ?, ?, ?)""",
                (wrestler_id, opponent_id, year, count),
            )
        cursor.close()
        # Note: Commit is deferred if in batch mode via _execute_and_commit or context manager

    def update_wrestler_from_matches(self, wrestler_id: int):
        """Using the stored match info for the wrestler, update their metadata in the SQL db.

        Because this is a combined read/write to the database, or rather a write based on
        a read, there may be commit issues if called within a batch mode context.
        """
        from joshirank.analysis.gender import update_gender_diverse_classification

        # Update gender classification for gender-diverse wrestlers
        update_gender_diverse_classification(wrestler_id)

    def get_cm_profile_for_wrestler(self, wrestler_id: int) -> dict:
        """Return the CM profile data for a wrestler as a dict."""
        row = self._select_and_fetchone(
            """SELECT cm_profile_json FROM wrestlers WHERE wrestler_id=?""",
            (wrestler_id,),
        )

        if row and row[0]:
            return json.loads(row[0])
        else:
            return {}

    def close(self):
        # self.db.close()
        self.sqldb_ro.close()

    def get_wrestler(self, wrestler_id: int) -> dict:
        """Given a wrestler ID, return their stored data as a dict."""
        if wrestler_id == -1:
            return {
                "name": "Placeholder",
                "last_updated": datetime.datetime.now().isoformat(),
            }
        row = self._select_and_fetchone_dict(
            """SELECT * FROM wrestlers WHERE wrestler_id=?""", (wrestler_id,)
        )
        if row:
            # convert last_updated to epoch timestamp
            if "last_updated" in row and row["last_updated"]:
                # SQLite CURRENT_TIMESTAMP is in UTC, parse as UTC and convert to epoch
                dt = datetime.datetime.fromisoformat(row["last_updated"]).replace(
                    tzinfo=datetime.timezone.utc
                )
                row["timestamp"] = dt.timestamp()
            else:
                row["timestamp"] = 0
            return row
        else:
            raise KeyError(f"Wrestler ID {wrestler_id} not found in database.")

    def all_wrestler_ids(self) -> list[int]:
        """Return a list of all wrestler IDs in the database."""
        rows = self._select_and_fetchall("""SELECT wrestler_id FROM wrestlers""", ())
        return [row[0] for row in rows]

    def wrestlers_sorted_by_match_count(self, year: int = 2025):
        "yield (wrestler id, match_count) sorted by number of matches descending"
        query = """SELECT wrestler_id, match_count FROM matches WHERE year = ? ORDER BY match_count DESC"""
        for row in self._select_and_fetchall(query, (year,)):
            yield row[0], row[1]

    def wrestler_exists(self, wrestler_id: int) -> bool:
        row = self._select_and_fetchone(
            """SELECT 1 FROM wrestlers WHERE wrestler_id=?""", (wrestler_id,)
        )

        return row is not None

    def all_female_wrestlers(self) -> list[int]:
        """Return a generator of wrestler ids and info"""
        rows = self._select_and_fetchall(
            """SELECT wrestler_id FROM wrestlers WHERE is_female=1""", ()
        )
        return [row[0] for row in rows]

    def all_female_wrestlers_with_matches_in_year(self, year: int) -> list[int]:
        """Return a list of wrestler ids"""
        rows = self._select_and_fetchall(
            """SELECT w.wrestler_id 
            FROM wrestlers w
            JOIN matches m ON w.wrestler_id = m.wrestler_id
            WHERE w.is_female=1 AND m.year=? and m.match_count > 0""",
            (year,),
        )
        return [row[0] for row in rows]

    def wrestler_in_sql(self, wrestler_id: int) -> bool:
        row = self._select_and_fetchone(
            """SELECT 1 FROM wrestlers WHERE wrestler_id=?""", (wrestler_id,)
        )

        return row is not None

    def get_name(self, wrestler_id: int) -> str:
        # first try to retrieve from sqldb
        row = self._select_and_fetchone(
            """SELECT name FROM wrestlers WHERE wrestler_id=?""", (wrestler_id,)
        )
        if row and row[0]:
            return row[0]
        else:
            return "Unknown"

    def find_wrestlers_by_name(
        self, name: str, limit: int = 50, female_only: bool = False
    ) -> list[dict]:
        """Search for wrestlers by name (case-insensitive partial match).

        Args:
            name: Name or partial name to search for
            limit: Maximum number of results to return (default 50)
            female_only: If True, only return female wrestlers

        Returns:
            List of dicts with 'wrestler_id', 'name', 'is_female', 'promotion' keys
            Sorted by exact match first, then alphabetically
        """
        search_pattern = f"%{name}%"

        if female_only:
            query = """
                SELECT wrestler_id, name, is_female, promotion 
                FROM wrestlers 
                WHERE name LIKE ? AND is_female = 1
                ORDER BY 
                    CASE WHEN LOWER(name) = LOWER(?) THEN 0 ELSE 1 END,
                    name
                LIMIT ?
            """
            rows = self._select_and_fetchall(query, (search_pattern, name, limit))
        else:
            query = """
                SELECT wrestler_id, name, is_female, promotion 
                FROM wrestlers 
                WHERE name LIKE ?
                ORDER BY 
                    CASE WHEN LOWER(name) = LOWER(?) THEN 0 ELSE 1 END,
                    name
                LIMIT ?
            """
            rows = self._select_and_fetchall(query, (search_pattern, name, limit))

        results = []
        for row in rows:
            results.append(
                {
                    "wrestler_id": row[0],
                    "name": row[1],
                    "is_female": bool(row[2]) if row[2] is not None else False,
                    "promotion": row[3] if row[3] else "",
                }
            )
        return results

    def get_matches(self, wrestler_id: int, year: int) -> list[dict]:
        # first try to get from sqlite
        row = self._select_and_fetchone(
            """SELECT cm_matches_json FROM matches WHERE wrestler_id=? AND year=?""",
            (wrestler_id, year),
        )

        if row:
            return json.loads(row[0])

        # fallback: return empty list
        return []

    def match_years_available(self, wrestler_id: int) -> set[int]:
        """Return all years that matches exist for a wrestler."""
        rows = self._select_and_fetchall(
            """SELECT year FROM matches WHERE wrestler_id=?""", (wrestler_id,)
        )
        years = set()
        for row in rows:
            years.add(int(row[0]))
        return years

    def get_matches_timestamp(self, wrestler_id: int, year: int) -> float:
        """Return the timestamp when matches were last updated for a wrestler/year.

        Returns 0 if no matches exist.
        """
        row = self._select_and_fetchone(
            """SELECT last_updated FROM matches WHERE wrestler_id=? AND year=?""",
            (wrestler_id, year),
        )
        if row and row[0]:
            # SQLite CURRENT_TIMESTAMP is in UTC, parse as UTC and convert to epoch
            dt = datetime.datetime.fromisoformat(row[0]).replace(
                tzinfo=datetime.timezone.utc
            )
            return dt.timestamp()
        return 0.0

    def get_match_info(self, wrestler_id: int, year: int = 2025) -> dict:
        """Return match metadata for a wrestler."""
        row = self._select_and_fetchone_dict(
            """SELECT opponents, match_count, countries_worked, promotions_worked 
            FROM matches WHERE wrestler_id=? AND year=?""",
            (wrestler_id, year),
        )

        if row:
            row["opponents"] = json.loads(row["opponents"]) if row["opponents"] else []
            row["match_count"] = row["match_count"] if row["match_count"] else 0
            row["countries_worked"] = (
                json.loads(row["countries_worked"]) if row["countries_worked"] else {}
            )
            row["promotions_worked"] = (
                json.loads(row["promotions_worked"]) if row["promotions_worked"] else {}
            )
            return row
        else:
            return {
                "opponents": [],
                "match_count": 0,
                "countries_worked": {},
                "promotions_worked": {},
            }

    def get_all_colleagues(self, wrestler_id: int) -> set[int]:
        """Given a wrestler ID, return a set of all wrestler IDs that appeared in a match with them across all years.

        Uses normalized opponents table for fast lookups without JSON parsing.
        """
        rows = self._select_and_fetchall(
            """SELECT DISTINCT opponent_id FROM wrestler_opponents 
            WHERE wrestler_id=?""",
            (wrestler_id,),
        )
        return {row[0] for row in rows}

    def get_all_inverse_colleagues(self, wrestler_id: int) -> set[int]:
        """Given a wrestler ID, return a set of all wrestler IDs that
        had this wrestler as an opponent across all years.

        Uses normalized opponents table with index for fast lookups (~1ms).
        """
        rows = self._select_and_fetchall(
            """SELECT DISTINCT wrestler_id FROM wrestler_opponents 
            WHERE opponent_id=?""",
            (wrestler_id,),
        )
        return {row[0] for row in rows}

    def save_promotion(self, promotion_id: int, promotion_data: dict):
        """Save promotion data to the database.

        Args:
            promotion_id: CageMatch promotion ID
            promotion_data: Dict with promotion info from parse_promotion_page()
        """
        try:
            cm_promotion_json = json.dumps(promotion_data)
        except:
            logger.error(
                "Could not serialize promotion data for promotion ID {}: {}",
                promotion_id,
                promotion_data,
            )
            raise

        name = promotion_data.get("Name", "")
        founded = promotion_data.get("Founded", "")
        country = promotion_data.get("Country", "")

        self._execute_and_commit(
            """
        INSERT OR REPLACE INTO promotions
        (promotion_id, name, founded, country, cm_promotion_json, last_updated)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (promotion_id, name, founded, country, cm_promotion_json),
        )

    def get_promotion(self, promotion_id: int) -> dict | None:
        """Get promotion data by ID.

        Returns:
            Dict with promotion info, or None if not found
        """
        row = self._select_and_fetchone_dict(
            """SELECT * FROM promotions WHERE promotion_id=?""",
            (promotion_id,),
        )
        if row:
            # Parse timestamp if present
            if "last_updated" in row and row["last_updated"]:
                dt = datetime.datetime.fromisoformat(row["last_updated"]).replace(
                    tzinfo=datetime.timezone.utc
                )
                row["timestamp"] = dt.timestamp()
            return row
        return None

    def get_promotion_name(self, promotion_id: int) -> str:
        """Get the name of a promotion by ID.

        Returns:
            Promotion name, or str(promotion_id) if not found
        """
        row = self._select_and_fetchone(
            """SELECT name FROM promotions WHERE promotion_id=?""",
            (promotion_id,),
        )
        if row and row[0]:
            return row[0]
        return str(promotion_id)

    def promotion_exists(self, promotion_id: int) -> bool:
        """Check if a promotion exists in the database."""
        row = self._select_and_fetchone(
            """SELECT 1 FROM promotions WHERE promotion_id=?""",
            (promotion_id,),
        )
        return row is not None

    def all_promotion_ids(self) -> list[int]:
        """Return a list of all promotion IDs in the database."""
        rows = self._select_and_fetchall("""SELECT promotion_id FROM promotions""", ())
        return [row[0] for row in rows]

    def get_promotion_timestamp(self, promotion_id: int) -> float:
        """Get the last update timestamp for a promotion.

        Returns 0 if promotion not found.
        """
        row = self._select_and_fetchone(
            """SELECT last_updated FROM promotions WHERE promotion_id=?""",
            (promotion_id,),
        )
        if row and row[0]:
            dt = datetime.datetime.fromisoformat(row[0]).replace(
                tzinfo=datetime.timezone.utc
            )
            return dt.timestamp()
        return 0.0

    def _seed_database(self):
        """Seed the database with known missing profiles."""
        logger.info("Seeding database with known missing profiles...")
        missing_wrestlers = [9232]
        for wid in missing_wrestlers:
            self.save_profile_for_wrestler(wid, {"Missing Profile": True})
            self.save_matches_for_wrestler(wid, [], 2025)


# Default read-only database instance for convenience
_default_db_path = pathlib.Path("data/joshi_wrestlers.y")
wrestler_db = WrestlerDb(_default_db_path)


@functools.lru_cache(maxsize=None)
def get_name(wrestler_id: int) -> str:
    return wrestler_db.get_name(wrestler_id)


@functools.lru_cache(maxsize=None)
def get_promotion_name(promotion_id: int) -> str:
    """Get promotion name by ID, with caching.

    Args:
        promotion_id: CageMatch promotion ID

    Returns:
        Promotion name, or str(promotion_id) if not found
    """
    return wrestler_db.get_promotion_name(promotion_id)


if __name__ == "__main__":
    # remove the cm_matches_json column from the wrestlers table

    pass
