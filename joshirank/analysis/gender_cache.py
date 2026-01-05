"""Gender prediction caching for wrestler analysis.

Provides persistent SQLite-based caching for gender predictions to avoid expensive
recalculation across scrape runs. Cache entries expire after a short time period
as predictions improve with more data.
"""

import pathlib
import sqlite3
import time


class GenderCache:
    """Persistent cache for gender predictions using SQLite for efficient updates.

    Uses SQLite instead of JSON to allow:
    - Single-record updates without rewriting entire file
    - Better concurrent access
    - Efficient queries for stale entries
    - Indexes for fast lookups

    Schema:
        CREATE TABLE gender_predictions (
            wrestler_id INTEGER PRIMARY KEY,
            confidence REAL NOT NULL,
            timestamp REAL NOT NULL,
            version INTEGER NOT NULL
        )

    Staleness policy: Recalculate if cached prediction is >2 hours old
    (kept short as calculation improves with more data)
    """

    CACHE_VERSION = 1
    STALENESS_HOURS = 2  # keep very short, as the calculation improves with more data

    def __init__(self, cache_path: pathlib.Path | None = None):
        if cache_path is None:
            cache_path = pathlib.Path("data/gender_predictions_cache.db")
        self.cache_path = cache_path
        self._conn = None
        self._initialize_db()
        self._migrate_from_json_if_needed()

    def _initialize_db(self):
        """Initialize SQLite database and create table if needed."""
        # Ensure directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self.cache_path))
        self._conn.row_factory = sqlite3.Row

        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gender_predictions (
                wrestler_id INTEGER PRIMARY KEY,
                confidence REAL NOT NULL,
                timestamp REAL NOT NULL,
                version INTEGER NOT NULL
            )
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON gender_predictions(timestamp)
        """
        )
        self._conn.commit()

    def _migrate_from_json_if_needed(self):
        """Migrate data from old JSON cache file if it exists."""
        json_path = self.cache_path.parent / "gender_predictions_cache.json"
        if not json_path.exists():
            return

        try:
            import json

            with open(json_path, "r") as f:
                data = json.load(f)

            # Import existing predictions into SQLite
            cursor = self._conn.cursor()
            for wid_str, entry in data.items():
                wrestler_id = int(wid_str)
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO gender_predictions 
                    (wrestler_id, confidence, timestamp, version)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        wrestler_id,
                        entry["confidence"],
                        entry["timestamp"],
                        entry.get("version", 1),
                    ),
                )
            self._conn.commit()

            # Rename old JSON file to .migrated
            json_path.rename(json_path.with_suffix(".json.migrated"))
            print(f"Migrated {len(data)} entries from JSON to SQLite gender cache")
        except Exception as e:
            print(f"Warning: Failed to migrate gender cache from JSON: {e}")

    def get(self, wrestler_id: int) -> float | None:
        """Get cached gender prediction for wrestler.

        Returns:
            Confidence score (0.0-1.0) if cached and fresh, None if stale/missing
        """
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT confidence, timestamp, version 
            FROM gender_predictions 
            WHERE wrestler_id = ?
        """,
            (wrestler_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        # Check version compatibility
        if row["version"] != self.CACHE_VERSION:
            return None

        # Check staleness
        age_hours = (time.time() - row["timestamp"]) / 3600
        if age_hours > self.STALENESS_HOURS:
            return None

        return row["confidence"]

    def set(self, wrestler_id: int, confidence: float):
        """Cache a gender prediction for a wrestler."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO gender_predictions 
            (wrestler_id, confidence, timestamp, version)
            VALUES (?, ?, ?, ?)
        """,
            (wrestler_id, confidence, time.time(), self.CACHE_VERSION),
        )
        self._conn.commit()

    def save(self):
        """Save cache to disk (for compatibility - commits happen on set())."""
        # SQLite auto-commits on each set(), but we commit here for safety
        if self._conn:
            self._conn.commit()

    def clear_stale(self) -> int:
        """Remove stale entries from cache.

        Returns:
            Number of entries removed
        """
        now = time.time()
        stale_threshold = now - (self.STALENESS_HOURS * 3600)

        cursor = self._conn.cursor()
        cursor.execute(
            """
            DELETE FROM gender_predictions 
            WHERE timestamp < ?
        """,
            (stale_threshold,),
        )
        removed = cursor.rowcount
        self._conn.commit()
        return removed

    def __len__(self) -> int:
        """Return the number of cached entries."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM gender_predictions")
        return cursor.fetchone()[0]

    def clear(self):
        """Clear all cached entries."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM gender_predictions")
        self._conn.commit()

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self):
        """Ensure connection is closed when object is destroyed."""
        self.close()


# Global cache instance
_gender_cache = GenderCache()


def clear_gender_cache():
    """Clear all cached gender predictions.

    Useful for forcing recalculation after database updates or for testing.
    """
    global _gender_cache
    _gender_cache.clear()
    _gender_cache.save()


def get_gender_cache_stats() -> dict:
    """Get statistics about the gender prediction cache.

    Returns:
        Dict with cache statistics:
        - total_entries: Number of cached predictions
        - cache_file: Path to cache file
        - exists: Whether cache file exists
    """
    return {
        "total_entries": len(_gender_cache),
        "cache_file": str(_gender_cache.cache_path),
        "exists": _gender_cache.cache_path.exists(),
    }
