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

# import shelve
import sqlite3
from collections import Counter

from loguru import logger

from joshirank.cagematch.data import wrestler_name_overrides
from joshirank.cagematch.profile import CMProfile
from joshirank.joshi_data import considered_female, promotion_abbreviations


@functools.lru_cache(maxsize=None)
def is_joshi(wrestler_id: int) -> bool:
    """Determine if a wrestler is female based on their profile data."""

    return db.is_female(wrestler_id)


def is_female(wrestler_id: int, wrestler_info: dict) -> bool:
    if wrestler_id in considered_female:
        return True
    gender = wrestler_info.get("profile", {}).get("Gender", "")
    return gender.lower() == "female"


class WrestlerDb:
    def __init__(self, path: pathlib.Path):
        self.path = path
        # self.db = shelve.open(str(self.path), writeback=True)
        self.sqldb = sqlite3.connect(str(self.path.with_suffix(".sqlite3")))
        self.initialize_sql_db()

    def initialize_sql_db(self):
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
        row = self.select_and_fetchone(
            """Select is_female from wrestlers where wrestler_id=?""", (wrestler_id,)
        )

        if not row:
            return False
        return bool(row[0])

    def save_profile_for_wrestler(self, wrestler_id: int, profile_data: dict):
        """Save the profile data for a wrestler in the sql table as JSON."""
        cm_profile_json = json.dumps(profile_data)
        cursor = self.sqldb.cursor()
        cursor.execute(
            """
        INSERT OR REPLACE INTO wrestlers
        (wrestler_id, cm_profile_json, last_updated)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
            (wrestler_id, cm_profile_json),
        )
        # ensure the transaction is committed so the data is persisted,
        # then close the cursor

        self.sqldb.commit()
        cursor.close()

    def select_and_fetchone(self, query: str, params: tuple) -> tuple | None:
        """Helper method to execute a select query and fetch one result."""
        cursor = self.sqldb.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        cursor.close()
        return row

    def select_and_fetchall(self, query: str, params: tuple) -> list[tuple]:
        """Helper method to execute a select query and fetch all results."""
        cursor = self.sqldb.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def get_cm_profile_for_wrestler(self, wrestler_id: int) -> dict:
        """Return the CM profile data for a wrestler as a dict."""
        row = self.select_and_fetchone(
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

        cursor = self.sqldb.cursor()

        cursor.execute(
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
        cursor.close()
        self.sqldb.commit()

    def save_matches_for_wrestler(self, wrestler_id: int, matches: list[dict]):
        """Save the match data for a wrestler in the sql table as JSON."""
        cm_matches_json = json.dumps(matches)
        cursor = self.sqldb.cursor()
        cursor.execute(
            """
        INSERT OR REPLACE INTO matches
        (wrestler_id, cm_matches_json)
        VALUES (?, ?)
        """,
            (wrestler_id, cm_matches_json),
        )
        cursor.close()
        self.sqldb.commit()

    def update_matches_from_matches(self, wrestler_id: int):
        """Using the stored json matches for the wrestler, update their metadata in the SQL db."""
        row = self.select_and_fetchone(
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
            cursor = self.sqldb.cursor()
            cursor.execute(
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
            cursor.close()
            self.sqldb.commit()

    def update_wrestler_from_matches(self, wrestler_id: int):
        """Using the stored match info for the wrestler, update their metadata in the SQL db."""
        # get countries worked from matches
        row = self.select_and_fetchone(
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

            cursor = self.sqldb.cursor()
            cursor.execute(
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
        cursor = self.sqldb.cursor()
        cursor.execute(
            """Select * from wrestlers where wrestler_id=?""", (wrestler_id,)
        )
        row = cursor.fetchone()

        # convert the row to a dict using column names
        if row:
            d = {}
            col_names = [description[0] for description in cursor.description]
            d = dict(zip(col_names, row))
            cursor.close()
            # print(d.get("cm_profile_json", "{}"))
            # d["profile"] = json.loads(d.get("cm_profile_json", "{}"))
            # d["matches"] = json.loads(d.get("cm_matches_json", "[]"))
            return d
        else:
            cursor.close()
            raise KeyError(f"Wrestler ID {wrestler_id} not found in database.")

    def all_wrestler_ids(self) -> list[int]:
        """Return a list of all wrestler IDs in the database."""
        rows = self.select_and_fetchall("""Select wrestler_id from wrestlers""", ())
        return [row[0] for row in rows]

    def wrestler_exists(self, wrestler_id: int) -> bool:
        row = self.select_and_fetchone(
            """Select 1 from wrestlers where wrestler_id=?""", (wrestler_id,)
        )

        return row is not None

    def all_female_wrestlers(self):
        """Return a generator of wrestler ids and info"""
        rows = self.select_and_fetchall(
            """Select wrestler_id from wrestlers where is_female=1""", ()
        )
        return [row[0] for row in rows]

    def wrestler_in_sql(self, wrestler_id: int) -> bool:
        row = self.select_and_fetchone(
            """Select 1 from wrestlers where wrestler_id=?""", (wrestler_id,)
        )

        return row is not None

    def get_name(self, wrestler_id: int) -> str:

        # first try to retrieve from sqldb
        row = self.select_and_fetchone(
            """Select name from wrestlers where wrestler_id=?""", (wrestler_id,)
        )
        if row and row[0]:
            return row[0]

        else:
            raise KeyError(f"Wrestler ID {wrestler_id} not found in database.")

    def get_matches(self, wrestler_id: int) -> list[dict]:
        # first try to get from sqlite
        row = self.select_and_fetchone(
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
        row = self.select_and_fetchone(
            """Select opponents, match_count, countries_worked from matches where wrestler_id=?""",
            (wrestler_id,),
        )

        if row:
            opponents = json.loads(row[0]) if row[0] else []
            match_count = row[1] if row[1] else 0
            countries_worked = json.loads(row[2]) if row[2] else {}
            return {
                "opponents": opponents,
                "match_count": match_count,
                "countries_worked": countries_worked,
            }
        else:
            return {
                "opponents": [],
                "match_count": 0,
                "countries_worked": {},
            }

    def save_matches(self, wrestler_id: int, matches: list[dict]):
        match_json = json.dumps(matches)
        cursor = self.sqldb.cursor()
        cursor.execute(
            """
        UPDATE matches
        SET cm_matches_json=?
        WHERE wrestler_id=?
        """,
            (match_json, wrestler_id),
        )
        cursor.close()
        self.sqldb.commit()

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


def _determine_name_from_profile(wrestler_profile: dict) -> str:

    best_name = wrestler_profile.get("Current gimmick")
    if best_name:
        return best_name
    elif "_name" in wrestler_profile:
        return wrestler_profile["_name"]
    else:
        alter_ego = wrestler_profile.get("Alter egos")
        if type(alter_ego) is str and "a.k.a." in alter_ego:
            alter_ego = alter_ego.split("a.k.a.")[0].strip()
        if type(alter_ego) is str:
            return alter_ego
        elif type(alter_ego) is list and len(alter_ego) > 0:
            return alter_ego[0]
        else:
            return "Unknown"


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
