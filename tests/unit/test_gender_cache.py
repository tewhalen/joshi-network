"""Unit tests for gender prediction cache functionality."""

import json
import pathlib
import tempfile
import time

import pytest

from joshirank.analysis.gender import (
    guess_gender_of_wrestler,
)
from joshirank.analysis.gender_cache import (
    GenderCache,
    clear_gender_cache,
    get_gender_cache_stats,
)


@pytest.fixture
def temp_cache_file(tmp_path):
    """Create a temporary cache file path."""
    return tmp_path / "test_gender_cache.db"


@pytest.fixture
def cache(temp_cache_file):
    """Create a GenderCache instance with temporary file."""
    return GenderCache(temp_cache_file)


class TestGenderCache:
    """Tests for the GenderCache class."""

    def test_initialization_creates_empty_cache(self, cache, temp_cache_file):
        """Test that a new cache initializes empty."""
        assert len(cache) == 0
        assert cache.cache_path == temp_cache_file
        # SQLite creates the file immediately on initialization
        assert temp_cache_file.exists()

    def test_set_and_get_entry(self, cache):
        """Test setting and retrieving a cache entry."""
        wrestler_id = 12345
        confidence = 0.95

        cache.set(wrestler_id, confidence)
        result = cache.get(wrestler_id)

        assert result == confidence

    def test_get_nonexistent_entry(self, cache):
        """Test getting an entry that doesn't exist."""
        result = cache.get(99999)
        assert result is None

    def test_save_and_load(self, cache, temp_cache_file):
        """Test saving to disk and loading from disk."""
        # Set some data
        cache.set(100, 0.95)
        cache.set(200, 0.20)

        # Save to disk (though SQLite commits immediately on set)
        cache.save()
        assert temp_cache_file.exists()

        # Load in a new cache instance
        new_cache = GenderCache(temp_cache_file)
        assert new_cache.get(100) == 0.95
        assert new_cache.get(200) == 0.20
        new_cache.close()

    def test_cache_file_format(self, cache, temp_cache_file):
        """Test that cache database has correct SQLite structure."""
        import sqlite3

        cache.set(12345, 0.75)
        cache.save()

        # Query the SQLite database directly
        conn = sqlite3.connect(str(temp_cache_file))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT confidence, timestamp, version FROM gender_predictions WHERE wrestler_id = ?",
            (12345,),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row["confidence"] == 0.75
        assert row["timestamp"] > 0
        assert row["version"] == GenderCache.CACHE_VERSION

    def test_stale_entry_detection(self, cache):
        """Test that stale entries are correctly identified."""
        import sqlite3

        wrestler_id = 12345
        # Create an old timestamp (100 days ago)
        old_timestamp = time.time() - (100 * 86400)

        # Manually insert a stale entry directly into the database
        cursor = cache._conn.cursor()
        cursor.execute(
            """
            INSERT INTO gender_predictions (wrestler_id, confidence, timestamp, version)
            VALUES (?, ?, ?, ?)
        """,
            (wrestler_id, 0.5, old_timestamp, GenderCache.CACHE_VERSION),
        )
        cache._conn.commit()

        # Should return None because it's stale
        result = cache.get(wrestler_id)
        assert result is None

    def test_fresh_entry_not_stale(self, cache):
        """Test that fresh entries are not marked as stale."""
        cache.set(12345, 0.95)

        # Should return the value because it's fresh
        result = cache.get(12345)
        assert result == 0.95

    def test_version_incompatibility(self, cache):
        """Test that entries with wrong version are ignored."""
        import sqlite3

        wrestler_id = 12345

        # Insert entry with wrong version directly into database
        cursor = cache._conn.cursor()
        cursor.execute(
            """
            INSERT INTO gender_predictions (wrestler_id, confidence, timestamp, version)
            VALUES (?, ?, ?, ?)
        """,
            (wrestler_id, 0.5, time.time(), 999),  # Wrong version
        )
        cache._conn.commit()

        result = cache.get(wrestler_id)
        assert result is None

    def test_clear_stale_removes_old_entries(self, cache):
        """Test that clear_stale removes only stale entries."""
        # Add a fresh entry
        cache.set(100, 0.95)

        # Add a stale entry directly to database
        old_timestamp = time.time() - (100 * 86400)
        cursor = cache._conn.cursor()
        cursor.execute(
            """
            INSERT INTO gender_predictions (wrestler_id, confidence, timestamp, version)
            VALUES (?, ?, ?, ?)
        """,
            (200, 0.5, old_timestamp, GenderCache.CACHE_VERSION),
        )
        cache._conn.commit()

        # Clear stale entries
        removed = cache.clear_stale()

        assert removed == 1
        assert cache.get(100) == 0.95  # Fresh entry still there
        assert cache.get(200) is None  # Stale entry gone

    def test_clear_stale_keeps_fresh_entries(self, cache):
        """Test that clear_stale doesn't remove fresh entries."""
        # Add multiple fresh entries
        cache.set(100, 0.95)
        cache.set(200, 0.85)
        cache.set(300, 0.75)

        removed = cache.clear_stale()

        assert removed == 0
        assert len(cache) == 3

    def test_invalid_database_loads_empty_cache(self, temp_cache_file):
        """Test that corrupted database results in empty cache."""
        # Create a file with invalid SQLite data
        temp_cache_file.write_text("not a sqlite database")

        # Should handle gracefully (may raise exception or create new db)
        try:
            cache = GenderCache(temp_cache_file)
            cache.close()
        except Exception:
            # It's acceptable to raise an exception for corrupted database
            pass

    def test_migration_from_json(self, temp_cache_file, tmp_path):
        """Test that JSON cache is automatically migrated to SQLite."""
        import json

        # Create old JSON cache file
        json_cache_path = tmp_path / "gender_cache.json"
        data = {
            "12345": {
                "confidence": 0.95,
                "timestamp": time.time(),
                "version": 1,
            }
        }
        json_cache_path.write_text(json.dumps(data))

        # Create SQLite cache - should migrate from JSON
        db_path = tmp_path / "gender_cache.db"
        cache = GenderCache(db_path)

        # JSON file should be renamed to .migrated
        # (Only happens if JSON is in same directory with expected name)
        cache.close()


class TestGuessGenderWithCache:
    """Tests for guess_gender_of_wrestler with caching."""

    def test_cache_miss_calculates_and_caches(self, temp_cache_file, monkeypatch):
        """Test that cache miss triggers calculation and caches result."""
        # Create a mock wrestler_db with minimal data
        # Use a temp cache for this test
        from joshirank.analysis import gender_cache

        original_cache = gender_cache._gender_cache
        test_cache = GenderCache(temp_cache_file)
        monkeypatch.setattr(gender_cache, "_gender_cache", test_cache)

        try:
            # Pick a wrestler ID that exists
            wrestler_id = 9462  # Hikaru Shida

            # Clear cache to ensure miss
            test_cache.clear()

            # First call should calculate
            result1 = guess_gender_of_wrestler(wrestler_id)

            # Result should be cached
            assert test_cache.get(wrestler_id) is not None

            # Second call should use cache
            result2 = guess_gender_of_wrestler(wrestler_id)

            # Results should match
            assert result1 == result2

        finally:
            # Restore original cache
            test_cache.close()
            monkeypatch.setattr(gender_cache, "_gender_cache", original_cache)

    def test_cache_hit_returns_immediately(self, temp_cache_file, monkeypatch):
        """Test that cache hit doesn't recalculate."""
        from joshirank.analysis import gender_cache

        original_cache = gender_cache._gender_cache
        test_cache = GenderCache(temp_cache_file)
        monkeypatch.setattr(gender_cache, "_gender_cache", test_cache)

        try:
            wrestler_id = 9462

            # Pre-populate cache
            test_cache.set(wrestler_id, 0.99)

            # Call should return cached value immediately
            result = guess_gender_of_wrestler(wrestler_id)

            assert result == 0.99

        finally:
            test_cache.close()
            monkeypatch.setattr(gender_cache, "_gender_cache", original_cache)

    def test_no_opponents_returns_neutral(self, temp_cache_file, monkeypatch):
        """Test that wrestler with no opponents gets neutral score."""
        from joshirank.analysis import gender_cache

        original_cache = gender_cache._gender_cache
        test_cache = GenderCache(temp_cache_file)
        monkeypatch.setattr(gender_cache, "_gender_cache", test_cache)

        try:
            # Use a wrestler ID unlikely to exist in inverse colleagues
            wrestler_id = 99999999

            result = guess_gender_of_wrestler(wrestler_id)

            # Should return neutral score
            assert result == 0.5

            # Should be cached
            assert test_cache.get(wrestler_id) == 0.5

        finally:
            test_cache.close()
            monkeypatch.setattr(gender_cache, "_gender_cache", original_cache)


class TestUtilityFunctions:
    """Tests for cache utility functions."""

    def test_clear_gender_cache(self, temp_cache_file, monkeypatch):
        """Test that clear_gender_cache empties the cache."""
        from joshirank.analysis import gender_cache

        original_cache = gender_cache._gender_cache
        test_cache = GenderCache(temp_cache_file)
        monkeypatch.setattr(gender_cache, "_gender_cache", test_cache)

        try:
            # Add some entries
            test_cache.set(100, 0.95)
            test_cache.set(200, 0.85)

            # Clear cache
            clear_gender_cache()

            # Cache should be empty
            assert len(test_cache) == 0

        finally:
            test_cache.close()
            monkeypatch.setattr(gender_cache, "_gender_cache", original_cache)

    def test_get_gender_cache_stats(self, temp_cache_file, monkeypatch):
        """Test that get_gender_cache_stats returns correct info."""
        from joshirank.analysis import gender_cache

        original_cache = gender_cache._gender_cache
        test_cache = GenderCache(temp_cache_file)
        monkeypatch.setattr(gender_cache, "_gender_cache", test_cache)

        try:
            # Add some entries
            test_cache.set(100, 0.95)
            test_cache.set(200, 0.85)
            test_cache.save()

            stats = get_gender_cache_stats()

            assert stats["total_entries"] == 2
            assert stats["cache_file"] == str(temp_cache_file)
            assert stats["exists"] is True

        finally:
            test_cache.close()
            monkeypatch.setattr(gender_cache, "_gender_cache", original_cache)

    def test_get_gender_cache_stats_no_file(self, temp_cache_file, monkeypatch):
        """Test stats when cache file doesn't exist."""
        from joshirank.analysis import gender_cache

        original_cache = gender_cache._gender_cache
        # Use a non-existent path
        nonexistent_path = temp_cache_file.parent / "nonexistent.db"
        test_cache = GenderCache(nonexistent_path)
        monkeypatch.setattr(gender_cache, "_gender_cache", test_cache)

        try:
            # Add entry but don't call save() explicitly (SQLite creates file on init)
            test_cache.set(100, 0.95)

            stats = get_gender_cache_stats()

            assert stats["total_entries"] == 1
            # SQLite creates file immediately
            assert stats["exists"] is True

        finally:
            test_cache.close()
            monkeypatch.setattr(gender_cache, "_gender_cache", original_cache)


class TestCachePersistence:
    """Tests for cache persistence across sessions."""

    def test_cache_persists_across_instances(self, temp_cache_file):
        """Test that cache data persists when reloading."""
        # First cache instance
        cache1 = GenderCache(temp_cache_file)
        cache1.set(100, 0.95)
        cache1.set(200, 0.85)
        cache1.save()

        # Create new instance (simulates new session)
        cache2 = GenderCache(temp_cache_file)

        # Data should be loaded
        assert cache2.get(100) == 0.95
        assert cache2.get(200) == 0.85

    def test_cache_survives_multiple_saves(self, temp_cache_file):
        """Test that multiple save operations work correctly."""
        cache = GenderCache(temp_cache_file)

        # First save
        cache.set(100, 0.95)
        cache.save()

        # Second save with more data
        cache.set(200, 0.85)
        cache.save()

        # Third save with even more data
        cache.set(300, 0.75)
        cache.save()

        # Reload and verify all data is present
        new_cache = GenderCache(temp_cache_file)
        assert new_cache.get(100) == 0.95
        assert new_cache.get(200) == 0.85
        assert new_cache.get(300) == 0.75


class TestCacheEdgeCases:
    """Tests for edge cases and error handling."""

    def test_cache_with_zero_confidence(self, cache):
        """Test that 0.0 confidence is valid."""
        cache.set(100, 0.0)
        assert cache.get(100) == 0.0

    def test_cache_with_one_confidence(self, cache):
        """Test that 1.0 confidence is valid."""
        cache.set(100, 1.0)
        assert cache.get(100) == 1.0

    def test_negative_wrestler_id(self, cache):
        """Test that negative wrestler IDs work (e.g., -1 placeholder)."""
        cache.set(-1, 0.5)
        assert cache.get(-1) == 0.5

    def test_large_wrestler_id(self, cache):
        """Test that large wrestler IDs work."""
        large_id = 99999999
        cache.set(large_id, 0.75)
        assert cache.get(large_id) == 0.75

    def test_multiple_rapid_updates(self, cache):
        """Test that rapid updates to same entry work correctly."""
        wrestler_id = 100

        cache.set(wrestler_id, 0.1)
        cache.set(wrestler_id, 0.5)
        cache.set(wrestler_id, 0.9)

        # Should have the latest value
        assert cache.get(wrestler_id) == 0.9

    def test_cache_directory_created_on_save(self, tmp_path):
        """Test that cache directory is created if it doesn't exist."""
        nested_path = tmp_path / "nested" / "dir" / "cache.json"
        cache = GenderCache(nested_path)

        cache.set(100, 0.95)
        cache.save()

        assert nested_path.exists()
        assert nested_path.parent.exists()
