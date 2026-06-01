"""
性能分析工具
"""

import time
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from functools import wraps


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    
    @property
    def avg_time(self) -> float:
        return self.total_time / self.call_count if self.call_count > 0 else 0.0
    
    @property
    def calls_per_second(self) -> float:
        return self.call_count / self.total_time if self.total_time > 0 else 0.0


class PerformanceProfiler:
    """
    性能分析器 - 追踪函数执行时间和调用次数
    """
    
    def __init__(self):
        self._metrics: Dict[str, PerformanceMetric] = {}
        self._lock = threading.Lock()
        self._enabled = True
    
    def enable(self) -> None:
        """启用性能分析"""
        self._enabled = True
    
    def disable(self) -> None:
        """禁用性能分析"""
        self._enabled = False
    
    def reset(self) -> None:
        """重置所有指标"""
        with self._lock:
            self._metrics.clear()
    
    def record(self, name: str, duration: float) -> None:
        """
        记录一个操作
        
        Args:
            name: 操作名称
            duration: 持续时间（秒）
        """
        if not self._enabled:
            return
        
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = PerformanceMetric(name=name)
            
            metric = self._metrics[name]
            metric.call_count += 1
            metric.total_time += duration
            metric.min_time = min(metric.min_time, duration)
            metric.max_time = max(metric.max_time, duration)
    
    def get_metric(self, name: str) -> Optional[PerformanceMetric]:
        """
        获取指定指标
        
        Args:
            name: 指标名称
            
        Returns:
            PerformanceMetric 或 None
        """
        with self._lock:
            return self._metrics.get(name)
    
    def get_all_metrics(self) -> List[PerformanceMetric]:
        """
        获取所有指标
        
        Returns:
            指标列表
        """
        with self._lock:
            return list(self._metrics.values())
    
    def get_top_slowest(self, limit: int = 10) -> List[PerformanceMetric]:
        """
        获取最慢的操作
        
        Args:
            limit: 返回数量
            
        Returns:
            按平均时间排序的指标列表
        """
        with self._lock:
            metrics = sorted(
                self._metrics.values(),
                key=lambda m: m.avg_time,
                reverse=True
            )
            return metrics[:limit]
    
    def get_top_most_called(self, limit: int = 10) -> List[PerformanceMetric]:
        """
        获取调用次数最多的操作
        
        Args:
            limit: 返回数量
            
        Returns:
            按调用次数排序的指标列表
        """
        with self._lock:
            metrics = sorted(
                self._metrics.values(),
                key=lambda m: m.call_count,
                reverse=True
            )
            return metrics[:limit]
    
    def profile(self, name: Optional[str] = None):
        """
        装饰器 - 自动追踪函数性能
        
        Args:
            name: 指标名称，默认为函数名
            
        Usage:
            @profiler.profile()
            def my_function():
                pass
            
            @profiler.profile("custom_name")
            def another_function():
                pass
        """
        def decorator(func: Callable) -> Callable:
            metric_name = name or func.__name__
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = time.perf_counter() - start
                    self.record(metric_name, duration)
            
            return wrapper
        
        return decorator
    
    def report(self) -> str:
        """
        生成性能报告
        
        Returns:
            格式化的性能报告
        """
        metrics = self.get_all_metrics()
        
        if not metrics:
            return "No performance data recorded."
        
        lines = [
            "=" * 70,
            "Performance Report",
            "=" * 70,
            f"Total metrics: {len(metrics)}",
            f"Enabled: {self._enabled}",
            "=" * 70,
            "",
            "Top 10 Slowest Operations:",
            "-" * 70,
        ]
        
        for i, metric in enumerate(self.get_top_slowest(10), 1):
            lines.append(
                f"{i:2d}. {metric.name:<30s} "
                f"avg={metric.avg_time*1000:8.3f}ms  "
                f"min={metric.min_time*1000:8.3f}ms  "
                f"max={metric.max_time*1000:8.3f}ms  "
                f"calls={metric.call_count:6d}"
            )
        
        lines.extend(["", "Top 10 Most Called Operations:", "-" * 70])
        
        for i, metric in enumerate(self.get_top_most_called(10), 1):
            lines.append(
                f"{i:2d}. {metric.name:<30s} "
                f"calls={metric.call_count:6d}  "
                f"avg={metric.avg_time*1000:8.3f}ms"
            )
        
        lines.extend(["", "=" * 70])
        
        return "\n".join(lines)


# 全局性能分析器实例
_global_profiler = PerformanceProfiler()


def get_profiler() -> PerformanceProfiler:
    """获取全局性能分析器"""
    return _global_profiler


def profile(name: Optional[str] = None):
    """
    便捷装饰器 - 使用全局性能分析器
    
    Usage:
        @profile()
        def my_function():
            pass
    """
    return _global_profiler.profile(name)
