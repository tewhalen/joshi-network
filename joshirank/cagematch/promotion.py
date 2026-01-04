"""Code to support scraping of promotion data from CageMatch.net."""

from bs4 import BeautifulSoup


def parse_promotion_page(html_data: str) -> dict:
    """Parse the HTML of a CageMatch promotion page into a dictionary."""
    soup = BeautifulSoup(html_data, "html.parser")
    promotion_data = {}

    # Find all InformationBoxTable sections
    info_tables = soup.find_all("div", class_="InformationBoxTable")
    
    for info_table in info_tables:
        # Find all rows in this table
        rows = info_table.find_all("div", class_="InformationBoxRow")
        for row in rows:
            title_div = row.find("div", class_="InformationBoxTitle")
            contents_div = row.find("div", class_="InformationBoxContents")
            
            if not title_div or not contents_div:
                continue
            
            label = title_div.text.strip().rstrip(":")
            value = contents_div.text.strip()
            
            # Map CageMatch fields to our schema
            if label == "Current name":
                promotion_data["Name"] = value
            elif label == "Active Time":
                # Extract founding year from "2011 - today" or similar
                parts = value.split(" - ")
                if parts:
                    promotion_data["Founded"] = parts[0].strip()
            elif label == "Location":
                # Extract country from "Tokyo, Japan" format
                parts = value.split(",")
                if parts:
                    promotion_data["Country"] = parts[-1].strip()

    return promotion_data


class CMPromotion:
    """CageMatch promotion parser."""

    id: int
    promotion_data: dict

    def name(self) -> str:
        return self.promotion_data.get("Name", "Unknown Promotion")

    def founded(self) -> str:
        return self.promotion_data.get("Founded", "")

    def country(self) -> str:
        return self.promotion_data.get("Country", "")

    def to_dict(self) -> dict:
        """Convert promotion data to a dictionary for storage."""
        return self.promotion_data.copy()

    @classmethod
    def from_html(cls, promotion_id: int, html_data: str):
        promotion = cls()
        promotion.id = promotion_id
        promotion.promotion_data = parse_promotion_page(html_data)
        return promotion

    @classmethod
    def from_dict(cls, promotion_id: int, promotion_data: dict):
        promotion = cls()
        promotion.id = promotion_id
        promotion.promotion_data = promotion_data
        return promotion
