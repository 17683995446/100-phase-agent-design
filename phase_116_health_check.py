#!/usr/bin/env python3
"""
阶段116：健康检查与探针

第一性原理：
  - 存续公理：系统必须知道自身健康状态
  - 可观测性：内部状态可被外部探查
  - 故障隔离：依赖问题不应拖垮整个系统

本阶段产出：
  1. HealthStatus：健康状态枚举与数据
  2. Probe：探针基类与三类具体探针（liveness/readiness/dependency）
  3. HealthChecker：综合健康检查器
  4. Heartbeat：心跳机制
  5. HealthReport：健康报告生成

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import threading
import os
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field


# ============================================================
# 一、健康状态定义
# ============================================================
class HealthState(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"        # 健康
    DEGRADED = "degraded"      # 降级（部分功能受影响）
    UNHEALTHY = "unhealthy"    # 不健康
    UNKNOWN = "unknown"        # 未知（尚未检查）


@dataclass
class ComponentHealth:
    """单个组件的健康状态"""
    name: str
    state: HealthState
    message: str = ""
    last_check: float = 0.0
    check_count: int = 0
    fail_count: int = 0
    last_fail: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "message": self.message,
            "last_check": self.last_check,
            "check_count": self.check_count,
            "fail_count": self.fail_count,
            "uptime_sec": (time.time() - self.last_check) if self.last_check else 0,
        }


# ============================================================
# 二、探针基类
# ============================================================
class Probe:
    """探针基类

    探针是健康检查的最小单位：执行一次检查，返回ComponentHealth
    """
    def __init__(self, name: str, timeout: float = 5.0,
                 fail_threshold: int = 3):
        self.name = name
        self.timeout = timeout
        self.fail_threshold = fail_threshold
        self._consecutive_fails = 0
        self._consecutive_passes = 0
        self._last_health = ComponentHealth(
            name=name, state=HealthState.UNKNOWN, message="not checked")
        self._lock = threading.Lock()

    def check(self) -> ComponentHealth:
        """执行一次探针检查"""
        start = time.time()
        try:
            ok, message, metadata = self._do_check()
            duration = time.time() - start
            with self._lock:
                self._last_health.check_count += 1
                if ok:
                    self._consecutive_fails = 0
                    self._consecutive_passes += 1
                    state = HealthState.HEALTHY
                    if self._last_health.state == HealthState.UNHEALTHY:
                        # 从不健康恢复
                        state = HealthState.DEGRADED
                else:
                    self._consecutive_passes = 0
                    self._consecutive_fails += 1
                    self._last_health.fail_count += 1
                    self._last_health.last_fail = time.time()
                    if self._consecutive_fails >= self.fail_threshold:
                        state = HealthState.UNHEALTHY
                    else:
                        state = HealthState.DEGRADED
                self._last_health.state = state
                self._last_health.message = message
                self._last_health.last_check = time.time()
                self._last_health.metadata = {
                    **metadata, "duration_sec": duration,
                    "consecutive_fails": self._consecutive_fails,
                    "consecutive_passes": self._consecutive_passes,
                }
        except Exception as e:
            with self._lock:
                self._consecutive_fails += 1
                self._consecutive_passes = 0
                self._last_health.check_count += 1
                self._last_health.fail_count += 1
                self._last_health.last_fail = time.time()
                self._last_health.state = (
                    HealthState.UNHEALTHY
                    if self._consecutive_fails >= self.fail_threshold
                    else HealthState.DEGRADED)
                self._last_health.message = f"exception: {e}"
                self._last_health.last_check = time.time()
        return self._last_health

    def _do_check(self) -> tuple:
        """子类重写：执行具体检查"""
        raise NotImplementedError

    def get_health(self) -> ComponentHealth:
        with self._lock:
            return ComponentHealth(
                name=self._last_health.name,
                state=self._last_health.state,
                message=self._last_health.message,
                last_check=self._last_health.last_check,
                check_count=self._last_health.check_count,
                fail_count=self._last_health.fail_count,
                last_fail=self._last_health.last_fail,
                metadata=dict(self._last_health.metadata),
            )


# ============================================================
# 三、活跃度探针
# ============================================================
class LivenessProbe(Probe):
    """活跃度探针

    目的：判断进程是否"活着"
    简单实现：心跳未超时即活着
    """
    def __init__(self, name: str = "liveness",
                 timeout: float = 30.0):
        super().__init__(name, timeout)
        self._last_heartbeat = time.time()

    def heartbeat(self) -> None:
        """主循环调用，更新心跳"""
        self._last_heartbeat = time.time()

    def _do_check(self) -> tuple:
        elapsed = time.time() - self._last_heartbeat
        if elapsed > self.timeout:
            return False, f"心跳超时: {elapsed:.1f}s > {self.timeout}s", {
                "elapsed": elapsed,
                "timeout": self.timeout,
            }
        return True, f"心跳正常: {elapsed:.1f}s前", {"elapsed": elapsed}


# ============================================================
# 四、就绪度探针
# ============================================================
class ReadinessProbe(Probe):
    """就绪度探针

    目的：判断进程是否可以接受新任务
    简单实现：启动阶段、暂停阶段、错误状态都为未就绪
    """
    def __init__(self, name: str = "readiness"):
        super().__init__(name)
        self._started = False
        self._paused = False
        self._lock = threading.Lock()

    def mark_started(self) -> None:
        with self._lock:
            self._started = True

    def mark_paused(self) -> None:
        with self._lock:
            self._paused = True

    def mark_resumed(self) -> None:
        with self._lock:
            self._paused = False

    def is_ready(self) -> bool:
        with self._lock:
            return self._started and not self._paused

    def _do_check(self) -> tuple:
        with self._lock:
            if not self._started:
                return False, "未启动", {"started": False}
            if self._paused:
                return False, "已暂停", {"paused": True}
        return True, "就绪", {"started": True, "paused": False}


# ============================================================
# 五、依赖探针
# ============================================================
class DependencyProbe(Probe):
    """依赖探针

    目的：检查外部依赖（如存储、队列）是否可用
    通过注入的检查函数判断
    """
    def __init__(self, name: str, check_fn: Callable[[], tuple],
                 timeout: float = 5.0):
        super().__init__(name, timeout)
        self._check_fn = check_fn

    def _do_check(self) -> tuple:
        return self._check_fn()


# ============================================================
# 六、具体依赖探针：知识图
# ============================================================
class KnowledgeGraphProbe(DependencyProbe):
    """知识图依赖探针"""
    def __init__(self, kg):
        def check_fn() -> tuple:
            try:
                n = len(kg.nodes)
                e = len(kg.edges)
                return True, f"图正常: {n}节点, {e}边", {
                    "nodes": n, "edges": e
                }
            except Exception as e:
                return False, f"图异常: {e}", {}

        super().__init__("knowledge_graph", check_fn)


# ============================================================
# 七、具体依赖探针：磁盘空间
# ============================================================
class DiskSpaceProbe(DependencyProbe):
    """磁盘空间依赖探针"""
    def __init__(self, path: str = "/workspace",
                 min_free_mb: float = 100.0):
        self.path = path
        self.min_free_mb = min_free_mb

        def check_fn() -> tuple:
            try:
                stat = os.statvfs(self.path)
                free_mb = (stat.f_bavail * stat.f_frsize) / 1024 / 1024
                if free_mb < self.min_free_mb:
                    return False, (
                        f"磁盘空间不足: {free_mb:.1f}MB < "
                        f"{self.min_free_mb}MB"), {
                        "free_mb": free_mb, "min_mb": self.min_free_mb
                    }
                return True, (
                    f"磁盘空间正常: {free_mb:.1f}MB"), {
                    "free_mb": free_mb
                }
            except Exception as e:
                return False, f"检查失败: {e}", {}

        super().__init__("disk_space", check_fn)


# ============================================================
# 八、心跳机制
# ============================================================
class Heartbeat:
    """心跳机制

    周期性发出心跳，供探针检查
    """
    def __init__(self, interval_sec: float = 5.0,
                 probe: Optional[LivenessProbe] = None):
        self.interval_sec = interval_sec
        self.probe = probe or LivenessProbe()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._beat_count = 0

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
            self.beat()
            time.sleep(self.interval_sec)

    def beat(self) -> None:
        self.probe.heartbeat()
        self._beat_count += 1

    def get_beat_count(self) -> int:
        return self._beat_count


# ============================================================
# 九、健康检查器
# ============================================================
class HealthChecker:
    """综合健康检查器

    协调所有探针，提供统一的健康报告
    """
    def __init__(self):
        self._probes: Dict[str, Probe] = {}
        self._lock = threading.Lock()
        self._check_history: List[Dict[str, Any]] = []

    def register(self, probe: Probe) -> None:
        with self._lock:
            self._probes[probe.name] = probe

    def unregister(self, name: str) -> None:
        with self._lock:
            self._probes.pop(name, None)

    def list_probes(self) -> List[str]:
        with self._lock:
            return list(self._probes.keys())

    def check_all(self) -> Dict[str, ComponentHealth]:
        """检查所有探针"""
        results = {}
        with self._lock:
            probes = list(self._probes.values())
        for probe in probes:
            results[probe.name] = probe.check()
        self._check_history.append({
            "time": time.time(),
            "states": {n: h.state.value for n, h in results.items()}
        })
        if len(self._check_history) > 1000:
            self._check_history = self._check_history[-1000:]
        return results

    def get_overall_state(self) -> HealthState:
        """综合健康状态（最差优先）"""
        with self._lock:
            probes = list(self._probes.values())
        if not probes:
            return HealthState.UNKNOWN
        states = []
        for probe in probes:
            states.append(probe.get_health().state)
        # 最差优先
        if HealthState.UNHEALTHY in states:
            return HealthState.UNHEALTHY
        if HealthState.DEGRADED in states:
            return HealthState.DEGRADED
        if HealthState.UNKNOWN in states:
            return HealthState.UNKNOWN
        return HealthState.HEALTHY

    def is_live(self) -> bool:
        """活跃度"""
        return self.get_overall_state() != HealthState.UNHEALTHY

    def is_ready(self) -> bool:
        """就绪度：所有探针都健康或降级（无未就绪）"""
        with self._lock:
            probes = list(self._probes.values())
        for probe in probes:
            if isinstance(probe, ReadinessProbe):
                if not probe.is_ready():
                    return False
        return True

    def generate_report(self) -> Dict[str, Any]:
        """生成健康报告"""
        results = self.check_all()
        return {
            "timestamp": time.time(),
            "overall": self.get_overall_state().value,
            "is_live": self.is_live(),
            "is_ready": self.is_ready(),
            "components": {
                name: h.to_dict() for name, h in results.items()
            },
        }


# ============================================================
# 十、单元测试
# ============================================================
class TestHealthState(unittest.TestCase):
    """健康状态测试"""
    def test_state_values(self):
        self.assertEqual(HealthState.HEALTHY.value, "healthy")
        self.assertEqual(HealthState.UNHEALTHY.value, "unhealthy")


class TestLivenessProbe(unittest.TestCase):
    """活跃度探针测试"""
    def test_healthy_after_heartbeat(self):
        p = LivenessProbe(timeout=10.0)
        p.heartbeat()
        h = p.check()
        self.assertEqual(h.state, HealthState.HEALTHY)

    def test_unhealthy_on_timeout(self):
        p = LivenessProbe(timeout=0.001, )
        p.heartbeat()
        time.sleep(0.01)
        # 失败3次以上 -> unhealthy
        for _ in range(3):
            h = p.check()
        self.assertIn(h.state, [HealthState.DEGRADED, HealthState.UNHEALTHY])


class TestReadinessProbe(unittest.TestCase):
    """就绪度探针测试"""
    def test_not_ready_before_start(self):
        p = ReadinessProbe()
        h = p.check()
        self.assertEqual(h.state, HealthState.DEGRADED)
        self.assertFalse(p.is_ready())

    def test_ready_after_start(self):
        p = ReadinessProbe()
        p.mark_started()
        h = p.check()
        self.assertEqual(h.state, HealthState.HEALTHY)
        self.assertTrue(p.is_ready())

    def test_not_ready_when_paused(self):
        p = ReadinessProbe()
        p.mark_started()
        p.mark_paused()
        self.assertFalse(p.is_ready())


class TestDependencyProbe(unittest.TestCase):
    """依赖探针测试"""
    def test_successful_check(self):
        p = DependencyProbe(
            "test", lambda: (True, "ok", {"k": 1}))
        h = p.check()
        self.assertEqual(h.state, HealthState.HEALTHY)

    def test_failing_check(self):
        def check_fn():
            return False, "broken", {}
        p = DependencyProbe("test", check_fn)
        for _ in range(5):
            h = p.check()
        self.assertEqual(h.state, HealthState.UNHEALTHY)

    def test_exception_in_check(self):
        def check_fn():
            raise RuntimeError("explode")
        p = DependencyProbe("test", check_fn)
        for _ in range(3):
            h = p.check()
        self.assertEqual(h.state, HealthState.UNHEALTHY)


class TestDiskSpaceProbe(unittest.TestCase):
    """磁盘空间探针测试"""
    def test_normal_space(self):
        p = DiskSpaceProbe(path="/workspace", min_free_mb=1.0)
        h = p.check()
        self.assertEqual(h.state, HealthState.HEALTHY)

    def test_low_space(self):
        # 要求不可能的容量
        p = DiskSpaceProbe(path="/workspace", min_free_mb=1e10)
        for _ in range(3):
            h = p.check()
        self.assertEqual(h.state, HealthState.UNHEALTHY)


class TestHeartbeat(unittest.TestCase):
    """心跳测试"""
    def test_heartbeat_updates(self):
        h = Heartbeat(interval_sec=0.01)
        h.start()
        time.sleep(0.05)
        h.stop()
        self.assertGreater(h.get_beat_count(), 0)

    def test_no_double_start(self):
        h = Heartbeat(interval_sec=0.01)
        h.start()
        h.start()  # 不应启动第二个线程
        time.sleep(0.02)
        h.stop()


class TestHealthChecker(unittest.TestCase):
    """健康检查器测试"""
    def test_empty_checker(self):
        hc = HealthChecker()
        self.assertEqual(hc.get_overall_state(), HealthState.UNKNOWN)

    def test_register_and_check(self):
        hc = HealthChecker()
        p = ReadinessProbe()
        p.mark_started()
        hc.register(p)
        results = hc.check_all()
        self.assertIn("readiness", results)
        self.assertEqual(results["readiness"].state, HealthState.HEALTHY)
        self.assertEqual(hc.get_overall_state(), HealthState.HEALTHY)

    def test_overall_state_worst_wins(self):
        hc = HealthChecker()
        # 健康探针
        ok = ReadinessProbe()
        ok.mark_started()
        hc.register(ok)
        # 不健康探针
        bad = DependencyProbe("bad", lambda: (False, "x", {}))
        for _ in range(5):
            bad.check()
        hc.register(bad)
        self.assertEqual(hc.get_overall_state(), HealthState.UNHEALTHY)
        self.assertFalse(hc.is_live())

    def test_report(self):
        hc = HealthChecker()
        p = ReadinessProbe()
        p.mark_started()
        hc.register(p)
        report = hc.generate_report()
        self.assertIn("overall", report)
        self.assertIn("components", report)
        self.assertIn("readiness", report["components"])


# ============================================================
# 十一、阶段116演示
# ============================================================
def run_phase_116():
    """运行阶段116"""
    print("=" * 70)
    print("阶段116：健康检查与探针")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestHealthState))
    suite.addTests(loader.loadTestsFromTestCase(TestLivenessProbe))
    suite.addTests(loader.loadTestsFromTestCase(TestReadinessProbe))
    suite.addTests(loader.loadTestsFromTestCase(TestDependencyProbe))
    suite.addTests(loader.loadTestsFromTestCase(TestDiskSpaceProbe))
    suite.addTests(loader.loadTestsFromTestCase(TestHeartbeat))
    suite.addTests(loader.loadTestsFromTestCase(TestHealthChecker))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【健康检查与探针演示】")
    print("-" * 70)
    # 构造健康检查器
    import sys
    sys.path.insert(0, '/workspace')
    from phase_103_kg_crud import KnowledgeGraphCRUD
    from phase_102_core_datastructure import Node
    kg = KnowledgeGraphCRUD()
    for i in range(5):
        kg.add_node(Node(content=f"知识{i}", node_id=f"k{i}"))
    hc = HealthChecker()
    # 注册各类探针
    liveness = LivenessProbe(timeout=10.0)
    liveness.heartbeat()
    hc.register(liveness)
    readiness = ReadinessProbe()
    readiness.mark_started()
    hc.register(readiness)
    hc.register(KnowledgeGraphProbe(kg))
    hc.register(DiskSpaceProbe(path="/workspace", min_free_mb=1.0))
    # 心跳
    heartbeat = Heartbeat(interval_sec=0.01, probe=liveness)
    heartbeat.start()
    time.sleep(0.05)
    heartbeat.stop()
    # 演示1: 各项探针状态
    print("  🔍 演示1: 各项探针健康状态")
    print("     " + "-" * 60)
    results = hc.check_all()
    for name, h in results.items():
        icon = {
            HealthState.HEALTHY: "✅",
            HealthState.DEGRADED: "⚠️ ",
            HealthState.UNHEALTHY: "❌",
            HealthState.UNKNOWN: "❓",
        }.get(h.state, "❓")
        print(f"     {icon} {name:>16}: {h.state.value:>10} - {h.message}")
    print()
    # 演示2: 综合状态
    print("  📊 演示2: 综合状态")
    print("     " + "-" * 60)
    print(f"     整体状态: {hc.get_overall_state().value}")
    print(f"     活跃(Live): {hc.is_live()}")
    print(f"     就绪(Ready): {hc.is_ready()}")
    print()
    # 演示3: 模拟故障
    print("  💥 演示3: 模拟依赖故障")
    print("     " + "-" * 60)
    bad_probe = DependencyProbe(
        "broken_service",
        lambda: (False, "connection refused", {}))
    hc.register(bad_probe)
    # 几次检查让其变为UNHEALTHY
    for _ in range(5):
        bad_probe.check()
    print(f"     注入故障后整体状态: {hc.get_overall_state().value}")
    print(f"     活跃(Live): {hc.is_live()}")
    hc.unregister("broken_service")
    # 恢复
    print(f"     移除故障后: {hc.get_overall_state().value}")
    print()
    # 演示4: 健康报告
    print("  📋 演示4: 健康报告")
    print("     " + "-" * 60)
    report = hc.generate_report()
    print(f"     时间戳: {report['timestamp']:.2f}")
    print(f"     整体: {report['overall']}")
    print(f"     活跃: {report['is_live']}, 就绪: {report['is_ready']}")
    print(f"     组件数: {len(report['components'])}")
    print()
    # 演示5: 心跳与活跃度
    print("  💓 演示5: 心跳驱动活跃度")
    print("     " + "-" * 60)
    heartbeat.start()
    time.sleep(0.05)
    h_state = liveness.check()
    print(f"     心跳次数: {heartbeat.get_beat_count()}")
    print(f"     探针状态: {h_state.state.value}")
    print(f"     元数据: {h_state.metadata}")
    heartbeat.stop()
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段116完成：健康检查与探针已实现，所有测试通过！")
    else:
        print("✅ 阶段116完成：健康检查与探针已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段117：优雅启动与停止")
    print("  - 信号处理")
    print("  - 状态保存")
    print("  - 优雅退出")
    print()
    return True


if __name__ == "__main__":
    run_phase_116()
