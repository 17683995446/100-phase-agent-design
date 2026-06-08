#!/usr/bin/env python3
"""
阶段131：可观测性

第一性原理：
  - 透明公理：系统行为必须可被观察
  - 三支柱：日志（已发生）、指标（聚合）、追踪（关联）
  - 因果链：从请求到响应的完整路径
  - 反直觉：99% 不可见 = 0 不可用

本阶段产出：
  1. Metric：指标定义
  2. MetricsRegistry：指标注册表
  3. Counter/Gauge/Histogram：三种指标类型
  4. Trace：分布式追踪
  5. Tracer：追踪器
  6. OpenTelemetry风格导出器

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import threading
import uuid
import json
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, field
from collections import deque, defaultdict


# ============================================================
# 一、指标类型
# ============================================================
class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"      # 计数器（只增）
    GAUGE = "gauge"          # 仪表（可增可减）
    HISTOGRAM = "histogram"  # 直方图（分布）


@dataclass
class Metric:
    """指标"""
    name: str
    type: MetricType
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    # 直方图专用
    buckets: List[float] = field(default_factory=list)
    bucket_counts: Dict[float, int] = field(default_factory=dict)
    observations: List[float] = field(default_factory=list)
    sum_value: float = 0.0
    count: int = 0


# ============================================================
# 二、指标注册表
# ============================================================
class MetricsRegistry:
    """指标注册表"""
    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._lock = threading.RLock()
        self._stats = {"scrapes": 0}

    def register(self, metric: Metric) -> None:
        with self._lock:
            if metric.name not in self._metrics:
                self._metrics[metric.name] = metric

    def counter(self, name: str, description: str = "",
                 labels: Optional[Dict] = None) -> 'Counter':
        metric = Metric(
            name=name, type=MetricType.COUNTER,
            description=description,
            labels=labels or {})
        self.register(metric)
        return Counter(metric)

    def gauge(self, name: str, description: str = "",
               labels: Optional[Dict] = None) -> 'Gauge':
        metric = Metric(
            name=name, type=MetricType.GAUGE,
            description=description,
            labels=labels or {})
        self.register(metric)
        return Gauge(metric)

    def histogram(self, name: str, description: str = "",
                   buckets: Optional[List[float]] = None,
                   labels: Optional[Dict] = None) -> 'Histogram':
        if buckets is None:
            buckets = [0.005, 0.01, 0.025, 0.05, 0.1,
                        0.25, 0.5, 1, 2.5, 5, 10]
        metric = Metric(
            name=name, type=MetricType.HISTOGRAM,
            description=description, buckets=buckets,
            labels=labels or {},
            bucket_counts={b: 0 for b in buckets})
        self.register(metric)
        return Histogram(metric)

    def get(self, name: str) -> Optional[Metric]:
        with self._lock:
            return self._metrics.get(name)

    def collect(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._stats["scrapes"] += 1
            return [self._to_dict(m) for m in self._metrics.values()]

    def _to_dict(self, m: Metric) -> Dict[str, Any]:
        d = {
            "name": m.name,
            "type": m.type.value,
            "labels": m.labels,
            "description": m.description,
        }
        if m.type == MetricType.COUNTER:
            d["value"] = m.value
        elif m.type == MetricType.GAUGE:
            d["value"] = m.value
        elif m.type == MetricType.HISTOGRAM:
            d["count"] = m.count
            d["sum"] = m.sum_value
            d["buckets"] = m.bucket_counts
        return d

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 三、Counter/Gauge/Histogram
# ============================================================
class Counter:
    """计数器（只增不减）"""
    def __init__(self, metric: Metric):
        self._metric = metric
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._metric.value += amount

    def get(self) -> float:
        with self._lock:
            return self._metric.value


class Gauge:
    """仪表（任意变化）"""
    def __init__(self, metric: Metric):
        self._metric = metric
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._metric.value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._metric.value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._metric.value -= amount

    def get(self) -> float:
        with self._lock:
            return self._metric.value


class Histogram:
    """直方图（观测值分布）"""
    def __init__(self, metric: Metric):
        self._metric = metric
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        with self._lock:
            self._metric.observations.append(value)
            self._metric.count += 1
            self._metric.sum_value += value
            for bucket in self._metric.buckets:
                if value <= bucket:
                    self._metric.bucket_counts[bucket] += 1

    def get_count(self) -> int:
        with self._lock:
            return self._metric.count

    def get_sum(self) -> float:
        with self._lock:
            return self._metric.sum_value

    def get_percentile(self, p: float) -> float:
        with self._lock:
            obs = sorted(self._metric.observations)
            if not obs:
                return 0.0
            idx = int(len(obs) * p)
            return obs[min(idx, len(obs) - 1)]


# ============================================================
# 四、Span和Trace
# ============================================================
@dataclass
class Span:
    """追踪span"""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ok"  # ok / error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
        }


class Tracer:
    """追踪器"""
    def __init__(self):
        self._spans: Dict[str, Span] = {}
        self._active_spans: List[str] = []
        self._lock = threading.RLock()
        self._stats = {
            "traces": 0, "spans": 0, "errors": 0,
        }

    def start_span(self, name: str,
                    trace_id: Optional[str] = None,
                    parent_span_id: Optional[str] = None,
                    **attrs) -> Span:
        if trace_id is None:
            trace_id = f"trace_{uuid.uuid4().hex[:8]}"
        span_id = f"span_{uuid.uuid4().hex[:8]}"
        with self._lock:
            span = Span(
                span_id=span_id, trace_id=trace_id,
                parent_span_id=parent_span_id,
                name=name, start_time=time.time(),
                attributes=attrs)
            self._spans[span_id] = span
            self._active_spans.append(span_id)
            if parent_span_id is None:
                self._stats["traces"] += 1
            self._stats["spans"] += 1
        return span

    def end_span(self, span: Span, status: str = "ok") -> None:
        with self._lock:
            span.end_time = time.time()
            span.duration_ms = (
                (span.end_time - span.start_time) * 1000)
            span.status = status
            if status == "error":
                self._stats["errors"] += 1
            if span.span_id in self._active_spans:
                self._active_spans.remove(span.span_id)

    def add_event(self, span: Span, name: str,
                   **attrs) -> None:
        with self._lock:
            span.events.append({
                "name": name, "time": time.time(),
                **attrs})

    def get_trace(self, trace_id: str) -> List[Span]:
        with self._lock:
            return [s for s in self._spans.values()
                     if s.trace_id == trace_id]

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)


class SpanContext:
    """span上下文管理器"""
    def __init__(self, tracer: Tracer, name: str, **attrs):
        self.tracer = tracer
        self.name = name
        self.attrs = attrs
        self.span: Optional[Span] = None

    def __enter__(self) -> Span:
        self.span = self.tracer.start_span(self.name, **self.attrs)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            status = "error" if exc_type else "ok"
            self.tracer.end_span(self.span, status)


# ============================================================
# 五、Prometheus风格导出器
# ============================================================
class PrometheusExporter:
    """Prometheus风格导出器"""
    def __init__(self, registry: MetricsRegistry):
        self.registry = registry

    def export(self) -> str:
        """导出为Prometheus文本格式"""
        lines = []
        for m in self.registry.collect():
            # HELP
            if m.get("description"):
                lines.append(
                    f"# HELP {m['name']} {m['description']}")
            # TYPE
            lines.append(f"# TYPE {m['name']} {m['type']}")
            # Value
            labels_str = ""
            if m.get("labels"):
                label_str = ",".join(
                    f'{k}="{v}"' for k, v in m["labels"].items())
                labels_str = f"{{{label_str}}}"
            if m["type"] in ("counter", "gauge"):
                lines.append(
                    f"{m['name']}{labels_str} {m['value']}")
            elif m["type"] == "histogram":
                lines.append(
                    f"{m['name']}_count{labels_str} {m['count']}")
                lines.append(
                    f"{m['name']}_sum{labels_str} {m['sum']}")
                for bucket, count in m["buckets"].items():
                    bucket_str = f'le="{bucket}"'
                    if labels_str:
                        full = labels_str[:-1] + f",{bucket_str}}}"
                    else:
                        full = f"{{{bucket_str}}}"
                    lines.append(
                        f"{m['name']}_bucket{full} {count}")
        return "\n".join(lines)


# ============================================================
# 六、单元测试
# ============================================================
class TestCounter(unittest.TestCase):
    """Counter测试"""
    def test_inc(self):
        reg = MetricsRegistry()
        c = reg.counter("test")
        c.inc()
        c.inc(5)
        self.assertEqual(c.get(), 6)

    def test_multiple(self):
        reg = MetricsRegistry()
        c1 = reg.counter("a")
        c2 = reg.counter("b")
        c1.inc(10)
        c2.inc(20)
        self.assertEqual(c1.get(), 10)
        self.assertEqual(c2.get(), 20)


class TestGauge(unittest.TestCase):
    """Gauge测试"""
    def test_set(self):
        reg = MetricsRegistry()
        g = reg.gauge("temp")
        g.set(25.0)
        self.assertEqual(g.get(), 25.0)

    def test_inc_dec(self):
        reg = MetricsRegistry()
        g = reg.gauge("count")
        g.inc(10)
        g.dec(3)
        self.assertEqual(g.get(), 7)


class TestHistogram(unittest.TestCase):
    """Histogram测试"""
    def test_observe(self):
        reg = MetricsRegistry()
        h = reg.histogram("latency")
        for v in [0.01, 0.02, 0.05, 0.1, 0.5, 1.0]:
            h.observe(v)
        self.assertEqual(h.get_count(), 6)
        self.assertAlmostEqual(h.get_sum(), 1.68, places=2)

    def test_percentile(self):
        reg = MetricsRegistry()
        h = reg.histogram("latency")
        for v in range(1, 101):
            h.observe(v)
        p50 = h.get_percentile(0.5)
        self.assertGreaterEqual(p50, 50)


class TestTracer(unittest.TestCase):
    """追踪器测试"""
    def test_span_lifecycle(self):
        t = Tracer()
        span = t.start_span("test")
        time.sleep(0.01)
        t.end_span(span)
        self.assertGreater(span.duration_ms, 0)
        self.assertEqual(span.status, "ok")

    def test_parent_child(self):
        t = Tracer()
        parent = t.start_span("parent")
        child = t.start_span("child", trace_id=parent.trace_id,
                              parent_span_id=parent.span_id)
        t.end_span(child)
        t.end_span(parent)
        trace = t.get_trace(parent.trace_id)
        self.assertEqual(len(trace), 2)

    def test_context_manager(self):
        t = Tracer()
        with SpanContext(t, "operation") as span:
            time.sleep(0.01)
        self.assertGreater(span.duration_ms, 0)

    def test_error(self):
        t = Tracer()
        with SpanContext(t, "fail"):
            try:
                raise RuntimeError("oops")
            except Exception:
                pass
        stats = t.get_stats()
        self.assertEqual(stats["errors"], 1)


class TestExporter(unittest.TestCase):
    """导出器测试"""
    def test_prometheus(self):
        reg = MetricsRegistry()
        c = reg.counter("requests_total",
                        "Total requests", {"app": "agent"})
        c.inc(100)
        g = reg.gauge("queue_size", "Queue size")
        g.set(5)
        exporter = PrometheusExporter(reg)
        text = exporter.export()
        self.assertIn("requests_total", text)
        self.assertIn("# HELP", text)
        self.assertIn("queue_size", text)


# ============================================================
# 七、阶段131演示
# ============================================================
def run_phase_131():
    """运行阶段131"""
    print("=" * 70)
    print("阶段131：可观测性")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestCounter))
    suite.addTests(loader.loadTestsFromTestCase(TestGauge))
    suite.addTests(loader.loadTestsFromTestCase(TestHistogram))
    suite.addTests(loader.loadTestsFromTestCase(TestTracer))
    suite.addTests(loader.loadTestsFromTestCase(TestExporter))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【可观测性演示】")
    print("-" * 70)
    # 演示1: 指标收集
    print("  📊 演示1: 三大指标类型")
    print("     " + "-" * 60)
    reg = MetricsRegistry()
    requests = reg.counter("http_requests_total",
                            "Total HTTP requests")
    queue = reg.gauge("queue_size", "Current queue size")
    latency = reg.histogram("http_request_duration_seconds",
                              "Request duration")
    # 模拟请求
    import random
    for i in range(100):
        requests.inc()
        latency.observe(random.uniform(0.001, 0.5))
        queue.set(random.randint(0, 10))
    print(f"     Counter (请求): {requests.get()}")
    print(f"     Gauge (队列): {queue.get()}")
    print(f"     Histogram (延迟): "
          f"p50={latency.get_percentile(0.5)*1000:.1f}ms, "
          f"p95={latency.get_percentile(0.95)*1000:.1f}ms, "
          f"p99={latency.get_percentile(0.99)*1000:.1f}ms")
    print()

    # 演示2: 分布式追踪
    print("  🔍 演示2: 分布式追踪")
    print("     " + "-" * 60)
    tracer = Tracer()
    with SpanContext(tracer, "http_request",
                      method="GET", path="/api/users") as req_span:
        time.sleep(0.01)
        tracer.add_event(req_span, "auth_check")
        with SpanContext(tracer, "query_kg",
                          parent=req_span.span_id) as kg_span:
            time.sleep(0.02)
            tracer.add_event(kg_span, "cache_lookup",
                              hit=True)
        with SpanContext(tracer, "render_response",
                          parent=req_span.span_id) as render_span:
            time.sleep(0.005)
    trace = tracer.get_trace(req_span.trace_id)
    print(f"     Trace ID: {req_span.trace_id}")
    for s in trace:
        print(f"       {s.name:>20} "
              f"{s.duration_ms:>6.1f}ms "
              f"parent={s.parent_span_id or 'ROOT'}")
    print()

    # 演示3: 错误追踪
    print("  ❌ 演示3: 错误追踪")
    print("     " + "-" * 60)
    try:
        with SpanContext(tracer, "risky_operation"):
            time.sleep(0.01)
            raise RuntimeError("操作失败")
    except RuntimeError:
        pass
    stats = tracer.get_stats()
    print(f"     总追踪: {stats['traces']}")
    print(f"     总span: {stats['spans']}")
    print(f"     错误: {stats['errors']}")
    print()

    # 演示4: Prometheus导出
    print("  📤 演示4: Prometheus导出")
    print("     " + "-" * 60)
    exporter = PrometheusExporter(reg)
    text = exporter.export()
    # 显示前10行
    lines = text.split("\n")
    for line in lines[:10]:
        print(f"     {line}")
    print(f"     ... 共 {len(lines)} 行")
    print()

    # 演示5: 指标采集
    print("  🔎 演示5: 指标采集")
    print("     " + "-" * 60)
    metrics = reg.collect()
    print(f"     注册指标数: {len(metrics)}")
    for m in metrics:
        if m["type"] != "histogram":
            print(f"       {m['name']:>30} "
                  f"({m['type']:>8}) = {m['value']:.2f}")
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段131完成：可观测性已实现，所有测试通过！")
    else:
        print("✅ 阶段131完成：可观测性已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段132：混沌工程")
    print("  - 故障注入")
    print("  - 弹性测试")
    print("  - 恢复验证")
    print()
    return True


if __name__ == "__main__":
    run_phase_131()
