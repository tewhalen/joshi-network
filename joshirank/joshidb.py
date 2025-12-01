import functools
import pathlib
import shelve

from joshirank.joshi_data import considered_female, promotion_abbreviations


@functools.lru_cache(maxsize=None)
def is_joshi(wrestler_id: int) -> bool:
    """Determine if a wrestler is female based on their profile data."""
    if wrestler_id in considered_female:
        return True
    wrestler_profile = db.get_wrestler(wrestler_id)
    return is_female(wrestler_id, wrestler_profile)


def is_female(wrestler_id: int, wrestler_info: dict) -> bool:
    if wrestler_id in considered_female:
        return True
    gender = wrestler_info.get("profile", {}).get("Gender", "")
    return gender.lower() == "female"


class WrestlerDb:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.db = shelve.open(str(self.path), writeback=True)

    def close(self):
        self.db.close()

    def get_wrestler(self, wrestler_id: int) -> dict:
        return self.db.get(str(wrestler_id), {})

    def save_wrestler(self, wrestler_id: int, data: dict):
        self.db[str(wrestler_id)] = data
        self.db.sync()

    def all_wrestler_ids(self):
        self.db.sync()
        return list(self.db.keys())

    def wrestler_exists(self, wrestler_id: int) -> bool:
        return str(wrestler_id) in self.db

    def all_female_wrestlers(self):
        self.db.sync()
        for wid, info in self.db.items():
            if is_female(int(wid), info):
                yield int(wid), info


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
    if wrestler_id == 4813:
        return "Nanae Takahashi"
    elif wrestler_id == 21791:
        return "Cora Jade"
    elif wrestler_id == 3709:
        return "Kaori Yoneyama"
    elif wrestler_id == 20441:
        return "Haruna Neko"
    elif wrestler_id == 4913:
        return "Tanny Mouse"
    elif wrestler_id == 16871:
        return "Charli Evans"
    wrestler_info = db.get_wrestler(wrestler_id)
    best_name = wrestler_info.get("profile", {}).get("Current gimmick")
    if best_name:
        return best_name
    else:
        alter_ego = wrestler_info.get("profile", {}).get("Alter egos")
        if type(alter_ego) is str and "a.k.a." in alter_ego:
            alter_ego = alter_ego.split("a.k.a.")[0].strip()
        if type(alter_ego) is str:
            return alter_ego
        elif type(alter_ego) is list and len(alter_ego) > 0:
            return alter_ego[0]
        else:
            return f"Unknown ({wrestler_id})"


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
    test_ids = [28004, 26912, 32147, 26559, 4813, 21791]
    for wid in test_ids:
        print(f"Wrestler ID: {wid}")
        print(f"Name: {get_name(wid)}")
        print(f"Promotion: {get_promotion(wid)}")
        print(f"Is Joshi: {is_joshi(wid)}")
        print()
