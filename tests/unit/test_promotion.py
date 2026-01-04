"""Unit tests for promotion parsing."""

import pathlib

import pytest

from joshirank.cagematch.promotion import CMPromotion, parse_promotion_page

# Get path to fixtures
FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "fixtures" / "html"


# Sample HTML from a CageMatch promotion page (Stardom)
SAMPLE_PROMOTION_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="InformationBoxTable">
    <div class="InformationBoxRow">
        <div class="InformationBoxTitle">Current name:</div>
        <div class="InformationBoxContents">World Wonder Ring Stardom</div>
    </div>
    <div class="InformationBoxRow">
        <div class="InformationBoxTitle">Location:</div>
        <div class="InformationBoxContents">Tokyo, Japan</div>
    </div>
    <div class="InformationBoxRow">
        <div class="InformationBoxTitle">Active Time:</div>
        <div class="InformationBoxContents">2011 - today</div>
    </div>
</div>
</body>
</html>
"""

# Sample HTML with minimal data
MINIMAL_PROMOTION_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="InformationBoxTable">
    <div class="InformationBoxRow">
        <div class="InformationBoxTitle">Current name:</div>
        <div class="InformationBoxContents">Test Promotion</div>
    </div>
</div>
</body>
</html>
"""

# HTML with no InfoTable (edge case)
NO_TABLE_HTML = """
<!DOCTYPE html>
<html>
<body>
<div>No promotion data here</div>
</body>
</html>
"""


class TestParsePromotionPage:
    """Test the parse_promotion_page function."""

    def test_parse_full_promotion(self):
        """Test parsing a complete promotion page."""
        result = parse_promotion_page(SAMPLE_PROMOTION_HTML)

        assert result["Name"] == "World Wonder Ring Stardom"
        assert result["Founded"] == "2011"
        assert result["Country"] == "Japan"

    def test_parse_minimal_promotion(self):
        """Test parsing a promotion with minimal data."""
        result = parse_promotion_page(MINIMAL_PROMOTION_HTML)

        assert result["Name"] == "Test Promotion"
        assert "Founded" not in result
        assert "Country" not in result

    def test_parse_no_table(self):
        """Test parsing HTML with no InfoTable."""
        result = parse_promotion_page(NO_TABLE_HTML)

        assert result == {}

    def test_parse_empty_string(self):
        """Test parsing an empty string."""
        result = parse_promotion_page("")

        assert result == {}


class TestCMPromotion:
    """Test the CMPromotion class."""

    def test_from_html(self):
        """Test creating a CMPromotion from HTML."""
        promotion = CMPromotion.from_html(745, SAMPLE_PROMOTION_HTML)

        assert promotion.id == 745
        assert promotion.name() == "World Wonder Ring Stardom"
        assert promotion.founded() == "2011"
        assert promotion.country() == "Japan"

    def test_from_dict(self):
        """Test creating a CMPromotion from a dict."""
        data = {
            "Name": "Test Promotion",
            "Founded": "2020",
            "Country": "USA",
        }
        promotion = CMPromotion.from_dict(123, data)

        assert promotion.id == 123
        assert promotion.name() == "Test Promotion"
        assert promotion.founded() == "2020"
        assert promotion.country() == "USA"

    def test_to_dict(self):
        """Test converting CMPromotion to dict."""
        promotion = CMPromotion.from_html(745, SAMPLE_PROMOTION_HTML)
        result = promotion.to_dict()

        assert result["Name"] == "World Wonder Ring Stardom"
        assert result["Founded"] == "2011"
        assert result["Country"] == "Japan"

    def test_missing_fields(self):
        """Test handling of missing fields."""
        promotion = CMPromotion.from_html(123, MINIMAL_PROMOTION_HTML)

        assert promotion.name() == "Test Promotion"
        assert promotion.founded() == ""
        assert promotion.country() == ""

    def test_unknown_promotion(self):
        """Test handling of completely unknown promotion."""
        promotion = CMPromotion.from_html(999, NO_TABLE_HTML)

        assert promotion.name() == "Unknown Promotion"
        assert promotion.founded() == ""
        assert promotion.country() == ""


class TestPromotionWithFixtures:
    """Test promotion parsing with real HTML fixtures."""

    def test_parse_stardom_fixture(self):
        """Test parsing the Stardom promotion fixture."""
        fixture_path = FIXTURES_DIR / "promotion_745_stardom.html"

        if not fixture_path.exists():
            pytest.skip(f"Fixture not found: {fixture_path}")

        # Try reading with different encodings
        try:
            html = fixture_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                html = fixture_path.read_text(encoding="latin-1")
            except:
                pytest.skip(f"Could not decode fixture file: {fixture_path}")

        promotion = CMPromotion.from_html(745, html)

        assert promotion.id == 745
        assert promotion.name() == "World Wonder Ring Stardom"
        assert promotion.founded() == "2011"
        assert promotion.country() == "Japan"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
