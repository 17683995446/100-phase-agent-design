"""
简单而实用的缓存机制
"""

import time
import threading
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from functools import wraps


@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    expire_at: Optional[float] = None  # 过期时间戳，None表示永不过期
    hit_count: int = 0


class LRUCache:
    """
    LRU缓存 - 线程安全的、带过期时间的缓存
    """

    def __init__(self, max_size: int = 1000, default_ttl: Optional[float] = None):
        """
        初始化缓存

        Args:
            max_size: 最大缓存条目数量
            default_ttl: 默认过期时间（秒），None表示永不过期
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'inserts': 0,
            'evictions': 0,
            'expirations': 0
        }

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期则返回None
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats['misses'] += 1
                return None

            # 检查是否过期
            if entry.expire_at is not None and time.time() > entry.expire_at:
                self._stats['expirations'] += 1
                del self._cache[key]
                return None

            # 更新命中计数
            entry.hit_count += 1
            self._stats['hits'] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None表示使用默认值
        """
        with self._lock:
            # 如果缓存已满，先删除最少命中的条目
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()

            expire_at = None
            if ttl is not None:
                expire_at = time.time() + ttl
            elif self.default_ttl is not None:
                expire_at = time.time() + self.default_ttl

            self._cache[key] = CacheEntry(value, expire_at)
            self._stats['inserts'] += 1

    def delete(self, key: str) -> bool:
        """
        删除缓存条目

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()

    def _evict_lru(self) -> None:
        """删除最少命中的条目"""
        if not self._cache:
            return

        # 找最少命中的条目
        min_key = min(self._cache.keys(), key=lambda k: self._cache[k].hit_count)
        del self._cache[min_key]
        self._stats['evictions'] += 1

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            total = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total) * 100 if total > 0 else 0
            return {
                **self._stats,
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_rate': hit_rate
            }

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: str) -> bool:
        with self._lock:
            return key in self._cache


def lru_cache_decorator(max_size: int = 100, ttl: Optional[float] = None):
    """
    缓存装饰器 - 基于LRU策略缓存函数结果

    Args:
        max_size: 最大缓存条目数量
        ttl: 过期时间（秒），None表示永不过期

    Usage:
        @lru_cache_decorator()
        def expensive_function(x):
            return x * x
    """
    cache = LRUCache(max_size=max_size, default_ttl=ttl)

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            key_parts = [str(arg) for arg in args]
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            key = "|".join(key_parts)

            # 尝试从缓存获取
            cached = cache.get(key)
            if cached is not None:
                return cached

            # 计算结果并缓存
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        # 添加获取缓存统计的方法
        wrapper.cache_stats = lambda: cache.get_stats()
        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache = cache

        return wrapper

    return decorator


# 全局默认缓存实例
_default_cache = LRUCache(max_size=1000)


def get_default_cache() -> LRUCache:
    """获取全局默认缓存实例"""
    return _default_cache
