"""
性能分析工具测试
"""

import time
import pytest
from core import PerformanceProfiler, get_profiler, profile


class TestPerformanceProfiler:
    """测试性能分析器"""
    
    def test_basic_record(self):
        """测试基本记录"""
        profiler = PerformanceProfiler()
        profiler.record("test_op", 0.1)
        
        metric = profiler.get_metric("test_op")
        assert metric is not None
        assert metric.call_count == 1
        assert metric.total_time == 0.1
        assert metric.avg_time == 0.1
    
    def test_multiple_records(self):
        """测试多次记录"""
        profiler = PerformanceProfiler()
        profiler.record("test_op", 0.1)
        profiler.record("test_op", 0.2)
        profiler.record("test_op", 0.3)
        
        metric = profiler.get_metric("test_op")
        assert metric.call_count == 3
        assert metric.total_time == pytest.approx(0.6)
        assert metric.avg_time == pytest.approx(0.2)
        assert metric.min_time == pytest.approx(0.1)
        assert metric.max_time == pytest.approx(0.3)
    
    def test_multiple_operations(self):
        """测试多个不同操作"""
        profiler = PerformanceProfiler()
        profiler.record("op1", 0.1)
        profiler.record("op2", 0.2)
        profiler.record("op3", 0.3)
        
        metrics = profiler.get_all_metrics()
        assert len(metrics) == 3
    
    def test_top_slowest(self):
        """测试最慢操作排序"""
        profiler = PerformanceProfiler()
        profiler.record("fast", 0.01)
        profiler.record("slow", 0.5)
        profiler.record("medium", 0.1)
        
        top = profiler.get_top_slowest(2)
        assert len(top) == 2
        assert top[0].name == "slow"
        assert top[1].name == "medium"
    
    def test_top_most_called(self):
        """测试最多调用排序"""
        profiler = PerformanceProfiler()
        for _ in range(5):
            profiler.record("frequent", 0.01)
        for _ in range(2):
            profiler.record("rare", 0.1)
        
        top = profiler.get_top_most_called(2)
        assert len(top) == 2
        assert top[0].name == "frequent"
        assert top[1].name == "rare"
    
    def test_reset(self):
        """测试重置"""
        profiler = PerformanceProfiler()
        profiler.record("op1", 0.1)
        profiler.record("op2", 0.2)
        
        profiler.reset()
        assert len(profiler.get_all_metrics()) == 0
    
    def test_enable_disable(self):
        """测试启用/禁用"""
        profiler = PerformanceProfiler()
        profiler.disable()
        profiler.record("op1", 0.1)  # 应该被忽略
        profiler.record("op1", 0.2)  # 应该被忽略
        
        profiler.enable()
        profiler.record("op1", 0.1)  # 应该被记录
        profiler.record("op2", 0.2)
        
        # op1 应该有 1 次记录，op2 应该有 1 次记录
        assert len(profiler.get_all_metrics()) == 2
        assert profiler.get_metric("op1").call_count == 1
        assert profiler.get_metric("op2").call_count == 1
    
    def test_profile_decorator(self):
        """测试装饰器"""
        profiler = PerformanceProfiler()
        
        @profiler.profile()
        def slow_function():
            time.sleep(0.01)
            return 42
        
        result = slow_function()
        assert result == 42
        
        metric = profiler.get_metric("slow_function")
        assert metric is not None
        assert metric.call_count == 1
        assert metric.total_time >= 0.01
    
    def test_profile_decorator_with_name(self):
        """测试带名称的装饰器"""
        profiler = PerformanceProfiler()
        
        @profiler.profile("custom_name")
        def my_function():
            return 1
        
        my_function()
        
        metric = profiler.get_metric("custom_name")
        assert metric is not None
        assert metric.name == "custom_name"
    
    def test_global_profiler(self):
        """测试全局性能分析器"""
        profiler1 = get_profiler()
        profiler2 = get_profiler()
        
        assert profiler1 is profiler2
    
    def test_report_generation(self):
        """测试报告生成"""
        profiler = PerformanceProfiler()
        profiler.record("operation1", 0.1)
        profiler.record("operation2", 0.2)
        
        report = profiler.report()
        assert "Performance Report" in report
        assert "operation1" in report
        assert "operation2" in report
    
    def test_empty_report(self):
        """测试空报告"""
        profiler = PerformanceProfiler()
        # 不记录任何数据，直接生成报告
        report_text = profiler.report()
        assert "No performance data recorded." in report_text


class TestGlobalProfileDecorator:
    """测试全局 profile 装饰器"""
    
    def test_global_decorator(self):
        """测试全局装饰器"""
        profiler = get_profiler()
        profiler.reset()
        
        @profile()
        def test_func():
            time.sleep(0.001)
            return 123
        
        result = test_func()
        assert result == 123
        
        metric = profiler.get_metric("test_func")
        assert metric is not None
        assert metric.call_count == 1
    
    def test_global_decorator_with_name(self):
        """测试全局装饰器带名称"""
        profiler = get_profiler()
        profiler.reset()
        
        @profile("named_func")
        def some_func():
            return 1
        
        some_func()
        
        metric = profiler.get_metric("named_func")
        assert metric is not None
