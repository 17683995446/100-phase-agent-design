#!/usr/bin/env python3
"""
性能分析工具使用示例
"""

import time
from core import get_profiler, profile


def example_basic_usage():
    """基本用法示例"""
    print("=" * 70)
    print("基本用法示例")
    print("=" * 70)
    
    profiler = get_profiler()
    profiler.reset()
    
    # 模拟一些操作
    profiler.record("数据库查询", 0.023)
    profiler.record("数据库查询", 0.031)
    profiler.record("文件读取", 0.012)
    profiler.record("网络请求", 0.150)
    profiler.record("网络请求", 0.180)
    profiler.record("网络请求", 0.220)
    profiler.record("数据处理", 0.005)
    
    print("\n性能指标:")
    print(profiler.report())


def example_decorator_usage():
    """装饰器用法示例"""
    print("\n" + "=" * 70)
    print("装饰器用法示例")
    print("=" * 70)
    
    profiler = get_profiler()
    profiler.reset()
    
    # 使用装饰器自动追踪
    @profile()
    def slow_operation():
        time.sleep(0.1)
        return "result"
    
    @profile("快速操作")
    def fast_operation():
        time.sleep(0.01)
        return "fast"
    
    # 执行操作
    for i in range(3):
        slow_operation()
    
    for i in range(5):
        fast_operation()
    
    print("\n装饰器追踪结果:")
    print(profiler.report())


def example_custom_profiler():
    """自定义分析器示例"""
    print("\n" + "=" * 70)
    print("自定义分析器示例")
    print("=" * 70)
    
    from core import PerformanceProfiler
    
    custom_profiler = PerformanceProfiler()
    
    @custom_profiler.profile("数据库查询")
    def query_database():
        time.sleep(0.05)
        return True
    
    @custom_profiler.profile("数据处理")
    def process_data():
        time.sleep(0.02)
        return [1, 2, 3]
    
    # 执行操作
    query_database()
    query_database()
    process_data()
    
    print("\n自定义分析器结果:")
    print(custom_profiler.report())


def example_integration():
    """集成示例 - 追踪多个操作"""
    print("\n" + "=" * 70)
    print("集成示例")
    print("=" * 70)
    
    profiler = get_profiler()
    profiler.reset()
    
    # 模拟一个典型的工作流程
    @profile("初始化")
    def initialize():
        time.sleep(0.01)
        return "initialized"
    
    @profile("加载数据")
    def load_data():
        time.sleep(0.05)
        return ["data1", "data2", "data3"]
    
    @profile("处理数据")
    def process_items(items):
        time.sleep(0.03)
        return [item.upper() for item in items]
    
    @profile("保存结果")
    def save_results(results):
        time.sleep(0.02)
        return len(results)
    
    # 执行工作流程
    initialize()
    data = load_data()
    processed = process_items(data)
    count = save_results(processed)
    
    print(f"\n处理了 {count} 个项目")
    print(profiler.report())


def main():
    print("\n" + "=" * 70)
    print("    第一原理轻量级永动机知识图谱智能体")
    print("    性能分析工具使用示例")
    print("=" * 70 + "\n")
    
    example_basic_usage()
    example_decorator_usage()
    example_custom_profiler()
    example_integration()
    
    print("\n" + "=" * 70)
    print("所有示例执行完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
