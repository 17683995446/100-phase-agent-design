"""
缓存机制测试
"""

import time
import pytest
from core import LRUCache, lru_cache_decorator, get_default_cache


class TestLRUCache:
    """测试 LRU 缓存"""

    def test_basic_operations(self):
        """测试基本操作"""
        cache = LRUCache(max_size=10)
        
        # 设置缓存
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        # 获取缓存
        assert cache.get('key1') == 'value1'
        assert cache.get('key2') == 'value2'
        
        # 检查大小
        assert len(cache) == 2
        assert 'key1' in cache
        assert 'key2' in cache

    def test_missing_key(self):
        """测试缺失的键"""
        cache = LRUCache(max_size=10)
        
        assert cache.get('missing') is None
        assert 'missing' not in cache

    def test_delete(self):
        """测试删除操作"""
        cache = LRUCache(max_size=10)
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        # 删除存在的键
        assert cache.delete('key1') is True
        assert cache.get('key1') is None
        assert len(cache) == 1
        
        # 删除不存在的键
        assert cache.delete('key3') is False

    def test_clear(self):
        """测试清空操作"""
        cache = LRUCache(max_size=10)
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        cache.clear()
        assert len(cache) == 0
        assert cache.get('key1') is None

    def test_ttl_expiration(self):
        """测试过期时间"""
        cache = LRUCache(max_size=10, default_ttl=0.1)
        cache.set('key1', 'value1')
        
        # 立即获取，应该还没过期
        assert cache.get('key1') == 'value1'
        
        # 等待过期
        time.sleep(0.2)
        assert cache.get('key1') is None

    def test_custom_ttl(self):
        """测试自定义过期时间"""
        cache = LRUCache(max_size=10)
        cache.set('key1', 'value1', ttl=0.1)
        cache.set('key2', 'value2')  # 永不过期
        
        assert cache.get('key1') == 'value1'
        assert cache.get('key2') == 'value2'
        
        time.sleep(0.2)
        assert cache.get('key1') is None
        assert cache.get('key2') == 'value2'

    def test_lru_eviction(self):
        """测试 LRU 淘汰策略"""
        cache = LRUCache(max_size=3)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        # 获取 key2 和 key3 多次，增加它们的命中次数
        cache.get('key2')
        cache.get('key2')
        cache.get('key3')
        
        # 添加新键，应该淘汰 key1（最少命中）
        cache.set('key4', 'value4')
        
        assert cache.get('key1') is None
        assert cache.get('key2') == 'value2'
        assert cache.get('key3') == 'value3'
        assert cache.get('key4') == 'value4'

    def test_stats(self):
        """测试统计信息"""
        cache = LRUCache(max_size=10)
        
        # 一些操作
        cache.set('key1', 'value1')
        cache.get('key1')
        cache.get('key1')
        cache.get('missing')
        cache.set('key2', 'value2')
        
        stats = cache.get_stats()
        assert stats['hits'] == 2
        assert stats['misses'] == 1
        assert stats['inserts'] == 2
        assert stats['evictions'] == 0
        assert stats['size'] == 2
        assert stats['hit_rate'] > 0


class TestLRUCacheDecorator:
    """测试缓存装饰器"""

    def test_basic_decorator(self):
        """测试基本装饰器功能"""
        call_count = 0
        
        @lru_cache_decorator()
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * x
        
        # 第一次调用
        assert expensive_function(2) == 4
        assert call_count == 1
        
        # 第二次调用，应该从缓存获取
        assert expensive_function(2) == 4
        assert call_count == 1
        
        # 不同的参数
        assert expensive_function(3) == 9
        assert call_count == 2

    def test_decorator_with_kwargs(self):
        """测试带关键字参数的装饰器"""
        call_count = 0
        
        @lru_cache_decorator()
        def add(a, b=1):
            nonlocal call_count
            call_count += 1
            return a + b
        
        assert add(2) == 3
        assert add(2) == 3
        assert call_count == 1
        
        assert add(2, b=3) == 5
        assert add(2, b=3) == 5
        assert call_count == 2

    def test_decorator_ttl(self):
        """测试装饰器的过期时间"""
        call_count = 0
        
        @lru_cache_decorator(ttl=0.1)
        def func(x):
            nonlocal call_count
            call_count += 1
            return x
        
        assert func(1) == 1
        assert func(1) == 1
        assert call_count == 1
        
        time.sleep(0.2)
        
        assert func(1) == 1
        assert call_count == 2

    def test_decorator_clear(self):
        """测试装饰器清空缓存"""
        call_count = 0
        
        @lru_cache_decorator()
        def func(x):
            nonlocal call_count
            call_count += 1
            return x
        
        func(1)
        func(1)
        assert call_count == 1
        
        func.cache_clear()
        
        func(1)
        assert call_count == 2

    def test_decorator_stats(self):
        """测试装饰器统计信息"""
        @lru_cache_decorator()
        def func(x):
            return x
        
        func(1)
        func(1)
        func(2)
        
        stats = func.cache_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 2


class TestGlobalCache:
    """测试全局缓存"""

    def test_get_default_cache(self):
        """测试获取全局缓存"""
        cache1 = get_default_cache()
        cache2 = get_default_cache()
        
        assert cache1 is cache2
        
        cache1.set('key', 'value')
        assert cache2.get('key') == 'value'

    def test_default_cache_persistence(self):
        """测试默认缓存的持久化（在同一个进程内）"""
        cache = get_default_cache()
        cache.clear()
        
        cache.set('test', 'value')
        
        cache2 = get_default_cache()
        assert cache2.get('test') == 'value'
