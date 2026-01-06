"""Database wrapper providing read-only default with temporary write contexts.

Read-Only/Read-Write Pattern
=============================

This module implements a safety-first database access pattern where:

1. **Default is read-only**: All instances open with a persistent read-only SQLite connection
2. **Writes require explicit context**: Write operations only work within a `writable()` context
3. **Automatic cleanup**: Write connections are automatically closed after the context exits
4. **Single-writer guarantee**: Only one write context can be active at a time per instance

Why This Design?
----------------

- **Prevents accidental writes**: Most operations are read-only; explicit context makes writes intentional
- **Avoids lock conflicts**: Read-only connections can coexist; write contexts are clearly marked
- **Safe defaults**: Forgetting to close a read-only connection won't corrupt data
- **Performance**: Persistent read-only connection avoids repeated open/close overhead

Usage Pattern
-------------

Reading data (default, no special setup needed):
    ```python
    from joshirank.joshidb import wrestler_db

    # These work immediately - database is always open read-only
    wrestler = wrestler_db.get_wrestler(wrestler_id)
    name = wrestler_db.get_name(wrestler_id)
    matches = wrestler_db.get_matches(wrestler_id, year=2025)
    ```

Writing data (requires context manager):
    ```python
    from joshirank.joshidb import wrestler_db

    # Open temporary write connection
    with wrestler_db.writable():
        wrestler_db.save_profile_for_wrestler(wrestler_id, profile_data)
        wrestler_db.update_wrestler_from_profile(wrestler_id)
        # All writes committed automatically on context exit
    # Write connection closed here
    ```

Implementation Details
----------------------

Two connection attributes:
- `sqldb_ro`: Always-open read-only SQLite connection (persistent)
- `sqldb_rw`: Temporary read-write connection (only exists in writable() context)

Helper methods route to appropriate connection:
- `_select_*` methods: Use sqldb_ro (read-only)
- `_execute_*` methods: Use sqldb_rw (read-write, raises error if not in context)
- `_rw_cursor()`: Returns cursor from sqldb_rw
- `_commit()`: Commits on sqldb_rw

Error Handling:
- Accessing sqldb_rw outside context raises RuntimeError
- Nested writable() contexts raise RuntimeError
- Write methods called outside context will fail with clear error message

Multi-Process Safety:
---------------------

SQLite locking:
- Multiple read-only connections are safe (they share a read lock)
- Only one write connection allowed at a time (exclusive write lock)
- Write operations will block/fail if another process holds write lock

**Critical**: Never run multiple writable() contexts in different processes simultaneously.
The scraper's session limits help prevent this, but be careful with parallel scripts.

Backwards Compatibility
-----------------------

Legacy code may use deprecated `reopen_rw()` function in joshidb.py:
    ```python
    # OLD (deprecated but still works)
    from joshirank.joshidb import reopen_rw
    with reopen_rw():
        wrestler_db.save_profile_for_wrestler(...)

    # NEW (preferred)
    with wrestler_db.writable():
        wrestler_db.save_profile_for_wrestler(...)
    ```

Both work identically - `reopen_rw()` is just a wrapper around `wrestler_db.writable()`.
"""

import pathlib
import sqlite3
from contextlib import contextmanager


class DBWrapper:
    sqldb_ro: sqlite3.Connection
    __sqldb_rw: None | sqlite3.Connection
    path: pathlib.Path
    _batch_mode: bool

    def __init__(self, path: pathlib.Path):
        self.path = path
        db_file = self.path.with_suffix(".sqlite3")
        # Ensure database file exists so read-only open doesn't fail in tests
        if not db_file.exists():
            tmp_conn = sqlite3.connect(str(db_file))
            tmp_conn.close()
        # Always-open read-only connection
        self.sqldb_ro = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        self.__sqldb_rw = None  # Temporary write connection, only set in context
        self._batch_mode = False

    @property
    def sqldb_rw(self) -> sqlite3.Connection:
        """Return the read/write connection, or raise if not in writable context."""
        if self.__sqldb_rw is None:
            raise RuntimeError("Not in writable context!")
        return self.__sqldb_rw

    @contextmanager
    def writable(self):
        """Context manager for temporarily enabling write access on this instance.

        Opens a new write connection (self.sqldb_rw) for the duration of the context.
        All write methods use this connection if present.
        Commits all changes automatically on successful exit; rolls back on exception.
        """
        if self.__sqldb_rw is not None:
            raise RuntimeError("Already in writable context!")
        self.__sqldb_rw = sqlite3.connect(str(self.path.with_suffix(".sqlite3")))
        self._batch_mode = True

        try:
            yield self
            # Successful context exit: commit once for the whole batch
            self.__sqldb_rw.commit()
        except Exception:
            # Error within context: rollback changes
            self.__sqldb_rw.rollback()
            raise
        finally:
            self.__sqldb_rw.close()
            self.__sqldb_rw = None
            self._batch_mode = False

    def _select_and_fetchone(self, query: str, params: tuple) -> tuple | None:
        """Helper method to execute a select query and fetch one result."""
        cursor = self.sqldb_ro.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        cursor.close()
        return row

    def _select_and_fetchone_dict(self, query: str, params: tuple) -> dict | None:
        """Helper method to execute a select query and fetch one result as a dict."""
        cursor = self.sqldb_ro.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        if row:
            col_names = [description[0] for description in cursor.description]
            d = dict(zip(col_names, row))
            cursor.close()
            return d
        else:
            cursor.close()
            return None

    def _select_and_fetchall(self, query: str, params: tuple) -> list[tuple]:
        """Helper method to execute a select query and fetch all results."""
        cursor = self.sqldb_ro.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def _execute_and_commit(self, query: str, params: tuple) -> int:
        """Helper method to execute a query and commit changes."""
        rowcount = self._execute(query, params)

        # In batch mode, defer commit to context exit
        if not self._batch_mode:
            self.sqldb_rw.commit()

        # return the status of the execution if needed
        return rowcount

    def _execute(self, query: str, params: tuple) -> int:
        """Helper method to execute a read/write query without committing changes."""
        cursor = self.sqldb_rw.cursor()
        cursor.execute(query, params)
        rowcount = cursor.rowcount
        cursor.close()

        # return the status of the execution if needed
        return rowcount

    def _rw_cursor(self) -> sqlite3.Cursor:
        """Create and return a read/write cursor"""
        return self.sqldb_rw.cursor()

    def _commit(self):
        """Commit on the r/w connection."""
        self.sqldb_rw.commit()
