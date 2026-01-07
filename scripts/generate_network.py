import datetime
import json
import math
import pathlib
from collections import Counter

import click
from loguru import logger

from joshirank.analysis.promotion import (
    get_primary_promotion_for_year,
)
from joshirank.identifier import Identifier
from joshirank.joshi_data import joshi_promotions
from joshirank.joshidb import get_name, wrestler_db


def all_female_wrestlers():
    """Return a set of all joshi wrestler IDs."""
    return set(wrestler_db.all_female_wrestlers())


def is_japanese(wrestler_id: int):
    if wrestler_id in {
        4629,
        9555,  # iyo sky
        16547,  # yuka
        9462,  # shida
        22328,  # thekla?
        20432,  # mina
        2785,  # asuka
        19615,  # giulia
        11958,  # kairi sane
    }:
        return True
    wrestler_info = wrestler_db.get_wrestler(wrestler_id)
    if wrestler_info.get("location") == "Japan":
        return True
    elif "Japan" in wrestler_db.get_match_info(wrestler_id).get("countries_worked", {}):
        return True
    promotion = wrestler_info.get("promotion", "")
    if "Japan" in promotion or promotion in joshi_promotions:
        return True
    return False


def all_joshi_japanese_wrestlers():
    """Return a set of all joshi wrestler IDs."""
    joshi_wrestlers = set()
    for w_id in wrestler_db.all_female_wrestlers():
        if is_japanese(w_id):
            joshi_wrestlers.add(w_id)
    return joshi_wrestlers


def build_graph(from_wrestlers: set, year: int, threshold=8):
    promotion_id = Identifier()
    wrestlers = set()
    interactions = Counter()
    match_counts = Counter()
    for w_id in from_wrestlers:
        matches = wrestler_db.get_matches(w_id, year)

        for match in matches:
            if year and not match["date"].startswith(str(year)):
                continue
            match_counts[w_id] += 1
            for wrestler in match["wrestlers"]:
                if wrestler == w_id:
                    continue
                try:
                    pairing = [w_id, wrestler]
                except TypeError:
                    print(repr(w_id), repr(wrestler))
                    continue
                pairing.sort()
                interactions[tuple(pairing)] += 1

                wrestlers.add(wrestler)
        # wget_all_wrestlers(info))
    # print(match_counts.most_common(20))
    d = {}
    nodes = []
    to_remove = {x for x in wrestlers if match_counts[x] < threshold}
    wrestlers = wrestlers.difference(to_remove)
    logger.debug("Removed {} wrestlers with < {} matches", len(to_remove), threshold)
    logger.debug("Remaining wrestlers: {}", len(wrestlers))
    # wrestlers = wrestlers.intersection(joshi_wrestlers())
    for wrestler in wrestlers:
        promotion = get_primary_promotion_for_year(wrestler, year)

        nodes.append(
            {
                "id": str(wrestler),
                "group": promotion_id[promotion],
                "promotion": promotion,
                "name": get_name(wrestler),
                "matches": math.log10(match_counts[wrestler]),
            }
        )
    d["nodes"] = nodes
    # print(promotion_id)
    links = []
    for interaction, count in interactions.items():
        source, target = tuple(interaction)
        if int(source) in wrestlers and int(target) in wrestlers and count > 1:
            links.append(
                {
                    "source": str(source),
                    "target": str(target),
                    # "value": count,
                    "value": math.log10(count),
                }
            )
    d["links"] = links

    return d


@click.command()
@click.argument(
    "year",
    type=int,
    default=datetime.datetime.now().year - 1,
)
def main(year: int):
    """Generate network graph JSON files."""
    logger.info(f"Generating network graph for year {year}...")

    # Create year subdirectory
    output_dir = pathlib.Path(f"output/{year}")
    output_dir.mkdir(parents=True, exist_ok=True)

    output = build_graph(all_female_wrestlers(), year)
    fn = output_dir / "network.json"
    logger.info(
        f"Writing {len(output['nodes'])} wrestlers with {len(output['links'])} links to '{fn}'"
    )
    json.dump(output, open(fn, "w"), indent=2)

    # Also write to old location for backwards compatibility
    json.dump(output, open("output/joshi_net-sm.json", "w"), indent=2)

    output = build_graph(all_joshi_japanese_wrestlers(), year, threshold=2)
    fn_jpn = output_dir / "network-jpn.json"
    logger.info(
        f"Writing {len(output['nodes'])} wrestlers with {len(output['links'])} links to '{fn_jpn}'"
    )
    json.dump(output, open(fn_jpn, "w"), indent=2)

    # Also write to old location for backwards compatibility
    json.dump(output, open("output/joshi_net-jpn.json", "w"), indent=2)


if __name__ == "__main__":
    main()
