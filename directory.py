import json
import pathlib
from collections import Counter

from scrape import get_all_wrestlers

joshi_promotions = {
    "Gatoh Move Pro Wrestling",
    "Ice Ribbon",
    "World Wonder Ring Stardom",
    "Tokyo Joshi Pro-Wrestling",
    "SEAdLINNNG",
    "Sendai Girls' Pro Wrestling",
    "OZ Academy",
    "Marvelous That's Women Pro Wrestling",
    "World Woman Pro-Wrestling Diana",
    "Pro Wrestling WAVE",
    #  "Pro Wrestling FREEDOMS",
    "Actwres girl'Z",
    "Girl's Pro-Wrestling Unit Color's",
    "Prominence",
}


def create_directory():
    data = pathlib.Path("data").glob("[0-9]*.json")

    directory = {}

    for wrestler_json in data:
        info = json.load(wrestler_json.open())
        w_id = wrestler_json.stem
        proms = Counter(match["promotion"][1] for match in info if match["promotion"])
        names = Counter()
        for match in info:
            for wrestler_id, wrestler_name in match["wrestlers"]:
                if wrestler_id == w_id:
                    names[wrestler_name.strip()] += 1

        print(w_id, proms.most_common(1), names.most_common(1))
        joshi = False
        if joshi_promotions & set(proms.keys()):
            joshi = True
        d = {
            "name": names.most_common(1)[0][0],
            "promotion": proms.most_common(1)[0][0],
            "joshi": joshi,
            "matches": len(info),
        }
        directory[w_id] = d
        # for match in info:
    return directory


if __name__ == "__main__":
    json.dump(create_directory(), open("joshi_dir.json", "w"), indent=2)
