import heapq
from dataclasses import dataclass, field
from typing import Optional


@dataclass(order=True)
class WorkItem:
    priority: int = field(compare=True)
    object_id: int = field(
        compare=False
    )  # Wrestler ID or Promotion ID depending on operation
    operation: str = field(compare=False)
    year: Optional[int] = field(default=None, compare=False)
    force: bool = field(default=False, compare=False)


class WorkQueue:
    """In-memory priority queue derived from database state."""

    def __init__(self):
        self._queue: list[WorkItem] = []
        self._seen: set[tuple] = set()  # Deduplication

    def enqueue(self, item: WorkItem):
        """Add item if not already queued.

        Automatically filters out sentinel value object_id = -1.
        """
        # Skip sentinel value -1 (used for missing wrestlers in match data)
        if item.object_id == -1:
            return

        key = (item.object_id, item.operation, item.year)

        if key not in self._seen:
            heapq.heappush(self._queue, item)
            self._seen.add(key)

    def dequeue(self) -> Optional[WorkItem]:
        """Get highest priority item."""
        if self._queue:
            item = heapq.heappop(self._queue)
            return item
        return None

    def __len__(self):
        return len(self._queue)
