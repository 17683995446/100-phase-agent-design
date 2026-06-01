#!/usr/bin/env python3
"""
缓存机制使用示例
"""

import time
from core import LRUCache, lru_cache_decorator, get_default_cache


def example_basic_cache():
    """基本缓存使用示例"""
    print("=" * 70)
    print("基本缓存使用示例")
    print("=" * 70)

    cache = LRUCache(max_size=5)

    # 设置缓存
    cache.set('key1', 'value1')
    cache.set('key2', 'value2')
    print(f"\n设置了 key1, key2")

    # 获取缓存
    print(f"key1 = {cache.get('key1')}")
    print(f"key2 = {cache.get('key2')}")

    # 检查统计
    stats = cache.get_stats()
    print(f"\n缓存统计:")
    print(f"  缓存大小: {stats['size']}/{stats['max_size']}")
    print(f"  命中次数: {stats['hits']}")
    print(f"  未命中次数: {stats['misses']}")


def example_ttl_cache():
    """带过期时间的缓存示例"""
    print("\n" + "=" * 70)
    print("带过期时间的缓存示例")
    print("=" * 70)

    cache = LRUCache(max_size=10, default_ttl=0.5)
    cache.set('temp_key', 'temp_value')

    print(f"\n设置了 temp_key，TTL = 0.5秒")
    print(f"立即获取: {cache.get('temp_key')}")

    print("\n等待 0.6 秒...")
    time.sleep(0.6)

    print(f"过期后获取: {cache.get('temp_key')}")
    print("(返回 None 说明缓存已过期)")


def example_decorator():
    """缓存装饰器使用示例"""
    print("\n" + "=" * 70)
    print("缓存装饰器使用示例")
    print("=" * 70)

    # 使用装饰器
    call_count = 0

    @lru_cache_decorator(max_size=3, ttl=1.0)
    def expensive_calculation(x):
        nonlocal call_count
        call_count += 1
        print(f"  计算中: expensive_calculation({x})")
        time.sleep(0.1)  # 模拟耗时操作
        return x * x

    print("\n第一次调用 (应该计算):")
    result1 = expensive_calculation(2)
    print(f"  结果: {result1}")
    print(f"  调用次数: {call_count}")

    print("\n第二次调用 (应该从缓存获取):")
    result2 = expensive_calculation(2)
    print(f"  结果: {result2}")
    print(f"  调用次数: {call_count} (没变，说明从缓存获取)")

    print("\n查看缓存统计:")
    stats = expensive_calculation.cache_stats()
    print(f"  命中率: {stats['hit_rate']:.1f}%")
    print(f"  命中次数: {stats['hits']}")


def example_global_cache():
    """全局缓存使用示例"""
    print("\n" + "=" * 70)
    print("全局缓存使用示例")
    print("=" * 70)

    cache = get_default_cache()

    cache.set('global_data', {'key': 'value'})
    print(f"\n设置全局缓存: global_data = {cache.get('global_data')}")

    # 在其他地方也可以获取
    cache2 = get_default_cache()
    print(f"从其他地方获取: {cache2.get('global_data')}")


def example_lru_eviction():
    """LRU 淘汰策略示例"""
    print("\n" + "=" * 70)
    print("LRU 淘汰策略示例")
    print("=" * 70)

    cache = LRUCache(max_size=3)

    # 添加 3 个键
    cache.set('a', 1)
    cache.set('b', 2)
    cache.set('c', 3)

    # 增加 a 和 b 的命中次数
    cache.get('a')
    cache.get('a')
    cache.get('b')

    print(f"\n当前缓存有 a, b, c")
    print(f"添加 d (应该淘汰最少命中的 c)")
    cache.set('d', 4)

    print(f"\n检查缓存:")
    print(f"  a 是否在缓存: {cache.get('a') is not None}")
    print(f"  b 是否在缓存: {cache.get('b') is not None}")
    print(f"  c 是否在缓存: {cache.get('c') is not None} (应该不在)")
    print(f"  d 是否在缓存: {cache.get('d') is not None}")


def main():
    print("\n" + "=" * 70)
    print("    第一原理轻量级永动机知识图谱智能体")
    print("    缓存机制使用示例")
    print("=" * 70)

    example_basic_cache()
    example_ttl_cache()
    example_decorator()
    example_global_cache()
    example_lru_eviction()

    print("\n" + "=" * 70)
    print("示例运行完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
