"""Post-scrape match parsing"""

import re

from bs4 import BeautifulSoup, Tag

import joshirank.cagematch.cm_parse as cm_parse

date_re = re.compile(r"\(([0-9]+)\.([0-9]+)\.([0-9]+)\)")

id_href = re.compile("nr=([0-9]+)")
tag_href = re.compile("[?]id=(28|29)")
event_href = re.compile("[?]id=1")


def remove_colon(text: str) -> str:
    return text.strip().strip(":")


def get_matchtype(match: Tag):
    m = match.find(class_="MatchType")
    if m:
        return remove_colon(m.text)
    else:
        return ""


missing_wrestlers = {}


def find_missing(text: str, results):

    for missing_wrestler, w_wid in missing_wrestlers.items():
        if missing_wrestler in text:

            results.append({"name": missing_wrestler, "id": w_wid})


def parse_wrestler(wrestler: Tag) -> int:
    """Get the id number from an a tag"""
    return int(id_href.search(wrestler["href"]).group(1))


def parse_match(match: BeautifulSoup) -> dict:
    """Parse the match."""
    m = {}
    m["match_type"] = get_matchtype(match)
    m["date"] = cm_parse.m_date(match)
    m["promotion"] = cm_parse.m_promotion(match)
    # m["raw_result"] = match.text

    d_split = match.find(string=re.compile("defeat[s]?"))
    vs_split = match.find(string=re.compile("vs[.]"))
    if d_split:

        winners = d_split.find_previous_siblings("a")
        losers = d_split.find_next_siblings("a")

        m["winners"] = tuple(sorted(parse_wrestler(x) for x in winners))
        m["losers"] = tuple(sorted(parse_wrestler(x) for x in losers))

        side_a, side_b = match.text.split("defeat")
        find_missing(side_a, m["winners"])
        find_missing(side_b, m["losers"])

    elif vs_split:
        # draw?
        m["draw"] = True
        m["side_one"] = [
            parse_wrestler(x) for x in vs_split.find_previous_siblings("a")
        ]
        m["side_two"] = [parse_wrestler(x) for x in vs_split.find_next_siblings("a")]

    return m
