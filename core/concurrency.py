import threading
from typing import Generic, TypeVar, Dict, List, Optional, Any

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')


class ReadWriteLock:
    """
    读写锁实现 - 允许多个读者同时读，但写操作是独占的
    
    读锁与读锁不互斥，读锁与写锁互斥，写锁与写锁互斥
    """
    
    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0
    
    def acquire_read(self):
        """获取读锁"""
        with self._read_ready:
            self._readers += 1
    
    def release_read(self):
        """释放读锁"""
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()
    
    def acquire_write(self):
        """获取写锁"""
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()
    
    def release_write(self):
        """释放写锁"""
        self._read_ready.release()
    
    def __enter__(self):
        raise RuntimeError("Use 'read_lock()' or 'write_lock()' context managers")
    
    def read_lock(self):
        """读锁上下文管理器"""
        class ReadContextManager:
            def __init__(self, rwlock):
                self.rwlock = rwlock
            
            def __enter__(self):
                self.rwlock.acquire_read()
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.rwlock.release_read()
                return False
        
        return ReadContextManager(self)
    
    def write_lock(self):
        """写锁上下文管理器"""
        class WriteContextManager:
            def __init__(self, rwlock):
                self.rwlock = rwlock
            
            def __enter__(self):
                self.rwlock.acquire_write()
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.rwlock.release_write()
                return False
        
        return WriteContextManager(self)


class ThreadSafeDict(Generic[K, V]):
    """
    线程安全的字典包装器
    使用读写锁优化读多写少的场景
    """
    
    def __init__(self):
        self._data: Dict[K, V] = {}
        self._lock = ReadWriteLock()
    
    def __getitem__(self, key: K) -> V:
        with self._lock.read_lock():
            return self._data[key]
    
    def __setitem__(self, key: K, value: V):
        with self._lock.write_lock():
            self._data[key] = value
    
    def __delitem__(self, key: K):
        with self._lock.write_lock():
            del self._data[key]
    
    def __contains__(self, key: K) -> bool:
        with self._lock.read_lock():
            return key in self._data
    
    def __len__(self) -> int:
        with self._lock.read_lock():
            return len(self._data)
    
    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        with self._lock.read_lock():
            return self._data.get(key, default)
    
    def setdefault(self, key: K, default: V) -> V:
        with self._lock.write_lock():
            return self._data.setdefault(key, default)
    
    def pop(self, key: K, default: Optional[V] = None) -> Optional[V]:
        with self._lock.write_lock():
            if key in self._data:
                return self._data.pop(key)
            return default
    
    def clear(self):
        with self._lock.write_lock():
            self._data.clear()
    
    def keys(self):
        with self._lock.read_lock():
            return list(self._data.keys())
    
    def values(self):
        with self._lock.read_lock():
            return list(self._data.values())
    
    def items(self):
        with self._lock.read_lock():
            return list(self._data.items())
    
    def update(self, other: Dict[K, V]):
        with self._lock.write_lock():
            self._data.update(other)
    
    def copy(self) -> Dict[K, V]:
        with self._lock.read_lock():
            return self._data.copy()


class ThreadSafeList(Generic[T]):
    """
    线程安全的列表包装器
    使用读写锁优化读多写少的场景
    """
    
    def __init__(self):
        self._data: List[T] = []
        self._lock = ReadWriteLock()
    
    def __getitem__(self, index: int) -> T:
        with self._lock.read_lock():
            return self._data[index]
    
    def __setitem__(self, index: int, value: T):
        with self._lock.write_lock():
            self._data[index] = value
    
    def __delitem__(self, index: int):
        with self._lock.write_lock():
            del self._data[index]
    
    def __len__(self) -> int:
        with self._lock.read_lock():
            return len(self._data)
    
    def __contains__(self, item: T) -> bool:
        with self._lock.read_lock():
            return item in self._data
    
    def append(self, item: T):
        with self._lock.write_lock():
            self._data.append(item)
    
    def extend(self, items: List[T]):
        with self._lock.write_lock():
            self._data.extend(items)
    
    def insert(self, index: int, item: T):
        with self._lock.write_lock():
            self._data.insert(index, item)
    
    def pop(self, index: int = -1) -> T:
        with self._lock.write_lock():
            return self._data.pop(index)
    
    def remove(self, item: T):
        with self._lock.write_lock():
            self._data.remove(item)
    
    def clear(self):
        with self._lock.write_lock():
            self._data.clear()
    
    def index(self, item: T, start: int = 0, end: Optional[int] = None) -> int:
        with self._lock.read_lock():
            if end is None:
                return self._data.index(item, start)
            return self._data.index(item, start, end)
    
    def count(self, item: T) -> int:
        with self._lock.read_lock():
            return self._data.count(item)
    
    def copy(self) -> List[T]:
        with self._lock.read_lock():
            return self._data.copy()
    
    def sort(self, key=None, reverse: bool = False):
        with self._lock.write_lock():
            self._data.sort(key=key, reverse=reverse)
    
    def reverse(self):
        with self._lock.write_lock():
            self._data.reverse()


class AtomicCounter:
    """
    原子计数器
    线程安全的计数器实现
    """
    
    def __init__(self, initial: int = 0):
        self._value = initial
        self._lock = threading.Lock()
    
    @property
    def value(self) -> int:
        with self._lock:
            return self._value
    
    def increment(self, delta: int = 1) -> int:
        """原子增加并返回新值"""
        with self._lock:
            self._value += delta
            return self._value
    
    def decrement(self, delta: int = 1) -> int:
        """原子减少并返回新值"""
        with self._lock:
            self._value -= delta
            return self._value
    
    def get_and_increment(self, delta: int = 1) -> int:
        """获取旧值并原子增加"""
        with self._lock:
            old = self._value
            self._value += delta
            return old
    
    def get_and_decrement(self, delta: int = 1) -> int:
        """获取旧值并原子减少"""
        with self._lock:
            old = self._value
            self._value -= delta
            return old
    
    def compare_and_set(self, expected: int, new_value: int) -> bool:
        """
        比较并设置
        
        如果当前值等于 expected，则设置为 new_value 并返回 True
        否则返回 False
        """
        with self._lock:
            if self._value == expected:
                self._value = new_value
                return True
            return False
    
    def reset(self, value: int = 0):
        """重置计数器"""
        with self._lock:
            self._value = value
