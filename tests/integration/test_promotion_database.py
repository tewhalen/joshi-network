"""Integration tests for promotion database operations."""

import pathlib
import tempfile

import pytest

from joshirank.joshidb import WrestlerDb


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = pathlib.Path(tmpdir) / "test.y"
        db = WrestlerDb(db_path)
        yield db
        db.close()


class TestPromotionDatabase:
    """Test promotion database operations."""

    def test_save_and_get_promotion(self, temp_db):
        """Test saving and retrieving a promotion."""
        promotion_data = {
            "Name": "World Wonder Ring Stardom",
            "Founded": "January 2011",
            "Country": "Japan",
        }

        # Save promotion
        temp_db.save_promotion(745, promotion_data)

        # Retrieve promotion
        result = temp_db.get_promotion(745)

        assert result is not None
        assert result["name"] == "World Wonder Ring Stardom"
        assert result["founded"] == "January 2011"
        assert result["country"] == "Japan"
        assert "cm_promotion_json" in result
        assert "last_updated" in result
        assert "timestamp" in result

    def test_get_promotion_name(self, temp_db):
        """Test retrieving promotion name by ID."""
        promotion_data = {
            "Name": "All Elite Wrestling",
            "Founded": "2019",
            "Country": "USA",
        }

        temp_db.save_promotion(17025, promotion_data)

        name = temp_db.get_promotion_name(17025)
        assert name == "All Elite Wrestling"

    def test_get_nonexistent_promotion_name(self, temp_db):
        """Test retrieving name for promotion that doesn't exist."""
        name = temp_db.get_promotion_name(99999)
        assert name == "99999"  # Returns ID as string

    def test_promotion_exists(self, temp_db):
        """Test checking if promotion exists."""
        promotion_data = {"Name": "Test Promotion"}

        assert not temp_db.promotion_exists(123)

        temp_db.save_promotion(123, promotion_data)

        assert temp_db.promotion_exists(123)

    def test_all_promotion_ids(self, temp_db):
        """Test retrieving all promotion IDs."""
        promotions = [
            (745, {"Name": "Stardom"}),
            (17025, {"Name": "AEW"}),
            (326, {"Name": "Ice Ribbon"}),
        ]

        for promo_id, data in promotions:
            temp_db.save_promotion(promo_id, data)

        all_ids = temp_db.all_promotion_ids()

        assert len(all_ids) == 3
        assert 745 in all_ids
        assert 17025 in all_ids
        assert 326 in all_ids

    def test_get_promotion_timestamp(self, temp_db):
        """Test retrieving promotion timestamp."""
        promotion_data = {"Name": "Test Promotion"}

        # Non-existent promotion returns 0
        timestamp = temp_db.get_promotion_timestamp(999)
        assert timestamp == 0.0

        # Save promotion and check timestamp
        temp_db.save_promotion(123, promotion_data)
        timestamp = temp_db.get_promotion_timestamp(123)
        assert timestamp > 0.0

    def test_update_promotion(self, temp_db):
        """Test updating an existing promotion."""
        # Initial save
        temp_db.save_promotion(123, {"Name": "Old Name", "Country": "USA"})

        # Update
        temp_db.save_promotion(123, {"Name": "New Name", "Country": "Canada"})

        # Verify update
        result = temp_db.get_promotion(123)
        assert result["name"] == "New Name"
        assert result["country"] == "Canada"

    def test_get_nonexistent_promotion(self, temp_db):
        """Test retrieving a promotion that doesn't exist."""
        result = temp_db.get_promotion(99999)
        assert result is None

    def test_save_promotion_with_empty_fields(self, temp_db):
        """Test saving promotion with missing fields."""
        promotion_data = {"Name": "Test Promotion"}  # No Founded or Country

        temp_db.save_promotion(456, promotion_data)

        result = temp_db.get_promotion(456)
        assert result["name"] == "Test Promotion"
        assert result["founded"] == ""
        assert result["country"] == ""

    def test_save_promotion_with_special_characters(self, temp_db):
        """Test saving promotion with special characters in name."""
        promotion_data = {
            "Name": "Pro Wrestling WAVE",
            "Founded": "2007",
            "Country": "Japan",
        }

        temp_db.save_promotion(327, promotion_data)

        result = temp_db.get_promotion(327)
        assert result["name"] == "Pro Wrestling WAVE"


class TestPromotionIntegrationWithMatches:
    """Test promotion data in context of match statistics."""

    def test_promotions_worked_with_names(self, temp_db):
        """Test that we can resolve promotion IDs from match data."""
        # Save some promotions
        promotions = {
            745: {"Name": "Stardom"},
            326: {"Name": "Ice Ribbon"},
            327: {"Name": "WAVE"},
        }

        for promo_id, data in promotions.items():
            temp_db.save_promotion(promo_id, data)

        # Verify we can resolve them
        assert temp_db.get_promotion_name(745) == "Stardom"
        assert temp_db.get_promotion_name(326) == "Ice Ribbon"
        assert temp_db.get_promotion_name(327) == "WAVE"
        assert temp_db.get_promotion_name(999) == "999"  # Unknown promotion


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
