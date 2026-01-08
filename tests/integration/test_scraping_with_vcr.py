"""Example test showing how to use VCR for recording network requests.

This test uses pytest-vcr to record HTTP requests the first time it runs,
then replay them in subsequent runs without hitting the network.
"""

import pytest

from joshirank.cagematch.scraper import CageMatchScraper


@pytest.mark.vcr()
def test_scrape_profile_with_vcr():
    """Test profile scraping with VCR recording/replay.

    First run: Records HTTP request to fixtures/vcr_cassettes/test_scrape_profile_with_vcr.yaml
    Subsequent runs: Replays from cassette (no network access)
    """
    scraper = CageMatchScraper()
    profile = scraper.scrape_profile(wrestler_id=4629)  # Emi Sakura

    assert profile.name() == "Emi Sakura"
    assert profile.is_female() is True


@pytest.mark.vcr()
def test_scrape_matches_with_vcr():
    """Test match scraping with VCR recording/replay."""
    scraper = CageMatchScraper()
    matches, _ = scraper.scrape_matches(wrestler_id=4629, year=2025)

    assert len(matches) > 0
    # Should have the wrestler ID in every match
    for match in matches:
        assert 4629 in match["wrestlers"]


# Uncomment to run these tests - they will hit the network the first time!
# After that, they'll use the recorded cassettes


@pytest.mark.vcr()
def test_scrape_new_wrestler():
    """Example of recording a new wrestler's data."""
    scraper = CageMatchScraper()
    profile = scraper.scrape_profile(wrestler_id=9462)  # Hikaru Shida

    assert profile.name() == "Hikaru Shida"


@pytest.mark.vcr()
def test_scrape_all_matches():
    """Example of recording all matches for a wrestler."""
    scraper = CageMatchScraper()
    matches = scraper.scrape_all_matches(wrestler_id=828)  # Aja Kong

    assert len(matches) > 0
    for match in matches:
        assert 828 in match["wrestlers"], (
            "Wrestler ID should be in every match, but isn't in: {}".format(match)
        )
