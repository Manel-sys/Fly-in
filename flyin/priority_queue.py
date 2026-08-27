class MinPriorityQueue:
    def __init__(self, items: list[tuple[int, str]]) -> None:
        self._heap: list[tuple[int, str]] = items
        self._heapify()

    def _heapify(self) -> None:
        last_parent: int = (len(self._heap) - 2) // 2

        while last_parent >= 0:
            self._sift_down(last_parent)
            last_parent -= 1

    def _sift_up(self, index: int) -> None:
        while index > 0:
            parent: int = (index - 1) // 2

            if self._heap[index] >= self._heap[parent]:
                break

            self._heap[index], self._heap[parent] = (self._heap[parent],
                                                     self._heap[index]
                                                     )

            index = parent

    def _sift_down(self, index: int) -> None:
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
        return len(self._heap) == 0

    def push(self, distance: int, zone: str) -> None:
        self._heap.append((distance, zone))
        self._sift_up(len(self._heap) - 1)

    def pop(self) -> tuple[int, str]:
        if not self._heap:
            raise IndexError("Trying to pop from empty priority queue")

        if len(self._heap) == 1:
            return self._heap.pop()

        smallest = self._heap[0]

        self._heap[0] = self._heap.pop()
        self._sift_down(0)

        return smallest
