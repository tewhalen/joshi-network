import pathlib
import shelve


def is_joshi(wrestler_id: int) -> bool:
    """Determine if a wrestler is female based on their profile data."""
    if wrestler_id in (22620,):  # abadon special case
        return True
    wrestler_profile = db.get_wrestler(wrestler_id).get("profile", {})

    gender = wrestler_profile.get("Gender", "")
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

# import dbm

# print("xx", dbm.whichdb(pathlib.Path("data/joshi_wrestlers.db")))


def get_name(wrestler_id: int) -> str:
    if wrestler_id == 4813:
        return "Nanae Takahashi"
    elif wrestler_id == 21791:
        return "Cora Jade"
    elif wrestler_id == 3709:
        return "Kaori Yoneyama"
    wrestler_info = db.get_wrestler(wrestler_id)
    best_name = wrestler_info.get("profile", {}).get("Current gimmick")
    if best_name:
        return best_name
    else:
        alter_ego = wrestler_info.get("profile", {}).get("Alter egos")
        if alter_ego:
            return alter_ego
        else:
            return f"Unknown ({wrestler_id})"


def get_promotion(wrestler_id: int) -> str:
    wrestler_info = db.get_wrestler(wrestler_id)
    promotion = wrestler_info.get("profile", {}).get("Promotion", "")
    p_map = {
        "All Elite Wrestling": "AEW",
        "World Wonder Ring Stardom": "Stardom",
        "World Wrestling Entertainment": "WWE",
        "Tokyo Joshi Pro-Wrestling": "TJPW",
        "Marvelous That's Women Pro Wrestling": "Marvelous",
        "Sendai Girls' Pro Wrestling": "Sendai Girls",
        "Girl's Pro-Wrestling Unit Color's": "Colors",
        "Dream Star Fighting Marigold": "Marigold",
        "Ganbare Pro Wrestling": "Ganbare",
        "Pro Wrestling WAVE": "Wave",
        "Total Nonstop Action Wrestling": "TNA",
        "Women Of Wrestling": "WOW",
        "Yanagase Pro Wrestling": "Yanagase",
        "World Woman Pro-Wrestling Diana": "Diana",
        "National Wrestling Alliance": "NWA",
        "Consejo Mundial De Lucha Libre": "CMLL",
        "Ohio Valley Wrestling": "OVW",
        "Juggalo Championship Wrestling": "JCW",
        "Lucha Libre AAA Worldwide": "AAA",
        "Major League Wrestling": "MLW",
        "Gokigen Pro Wrestling": "Gokigen",
        "Pro-Wrestling Evolution": "Evolution",
        "Active Advance Pro Wrestling": "2AW",
        "Hokuto Pro Wrestling": "Hokuto",
        "Michinoku Pro Wrestling": "Michinoku",
        "Pro Wrestling Up Town": "UpTown",
        "P.P.P. Tokyo": "PPP Tokyo",
        "Freelancer": "",
        "Shinsyu Girls Pro Wrestling": "Shinsyu",
    }
    return p_map.get(promotion, promotion)
