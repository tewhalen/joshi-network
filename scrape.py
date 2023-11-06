import json
import pathlib
import re
import time
import urllib

import requests
from bs4 import BeautifulSoup, Tag

date_re = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)")

id_href = re.compile("nr=([0-9]+)")
tag_href = re.compile("[?]id=(28|29)")
event_href = re.compile("[?]id=1")


wrestler_url = """https://www.cagematch.net/?id=2&nr={wrestler_id}&page=4&year={year}&region=Asien"""


def get_matches(wrestler_id: int, year: int, start=0) -> list[dict]:
    """Get all the matches for that wrestler_id for the given year."""
    with requests.Session() as s:
        # print(wrestler_url.format(wrestler_id=wrestler_id, year=year))
        if start:
            url = wrestler_url + f"&s={start}"
        else:
            url = wrestler_url
        r = s.get(
            url.format(wrestler_id=wrestler_id, year=year),
            headers={"accept-encoding": "compress"},
        )
        if r:
            matches = list(parse_matches(r.text))
            if len(matches) == 100:
                return matches + get_matches(wrestler_id, year, start + 100)
            else:
                return matches


def parse_matches(content: str) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    # print(soup)
    for match in soup.find_all("tr", ["TRow1", "TRow2"]):
        # print(match)
        yield parse_match(match)


def parse_match(match: BeautifulSoup) -> dict:
    """Turn match html into a dictionary"""
    wrestlers = []
    promotion = None
    date = None

    for link in match.find_all("a"):
        # print(link["href"])
        if link["href"].startswith("?"):
            parsed = urllib.parse.parse_qs(link["href"][1:])
            if parsed["id"][0] == "2":
                if "nr" and "name" in parsed:
                    wrestlers.append((parsed["nr"][0], parsed["name"][0]))
            elif parsed["id"][0] == "8":
                # promotion
                if "nr" in parsed:
                    img = link.find("img")
                    if img:
                        promotion = (parsed["nr"][0], img["title"])

    for cell in match.find_all("td"):
        m = date_re.search(cell.text)
        if m:
            date = m.groups()
            break

    return {
        "date": date,
        "wrestlers": wrestlers,
        "promotion": promotion,
    }


def parse_event(event: Tag) -> list[dict]:
    results = []
    event_header = event.find("div", class_="QuickResultsHeader")
    date_m = date_re.search(event_header.text)
    if not date_m:
        raise SyntaxError("no date found!")
    day, month, year = date_m.groups()
    datestr = f"{year}-{month}-{day}"

    event_name = event_header.a.text

    for match in event.find_all("span", class_="MatchResults"):
        match_res = parse_match(match)
        match_res["date"] = datestr
        match_res["event"] = event_name
        results.append(match_res)
    return results


def reload_wrestler(wrestler_id, year):
    """Download the wrestler info for year if json dne or is older than 1 week."""
    json_file = pathlib.Path(f"data/{wrestler_id}.json")
    week = 60 * 60 * 24 * 7

    if json_file.exists() and (time.time() - json_file.stat().st_mtime) < week:
        # print("skipping..")
        m = json.load(json_file.open("r"))
    else:
        m = get_matches(wrestler_id, year)
        if m:
            with json_file.open("w") as fp:
                json.dump(m, fp, indent=2)
    return m


def get_all_wrestlers(matches):
    w = set()
    for match in matches:
        w.update(x[0] for x in match["wrestlers"])
    return w


def follow_wrestlers(wrestler_id, year):
    matches = reload_wrestler(wrestler_id, year)
    first_degree = get_all_wrestlers(matches)
    second_degree = set()
    print(len(first_degree), "first degree.")
    for wrestler_id in first_degree:
        matches = reload_wrestler(wrestler_id, year)
        second_degree.update(get_all_wrestlers(matches))
    second_degree = second_degree.difference(first_degree)
    print(len(second_degree), "second degree.")

    third_degree = set()
    for wrestler_id in second_degree:
        matches = reload_wrestler(wrestler_id, year)
        third_degree.update(get_all_wrestlers(matches))
    third_degree = third_degree.difference(first_degree).difference(second_degree)
    print(len(third_degree), "third degree.")


if __name__ == "__main__":
    follow_wrestlers(8562, 2023)  # ryo Mizumani
    follow_wrestlers(21342, 2023)  # ram kaicho
    follow_wrestlers(20534, 2023)  # unagi sayaka
    follow_wrestlers(13902, 2023)  # natsu sumire
    follow_wrestlers(18642, 2023)  # miyuki takase
    follow_wrestlers(15833, 2023)  # maya yukihi
    follow_wrestlers(11878, 2023)  # act
    # j son.dump(get_matches(8562, 2023), open("8562.json", "w"))
    # print(get_matches(8562, 2023))
    # result = scrape("https://www.cagematch.net/?id=8&nr=1467&page=8")

    # json.dump(result, open("tjpw-results.json", "w"), indent=4)
