"""Parser for CageMatch website wrestler data."""

import re

from bs4 import BeautifulSoup
from loguru import logger

from joshirank.cagematch.data import wrestler_name_overrides
from joshirank.cagematch.util import parse_cm_date
from joshirank.joshi_data import considered_female, promotion_abbreviations

date_re = re.compile(r"([0-9][0-9])\.([0-9][0-9])\.([0-9][0-9][0-9][0-9])")
id_href = re.compile("nr=([0-9]+)")
tag_href = re.compile("[?]id=(28|29)")
event_href = re.compile("[?]id=1")


def parse_wrestler_profile_page(html_data: str) -> dict:
    """Parse wrestler profile page HTML and return wrestler data as a dictionary."""

    soup = BeautifulSoup(html_data, "html.parser")

    wrestler_data = {}

    page_header = soup.find("h1", class_="TextHeader")
    if page_header:
        wrestler_data["_name"] = page_header.text.strip()
    info_pairs = soup.findAll("div", class_="InformationBoxRow")
    for pair in info_pairs:
        label = pair.find("div", class_="InformationBoxTitle").text.strip().strip(":")
        value = pair.find("div", class_="InformationBoxContents")
        if date_re.match(value.text.strip()):
            try:
                value = parse_cm_date(value.text.strip()).isoformat()
            except ValueError:
                pass
        elif value.stripped_strings and len(list(value.stripped_strings)) > 1:
            # multiple strings, make a list
            value = [s.strip() for s in value.stripped_strings]
        else:
            value = value.text.strip()
        wrestler_data[label] = value

    return wrestler_data


class CMProfile:
    """CageMatch wrestler profile parser."""

    id: int
    profile_data: dict

    def name(self) -> str:
        if self.id in wrestler_name_overrides:
            return wrestler_name_overrides[self.id]

        best_name = self.profile_data.get("Current gimmick")
        if best_name:
            return best_name
        elif "_name" in self.profile_data:
            return self.profile_data["_name"]
        else:
            alter_ego = self.profile_data.get("Alter egos")
            if type(alter_ego) is str and "a.k.a." in alter_ego:
                alter_ego = alter_ego.split("a.k.a.")[0].strip()
            if type(alter_ego) is str:
                return alter_ego
            elif type(alter_ego) is list and len(alter_ego) > 0:
                return alter_ego[0]
            else:
                return "Unknown"

    def is_female(self) -> bool:
        """Returns true if the wrestler is considered female based on profile."""
        if self.id in considered_female:
            return True
        gender = self.profile_data.get("Gender", "")
        if gender.lower() not in ("male", "female"):
            logger.debug("Gender-diverse wrestler {} ({})", self.name(), self.id)
        return gender.lower() == "female"

    @classmethod
    def from_html(cls, wrestler_id: int, html_data: str):
        profile = cls()
        profile.id = wrestler_id
        profile.profile_data = parse_wrestler_profile_page(html_data)
        return profile

    @classmethod
    def from_dict(cls, wrestler_id: int, data: dict):
        profile = cls()
        profile.id = wrestler_id
        profile.profile_data = data
        return profile

    def promotion(self) -> str:
        promotion = self.profile_data.get("Promotion", "Freelancer")

        return promotion_abbreviations.get(promotion, promotion)
