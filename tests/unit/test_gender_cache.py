"""Unit tests for gender prediction cache functionality."""

import json
import pathlib
import tempfile
import time

import pytest

from joshirank.queries import (
    GenderCache,
    _gender_cache,
    clear_gender_cache,
    get_gender_cache_stats,
    guess_gender_of_wrestler,
)


@pytest.fixture
def temp_cache_file(tmp_path):
    """Create a temporary cache file path."""
    return tmp_path / "test_gender_cache.json"


@pytest.fixture
def cache(temp_cache_file):
    """Create a GenderCache instance with temporary file."""
    return GenderCache(temp_cache_file)


class TestGenderCache:
    """Tests for the GenderCache class."""

    def test_initialization_creates_empty_cache(self, cache, temp_cache_file):
        """Test that a new cache initializes empty."""
        assert len(cache._cache) == 0
        assert cache.cache_path == temp_cache_file
        assert not temp_cache_file.exists()

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

        # Save to disk
        cache.save()
        assert temp_cache_file.exists()

        # Load in a new cache instance
        new_cache = GenderCache(temp_cache_file)
        assert new_cache.get(100) == 0.95
        assert new_cache.get(200) == 0.20

    def test_cache_file_format(self, cache, temp_cache_file):
        """Test that cache file has correct JSON structure."""
        cache.set(12345, 0.75)
        cache.save()

        with open(temp_cache_file) as f:
            data = json.load(f)

        assert "12345" in data
        assert data["12345"]["confidence"] == 0.75
        assert "timestamp" in data["12345"]
        assert "version" in data["12345"]
        assert data["12345"]["version"] == GenderCache.CACHE_VERSION

    def test_stale_entry_detection(self, cache):
        """Test that stale entries are correctly identified."""
        wrestler_id = 12345
        # Create an old timestamp (100 days ago)
        old_timestamp = time.time() - (100 * 86400)

        # Manually create a stale entry
        cache._cache[wrestler_id] = {
            "confidence": 0.5,
            "timestamp": old_timestamp,
            "version": GenderCache.CACHE_VERSION,
        }

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
        wrestler_id = 12345

        # Create entry with wrong version
        cache._cache[wrestler_id] = {
            "confidence": 0.5,
            "timestamp": time.time(),
            "version": 999,  # Wrong version
        }

        result = cache.get(wrestler_id)
        assert result is None

    def test_clear_stale_removes_old_entries(self, cache):
        """Test that clear_stale removes only stale entries."""
        # Add a fresh entry
        cache.set(100, 0.95)

        # Add a stale entry
        old_timestamp = time.time() - (100 * 86400)
        cache._cache[200] = {
            "confidence": 0.5,
            "timestamp": old_timestamp,
            "version": GenderCache.CACHE_VERSION,
        }

        # Clear stale entries
        removed = cache.clear_stale()

        assert removed == 1
        assert 100 in cache._cache
        assert 200 not in cache._cache

    def test_clear_stale_keeps_fresh_entries(self, cache):
        """Test that clear_stale doesn't remove fresh entries."""
        # Add multiple fresh entries
        cache.set(100, 0.95)
        cache.set(200, 0.85)
        cache.set(300, 0.75)

        removed = cache.clear_stale()

        assert removed == 0
        assert len(cache._cache) == 3

    def test_invalid_json_loads_empty_cache(self, temp_cache_file):
        """Test that invalid JSON results in empty cache."""
        # Create a file with invalid JSON
        temp_cache_file.write_text("{ invalid json }")

        cache = GenderCache(temp_cache_file)
        assert len(cache._cache) == 0

    def test_string_keys_converted_to_int(self, cache, temp_cache_file):
        """Test that string keys in JSON are converted to int."""
        # Manually write JSON with string keys
        data = {
            "12345": {
                "confidence": 0.95,
                "timestamp": time.time(),
                "version": 1,
            }
        }
        temp_cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_cache_file, "w") as f:
            json.dump(data, f)

        # Load cache
        cache = GenderCache(temp_cache_file)

        # Should be accessible via int key
        assert cache.get(12345) == 0.95


class TestGuessGenderWithCache:
    """Tests for guess_gender_of_wrestler with caching."""

    def test_cache_miss_calculates_and_caches(self, temp_cache_file, monkeypatch):
        """Test that cache miss triggers calculation and caches result."""
        # Create a mock wrestler_db with minimal data
        # Use a temp cache for this test
        from joshirank import queries
        from joshirank.joshidb import wrestler_db

        original_cache = queries._gender_cache
        test_cache = GenderCache(temp_cache_file)
        monkeypatch.setattr(queries, "_gender_cache", test_cache)

        try:
            # Pick a wrestler ID that exists
            wrestler_id = 9462  # Hikaru Shida

            # Clear cache to ensure miss
            test_cache._cache.clear()

            # First call should calculate
            result1 = guess_gender_of_wrestler(wrestler_db, wrestler_id)

            # Result should be cached
            assert wrestler_id in test_cache._cache

            # Second call should use cache
            result2 = guess_gender_of_wrestler(wrestler_db, wrestler_id)

            # Results should match
            assert result1 == result2

        finally:
            # Restore original cache
            monkeypatch.setattr(queries, "_gender_cache", original_cache)

    def test_cache_hit_returns_immediately(self, temp_cache_file, monkeypatch):
        """Test that cache hit doesn't recalculate."""
        from joshirank import queries
        from joshirank.joshidb import wrestler_db

        original_cache = queries._gender_cache
        test_cache = GenderCache(temp_cache_file)
        monkeypatch.setattr(queries, "_gender_cache", test_cache)

        try:
            wrestler_id = 9462

            # Pre-populate cache
            test_cache.set(wrestler_id, 0.99)

            # Call should return cached value immediately
            result = guess_gender_of_wrestler(wrestler_db, wrestler_id)

            assert result == 0.99

        finally:
            monkeypatch.setattr(queries, "_gender_cache", original_cache)

    def test_no_opponents_returns_neutral(self, temp_cache_file, monkeypatch):
        """Test that wrestler with no opponents gets neutral score."""
        from joshirank import queries
        from joshirank.joshidb import wrestler_db

        original_cache = queries._gender_cache
        test_cache = GenderCache(temp_cache_file)
        monkeypatch.setattr(queries, "_gender_cache", test_cache)

        try:
            # Use a wrestler ID unlikely to exist in inverse colleagues
            wrestler_id = 99999999

            result = guess_gender_of_wrestler(wrestler_db, wrestler_id)

            # Should return neutral score
            assert result == 0.5

            # Should be cached
            assert test_cache.get(wrestler_id) == 0.5

        finally:
            monkeypatch.setattr(queries, "_gender_cache", original_cache)


class TestUtilityFunctions:
    """Tests for cache utility functions."""

    def test_clear_gender_cache(self, temp_cache_file, monkeypatch):
        """Test that clear_gender_cache empties the cache."""
        from joshirank import queries

        original_cache = queries._gender_cache
        test_cache = GenderCache(temp_cache_file)
        monkeypatch.setattr(queries, "_gender_cache", test_cache)

        try:
            # Add some entries
            test_cache.set(100, 0.95)
            test_cache.set(200, 0.85)

            # Clear cache
            clear_gender_cache()

            # Cache should be empty
            assert len(test_cache._cache) == 0

        finally:
            monkeypatch.setattr(queries, "_gender_cache", original_cache)

    def test_get_gender_cache_stats(self, temp_cache_file, monkeypatch):
        """Test that get_gender_cache_stats returns correct info."""
        from joshirank import queries

        original_cache = queries._gender_cache
        test_cache = GenderCache(temp_cache_file)
        monkeypatch.setattr(queries, "_gender_cache", test_cache)

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
            monkeypatch.setattr(queries, "_gender_cache", original_cache)

    def test_get_gender_cache_stats_no_file(self, temp_cache_file, monkeypatch):
        """Test stats when cache file doesn't exist."""
        from joshirank import queries

        original_cache = queries._gender_cache
        test_cache = GenderCache(temp_cache_file)
        monkeypatch.setattr(queries, "_gender_cache", test_cache)

        try:
            # Don't save, so file doesn't exist
            test_cache.set(100, 0.95)

            stats = get_gender_cache_stats()

            assert stats["total_entries"] == 1
            assert stats["exists"] is False

        finally:
            monkeypatch.setattr(queries, "_gender_cache", original_cache)


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
