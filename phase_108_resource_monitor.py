#!/usr/bin/env python3
"""
阶段108：资源监控

第一性原理：
  - 存续公理：必须能感知自己的资源状态
  - 可见性：系统的状态对外部必须可观测
  - 主动性：资源紧张时系统应主动调整

本阶段产出：
  1. ResourceMonitor：CPU/内存/磁盘/文件句柄监控
  2. MetricsCollector：自定义指标采集
  3. AlertManager：阈值告警
  4. MetricsExporter：指标导出（JSON/Prometheus格式）

遵循原则：图难于其易，为大于其细
"""
import os
import time
import json
import unittest
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from collections import deque
from enum import Enum


# ============================================================
# 一、资源采样器
# ============================================================
class ResourceSampler:
    """资源采样器

    使用 /proc/self/* 读取Linux进程自身资源
    （避免引入psutil等外部依赖）
    """
    @staticmethod
    def sample_memory_mb() -> float:
        """采样内存占用（MB）"""
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        kb = float(line.split()[1])
                        return kb / 1024.0
        except (FileNotFoundError, ValueError):
            pass
        return 0.0

    @staticmethod
    def sample_memory_percent() -> float:
        """采样内存占用百分比"""
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss = float(line.split()[1])  # KB
                    if line.startswith("VmHWM:"):
                        hwm = float(line.split()[1])  # KB
            return (rss / hwm * 100) if hwm > 0 else 0
        except (FileNotFoundError, ValueError, UnboundLocalError):
            return 0.0

    @staticmethod
    def sample_cpu_seconds() -> float:
        """采样CPU使用时间（秒）"""
        try:
            with open("/proc/self/stat") as f:
                parts = f.read().split()
                # utime + stime
                utime = float(parts[13])
                stime = float(parts[14])
                return (utime + stime) / 100.0  # clock ticks -> sec
        except (FileNotFoundError, ValueError, IndexError):
            return 0.0

    @staticmethod
    def sample_fds() -> int:
        """采样文件句柄数"""
        try:
            return len(os.listdir("/proc/self/fd"))
        except (FileNotFoundError, OSError):
            return 0

    @staticmethod
    def sample_disk_usage(path: str = ".") -> Dict[str, float]:
        """采样磁盘使用"""
        try:
            stat = os.statvfs(path)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            return {
                "total_mb": total / 1024 / 1024,
                "used_mb": used / 1024 / 1024,
                "free_mb": free / 1024 / 1024,
                "usage_pct": (used / total * 100) if total > 0 else 0
            }
        except (OSError, AttributeError):
            return {"total_mb": 0, "used_mb": 0,
                    "free_mb": 0, "usage_pct": 0}


# ============================================================
# 二、告警级别
# ============================================================
class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ============================================================
# 三、告警
# ============================================================
@dataclass
class Alert:
    level: str
    metric: str
    value: float
    threshold: float
    message: str
    timestamp: float = field(default_factory=time.time)


# ============================================================
# 四、资源监控器
# ============================================================
class ResourceMonitor:
    """资源监控器

    持续采样并检查告警
    """
    DEFAULT_THRESHOLDS = {
        "memory_mb": {"warning": 100, "critical": 200},
        "memory_pct": {"warning": 60, "critical": 80},
        "cpu_pct": {"warning": 70, "critical": 90},
        "fd_count": {"warning": 500, "critical": 1000},
        "disk_pct": {"warning": 80, "critical": 95},
    }

    def __init__(self, sample_interval: float = 5.0,
                 thresholds: Optional[Dict] = None,
                 history_size: int = 720):  # 1小时@5s
        self.sample_interval = sample_interval
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self.history: deque = deque(maxlen=history_size)
        self.alerts: deque = deque(maxlen=100)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_cpu_time = 0.0
        self._last_sample_time = 0.0
        self._lock = threading.Lock()
        self._alert_callbacks: List[Callable] = []

    def on_alert(self, callback: Callable) -> None:
        """注册告警回调"""
        self._alert_callbacks.append(callback)

    def start(self) -> None:
        """启动后台采样"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sampling_loop,
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止采样"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _sampling_loop(self) -> None:
        """采样循环"""
        while self._running:
            try:
                self.sample_once()
            except Exception:
                pass
            time.sleep(self.sample_interval)

    def sample_once(self) -> Dict[str, Any]:
        """执行一次采样"""
        now = time.time()
        cpu_total = ResourceSampler.sample_cpu_seconds()
        if self._last_sample_time > 0:
            elapsed = now - self._last_sample_time
            cpu_delta = cpu_total - self._last_cpu_time
            cpu_pct = (cpu_delta / elapsed * 100) if elapsed > 0 else 0
        else:
            cpu_pct = 0.0
        self._last_cpu_time = cpu_total
        self._last_sample_time = now

        sample = {
            "timestamp": now,
            "memory_mb": ResourceSampler.sample_memory_mb(),
            "memory_pct": ResourceSampler.sample_memory_percent(),
            "cpu_pct": cpu_pct,
            "fd_count": ResourceSampler.sample_fds(),
            "disk": ResourceSampler.sample_disk_usage()
        }
        with self._lock:
            self.history.append(sample)
        self._check_alerts(sample)
        return sample

    def _check_alerts(self, sample: Dict[str, Any]) -> None:
        """检查并触发告警"""
        for metric, thresholds in self.thresholds.items():
            if metric == "disk_pct":
                value = sample.get("disk", {}).get("usage_pct", 0)
            elif metric == "fd_count":
                value = sample.get("fd_count", 0)
            else:
                value = sample.get(metric, 0)
            if value >= thresholds.get("critical", float("inf")):
                self._trigger_alert(AlertLevel.CRITICAL, metric,
                                    value, thresholds["critical"])
            elif value >= thresholds.get("warning", float("inf")):
                self._trigger_alert(AlertLevel.WARNING, metric,
                                    value, thresholds["warning"])

    def _trigger_alert(self, level: AlertLevel, metric: str,
                       value: float, threshold: float) -> None:
        """触发告警"""
        msg = f"{level.value.upper()}: {metric}={value:.2f} >= {threshold}"
        alert = Alert(
            level=level.value, metric=metric, value=value,
            threshold=threshold, message=msg
        )
        with self._lock:
            self.alerts.append(alert)
        for cb in self._alert_callbacks:
            try:
                cb(alert)
            except Exception:
                pass

    def get_current(self) -> Dict[str, Any]:
        """获取最新采样"""
        with self._lock:
            if self.history:
                return dict(self.history[-1])
        return {}

    def get_summary(self) -> Dict[str, Any]:
        """获取摘要统计"""
        with self._lock:
            if not self.history:
                return {}
            mem_vals = [s["memory_mb"] for s in self.history]
            cpu_vals = [s["cpu_pct"] for s in self.history]
            return {
                "samples": len(self.history),
                "memory_mb": {
                    "current": mem_vals[-1],
                    "max": max(mem_vals),
                    "avg": sum(mem_vals) / len(mem_vals)
                },
                "cpu_pct": {
                    "current": cpu_vals[-1],
                    "max": max(cpu_vals),
                    "avg": sum(cpu_vals) / len(cpu_vals)
                },
                "alerts": len(self.alerts)
            }


# ============================================================
# 五、自定义指标采集器
# ============================================================
class MetricsCollector:
    """自定义指标采集器

    允许业务代码注册自己的指标
    """
    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def inc(self, name: str, value: int = 1) -> None:
        """递增计数器"""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def dec(self, name: str, value: int = 1) -> None:
        """递减计数器"""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) - value

    def gauge(self, name: str, value: float) -> None:
        """设置仪表值"""
        with self._lock:
            self._gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        """记录直方图观测值"""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(value)
            if len(self._histograms[name]) > 1000:
                self._histograms[name] = self._histograms[name][-1000:]

    def snapshot(self) -> Dict[str, Any]:
        """获取所有指标的快照"""
        with self._lock:
            histo_summary = {}
            for name, values in self._histograms.items():
                if values:
                    histo_summary[name] = {
                        "count": len(values),
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                    }
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": histo_summary,
                "snapshot_at": time.time()
            }


# ============================================================
# 六、指标导出器
# ============================================================
class MetricsExporter:
    """指标导出器

    支持 JSON 和 Prometheus 文本格式
    """
    @staticmethod
    def to_json(metrics: Dict[str, Any]) -> str:
        return json.dumps(metrics, ensure_ascii=False, indent=2)

    @staticmethod
    def to_prometheus(metrics: Dict[str, Any]) -> str:
        """转换为 Prometheus 文本格式"""
        lines = []
        for name, value in metrics.get("counters", {}).items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        for name, value in metrics.get("gauges", {}).items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        for name, hist in metrics.get("histograms", {}).items():
            lines.append(f"# TYPE {name} summary")
            lines.append(f"{name}_count {hist['count']}")
            lines.append(f"{name}_avg {hist['avg']:.4f}")
            lines.append(f"{name}_max {hist['max']:.4f}")
        return "\n".join(lines)


# ============================================================
# 七、单元测试
# ============================================================
class TestResourceSampler(unittest.TestCase):
    """资源采样器测试"""
    def test_memory_sample(self):
        m = ResourceSampler.sample_memory_mb()
        self.assertGreater(m, 0)
        self.assertLess(m, 10000)  # 不应超过10GB

    def test_cpu_sample(self):
        c = ResourceSampler.sample_cpu_seconds()
        self.assertGreaterEqual(c, 0)

    def test_fds_sample(self):
        fds = ResourceSampler.sample_fds()
        self.assertGreater(fds, 0)

    def test_disk_sample(self):
        d = ResourceSampler.sample_disk_usage(".")
        self.assertIn("total_mb", d)
        self.assertIn("used_mb", d)


class TestResourceMonitor(unittest.TestCase):
    """资源监控器测试"""
    def test_sample_once(self):
        monitor = ResourceMonitor()
        sample = monitor.sample_once()
        self.assertIn("memory_mb", sample)
        self.assertIn("cpu_pct", sample)
        self.assertIn("timestamp", sample)

    def test_history(self):
        monitor = ResourceMonitor()
        for _ in range(3):
            monitor.sample_once()
        self.assertEqual(len(monitor.history), 3)

    def test_alert_callback(self):
        monitor = ResourceMonitor(thresholds={
            "memory_mb": {"warning": 0.001, "critical": 0.001}
        })
        alerts_received = []
        monitor.on_alert(lambda a: alerts_received.append(a))
        monitor.sample_once()
        # 内存必然超过0.001MB，应该触发告警
        self.assertGreater(len(alerts_received), 0)

    def test_summary(self):
        monitor = ResourceMonitor()
        for _ in range(5):
            monitor.sample_once()
        summary = monitor.get_summary()
        self.assertIn("samples", summary)
        self.assertIn("memory_mb", summary)


class TestMetricsCollector(unittest.TestCase):
    """指标采集器测试"""
    def test_counter(self):
        c = MetricsCollector()
        c.inc("requests", 3)
        c.inc("requests", 2)
        snap = c.snapshot()
        self.assertEqual(snap["counters"]["requests"], 5)

    def test_gauge(self):
        c = MetricsCollector()
        c.gauge("temperature", 36.5)
        snap = c.snapshot()
        self.assertEqual(snap["gauges"]["temperature"], 36.5)

    def test_histogram(self):
        c = MetricsCollector()
        for v in [0.1, 0.2, 0.3, 0.4, 0.5]:
            c.observe("latency", v)
        snap = c.snapshot()
        self.assertEqual(snap["histograms"]["latency"]["count"], 5)
        self.assertEqual(snap["histograms"]["latency"]["avg"], 0.3)


class TestMetricsExporter(unittest.TestCase):
    """指标导出器测试"""
    def test_json_export(self):
        c = MetricsCollector()
        c.inc("hits", 10)
        s = MetricsExporter.to_json(c.snapshot())
        data = json.loads(s)
        self.assertIn("counters", data)

    def test_prometheus_export(self):
        c = MetricsCollector()
        c.inc("hits", 10)
        c.gauge("temp", 25.0)
        s = MetricsExporter.to_prometheus(c.snapshot())
        self.assertIn("hits 10", s)
        self.assertIn("temp 25.0", s)


# ============================================================
# 八、阶段108演示
# ============================================================
def run_phase_108():
    """运行阶段108"""
    print("=" * 70)
    print("阶段108：资源监控")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestResourceSampler))
    suite.addTests(loader.loadTestsFromTestCase(TestResourceMonitor))
    suite.addTests(loader.loadTestsFromTestCase(TestMetricsCollector))
    suite.addTests(loader.loadTestsFromTestCase(TestMetricsExporter))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    print()
    print("-" * 70)
    print("【资源监控演示】")
    print("-" * 70)
    monitor = ResourceMonitor(thresholds={
        "memory_mb": {"warning": 50, "critical": 100},
        "fd_count": {"warning": 100, "critical": 500},
    })
    metrics = MetricsCollector()
    alerts_log = []
    monitor.on_alert(lambda a: alerts_log.append(a))
    print("  📊 连续采样5次（每次模拟一些负载）:")
    for i in range(5):
        # 模拟一些负载
        data = [j * 0.001 for j in range(10000)]
        _ = sum(data)
        sample = monitor.sample_once()
        metrics.inc("cycles")
        metrics.observe("cycle_duration", sample.get("cpu_pct", 0))
        print(f"    [{i+1}] 内存={sample['memory_mb']:.1f}MB "
              f"CPU={sample['cpu_pct']:.1f}% "
              f"FDs={sample['fd_count']}")
    print()
    print("  🪞 资源摘要:")
    summary = monitor.get_summary()
    for k, v in summary.items():
        if isinstance(v, dict):
            print(f"    {k}: current={v.get('current', 0):.2f}, "
                  f"max={v.get('max', 0):.2f}, "
                  f"avg={v.get('avg', 0):.2f}")
        else:
            print(f"    {k}: {v}")
    print()
    print(f"  🚨 告警日志: 共{len(alerts_log)}条")
    for alert in alerts_log[-3:]:
        print(f"    - [{alert.level}] {alert.message}")
    print()
    print("  📤 Prometheus格式导出预览:")
    metrics.gauge("memory_mb", summary["memory_mb"]["current"])
    metrics.gauge("cpu_pct", summary["cpu_pct"]["current"])
    prom = MetricsExporter.to_prometheus(metrics.snapshot())
    for line in prom.split("\n")[:6]:
        print(f"    {line}")
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ 阶段108完成：资源监控已实现，所有测试通过！")
    else:
        print("❌ 阶段108失败")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段109：配置文件支持")
    print("  - YAML/JSON配置加载")
    print("  - 参数校验")
    print("  - 热加载")
    print("  - 默认值与降级")
    print()
    return result.wasSuccessful()


if __name__ == "__main__":
    run_phase_108()
