import json
import math
import pathlib
from collections import Counter

from identifier import Identifier
from joshi_data import joshi_promotions, non_joshi

w_directory = json.load(open("joshi_dir.json"))


def joshi_wrestlers():
    return {x for x, y in w_directory.items() if y["joshi"] and x not in non_joshi}


j_p = list(joshi_promotions)


def build_graph():
    data = pathlib.Path("data").glob("[0-9]*.json")

    promotion_id = Identifier()
    wrestlers = set()
    interactions = Counter()
    match_counts = Counter()
    for df in data:
        info = json.load(df.open())
        w_id = int(df.stem)
        for match in info:
            match_counts[w_id] += 1
            for wrestler in match["wrestlers"]:
                pairing = [w_id, int(wrestler[0])]
                pairing.sort()
                interactions[tuple(pairing)] += 1

                wrestlers.add(wrestler[0])
        # wget_all_wrestlers(info))
    d = {}
    nodes = []
    to_remove = {x for x in wrestlers if match_counts[int(x)] < 2}
    wrestlers = wrestlers.difference(to_remove)
    wrestlers = wrestlers.intersection(joshi_wrestlers())
    for wrestler in wrestlers:
        nodes.append(
            {
                "id": str(wrestler),
                "group": promotion_id[w_directory[str(wrestler)]["promotion"]],
                "promotion": w_directory[str(wrestler)]["promotion"],
                "name": w_directory[str(wrestler)]["name"],
            }
        )
    d["nodes"] = nodes

    links = []
    for interaction, count in interactions.items():
        source, target = tuple(interaction)
        if str(source) in wrestlers and str(target) in wrestlers and count > 1:
            links.append(
                {
                    "source": str(source),
                    "target": str(target),
                    "value": math.log10(count),
                }
            )
    d["links"] = links

    return d


if __name__ == "__main__":
    output = build_graph()
    fn = "joshi_net.json"
    print(
        f"Writing {len(output['nodes'])} wrestlers with {len(output['links'])} links to '{fn}'"
    )
    json.dump(output, open(fn, "w"))
