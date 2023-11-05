import json
import re

import requests
from bs4 import BeautifulSoup, Tag

date_re = re.compile(r"\(([0-9]+)\.([0-9]+)\.([0-9]+)\)")

id_href = re.compile("nr=([0-9]+)")
tag_href = re.compile("[?]id=(28|29)")
event_href = re.compile("[?]id=1")


def scrape(url) -> list[dict]:
    """Given a starting url, scrape all the match data."""
    all_results = []
    with requests.Session() as s:
        for i in range(5):
            count = i * 100
            r = s.get(
                url + f"&s={count}",
                headers={"accept-encoding": "identity"},
            )
            if r:
                parse_res = parse_page(r.text)
                all_results.extend(parse_res)
    return all_results


def get_matchtype(match: Tag):
    m = match.find_previous_sibling(class_="MatchType")
    if m:
        return m.text.strip(":")
    else:
        return None


def parse_page(content) -> list[dict]:
    result_list = []
    soup = BeautifulSoup(content, "html.parser")
    for event in soup.find_all("div", class_="QuickResults"):
        result_list.extend(parse_event(event))

    return result_list


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


def parse_wrestler(wrestler: Tag) -> dict:
    """Get the name and id number from an a tag"""
    if tag_href.search(wrestler["href"]):
        return {
            "tag team": wrestler.text,
            "id": id_href.search(wrestler["href"]).group(1),
        }
    else:
        return {"name": wrestler.text, "id": id_href.search(wrestler["href"]).group(1)}


def parse_match(match: Tag) -> dict:
    """Parse the match."""
    m = {}
    m["match_type"] = get_matchtype(match)
    m["raw_result"] = match.text

    d_split = match.find(string=re.compile("defeat[s]?"))
    vs_split = match.find(string=re.compile("vs[.]"))
    if d_split:
        winners = d_split.find_previous_siblings("a")
        losers = d_split.find_next_siblings("a")

        m["winners"] = [parse_wrestler(x) for x in winners]
        m["losers"] = [parse_wrestler(x) for x in losers]

    elif vs_split:
        # draw?
        m["draw"] = True
        m["side_one"] = [
            parse_wrestler(x) for x in vs_split.find_previous_siblings("a")
        ]
        m["side_two"] = [parse_wrestler(x) for x in vs_split.find_next_siblings("a")]

    return m


if __name__ == "__main__":
    result = scrape("https://www.cagematch.net/?id=8&nr=1467&page=8")

    json.dump(result, open("tjpw-results.json", "w"), indent=4)
