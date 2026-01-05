"""Shared pytest fixtures for testing."""

import pathlib
import tempfile

import pytest

from joshirank.joshidb import WrestlerDb


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def html_fixtures(fixtures_dir):
    """Return the path to HTML fixtures directory."""
    return fixtures_dir / "html"


@pytest.fixture
def sample_profile_html(html_fixtures):
    """Load Emi Sakura's profile HTML."""
    return (html_fixtures / "wrestler_4629_profile.html").read_text()


@pytest.fixture
def sample_matches_html(html_fixtures):
    """Load Emi Sakura's 2025 matches HTML."""
    return (html_fixtures / "wrestler_4629_matches_2025.html").read_text()


@pytest.fixture
def temp_db():
    """Create a temporary test database.

    Yields a WrestlerDb instance with a fresh database.
    The database is automatically cleaned up after the test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = pathlib.Path(tmpdir) / "test_wrestlers.y"
        db = WrestlerDb(db_path)

        yield db

        db.close()


@pytest.fixture
def seeded_db(temp_db):
    """Create a test database with sample data.

    Seeds the database with a few known wrestlers for testing.
    """
    # Seed with Emi Sakura
    temp_db.save_profile_for_wrestler(
        4629,
        {
            "Name": "Emi Sakura",
            "Gender": "female",
            "Promotion": "Gatoh Move",
            "Birthplace": "Japan",
        },
    )
    temp_db.update_wrestler_from_profile(4629)

    # Seed with a male wrestler for comparison
    temp_db.save_profile_for_wrestler(
        1,
        {
            "Name": "Test Male",
            "Gender": "male",
            "Promotion": "Test Promotion",
        },
    )
    temp_db.update_wrestler_from_profile(1)

    # Seed with a female wrestler
    temp_db.save_profile_for_wrestler(
        2,
        {
            "Name": "Test Female",
            "Gender": "female",
            "Promotion": "Stardom",
        },
    )
    temp_db.update_wrestler_from_profile(2)

    return temp_db
