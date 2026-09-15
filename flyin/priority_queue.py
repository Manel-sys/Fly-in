from typing import Any


class MinPriorityQueue:
    """A binary min-heap of ``(priority, payload)`` entries.

    Entries are always popped in ascending priority order. When two
    entries share the same priority, ties are broken by comparing their
    payloads directly (via Python's normal tuple/value comparison), so
    payloads pushed onto the same queue instance should be of a single,
    mutually-comparable shape.
    """

    def __init__(self, items: list[tuple[int | float, Any]]) -> None:
        """Build a heap from an initial list of (priority, payload)
        entries.

        Args:
            items: The initial entries to heapify. May be empty.
        """
        self._heap: list[tuple[int | float, Any]] = items
        self._heapify()

    def _heapify(self) -> None:
        """Establish the heap invariant over the initial ``_heap`` list
        in-place, in linear time."""

        last_parent: int = (len(self._heap) - 2) // 2

        while last_parent >= 0:
            self._sift_down(last_parent)
            last_parent -= 1

    def _sift_up(self, index: int) -> None:
        """Move the entry at ``index`` up toward the root until the heap
        invariant holds, swapping with its parent while it compares
        smaller."""

        while index > 0:
            parent: int = (index - 1) // 2

            if self._heap[index] >= self._heap[parent]:
                break

            self._heap[index], self._heap[parent] = (self._heap[parent],
                                                     self._heap[index]
                                                     )

            index = parent

    def _sift_down(self, index: int) -> None:
        """Move the entry at ``index`` down toward the leaves until the
        heap invariant holds, swapping with its smallest child each
        step."""

        size: int = len(self._heap)

        while True:
            left: int = 2 * index + 1
            right: int = 2 * index + 2

            smallest: int = index

            if left < size and self._heap[left] < self._heap[smallest]:
                smallest = left

            if right < size and self._heap[right] < self._heap[smallest]:
                smallest = right

            if smallest == index:
                break

            self._heap[index], self._heap[smallest] = (self._heap[smallest],
                                                       self._heap[index]
                                                       )
            index = smallest

    def is_empty(self) -> bool:
        """Return ``True`` if the queue currently holds no entries."""
        return len(self._heap) == 0

    def push(self, priority: int | float, payload: Any) -> None:
        """Insert a new entry into the queue.

        Args:
            priority: The value entries are ordered by; lower pops
                first.
            payload: The associated data to retrieve alongside the
                priority when this entry is popped.
        """

        self._heap.append((priority, payload))
        self._sift_up(len(self._heap) - 1)

    def pop(self) -> tuple[int | float, Any]:
        """Remove and return the entry with the smallest priority.

        Returns:
            The (priority, payload) tuple that was at the front of the
            queue.

        Raises:
            IndexError: If the queue is empty.
        """

        if not self._heap:
            raise IndexError("Trying to pop from empty priority queue")

        if len(self._heap) == 1:
            return self._heap.pop()

        smallest = self._heap[0]

        self._heap[0] = self._heap.pop()
        self._sift_down(0)

        return smallest
