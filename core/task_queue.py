from collections import deque
import threading
from typing import List, Optional, Set
from .concurrency import ReadWriteLock


class TaskQueue:
    def __init__(self, max_size: int = 200, history_limit: int = 10000):
        self._max_size = max_size
        self.queue: deque = deque(maxlen=self._max_size)
        self.history_limit = history_limit
        self.processed_history: Set[str] = set()

    @property
    def max_size(self) -> int:
        return self._max_size

    @max_size.setter
    def max_size(self, new_size: int) -> None:
        if new_size < 1:
            raise ValueError("Max size must be at least 1")
        
        # 重建队列，保存现有任务
        existing_tasks = list(self.queue)[:new_size]
        self._max_size = new_size
        self.queue = deque(existing_tasks, maxlen=self._max_size)

    def add(self, task: str) -> bool:
        if task in self.processed_history:
            return False
        if task in self.queue:
            return False
        if len(self.queue) >= self.max_size:
            return False
        self.queue.append(task)
        return True

    def batch_add(self, tasks: List[str]) -> int:
        added_count = 0
        for task in tasks:
            if self.add(task):
                added_count += 1
        return added_count

    def pop(self) -> Optional[str]:
        if not self.queue:
            return None
        task = self.queue.popleft()
        self.processed_history.add(task)
        self._cleanup_history()
        return task

    def _cleanup_history(self) -> None:
        if len(self.processed_history) > self.history_limit:
            old_tasks = list(self.processed_history)[:len(self.processed_history) // 2]
            for task in old_tasks:
                self.processed_history.discard(task)

    def peek(self) -> Optional[str]:
        if not self.queue:
            return None
        return self.queue[0]

    def is_empty(self) -> bool:
        return len(self.queue) == 0

    def is_full(self) -> bool:
        return len(self.queue) >= self.max_size

    def size(self) -> int:
        return len(self.queue)

    def get_all(self) -> List[str]:
        return list(self.queue)

    def clear(self) -> None:
        self.queue.clear()

    def clear_history(self) -> None:
        self.processed_history.clear()

    def is_processed(self, task: str) -> bool:
        return task in self.processed_history

    def get_history_size(self) -> int:
        return len(self.processed_history)

    def __repr__(self) -> str:
        return f"TaskQueue(size={len(self.queue)}, max={self.max_size}, processed={len(self.processed_history)})"


class ConcurrentTaskQueue(TaskQueue):
    """
    线程安全的任务队列
    
    使用简单的互斥锁进行保护，避免复杂的死锁问题
    """
    
    def __init__(self, max_size: int = 200, history_limit: int = 10000):
        super().__init__(max_size, history_limit)
        self._lock = threading.Lock()
    
    @property
    def max_size(self) -> int:
        with self._lock:
            return super().max_size
    
    @max_size.setter
    def max_size(self, new_size: int) -> None:
        with self._lock:
            self._max_size = new_size
            # 重建队列，保存现有任务
            existing_tasks = list(self.queue)[:new_size]
            self.queue = deque(existing_tasks, maxlen=self._max_size)
    
    def add(self, task: str) -> bool:
        with self._lock:
            if task in self.processed_history:
                return False
            if task in self.queue:
                return False
            if len(self.queue) >= self.max_size:
                return False
            self.queue.append(task)
            return True
    
    def batch_add(self, tasks: List[str]) -> int:
        added_count = 0
        with self._lock:
            for task in tasks:
                if task in self.processed_history:
                    continue
                if task in self.queue:
                    continue
                if len(self.queue) >= self.max_size:
                    continue
                self.queue.append(task)
                added_count += 1
        return added_count
    
    def pop(self) -> Optional[str]:
        with self._lock:
            if not self.queue:
                return None
            task = self.queue.popleft()
            self.processed_history.add(task)
            self._cleanup_history()
            return task
    
    def peek(self) -> Optional[str]:
        with self._lock:
            return super().peek()
    
    def is_empty(self) -> bool:
        with self._lock:
            return super().is_empty()
    
    def is_full(self) -> bool:
        with self._lock:
            return super().is_full()
    
    def size(self) -> int:
        with self._lock:
            return super().size()
    
    def get_all(self) -> List[str]:
        with self._lock:
            return super().get_all()
    
    def clear(self) -> None:
        with self._lock:
            super().clear()
    
    def clear_history(self) -> None:
        with self._lock:
            super().clear_history()
    
    def is_processed(self, task: str) -> bool:
        with self._lock:
            return super().is_processed(task)
    
    def get_history_size(self) -> int:
        with self._lock:
            return super().get_history_size()
    
    def __repr__(self) -> str:
        with self._lock:
            return f"ConcurrentTaskQueue(size={len(self.queue)}, max={self.max_size}, processed={len(self.processed_history)})"
