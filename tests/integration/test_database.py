"""Integration tests for database operations."""

import pytest


def test_attempting_to_write_outside_context_raises(temp_db):
    """Test that writing outside a writable context raises a RuntimeError."""
    with pytest.raises(
        RuntimeError,
    ):
        temp_db.save_profile_for_wrestler(1, {"Name": "Test"})


def test_nested_write_contexts_raise(temp_db):
    """Test that attempting to nest writable contexts raises a RuntimeError."""
    with pytest.raises(RuntimeError):
        with temp_db.writable():
            with temp_db.writable():
                pass


def test_select_and_fetchone_returns_false_if_no_results(temp_db):
    """Test that _select_and_fetchone raises if no results found."""
    result = temp_db._select_and_fetchone(
        "SELECT * FROM wrestlers WHERE wrestler_id = ?", (999999,)
    )
    assert not result


def test_failed_commit_rollsback(temp_db):
    """Test that a failed commit rolls back changes."""
    try:
        with temp_db.writable():
            temp_db._execute(
                "INSERT INTO wrestlers (wrestler_id, name, is_female) VALUES (?, ?, ?)",
                (1, "Test Wrestler", 1),
            )
            # Force an error
            temp_db._execute("INVALID SQL STATEMENT")
    except Exception:
        pass
    with pytest.raises(KeyError):
        wrestler = temp_db.get_wrestler(1)


def test_explict_commit_does_not_rollback(temp_db):
    """Test that a failure after an explicit commit does not roll back changes."""
    with pytest.raises(TypeError):
        with temp_db.writable():
            temp_db._execute(
                "INSERT INTO wrestlers (wrestler_id, name, is_female) VALUES (?, ?, ?)",
                (1, "Test Wrestler", 1),
            )
            temp_db._commit()
            # Force an error
            temp_db._execute("INVALID SQL STATEMENT")

    wrestler = temp_db.get_wrestler(1)
    assert wrestler["name"] == "Test Wrestler"


def test_save_and_retrieve_profile(temp_db):
    """Test saving and retrieving wrestler profile."""
    profile_data = {
        "Current gimmick": "Test Wrestler",
        "Gender": "female",
        "Promotion": "Test Promotion",
    }

    with temp_db.writable():
        temp_db.save_profile_for_wrestler(100, profile_data)

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

    with temp_db.writable():
        temp_db.save_matches_for_wrestler(100, matches, year=2025)

    retrieved_matches = temp_db.get_matches(100, year=2025)
    assert len(retrieved_matches) == 2
    assert retrieved_matches[0]["date"] == "2025-01-01"
    assert retrieved_matches[0]["is_victory"] is True


def test_update_match_metadata(temp_db):
    """Test that match metadata is correctly computed."""
    # Create a wrestler first
    with temp_db.writable():
        temp_db.save_profile_for_wrestler(
            100, {"Name": "Test", "Gender": "female", "Promotion": "Test"}
        )

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
    with temp_db.writable():
        temp_db.save_profile_for_wrestler(
            100, {"Name": "Test", "Gender": "female", "Promotion": "Test"}
        )

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

    colleagues = temp_db.get_all_colleagues(100)

    assert 200 in colleagues
    assert 300 in colleagues
    assert 100 not in colleagues  # Shouldn't include self
    assert len(colleagues) == 2  # Should be deduplicated
