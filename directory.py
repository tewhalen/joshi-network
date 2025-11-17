import json
import pathlib
from collections import Counter

from tabulate import tabulate

from joshirank.joshi_data import joshi_promotions, known_joshi, non_joshi, promotion_map
from scrape import get_all_wrestlers


def create_directory():
    data = pathlib.Path("data").glob("[0-9]*.json")

    directory = {}

    for wrestler_json in data:
        info = json.load(wrestler_json.open())
        w_id = wrestler_json.stem
        proms = Counter(match["promotion"][1] for match in info if match["promotion"])
        names = Counter()
        opps = set()
        for match in info:
            for wrestler_id, wrestler_name in match["wrestlers"]:
                if wrestler_id == w_id:
                    names[wrestler_name.strip()] += 1
                else:
                    opps.add(wrestler_id)
        # print(w_id, proms.most_common(1), names.most_common(1))
        joshi = False
        if w_id in known_joshi:
            joshi = True
        elif w_id in non_joshi:
            joshi = False
        elif joshi_promotions & set(x[0] for x in proms.most_common(3)):
            joshi = True

        d = {
            "name": names.most_common(1)[0][0],
            "promotion": promotion_map.get(w_id, proms.most_common(1)[0][0]),
            "joshi": joshi,
            "matches": len(info),
            "opponents": list(opps),
        }
        directory[w_id] = d
        # for match in info:
    return directory


def summarize_directory():
    d = json.load(open("joshi_dir.json"))
    proms = Counter(
        wrestler["promotion"] for wrestler in d.values() if wrestler["joshi"]
    )
    print(tabulate(proms.most_common()))


def find_outliers(d):
    pcts = {}
    for wr_d, wrestler in d.items():
        j = [d[wid]["joshi"] for wid in wrestler["opponents"] if wid in d]
        pcts[wr_d] = sum(j) / len(j)

    i = 0
    for w in sorted(pcts, key=pcts.get, reverse=True):
        if not d[w]["joshi"] and (w not in non_joshi):
            i += 1
            print(w, d[w]["name"], pcts[w], len(d[w]["opponents"]))
        if i > 20:
            break
    # print(pcts)
    i = 0
    print()
    for w in sorted(pcts, key=pcts.get):
        if d[w]["joshi"] and w not in known_joshi:
            i += 1
            print(w, d[w]["name"], pcts[w], len(d[w]["opponents"]))
        if i > 20:
            break
    # print(pcts)


if __name__ == "__main__":
    json.dump(create_directory(), open("joshi_dir.json", "w"), indent=2)
    summarize_directory()
