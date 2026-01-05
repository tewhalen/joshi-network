"""Unit tests for WorkQueue priority queue."""

from joshirank.scrape.workqueue import WorkItem, WorkQueue


def test_priority_ordering():
    """Test that WorkQueue dequeues items in priority order (lowest first)."""
    queue = WorkQueue()

    # Add items in random priority order
    queue.enqueue(WorkItem(priority=30, object_id=1, operation="test"))
    queue.enqueue(WorkItem(priority=1, object_id=2, operation="test"))
    queue.enqueue(WorkItem(priority=50, object_id=3, operation="test"))
    queue.enqueue(WorkItem(priority=10, object_id=4, operation="test"))
    queue.enqueue(WorkItem(priority=5, object_id=5, operation="test"))

    # Dequeue and verify order (should be ascending: 1, 5, 10, 30, 50)
    expected_priorities = [1, 5, 10, 30, 50]
    actual_priorities = []

    while len(queue) > 0:
        item = queue.dequeue()
        actual_priorities.append(item.priority)

    assert actual_priorities == expected_priorities


def test_deduplication():
    """Test that duplicate (wrestler_id, operation, year) tuples are filtered."""
    queue = WorkQueue()

    # Add same wrestler+operation twice with different priorities
    queue.enqueue(WorkItem(priority=10, object_id=100, operation="refresh_profile"))
    queue.enqueue(
        WorkItem(priority=5, object_id=100, operation="refresh_profile")
    )  # Duplicate - should be ignored

    # Add same wrestler with different operation
    queue.enqueue(
        WorkItem(priority=10, object_id=100, operation="refresh_matches", year=2025)
    )

    # Should only have 2 items (first profile + matches)
    assert len(queue) == 2

    # Verify the items are correct
    item1 = queue.dequeue()
    assert item1.object_id == 100
    assert item1.operation == "refresh_profile"
    assert item1.priority == 10  # First one wins, not the lower priority duplicate

    item2 = queue.dequeue()
    assert item2.object_id == 100
    assert item2.operation == "refresh_matches"
    assert item2.year == 2025


def test_sentinel_filtering():
    """Test that wrestler_id=-1 (sentinel value) is filtered out."""
    queue = WorkQueue()

    # Try to add sentinel value
    queue.enqueue(WorkItem(priority=1, object_id=-1, operation="test"))

    # Add valid item
    queue.enqueue(WorkItem(priority=1, object_id=200, operation="test"))

    # Should only have 1 item (sentinel filtered out)
    assert len(queue) == 1

    item = queue.dequeue()
    assert item.object_id == 200


def test_empty_queue():
    """Test dequeue on empty queue returns None."""
    queue = WorkQueue()

    assert len(queue) == 0
    assert queue.dequeue() is None


def test_workitem_with_year():
    """Test WorkItem with optional year parameter."""
    queue = WorkQueue()

    queue.enqueue(
        WorkItem(priority=10, object_id=1, operation="refresh_matches", year=2025)
    )
    queue.enqueue(
        WorkItem(priority=10, object_id=1, operation="refresh_matches", year=2024)
    )

    # Different years should be treated as different items
    assert len(queue) == 2
