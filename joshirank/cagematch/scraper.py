import time

import requests
from loguru import logger

import joshirank.cagematch.cm_match as cm_match
import joshirank.cagematch.profile as profile
from joshirank.cagematch.promotion import CMPromotion


class CageMatchScraper:
    session: requests.Session
    sleep_delay: float = 1.0
    max_requests_per_session: int = 100
    requests_made: int = 0

    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {"accept-encoding": "compress"}
        self.requests_made = 0

    def keep_going(self) -> bool:
        if self.requests_made >= self.max_requests_per_session:
            logger.warning("Out of requests for this session...")
            return False
        return True

    def scrape_profile(self, wrestler_id: int) -> profile.CMProfile:
        url = f"https://www.cagematch.net/?id=2&nr={wrestler_id}"
        time.sleep(self.sleep_delay)
        r = self.session.get(url)
        self.requests_made += 1
        if r:
            return profile.CMProfile.from_html(wrestler_id, r.text)
        else:
            raise ValueError(f"Failed to load profile for wrestler {wrestler_id}")

    def scrape_promotion(self, promotion_id: int) -> CMPromotion:
        url = f"https://www.cagematch.net/?id=8&nr={promotion_id}"
        time.sleep(self.sleep_delay)
        r = self.session.get(url)
        self.requests_made += 1
        if r:
            return CMPromotion.from_html(promotion_id, r.text)
        else:
            raise ValueError(f"Failed to load promotion {promotion_id}")

    def scrape_matches(
        self, wrestler_id: int, year: int, start=0
    ) -> tuple[list[dict], set[int]]:
        """Get all the matches for that wrestler_id for the given year.

        Returns:
            tuple of (matches, available_years) where available_years is the set of
            all years that have match data according to the year dropdown.
        """
        matches_url = (
            f"https://www.cagematch.net/?id=2&nr={wrestler_id}&page=4&year={year}"
        )
        all_matches = []
        available_years = set()

        while True:
            time.sleep(self.sleep_delay)
            if start:
                url = matches_url + f"&s={start}"
            else:
                url = matches_url
            r = self.session.get(url)
            self.requests_made += 1
            if r:
                matches = list(cm_match.extract_match_data_from_match_page(r.text))
                all_matches.extend(matches)

                # Extract available years from first page only
                if start == 0:
                    available_years = cm_match.extract_years_from_match_page(r.text)

                if len(matches) == 100:
                    start += 100
                else:
                    break
            else:
                break
        return all_matches, available_years

    def scrape_all_matches(self, wrestler_id: int, start=0) -> list[dict]:
        """Get all matches for the wrestler across all years."""
        all_matches_url = f"https://www.cagematch.net/?id=2&nr={wrestler_id}&page=4"
        all_matches = []

        while True:
            time.sleep(self.sleep_delay)
            if start:
                url = all_matches_url + f"&s={start}"
            else:
                url = all_matches_url
            r = self.session.get(url)
            self.requests_made += 1
            if r:
                matches = list(cm_match.extract_match_data_from_match_page(r.text))
                all_matches.extend(matches)

                if len(matches) == 100:
                    start += 100
                else:
                    break
            else:
                break
        return all_matches

    def match_years(self, wrestler_id: int) -> set[int]:
        """Get all years that wrestler has matches in."""
        matches_url = f"https://www.cagematch.net/?id=2&nr={wrestler_id}&page=4"

        r = self.session.get(matches_url)
        self.requests_made += 1
        years = set()
        if r:
            years = cm_match.extract_years_from_match_page(r.text)
        return years
