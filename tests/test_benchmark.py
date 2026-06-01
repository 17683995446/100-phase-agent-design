import pytest
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.knowledge_graph import KnowledgeGraph
from core.benchmark import (
    BenchmarkResult, BenchmarkRunner,
    KnowledgeGraphBenchmark, PerformanceMonitor
)


class TestBenchmarkResult:
    def test_creation(self):
        result = BenchmarkResult(
            name="test",
            iterations=10,
            total_time=1.0,
            min_time=0.05,
            max_time=0.15,
            avg_time=0.1,
            median_time=0.1,
            stdev_time=0.02,
            ops_per_second=10.0
        )
        assert result.name == "test"
        assert result.iterations == 10

    def test_to_dict(self):
        result = BenchmarkResult(
            name="test",
            iterations=10,
            total_time=1.0,
            min_time=0.05,
            max_time=0.15,
            avg_time=0.1,
            median_time=0.1,
            stdev_time=0.02,
            ops_per_second=10.0,
            metadata={"key": "value"}
        )
        d = result.to_dict()
        assert d["name"] == "test"
        assert d["ops_per_second"] == 10.0
        assert d["metadata"]["key"] == "value"


class TestBenchmarkRunner:
    def test_creation(self):
        runner = BenchmarkRunner()
        assert runner.warmup_iterations == 3
        assert len(runner.results) == 0

    def test_run_simple(self):
        runner = BenchmarkRunner()

        def simple_func():
            pass

        result = runner.run("simple", simple_func, iterations=10)
        assert result.name == "simple"
        assert result.iterations == 10
        assert len(runner.results) == 1

    def test_run_with_args(self):
        runner = BenchmarkRunner()

        def add_func(a, b):
            return a + b

        result = runner.run("add", add_func, iterations=10, args=(1, 2))
        assert result.name == "add"

    def test_generate_report(self):
        runner = BenchmarkRunner()

        def func():
            pass

        runner.run("test1", func, iterations=5)
        runner.run("test2", func, iterations=5)

        report = runner.generate_report()
        assert report["total_benchmarks"] == 2
        assert len(report["benchmarks"]) == 2

    def test_clear(self):
        runner = BenchmarkRunner()
        runner.run("test", lambda: None, iterations=1)
        runner.clear()
        assert len(runner.results) == 0


class TestKnowledgeGraphBenchmark:
    @pytest.fixture
    def sample_graph(self):
        kg = KnowledgeGraph(save_path="test_benchmark.json")
        kg.clear()
        return kg

    @pytest.fixture
    def benchmark(self, sample_graph):
        return KnowledgeGraphBenchmark(sample_graph)

    def test_benchmark_node_operations(self, benchmark):
        result = benchmark.benchmark_node_operations(node_count=100)
        assert result.name == "node_add"
        assert result.iterations == 10
        assert result.metadata["node_count"] == 100

    def test_benchmark_edge_operations(self, benchmark):
        result = benchmark.benchmark_edge_operations(edge_count=100)
        assert result.name == "edge_add"
        assert result.metadata["edge_count"] == 100

    def test_benchmark_query_operations(self, benchmark):
        result = benchmark.benchmark_query_operations(node_count=50)
        assert result.name == "query"
        assert result.metadata["node_count"] == 50

    def test_benchmark_save_load(self, benchmark):
        result = benchmark.benchmark_save_load(node_count=50)
        assert result.name == "save_load"

    def test_benchmark_similarity(self, benchmark):
        result = benchmark.benchmark_similarity(node_count=50)
        assert result.name == "similarity"

    def test_run_all(self, benchmark):
        report = benchmark.run_all(node_count=100)
        assert report["total_benchmarks"] == 5
        assert len(report["benchmarks"]) == 5


class TestPerformanceMonitor:
    def test_creation(self):
        monitor = PerformanceMonitor()
        assert len(monitor.get_stats()) == 0

    def test_record(self):
        monitor = PerformanceMonitor()
        monitor.record("add_node", 0.001)
        monitor.record("add_node", 0.002)

        stats = monitor.get_stats("add_node")
        assert stats["count"] == 2
        assert stats["avg_time_ms"] > 0

    def test_get_all_stats(self):
        monitor = PerformanceMonitor()
        monitor.record("op1", 0.001)
        monitor.record("op2", 0.002)

        stats = monitor.get_stats()
        assert "op1" in stats
        assert "op2" in stats

    def test_get_nonexistent_stats(self):
        monitor = PerformanceMonitor()
        stats = monitor.get_stats("nonexistent")
        assert stats == {}

    def test_reset(self):
        monitor = PerformanceMonitor()
        monitor.record("op", 0.001)
        monitor.reset()
        assert len(monitor.get_stats()) == 0


class TestBenchmarkIntegration:
    def test_end_to_end_benchmark(self):
        """端到端基准测试"""
        kg = KnowledgeGraph(save_path="test_e2e_benchmark.json")
        kg.clear()

        # 准备数据
        for i in range(200):
            kg.add_node(f"node_{i}", {"index": i})
        for i in range(199):
            kg.add_edge(f"node_{i}", f"node_{i+1}", "next", 0.9)

        benchmark = KnowledgeGraphBenchmark(kg)
        report = benchmark.run_all(node_count=200)

        # 验证报告结构
        assert "total_benchmarks" in report
        assert "total_time_ms" in report
        assert "benchmarks" in report

        for b in report["benchmarks"]:
            assert b["name"] in ["node_add", "edge_add", "query", "save_load", "similarity"]
            assert b["ops_per_second"] > 0

        # 清理
        import os
        if os.path.exists("test_e2e_benchmark.json"):
            os.remove("test_e2e_benchmark.json")

    def test_monitor_with_operations(self):
        """监控实际操作的性能"""
        kg = KnowledgeGraph(save_path="test_monitor.json")
        kg.clear()

        monitor = PerformanceMonitor()

        # 监控节点添加
        for i in range(50):
            start = time.perf_counter()
            kg.add_node(f"node_{i}")
            end = time.perf_counter()
            monitor.record("add_node", end - start)

        stats = monitor.get_stats("add_node")
        assert stats["count"] == 50
        assert stats["avg_time_ms"] > 0

        # 清理
        import os
        if os.path.exists("test_monitor.json"):
            os.remove("test_monitor.json")
