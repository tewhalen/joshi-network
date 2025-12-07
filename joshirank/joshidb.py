"""
Docstring for joshirank.joshidb

Handles persistent storage of wrestler data using shelve and sqlite3.

We keep partially-parsed scraped JSON data in a shelve database,
most notably match lists.
We use sqlite3 for efficient querying of derived wrestler metadata.

"""

import functools
import json
import pathlib
import sqlite3
from collections import Counter

from loguru import logger

from joshirank.cagematch.profile import CMProfile
from joshirank.db_wrapper import DBWrapper


@functools.lru_cache(maxsize=None)
def is_joshi(wrestler_id: int) -> bool:
    """Determine if a wrestler is female based on their profile data."""

    return db.is_female(wrestler_id)


class WrestlerDb(DBWrapper):
    def __init__(self, path: pathlib.Path):
        self.path = path

        self.sqldb = sqlite3.connect(str(self.path.with_suffix(".sqlite3")))
        self._initialize_sql_db()

    def _initialize_sql_db(self):
        """If necessary, create the SQL tables for wrestler metadata."""
        cursor = self.sqldb.cursor()
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
           
            PRIMARY KEY (wrestler_id)  
        )
        """
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_wrestler_fem ON wrestlers (is_female)"""
        )
        cursor.execute(
            """ CREATE TABLE IF NOT EXISTS matches (
            wrestler_id INTEGER,
            cm_matches_json TEXT,
            opponents TEXT,
            match_count INTEGER,
            countries_worked TEXT,
           
           
            PRIMARY KEY (wrestler_id) 
             ) """
        )
        cursor.close()
        self.sqldb.commit()

    def is_female(self, wrestler_id: int) -> bool:
        """Return True if the wrestler is considered female."""
        row = self._select_and_fetchone(
            """Select is_female from wrestlers where wrestler_id=?""", (wrestler_id,)
        )

        if not row:
            return False
        return bool(row[0])

    def save_profile_for_wrestler(self, wrestler_id: int, profile_data: dict):
        """Save the profile data for a wrestler in the sql table as JSON."""
        cm_profile_json = json.dumps(profile_data)
        self._execute_and_commit(
            """
        INSERT OR REPLACE INTO wrestlers
        (wrestler_id, cm_profile_json, last_updated)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
            (wrestler_id, cm_profile_json),
        )

    def get_cm_profile_for_wrestler(self, wrestler_id: int) -> dict:
        """Return the CM profile data for a wrestler as a dict."""
        row = self._select_and_fetchone(
            """Select cm_profile_json from wrestlers where wrestler_id=?""",
            (wrestler_id,),
        )

        if row and row[0]:
            return json.loads(row[0])
        else:
            return {}

    def update_wrestler_from_profile(self, wrestler_id: int):
        """Using the stored profile info for the wrestler, update their metadata in the SQL db."""

        wrestler_profile = self.get_cm_profile_for_wrestler(wrestler_id)
        if not wrestler_profile:
            raise ValueError(
                f"No profile data found for wrestler ID {wrestler_id} to update from."
            )
        cm_profile = CMProfile.from_dict(wrestler_id, wrestler_profile)

        self._execute_and_commit(
            """
        UPDATE wrestlers
        SET is_female=?, name=?, promotion=?
        WHERE wrestler_id=?
        """,
            (
                cm_profile.is_female(),
                cm_profile.name(),
                cm_profile.promotion(),
                wrestler_id,
            ),
        )

    def save_matches_for_wrestler(self, wrestler_id: int, matches: list[dict]):
        """Save the match data for a wrestler in the sql table as JSON."""
        cm_matches_json = json.dumps(matches)
        self._execute_and_commit(
            """
        INSERT OR REPLACE INTO matches
        (wrestler_id, cm_matches_json)
        VALUES (?, ?)
        """,
            (wrestler_id, cm_matches_json),
        )

    def update_matches_from_matches(self, wrestler_id: int):
        """Using the stored json matches for the wrestler, update their metadata in the SQL db."""
        row = self._select_and_fetchone(
            """Select cm_matches_json from matches where wrestler_id=?""",
            (wrestler_id,),
        )

        if row and row[0]:
            matches = json.loads(row[0])
            if not matches:
                return
            opponents, countries_worked = Counter(), Counter()
            for match in matches:
                for wid in match["wrestlers"]:
                    if wid != wrestler_id:
                        opponents[wid] += 1
                if "country" in match:
                    countries_worked[match["country"]] += 1
            self._execute_and_commit(
                """
            UPDATE matches
            SET opponents=?, match_count=?, countries_worked=?
            WHERE wrestler_id=?
            """,
                (
                    json.dumps([x[0] for x in opponents.most_common()]),
                    len(matches),
                    json.dumps(dict(countries_worked)),
                    wrestler_id,
                ),
            )

    def update_wrestler_from_matches(self, wrestler_id: int):
        """Using the stored match info for the wrestler, update their metadata in the SQL db."""
        # get countries worked from matches
        row = self._select_and_fetchone(
            """Select countries_worked from matches where wrestler_id=?""",
            (wrestler_id,),
        )

        if row and row[0]:
            # should be a dict stored as json
            countries_worked = json.loads(row[0])
            location = "Unknown"
            if countries_worked:
                # get the most common country
                location = max(countries_worked.items(), key=lambda x: x[1])[0]

            self._execute_and_commit(
                """
            UPDATE wrestlers
            SET location=?
            WHERE wrestler_id=?
            """,
                (location, wrestler_id),
            )
            cursor.close()
            self.sqldb.commit()

    def close(self):
        # self.db.close()
        self.sqldb.close()

    def get_wrestler(self, wrestler_id: int) -> dict:
        """Given a wrestler ID, return their stored data as a dict."""
        row = self._select_and_fetchone_dict(
            """Select * from wrestlers where wrestler_id=?""", (wrestler_id,)
        )
        if row:
            return row
        else:
            raise KeyError(f"Wrestler ID {wrestler_id} not found in database.")

    def all_wrestler_ids(self) -> list[int]:
        """Return a list of all wrestler IDs in the database."""
        rows = self._select_and_fetchall("""Select wrestler_id from wrestlers""", ())
        return [row[0] for row in rows]

    def wrestler_exists(self, wrestler_id: int) -> bool:
        row = self._select_and_fetchone(
            """Select 1 from wrestlers where wrestler_id=?""", (wrestler_id,)
        )

        return row is not None

    def all_female_wrestlers(self):
        """Return a generator of wrestler ids and info"""
        rows = self._select_and_fetchall(
            """Select wrestler_id from wrestlers where is_female=1""", ()
        )
        return [row[0] for row in rows]

    def wrestler_in_sql(self, wrestler_id: int) -> bool:
        row = self._select_and_fetchone(
            """Select 1 from wrestlers where wrestler_id=?""", (wrestler_id,)
        )

        return row is not None

    def get_name(self, wrestler_id: int) -> str:

        # first try to retrieve from sqldb
        row = self._select_and_fetchone(
            """Select name from wrestlers where wrestler_id=?""", (wrestler_id,)
        )
        if row and row[0]:
            return row[0]

        else:
            raise KeyError(f"Wrestler ID {wrestler_id} not found in database.")

    def get_matches(self, wrestler_id: int) -> list[dict]:
        # first try to get from sqlite
        row = self._select_and_fetchone(
            """Select cm_matches_json from matches where wrestler_id=?""",
            (wrestler_id,),
        )

        if row and row[0]:
            matches = json.loads(row[0])
            if matches:
                return matches

        # fallback: return empty list
        return []

    def get_match_info(self, wrestler_id: int) -> dict:
        """Return match metadata for a wrestler."""
        row = self._select_and_fetchone_dict(
            """Select opponents, match_count, countries_worked from matches where wrestler_id=?""",
            (wrestler_id,),
        )

        if row:
            row["opponents"] = json.loads(row["opponents"]) if row["opponents"] else []
            row["match_count"] = row["match_count"] if row["match_count"] else 0
            row["countries_worked"] = (
                json.loads(row["countries_worked"]) if row["countries_worked"] else {}
            )
            return row
        else:
            return {
                "opponents": [],
                "match_count": 0,
                "countries_worked": {},
            }

    def save_matches(self, wrestler_id: int, matches: list[dict]):
        match_json = json.dumps(matches)
        self._execute_and_commit(
            """
        UPDATE matches
        SET cm_matches_json=?
        WHERE wrestler_id=?
        """,
            (match_json, wrestler_id),
        )

    def get_all_colleagues(self, wrestler_id: int) -> set[int]:
        """Given a wrestler ID, return a set of all wrestler IDs that appeared in a match with them."""
        colleagues = set()
        for match in self.get_matches(wrestler_id):
            for wid in match["wrestlers"]:
                if wid != wrestler_id:
                    colleagues.add(wid)
        return colleagues


db = WrestlerDb(pathlib.Path("data/joshi_wrestlers.y"))
wrestler_db = db
# import dbm

# print("xx", dbm.whichdb(pathlib.Path("data/joshi_wrestlers.db")))


@functools.lru_cache(maxsize=None)
def get_name(wrestler_id: int) -> str:
    return db.get_name(wrestler_id)


def get_promotion_with_location(wrestler_id: int) -> str:
    wrestler_info = db.get_wrestler(wrestler_id)
    promotion = wrestler_info.get("promotion", "")
    if promotion == "" or promotion == "Freelancer":
        location = wrestler_info.get("location", "Unknown")
        if location != "Unknown":
            promotion = f"Freelancer ({location})"
        else:
            promotion = "Freelancer"
    return promotion


if __name__ == "__main__":
    # remove the cm_matches_json column from the wrestlers table
    import sys

    cursor = db.sqldb.cursor()
    cursor.execute("""ALTER TABLE wrestlers DROP COLUMN cm_matches_json""")
    cursor.close()
    db.sqldb.commit()
