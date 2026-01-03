"""Unit tests for CageMatch profile parsing."""

from joshirank.cagematch.profile import CMProfile


def test_parse_emi_sakura_profile(sample_profile_html):
    """Test parsing Emi Sakura's profile from real HTML."""
    profile = CMProfile.from_html(4629, sample_profile_html)

    assert profile.id == 4629
    assert profile.name() == "Emi Sakura"
    assert profile.is_female() is True
    # AEW is her current promotion according to CageMatch
    assert profile.promotion() == "AEW"


def test_profile_from_dict():
    """Test creating profile from dictionary data."""
    profile_data = {
        "Current gimmick": "Test Wrestler",
        "Gender": "female",
        "Promotion": "Test Promotion",
    }

    profile = CMProfile.from_dict(999, profile_data)

    assert profile.id == 999
    assert profile.name() == "Test Wrestler"
    assert profile.is_female() is True
    assert profile.promotion() == "Test Promotion"


def test_profile_gender_detection():
    """Test various gender detection scenarios."""
    # Explicit female
    female_profile = CMProfile.from_dict(1, {"Gender": "female"})
    assert female_profile.is_female() is True

    # Explicit male
    male_profile = CMProfile.from_dict(2, {"Gender": "male"})
    assert male_profile.is_female() is False

    # Missing gender - should default to False
    unknown_profile = CMProfile.from_dict(3, {"Name": "Test"})
    assert unknown_profile.is_female() is False
