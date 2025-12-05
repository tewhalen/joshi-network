"""
Docstring for joshirank.joshidb

Handles persistent storage of wrestler data using shelve and sqlite3.

We keep partially-parsed scraped JSON data in a shelve database,
most notably match lists.
We use sqlite3 for efficient querying of derived wrestler metadata.

"""

import functools
import pathlib
import shelve
import sqlite3

from joshirank.joshi_data import (
    considered_female,
    promotion_abbreviations,
    wrestler_name_overrides,
)


@functools.lru_cache(maxsize=None)
def is_joshi(wrestler_id: int) -> bool:
    """Determine if a wrestler is female based on their profile data."""
    return db._is_female(wrestler_id)


def is_female(wrestler_id: int, wrestler_info: dict) -> bool:
    if wrestler_id in considered_female:
        return True
    gender = wrestler_info.get("profile", {}).get("Gender", "")
    return gender.lower() == "female"


class WrestlerDb:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.db = shelve.open(str(self.path), writeback=True)
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
            PRIMARY KEY (wrestler_id)  
        )
        """
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_wrestler_fem ON wrestlers (is_female)"""
        )
        cursor.close()
        self.sqldb.commit()

    def _is_female(self, wrestler_id: int) -> bool:
        if not self.wrestler_in_sql(wrestler_id):
            self.update_wrestler_metadata(wrestler_id, self.get_wrestler(wrestler_id))

        cursor = self.sqldb.cursor()
        cursor.execute(
            """Select is_female from wrestlers where wrestler_id=?""", (wrestler_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        return bool(row[0])

    def update_wrestler_metadata(self, wrestler_id: int):
        """Update the SQL metadata for a wrestler based on their shelved profile info."""
        wrestler_info = self.get_wrestler(wrestler_id)
        cursor = self.sqldb.cursor()
        name = get_name(wrestler_id)
        promotion = get_promotion_with_location(wrestler_id)

        is_female_flag = is_female(wrestler_id, wrestler_info)
        location = wrestler_info.get("_guessed_location", "Unknown")
        timestamp = wrestler_info.get("timestamp", None)
        cursor.execute(
            """
        INSERT OR REPLACE INTO wrestlers
        (wrestler_id, is_female, name, promotion, last_updated, location)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                wrestler_id,
                is_female_flag,
                name,
                promotion,
                timestamp,
                location,
            ),
        )

    def close(self):
        self.db.close()
        self.sqldb.close()

    def get_wrestler(self, wrestler_id: int) -> dict:
        return self.db.get(str(wrestler_id), {})

    def save_wrestler(self, wrestler_id: int, data: dict):
        self.db[str(wrestler_id)] = data

        self.update_wrestler_metadata(wrestler_id, data)
        self.db.sync()
        self.sqldb.commit()

    def all_wrestler_ids(self):
        self.db.sync()
        return list(self.db.keys())

    def wrestler_exists(self, wrestler_id: int) -> bool:
        return str(wrestler_id) in self.db

    def all_female_wrestlers(self):
        """Return a generator of wrestler ids and info"""
        self.db.sync()
        for wid, info in self.db.items():
            if is_female(int(wid), info):
                yield int(wid), info

    def wrestler_in_sql(self, wrestler_id: int) -> bool:
        cursor = self.sqldb.cursor()
        cursor.execute(
            """Select 1 from wrestlers where wrestler_id=?""", (wrestler_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        return row is not None

    def get_name(self, wrestler_id: int) -> str:
        # if wrestler_id not in sqldb, update it
        if not self.wrestler_in_sql(wrestler_id):
            self.update_wrestler_metadata(wrestler_id, self.get_wrestler(wrestler_id))

        # first try to retrieve from sqldb
        cursor = self.sqldb.cursor()
        cursor.execute(
            "SELECT name FROM wrestlers WHERE wrestler_id = ?", (wrestler_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        if row:
            return row[0]
        else:
            raise KeyError(f"Wrestler ID {wrestler_id} not found in database.")


def make_clean_shelve_db(path: pathlib.Path):
    """Load a shelve database, remove it, and replace it with a fresh one with the old contents."""
    old_db = WrestlerDb(path)
    # iterate over all possible wrestler ids 0-99999
    old_contents = {}
    for i in range(100000):
        wid = str(i)
        if wid in old_db.db:
            old_contents[wid] = old_db.db[wid]

    old_db.close()
    # path.with_suffix(".db").unlink()
    new_db = WrestlerDb(path.with_suffix(".y"))
    for k, v in old_contents.items():
        new_db.db[k] = v
    new_db.close()


# make_clean_shelve_db(pathlib.Path("data/joshi_wrestlers.new"))

db = WrestlerDb(pathlib.Path("data/joshi_wrestlers.y"))
wrestler_db = db
# import dbm

# print("xx", dbm.whichdb(pathlib.Path("data/joshi_wrestlers.db")))


@functools.lru_cache(maxsize=None)
def get_name(wrestler_id: int) -> str:
    if wrestler_id in wrestler_name_overrides:
        return wrestler_name_overrides[wrestler_id]

    wrestler_info = db.get_wrestler(wrestler_id)
    best_name = _determine_name_from_profile(wrestler_info)
    if best_name != "Unknown":
        return best_name
    else:
        return f"Unknown Wrestler {wrestler_id}"


def _determine_name_from_profile(wrestler_info: dict) -> str:
    wrestler_profile = wrestler_info.get("profile", {})
    best_name = wrestler_profile.get("Current gimmick")
    if best_name:
        return best_name
    elif wrestler_profile.get("_name"):
        return wrestler_profile.get("_name")
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
    promotion = get_promotion(wrestler_id)
    if promotion == "":
        wrestler_info = db.get_wrestler(wrestler_id)
        location = wrestler_info.get("_guessed_location", "Unknown")
        if location != "Unknown":
            promotion = f"Freelancer ({location})"
        else:
            promotion = "Freelancer"
    return promotion


@functools.lru_cache(maxsize=None)
def get_promotion(wrestler_id: int) -> str:
    wrestler_info = db.get_wrestler(wrestler_id)
    promotion = wrestler_info.get("profile", {}).get("Promotion", "")

    return promotion_abbreviations.get(promotion, promotion)


if __name__ == "__main__":
    # test some wrestler ids
    from pprint import pprint

    test_ids = [28004, 26912, 32147, 26559, 4813, 21791]
    for wid in test_ids:
        print(f"Wrestler ID: {wid}")
        print(f"Name: {get_name(wid)}")
        print(f"Promotion: {get_promotion(wid)}")
        print(f"Is Joshi: {is_joshi(wid)}")
        pprint(db.get_wrestler(wid))
        print()
        db.update_wrestler_metadata(wid, db.get_wrestler(wid))
        print(db._is_female(wid))
    db.sqldb.commit()
