import time
import statistics
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class BenchmarkResult:
    """
    基准测试结果

    功能：记录单次基准测试的详细数据
    """
    name: str
    iterations: int
    total_time: float
    min_time: float
    max_time: float
    avg_time: float
    median_time: float
    stdev_time: float
    ops_per_second: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time_ms": round(self.total_time * 1000, 3),
            "min_time_ms": round(self.min_time * 1000, 6),
            "max_time_ms": round(self.max_time * 1000, 6),
            "avg_time_ms": round(self.avg_time * 1000, 6),
            "median_time_ms": round(self.median_time * 1000, 6),
            "stdev_time_ms": round(self.stdev_time * 1000, 6) if self.stdev_time else 0,
            "ops_per_second": round(self.ops_per_second, 2),
            "metadata": self.metadata
        }


class BenchmarkRunner:
    """
    基准测试运行器

    功能：运行基准测试并收集性能指标
    原理：多次执行目标函数，统计时间分布
    """

    def __init__(self, warmup_iterations: int = 3):
        self.warmup_iterations = warmup_iterations
        self.results: List[BenchmarkResult] = []

    def run(self, name: str, func: Callable, iterations: int = 100,
            args: tuple = (), kwargs: Optional[Dict] = None,
            metadata: Optional[Dict[str, Any]] = None) -> BenchmarkResult:
        """
        运行基准测试

        Args:
            name: 测试名称
            func: 待测试函数
            iterations: 迭代次数
            args: 函数位置参数
            kwargs: 函数关键字参数
            metadata: 额外元数据

        Returns:
            BenchmarkResult 对象
        """
        if kwargs is None:
            kwargs = {}

        # 预热
        for _ in range(self.warmup_iterations):
            func(*args, **kwargs)

        # 正式测试
        times: List[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            func(*args, **kwargs)
            end = time.perf_counter()
            times.append(end - start)

        total_time = sum(times)
        avg_time = total_time / iterations
        ops_per_second = iterations / total_time if total_time > 0 else float('inf')

        result = BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total_time,
            min_time=min(times),
            max_time=max(times),
            avg_time=avg_time,
            median_time=statistics.median(times),
            stdev_time=statistics.stdev(times) if len(times) > 1 else 0.0,
            ops_per_second=ops_per_second,
            metadata=metadata or {}
        )

        self.results.append(result)
        return result

    def get_results(self) -> List[BenchmarkResult]:
        """获取所有测试结果"""
        return self.results

    def clear(self) -> None:
        """清除结果"""
        self.results.clear()

    def generate_report(self) -> Dict[str, Any]:
        """
        生成性能报告

        Returns:
            包含所有测试结果的报告字典
        """
        return {
            "total_benchmarks": len(self.results),
            "total_time_ms": round(sum(r.total_time for r in self.results) * 1000, 3),
            "benchmarks": [r.to_dict() for r in self.results]
        }


class KnowledgeGraphBenchmark:
    """
    知识图谱专用基准测试套件

    功能：针对知识图谱核心操作的性能测试
    """

    def __init__(self, knowledge_graph):
        self.kg = knowledge_graph
        self.runner = BenchmarkRunner()

    def benchmark_node_operations(self, node_count: int = 1000) -> BenchmarkResult:
        """
        基准测试：节点操作

        功能：测试批量添加节点的性能
        """
        def add_nodes():
            self.kg.clear()
            for i in range(node_count):
                self.kg.add_node(f"node_{i}", {"index": i})

        return self.runner.run(
            "node_add",
            add_nodes,
            iterations=10,
            metadata={"node_count": node_count}
        )

    def benchmark_edge_operations(self, edge_count: int = 1000) -> BenchmarkResult:
        """
        基准测试：边操作

        功能：测试批量添加边的性能
        """
        # 先准备节点
        self.kg.clear()
        for i in range(edge_count + 1):
            self.kg.add_node(f"node_{i}")

        def add_edges():
            # 清空边但保留节点
            self.kg.edges.clear()
            self.kg._rebuild_edge_indexes()
            for i in range(edge_count):
                self.kg.add_edge(f"node_{i}", f"node_{i+1}", "next", 0.9)

        return self.runner.run(
            "edge_add",
            add_edges,
            iterations=10,
            metadata={"edge_count": edge_count}
        )

    def benchmark_query_operations(self, node_count: int = 100) -> BenchmarkResult:
        """
        基准测试：查询操作

        功能：测试节点查找和遍历的性能
        """
        # 准备数据
        self.kg.clear()
        for i in range(node_count):
            self.kg.add_node(f"node_{i}", {"group": i % 10})
        for i in range(node_count - 1):
            self.kg.add_edge(f"node_{i}", f"node_{i+1}", "next", 0.9)

        def query_nodes():
            for i in range(node_count):
                self.kg.get_node(f"node_{i}")
            self.kg.find_paths("node_0", f"node_{node_count-1}", max_depth=3)

        return self.runner.run(
            "query",
            query_nodes,
            iterations=100,
            metadata={"node_count": node_count}
        )

    def benchmark_save_load(self, node_count: int = 500) -> BenchmarkResult:
        """
        基准测试：保存和加载

        功能：测试持久化操作的性能
        """
        # 准备数据
        self.kg.clear()
        for i in range(node_count):
            self.kg.add_node(f"node_{i}", {"data": f"value_{i}"})
        for i in range(node_count - 1):
            self.kg.add_edge(f"node_{i}", f"node_{i+1}", "link", 0.5)

        def save_load():
            self.kg.save()
            self.kg.load()

        return self.runner.run(
            "save_load",
            save_load,
            iterations=10,
            metadata={"node_count": node_count}
        )

    def benchmark_similarity(self, node_count: int = 100) -> BenchmarkResult:
        """
        基准测试：相似度计算

        功能：测试节点相似度计算的性能
        """
        # 准备数据
        self.kg.clear()
        for i in range(node_count):
            self.kg.add_node(f"node_{i}", {"feature": i % 5})
        for i in range(node_count):
            for j in range(i + 1, min(i + 3, node_count)):
                self.kg.add_edge(f"node_{i}", f"node_{j}", "similar", 0.8)

        def compute_similarity():
            self.kg.compute_similarity("node_0", "node_1")
            self.kg.find_similar_nodes("node_0", top_k=5)

        return self.runner.run(
            "similarity",
            compute_similarity,
            iterations=50,
            metadata={"node_count": node_count}
        )

    def run_all(self, node_count: int = 1000) -> Dict[str, Any]:
        """
        运行所有基准测试

        Args:
            node_count: 测试数据规模

        Returns:
            完整性能报告
        """
        self.runner.clear()

        self.benchmark_node_operations(node_count)
        self.benchmark_edge_operations(node_count)
        self.benchmark_query_operations(min(node_count // 10, 100))
        self.benchmark_save_load(min(node_count // 2, 500))
        self.benchmark_similarity(min(node_count // 10, 100))

        return self.runner.generate_report()


class PerformanceMonitor:
    """
    性能监控器

    功能：实时监控知识图谱操作性能
    """

    def __init__(self):
        self._metrics: Dict[str, List[float]] = defaultdict(list)
        self._counts: Dict[str, int] = defaultdict(int)

    def record(self, operation: str, duration: float) -> None:
        """
        记录操作耗时

        Args:
            operation: 操作名称
            duration: 耗时（秒）
        """
        self._metrics[operation].append(duration)
        self._counts[operation] += 1

    def get_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """
        获取性能统计

        Args:
            operation: 指定操作名称（None 则返回所有）

        Returns:
            统计信息字典
        """
        if operation is not None:
            if operation not in self._metrics:
                return {}
            times = self._metrics[operation]
            return {
                "operation": operation,
                "count": self._counts[operation],
                "avg_time_ms": round(statistics.mean(times) * 1000, 6) if times else 0,
                "min_time_ms": round(min(times) * 1000, 6) if times else 0,
                "max_time_ms": round(max(times) * 1000, 6) if times else 0,
                "total_time_ms": round(sum(times) * 1000, 3)
            }

        return {
            op: self.get_stats(op)
            for op in self._metrics.keys()
        }

    def reset(self) -> None:
        """重置监控数据"""
        self._metrics.clear()
        self._counts.clear()
