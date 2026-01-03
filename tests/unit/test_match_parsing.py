"""Unit tests for match list parsing."""

from joshirank.cagematch.cm_match import extract_match_data_from_match_page


def test_parse_match_list(sample_matches_html):
    """Test parsing Emi Sakura's 2025 match list."""
    matches = list(extract_match_data_from_match_page(sample_matches_html))

    assert len(matches) > 0, "Should parse at least one match"

    # Check first match structure
    first_match = matches[0]
    assert "date" in first_match
    assert "wrestlers" in first_match
    assert "side_a" in first_match
    assert "side_b" in first_match
    assert "is_victory" in first_match
    assert "match_type" in first_match

    # Emi Sakura's ID should appear in wrestlers
    wrestler_ids = first_match["wrestlers"]
    assert 4629 in wrestler_ids, "Emi Sakura (4629) should be in her own matches"


def test_match_has_valid_dates(sample_matches_html):
    """Test that parsed matches have valid date formats."""
    matches = list(extract_match_data_from_match_page(sample_matches_html))

    for match in matches:
        date = match["date"]
        # Date should be ISO format YYYY-MM-DD or "Unknown"
        if date != "Unknown":
            assert len(date) == 10, f"Date should be YYYY-MM-DD format: {date}"
            assert date[4] == "-" and date[7] == "-"


def test_match_sides_are_lists(sample_matches_html):
    """Test that match sides are properly structured."""
    matches = list(extract_match_data_from_match_page(sample_matches_html))

    for match in matches:
        # Match parser returns tuples for sides
        assert isinstance(match["side_a"], (list, tuple))
        assert isinstance(match["side_b"], (list, tuple))
        assert len(match["side_a"]) > 0
        assert len(match["side_b"]) > 0

        # All IDs should be integers
        for wrestler_id in list(match["side_a"]) + list(match["side_b"]):
            assert isinstance(wrestler_id, int)
