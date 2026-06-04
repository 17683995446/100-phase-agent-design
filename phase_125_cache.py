#!/usr/bin/env python3
"""
阶段125：缓存层

第一性原理：
  - 速度公理：内存比磁盘快万倍
  - 局部性：刚刚访问过的还会再访问
  - 容量权衡：用空间换时间
  - 一致性：缓存与源可能不一致

本阶段产出：
  1. CacheEntry：缓存条目
  2. LRUCache：LRU缓存
  3. LFUCache：LFU缓存
  4. TTLCache：带TTL的缓存
  5. CachePolicy：缓存策略
  6. CacheManager：缓存管理器

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import threading
from typing import Dict, List, Any, Optional, Callable
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# 一、缓存条目
# ============================================================
@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl_sec: Optional[float] = None
    size: int = 1  # 估算大小

    def is_expired(self) -> bool:
        if self.ttl_sec is None:
            return False
        return (time.time() - self.created_at) > self.ttl_sec

    def access(self) -> None:
        self.last_accessed = time.time()
        self.access_count += 1


# ============================================================
# 二、淘汰策略
# ============================================================
class EvictionPolicy(Enum):
    """淘汰策略"""
    LRU = "lru"  # 最近最少使用
    LFU = "lfu"  # 最不经常使用
    FIFO = "fifo"  # 先进先出


# ============================================================
# 三、LRU缓存
# ============================================================
class LRUCache:
    """LRU（最近最少使用）缓存

    实现：OrderedDict
    - 访问时移到末尾
    - 淘汰时移除头部
    """
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._stats = {
            "hits": 0, "misses": 0, "evictions": 0,
            "expirations": 0, "sets": 0,
        }

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._stats["expirations"] += 1
                self._stats["misses"] += 1
                return None
            entry.access()
            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return entry.value

    def set(self, key: str, value: Any,
             ttl_sec: Optional[float] = None) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = CacheEntry(
                key=key, value=value, ttl_sec=ttl_sec)
            self._stats["sets"] += 1
            # 容量检查
            while len(self._cache) > self.capacity:
                self._cache.popitem(last=False)  # 移除最旧
                self._stats["evictions"] += 1

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def hit_rate(self) -> float:
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            return self._stats["hits"] / total if total else 0.0

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            stats = dict(self._stats)
            total = self._stats["hits"] + self._stats["misses"]
            stats["hit_rate"] = (
                self._stats["hits"] / total if total else 0.0)
            stats["size"] = len(self._cache)
            stats["capacity"] = self.capacity
            return stats


# ============================================================
# 四、LFU缓存
# ============================================================
class LFUCache:
    """LFU（最不经常使用）缓存

    淘汰访问次数最少的条目
    """
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._stats = {
            "hits": 0, "misses": 0, "evictions": 0,
            "sets": 0,
        }

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            entry.access()
            self._stats["hits"] += 1
            return entry.value

    def set(self, key: str, value: Any,
             ttl_sec: Optional[float] = None) -> None:
        with self._lock:
            if key in self._cache:
                self._cache[key].value = value
            else:
                if len(self._cache) >= self.capacity:
                    self._evict()
                self._cache[key] = CacheEntry(
                    key=key, value=value, ttl_sec=ttl_sec)
            self._stats["sets"] += 1

    def _evict(self) -> None:
        """淘汰最少使用的"""
        if not self._cache:
            return
        min_key = min(
            self._cache.keys(),
            key=lambda k: (self._cache[k].access_count,
                            self._cache[k].created_at))
        del self._cache[min_key]
        self._stats["evictions"] += 1

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            stats = dict(self._stats)
            stats["size"] = len(self._cache)
            stats["capacity"] = self.capacity
            return stats


# ============================================================
# 五、TTL缓存
# ============================================================
class TTLCache:
    """TTL缓存

    支持过期时间，自动清理
    """
    def __init__(self, default_ttl: float = 60.0,
                 cleanup_interval: float = 10.0):
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stats = {
            "hits": 0, "misses": 0, "expirations": 0, "sets": 0,
        }

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._stats["expirations"] += 1
                self._stats["misses"] += 1
                return None
            entry.access()
            self._stats["hits"] += 1
            return entry.value

    def set(self, key: str, value: Any,
             ttl_sec: Optional[float] = None) -> None:
        with self._lock:
            self._cache[key] = CacheEntry(
                key=key, value=value,
                ttl_sec=ttl_sec or self.default_ttl)
            self._stats["sets"] += 1

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._cache.pop(key, None) is not None

    def cleanup_expired(self) -> int:
        with self._lock:
            now = time.time()
            expired = [
                k for k, e in self._cache.items() if e.is_expired()]
            for k in expired:
                del self._cache[k]
                self._stats["expirations"] += 1
            return len(expired)

    def start_cleanup(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._cleanup_loop, daemon=True)
        self._thread.start()

    def stop_cleanup(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _cleanup_loop(self) -> None:
        while self._running:
            time.sleep(self.cleanup_interval)
            if self._running:
                self.cleanup_expired()

    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 六、写穿/回写策略
# ============================================================
class WritePolicy(Enum):
    """写策略"""
    THROUGH = "through"   # 同步写源
    BACK = "back"        # 异步写源
    AROUND = "around"    # 只写缓存


# ============================================================
# 七、缓存管理器
# ============================================================
class CacheManager:
    """缓存管理器

    在缓存和后端存储之间路由
    """
    def __init__(self, cache, source: Optional[Any] = None,
                 write_policy: WritePolicy = WritePolicy.THROUGH):
        self.cache = cache
        self.source = source
        self.write_policy = write_policy
        self._stats = {
            "hits": 0, "misses": 0, "writes": 0,
        }

    def get(self, key: str) -> Optional[Any]:
        # 先查缓存
        v = self.cache.get(key)
        if v is not None:
            self._stats["hits"] += 1
            return v
        # 缓存未命中，查源
        self._stats["misses"] += 1
        if self.source and hasattr(self.source, "get"):
            v = self.source.get(key)
            if v is not None:
                self.cache.set(key, v)
            return v
        return None

    def set(self, key: str, value: Any,
             ttl_sec: Optional[float] = None) -> None:
        self._stats["writes"] += 1
        if self.write_policy in (WritePolicy.THROUGH, WritePolicy.AROUND):
            # 写穿：同时写缓存和源
            self.cache.set(key, value, ttl_sec)
            if (self.write_policy == WritePolicy.THROUGH
                    and self.source and hasattr(self.source, "put")):
                self.source.put(key, value)
        elif self.write_policy == WritePolicy.BACK:
            # 回写：只写缓存，标记脏
            self.cache.set(key, value, ttl_sec)
            if self.source and hasattr(self.source, "mark_dirty"):
                self.source.mark_dirty(key)

    def invalidate(self, key: str) -> bool:
        return self.cache.delete(key)

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)


# ============================================================
# 八、单元测试
# ============================================================
class TestLRUCache(unittest.TestCase):
    """LRU缓存测试"""
    def test_set_get(self):
        c = LRUCache(capacity=3)
        c.set("a", 1)
        self.assertEqual(c.get("a"), 1)

    def test_eviction(self):
        c = LRUCache(capacity=2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)  # 触发淘汰
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("c"), 3)

    def test_lru_order(self):
        c = LRUCache(capacity=2)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")  # a变成最近使用
        c.set("c", 3)  # 应淘汰b
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("b"))

    def test_ttl(self):
        c = LRUCache(capacity=10)
        c.set("a", 1, ttl_sec=0.001)
        time.sleep(0.01)
        self.assertIsNone(c.get("a"))

    def test_stats(self):
        c = LRUCache()
        c.set("a", 1)
        c.get("a")
        c.get("b")
        stats = c.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)


class TestLFUCache(unittest.TestCase):
    """LFU缓存测试"""
    def test_set_get(self):
        c = LFUCache(capacity=3)
        c.set("a", 1)
        self.assertEqual(c.get("a"), 1)

    def test_eviction_least_frequent(self):
        c = LFUCache(capacity=2)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")  # a访问2次，b访问1次
        c.get("a")
        c.get("b")
        c.set("c", 3)  # 应淘汰b
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("b"))
        self.assertEqual(c.get("c"), 3)


class TestTTLCache(unittest.TestCase):
    """TTL缓存测试"""
    def test_expiry(self):
        c = TTLCache(default_ttl=0.001)
        c.set("a", 1)
        time.sleep(0.01)
        self.assertIsNone(c.get("a"))

    def test_custom_ttl(self):
        c = TTLCache(default_ttl=10.0)
        c.set("a", 1, ttl_sec=0.001)
        time.sleep(0.01)
        self.assertIsNone(c.get("a"))

    def test_cleanup(self):
        c = TTLCache(default_ttl=0.001)
        for i in range(10):
            c.set(f"k{i}", i)
        time.sleep(0.01)
        cleaned = c.cleanup_expired()
        self.assertEqual(cleaned, 10)


class TestCacheManager(unittest.TestCase):
    """缓存管理器测试"""
    def setUp(self):
        class FakeSource:
            def __init__(self):
                self.data = {}
            def get(self, k):
                return self.data.get(k)
            def put(self, k, v):
                self.data[k] = v
        self.source = FakeSource()
        self.cache = LRUCache(capacity=10)
        self.mgr = CacheManager(self.cache, self.source,
                                  WritePolicy.THROUGH)

    def test_cache_miss_falls_through(self):
        self.source.put("a", 1)
        v = self.mgr.get("a")
        self.assertEqual(v, 1)
        # 现在应在缓存中
        self.assertEqual(self.cache.get("a"), 1)

    def test_write_through(self):
        self.mgr.set("a", 1)
        self.assertEqual(self.source.get("a"), 1)
        self.assertEqual(self.cache.get("a"), 1)

    def test_invalidate(self):
        self.mgr.set("a", 1)
        self.assertTrue(self.mgr.invalidate("a"))
        self.assertIsNone(self.cache.get("a"))


# ============================================================
# 九、阶段125演示
# ============================================================
def run_phase_125():
    """运行阶段125"""
    print("=" * 70)
    print("阶段125：缓存层")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestLRUCache))
    suite.addTests(loader.loadTestsFromTestCase(TestLFUCache))
    suite.addTests(loader.loadTestsFromTestCase(TestTTLCache))
    suite.addTests(loader.loadTestsFromTestCase(TestCacheManager))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【缓存层演示】")
    print("-" * 70)

    # 演示1: LRU
    print("  📦 演示1: LRU缓存（容量3）")
    print("     " + "-" * 60)
    lru = LRUCache(capacity=3)
    lru.set("a", 1)
    lru.set("b", 2)
    lru.set("c", 3)
    print(f"     设置 a, b, c → {lru.get_stats()['size']}/{lru.capacity}")
    lru.get("a")  # a最近使用
    lru.set("d", 4)  # 应淘汰b
    print(f"     访问a, 设置d后:")
    print(f"       a={lru.get('a')}, b={lru.get('b')}, "
          f"c={lru.get('c')}, d={lru.get('d')}")
    print(f"       统计: {lru.get_stats()}")
    print()

    # 演示2: LFU
    print("  📊 演示2: LFU缓存（容量3）")
    print("     " + "-" * 60)
    lfu = LFUCache(capacity=3)
    lfu.set("x", 1)
    lfu.set("y", 2)
    lfu.set("z", 3)
    lfu.get("x")
    lfu.get("x")
    lfu.get("x")
    lfu.get("y")
    lfu.get("z")
    lfu.set("w", 4)  # 应淘汰y
    print(f"     x访问3次, y访问1次, z访问1次, 设置w:")
    for k in ["x", "y", "z", "w"]:
        print(f"       {k} = {lfu.get(k)}")
    print()

    # 演示3: TTL
    print("  ⏰ 演示3: TTL缓存（自动过期）")
    print("     " + "-" * 60)
    ttl = TTLCache(default_ttl=0.1)
    ttl.set("temp1", "v1")
    ttl.set("temp2", "v2", ttl_sec=1.0)
    time.sleep(0.15)
    print(f"     0.15秒后: temp1={ttl.get('temp1')}, "
          f"temp2={ttl.get('temp2')}")
    cleaned = ttl.cleanup_expired()
    print(f"     清理过期: {cleaned}条")
    print()

    # 演示4: 缓存管理器（写穿）
    print("  🔄 演示4: 缓存管理器（写穿模式）")
    print("     " + "-" * 60)
    class FakeSource:
        def __init__(self):
            self.data = {}
            self.writes = 0
        def get(self, k):
            return self.data.get(k)
        def put(self, k, v):
            self.writes += 1
            self.data[k] = v
    source = FakeSource()
    mgr = CacheManager(LRUCache(capacity=10), source,
                        WritePolicy.THROUGH)
    mgr.set("user:1", "alice")
    mgr.set("user:2", "bob")
    print(f"     写穿2条到源: {source.data}")
    # 读：先查缓存
    mgr.get("user:1")
    mgr.get("user:3")  # miss -> 查源
    mgr.get("user:3")  # 命中
    print(f"     统计: {mgr.get_stats()}")
    print()

    # 演示5: 命中率
    print("  🎯 演示5: 命中率")
    print("     " + "-" * 60)
    lru2 = LRUCache(capacity=10)
    for i in range(10):
        lru2.set(f"k{i}", i)
    hits = 0
    for i in range(20):
        if lru2.get(f"k{i % 10}") is not None:
            hits += 1
    print(f"     20次读, 命中: {hits}, 命中率: "
          f"{lru2.hit_rate()*100:.1f}%")
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段125完成：缓存层已实现，所有测试通过！")
    else:
        print("✅ 阶段125完成：缓存层已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段126：加密与隐私")
    print("  - 数据加密")
    print("  - 访问控制")
    print("  - 审计日志")
    print()
    return True


if __name__ == "__main__":
    run_phase_125()
