"""Integration tests for database operations."""

import json


def test_save_and_retrieve_profile(temp_db):
    """Test saving and retrieving wrestler profile."""
    profile_data = {
        "Current gimmick": "Test Wrestler",
        "Gender": "female",
        "Promotion": "Test Promotion",
    }

    temp_db.save_profile_for_wrestler(100, profile_data)
    temp_db.update_wrestler_from_profile(100)

    wrestler = temp_db.get_wrestler(100)
    assert wrestler["name"] == "Test Wrestler"
    assert wrestler["is_female"] == 1  # SQLite returns 1 for True
    assert wrestler["promotion"] == "Test Promotion"


def test_save_and_retrieve_matches(temp_db):
    """Test saving and retrieving match data."""
    matches = [
        {
            "date": "2025-01-01",
            "wrestlers": [100, 200],
            "side_a": [100],
            "side_b": [200],
            "is_victory": True,
            "match_type": "Singles",
        },
        {
            "date": "2025-01-02",
            "wrestlers": [100, 300],
            "side_a": [100],
            "side_b": [300],
            "is_victory": False,
            "match_type": "Singles",
        },
    ]

    temp_db.save_matches_for_wrestler(100, matches, year=2025)

    retrieved_matches = temp_db.get_matches(100, year=2025)
    assert len(retrieved_matches) == 2
    assert retrieved_matches[0]["date"] == "2025-01-01"
    assert retrieved_matches[0]["is_victory"] is True


def test_update_match_metadata(temp_db):
    """Test that match metadata is correctly computed."""
    # Create a wrestler first
    temp_db.save_profile_for_wrestler(
        100, {"Name": "Test", "Gender": "female", "Promotion": "Test"}
    )
    temp_db.update_wrestler_from_profile(100)

    matches = [
        {
            "date": "2025-01-01",
            "wrestlers": [100, 200],
            "side_a": [100],
            "side_b": [200],
            "is_victory": True,
            "match_type": "Singles",
            "country": "Japan",
        },
        {
            "date": "2025-01-02",
            "wrestlers": [100, 200],
            "side_a": [100],
            "side_b": [200],
            "is_victory": False,
            "match_type": "Singles",
            "country": "Japan",
        },
        {
            "date": "2025-01-03",
            "wrestlers": [100, 300],
            "side_a": [100],
            "side_b": [300],
            "is_victory": True,
            "match_type": "Singles",
            "country": "USA",
        },
    ]

    temp_db.save_matches_for_wrestler(100, matches, year=2025)
    temp_db.update_matches_from_matches(100)

    match_info = temp_db.get_match_info(100, year=2025)

    assert match_info["match_count"] == 3
    assert 200 in match_info["opponents"]
    assert 300 in match_info["opponents"]
    assert match_info["countries_worked"]["Japan"] == 2
    assert match_info["countries_worked"]["USA"] == 1


def test_is_female_check(seeded_db):
    """Test gender checking functionality."""
    assert seeded_db.is_female(4629) is True  # Emi Sakura
    assert seeded_db.is_female(1) is False  # Male wrestler
    assert seeded_db.is_female(2) is True  # Female wrestler


def test_all_female_wrestlers(seeded_db):
    """Test retrieving all female wrestlers."""
    female_wrestlers = seeded_db.all_female_wrestlers()

    assert 4629 in female_wrestlers
    assert 2 in female_wrestlers
    assert 1 not in female_wrestlers


def test_wrestler_exists(seeded_db):
    """Test checking wrestler existence."""
    assert seeded_db.wrestler_exists(4629) is True
    assert seeded_db.wrestler_exists(999999) is False


def test_get_colleagues(temp_db):
    """Test getting all colleagues from match history."""
    # Create wrestler and matches
    temp_db.save_profile_for_wrestler(
        100, {"Name": "Test", "Gender": "female", "Promotion": "Test"}
    )
    temp_db.update_wrestler_from_profile(100)

    matches = [
        {
            "date": "2025-01-01",
            "wrestlers": [100, 200],
            "side_a": [100],
            "side_b": [200],
            "is_victory": True,
        },
        {
            "date": "2025-01-02",
            "wrestlers": [100, 300],
            "side_a": [100],
            "side_b": [300],
            "is_victory": False,
        },
        {
            "date": "2025-01-03",
            "wrestlers": [100, 200],  # Duplicate opponent
            "side_a": [100],
            "side_b": [200],
            "is_victory": True,
        },
    ]

    temp_db.save_matches_for_wrestler(100, matches, year=2025)
    temp_db.update_matches_from_matches(100)

    colleagues = temp_db.get_all_colleagues(100)

    assert 200 in colleagues
    assert 300 in colleagues
    assert 100 not in colleagues  # Shouldn't include self
    assert len(colleagues) == 2  # Should be deduplicated
