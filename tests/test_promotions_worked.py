"""Test promotions_worked field functionality."""

from joshirank.analysis.promotion import all_tjpw_wrestlers
from joshirank.joshidb import wrestler_db


def test_promotions_worked_field():
    """Test that promotions_worked field is populated and accessible."""
    # Test with a known TJPW wrestler (Yuka Sakazaki)
    match_info = wrestler_db.get_match_info(16547, 2025)

    # Check that promotions_worked exists and is a dict
    assert "promotions_worked" in match_info
    assert isinstance(match_info["promotions_worked"], dict)

    # Check that it has promotion data
    promotions = match_info["promotions_worked"]
    assert len(promotions) > 0

    # Check that TJPW (1467) is in there
    assert "1467" in promotions or 1467 in promotions

    print("✓ promotions_worked field is correctly populated")


def test_all_tjpw_wrestlers():
    """Test that all_tjpw_wrestlers query works with new field."""
    tjpw_wrestlers = all_tjpw_wrestlers()

    # Should find at least 50 TJPW wrestlers
    assert len(tjpw_wrestlers) >= 50

    # Yuka Sakazaki (16547) should be in the list (TJPW regular)
    assert 16547 in tjpw_wrestlers

    # Hikaru Shida (9462) should be in the list (worked TJPW in 2022, 2024)
    assert 9462 in tjpw_wrestlers

    # Emi Sakura (4629) should be in the list (TJPW veteran)
    assert 4629 in tjpw_wrestlers

    print(f"✓ Found {len(tjpw_wrestlers)} TJPW wrestlers")


def test_countries_vs_promotions():
    """Verify both countries_worked and promotions_worked are independent."""
    match_info = wrestler_db.get_match_info(9462, 2025)  # Hikaru Shida

    # Both fields should exist
    assert "countries_worked" in match_info
    assert "promotions_worked" in match_info

    # Both should be dicts
    assert isinstance(match_info["countries_worked"], dict)
    assert isinstance(match_info["promotions_worked"], dict)

    print("✓ Both countries_worked and promotions_worked coexist correctly")


if __name__ == "__main__":
    test_promotions_worked_field()
    test_all_tjpw_wrestlers()
    test_countries_vs_promotions()
    print("\n✅ All tests passed!")
