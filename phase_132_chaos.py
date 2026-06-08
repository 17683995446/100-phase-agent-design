#!/usr/bin/env python3
"""
阶段132：混沌工程

第一性原理：
  - 信任公理：未经故障验证的系统不可信
  - 假设驱动：先有稳态假设，再注入故障
  - 反脆弱：通过破坏获得韧性
  - 最小爆炸半径：实验失败时不影响生产
  - 持续验证：混沌是过程，不是事件

本阶段产出：
  1. ChaosType：故障类型枚举
  2. FaultInjector：故障注入器
  3. SteadyStateHypothesis：稳态假设
  4. ChaosExperiment：混沌实验
  5. ChaosResult：实验结果
  6. ChaosRunner：实验执行器
  7. CircuitBreaker：安全熔断器
  8. RecoveryValidator：恢复验证器
  9. ResilienceTest：端到端弹性测试

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import random
import threading
import uuid
import json
import gc
import sys
import traceback
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import deque, defaultdict
from contextlib import contextmanager


# ============================================================
# 一、故障类型与策略
# ============================================================
class ChaosType(Enum):
    """混沌故障类型"""
    LATENCY = "latency"               # 延迟注入
    ERROR = "error"                   # 错误注入
    EXCEPTION = "exception"           # 异常注入
    MEMORY_PRESSURE = "memory"        # 内存压力
    CPU_SPIKE = "cpu"                 # CPU尖峰
    DISK_PRESSURE = "disk"            # 磁盘压力
    NETWORK_PARTITION = "network"     # 网络分区
    RESOURCE_EXHAUSTION = "exhaustion"  # 资源耗尽
    RANDOM_FAIL = "random_fail"       # 随机失败
    TIMEOUT = "timeout"               # 超时


class ChaosIntensity(Enum):
    """故障强度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class ChaosPolicy:
    """混沌策略"""
    intensity: ChaosIntensity = ChaosIntensity.MEDIUM
    probability: float = 0.5         # 故障触发概率
    duration_s: float = 1.0          # 故障持续时间
    max_concurrent: int = 3          # 最大并发故障数
    cooldown_s: float = 0.1          # 故障之间冷却
    blast_radius: float = 0.1        # 爆炸半径（受影响请求比例）
    max_retries: int = 2             # 失败最大重试次数

    def validate(self) -> bool:
        if not 0.0 <= self.probability <= 1.0:
            return False
        if self.duration_s < 0 or self.max_concurrent < 0:
            return False
        return True

    def intensity_factor(self) -> float:
        factors = {
            ChaosIntensity.LOW: 0.25,
            ChaosIntensity.MEDIUM: 0.5,
            ChaosIntensity.HIGH: 0.75,
            ChaosIntensity.EXTREME: 1.0,
        }
        return factors[self.intensity]


# ============================================================
# 二、稳态假设
# ============================================================
@dataclass
class SteadyStateHypothesis:
    """稳态假设
    定义系统在正常情况下应满足的不变量。
    """
    name: str
    predicate: Callable[[], bool]            # 谓词：返回True表示稳态
    description: str = ""
    tolerance: float = 0.05                  # 容差：允许偏离的比例

    def check(self) -> bool:
        """检查稳态"""
        try:
            return bool(self.predicate())
        except Exception:
            return False

    def is_violated(self) -> bool:
        return not self.check()


# ============================================================
# 三、故障注入器
# ============================================================
class FaultInjector:
    """故障注入器
    通过包装函数，在调用时按概率注入故障。
    """
    def __init__(self, policy: ChaosPolicy):
        self._policy = policy
        self._lock = threading.RLock()
        self._stats = {
            "injections": 0,
            "skipped": 0,
            "by_type": defaultdict(int),
        }
        self._active_faults: Dict[str, Dict[str, Any]] = {}

    @property
    def policy(self) -> ChaosPolicy:
        return self._policy

    def set_policy(self, policy: ChaosPolicy) -> None:
        with self._lock:
            if not policy.validate():
                raise ValueError("Invalid chaos policy")
            self._policy = policy

    def should_inject(self) -> bool:
        """是否应该注入"""
        return random.random() < self._policy.probability

    def inject(self, fault_type: ChaosType) -> None:
        """主动注入一个故障（不绑定函数）"""
        with self._lock:
            self._stats["injections"] += 1
            self._stats["by_type"][fault_type.value] += 1
            self._active_faults[str(uuid.uuid4())] = {
                "type": fault_type,
                "start": time.time(),
                "policy_intensity": self._policy.intensity_factor(),
            }

    def wrap(self, func: Callable, fault_type: Optional[ChaosType] = None,
             *fault_types: ChaosType) -> Callable:
        """包装一个函数，在调用时注入故障"""
        all_types = [fault_type] + list(fault_types) if fault_type else list(fault_types)
        if not all_types:
            all_types = [ChaosType.ERROR]

        def wrapper(*args, **kwargs):
            if not self.should_inject():
                with self._lock:
                    self._stats["skipped"] += 1
                return func(*args, **kwargs)

            chosen = random.choice(all_types)
            self.inject(chosen)
            return self._apply_fault(chosen, func, args, kwargs)

        wrapper.__wrapped__ = func
        wrapper.__name__ = getattr(func, "__name__", "wrapped")
        return wrapper

    def _apply_fault(self, fault_type: ChaosType, func: Callable,
                     args: tuple, kwargs: dict) -> Any:
        """应用具体故障"""
        intensity = self._policy.intensity_factor()
        if fault_type == ChaosType.LATENCY:
            delay = self._policy.duration_s * intensity
            time.sleep(delay)
            return func(*args, **kwargs)
        if fault_type == ChaosType.ERROR:
            return None
        if fault_type == ChaosType.EXCEPTION:
            raise RuntimeError(f"混沌异常: {fault_type.value}")
        if fault_type == ChaosType.TIMEOUT:
            time.sleep(self._policy.duration_s * intensity)
            return None
        if fault_type == ChaosType.RANDOM_FAIL:
            if random.random() < intensity:
                raise RuntimeError("随机失败")
            return func(*args, **kwargs)
        if fault_type == ChaosType.MEMORY_PRESSURE:
            # 模拟内存压力：分配并立即释放
            _ = [bytearray(1024) for _ in range(int(50 * intensity))]
            gc.collect()
            return func(*args, **kwargs)
        if fault_type == ChaosType.CPU_SPIKE:
            # 模拟CPU尖峰：忙等一小段时间
            end = time.time() + self._policy.duration_s * 0.01 * intensity
            while time.time() < end:
                pass
            return func(*args, **kwargs)
        if fault_type == ChaosType.DISK_PRESSURE:
            # 模拟磁盘压力：分配字符串
            _ = "x" * int(1000 * intensity)
            return func(*args, **kwargs)
        if fault_type == ChaosType.NETWORK_PARTITION:
            raise ConnectionError("网络分区")
        if fault_type == ChaosType.RESOURCE_EXHAUSTION:
            raise MemoryError("资源耗尽")
        return func(*args, **kwargs)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "injections": self._stats["injections"],
                "skipped": self._stats["skipped"],
                "by_type": dict(self._stats["by_type"]),
                "active_faults": len(self._active_faults),
            }

    def reset(self) -> None:
        with self._lock:
            self._stats = {"injections": 0, "skipped": 0, "by_type": defaultdict(int)}
            self._active_faults.clear()


# ============================================================
# 四、混沌实验
# ============================================================
@dataclass
class ChaosResult:
    """混沌实验结果"""
    experiment_id: str
    name: str
    fault_type: ChaosType
    passed: bool
    duration_ms: float
    steady_state_before: bool
    steady_state_during: bool
    steady_state_after: bool
    recovered: bool
    errors: List[str] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    samples: int = 0

    def summary(self) -> Dict[str, Any]:
        return {
            "id": self.experiment_id,
            "name": self.name,
            "fault": self.fault_type.value,
            "passed": self.passed,
            "duration_ms": round(self.duration_ms, 3),
            "steady_before": self.steady_state_before,
            "steady_during": self.steady_state_during,
            "steady_after": self.steady_state_after,
            "recovered": self.recovered,
            "samples": self.samples,
            "errors": list(self.errors[:5]),
        }


class ChaosExperiment:
    """混沌实验
    一个完整的实验：定义假设 -> 注入故障 -> 验证假设 -> 验证恢复
    """
    def __init__(self, name: str, fault_type: ChaosType,
                 hypothesis: SteadyStateHypothesis,
                 target: Optional[Callable] = None,
                 policy: Optional[ChaosPolicy] = None):
        self.experiment_id = str(uuid.uuid4())[:8]
        self.name = name
        self.fault_type = fault_type
        self.hypothesis = hypothesis
        self.target = target
        self.policy = policy or ChaosPolicy()
        self.injector = FaultInjector(self.policy)
        self._result: Optional[ChaosResult] = None
        self._lock = threading.RLock()

    def run(self, sample_count: int = 10) -> ChaosResult:
        """执行实验"""
        with self._lock:
            start = time.time()
            errors: List[str] = []
            observations: List[str] = []
            samples = 0
            steady_before = self.hypothesis.check()
            steady_during = True
            steady_after = True
            recovered = True

            try:
                # 阶段1：基线
                if not steady_before:
                    observations.append("基线已偏离稳态")

                # 阶段2：注入并采样
                failure_count = 0
                for i in range(sample_count):
                    samples += 1
                    try:
                        if self.target is not None:
                            wrapped = self.injector.wrap(self.target, self.fault_type)
                            wrapped()
                        else:
                            self.injector.inject(self.fault_type)
                    except Exception as e:
                        failure_count += 1
                        errors.append(f"sample{i}: {type(e).__name__}: {e}")
                    if not self.hypothesis.check():
                        steady_during = False

                # 阶段3：移除故障，等待恢复
                self.injector.reset()
                time.sleep(self.policy.cooldown_s + 0.01)
                steady_after = self.hypothesis.check()
                if not steady_after:
                    recovered = False

                passed = steady_before and steady_after and recovered
                observations.append(
                    f"失败样本 {failure_count}/{sample_count}"
                )
            except Exception as e:
                errors.append(f"实验异常: {e}")
                passed = False
                recovered = False
                observations.append(traceback.format_exc(limit=2))

            duration_ms = (time.time() - start) * 1000
            self._result = ChaosResult(
                experiment_id=self.experiment_id,
                name=self.name,
                fault_type=self.fault_type,
                passed=passed,
                duration_ms=duration_ms,
                steady_state_before=steady_before,
                steady_state_during=steady_during,
                steady_state_after=steady_after,
                recovered=recovered,
                errors=errors,
                observations=observations,
                samples=samples,
            )
            return self._result

    def result(self) -> Optional[ChaosResult]:
        return self._result


# ============================================================
# 五、熔断器
# ============================================================
class CircuitBreaker:
    """混沌熔断器
    当系统损伤过大时，停止后续实验。
    """
    def __init__(self, failure_threshold: int = 5,
                 error_rate_threshold: float = 0.5,
                 min_samples: int = 10):
        self.failure_threshold = failure_threshold
        self.error_rate_threshold = error_rate_threshold
        self.min_samples = min_samples
        self._failures = 0
        self._total = 0
        self._open = False
        self._lock = threading.RLock()
        self._reason: str = ""

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._open

    def record(self, success: bool) -> None:
        with self._lock:
            self._total += 1
            if not success:
                self._failures += 1
            # 条件1：连续失败次数达到阈值
            if self._failures >= self.failure_threshold:
                self._open = True
                self._reason = f"连续失败 {self._failures} 次"
                return
            # 条件2：样本数足够时，整体错误率超阈值
            if self._total >= self.min_samples:
                rate = self._failures / self._total
                if rate > self.error_rate_threshold:
                    self._open = True
                    self._reason = f"错误率 {rate:.2%} 超阈值"

    def reset(self) -> None:
        with self._lock:
            self._failures = 0
            self._total = 0
            self._open = False
            self._reason = ""

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "open": self._open,
                "failures": self._failures,
                "total": self._total,
                "error_rate": (self._failures / self._total) if self._total > 0 else 0.0,
                "reason": self._reason,
            }


# ============================================================
# 六、混沌运行器
# ============================================================
class ChaosRunner:
    """混沌实验运行器
    编排多个实验，串行或并行执行。
    """
    def __init__(self, breaker: Optional[CircuitBreaker] = None):
        self._experiments: List[ChaosExperiment] = []
        self._results: List[ChaosResult] = []
        self._breaker = breaker or CircuitBreaker()
        self._lock = threading.RLock()

    def add(self, experiment: ChaosExperiment) -> None:
        with self._lock:
            self._experiments.append(experiment)

    def run_all(self, sample_count: int = 5,
                stop_on_failure: bool = False) -> List[ChaosResult]:
        """串行执行所有实验"""
        with self._lock:
            results: List[ChaosResult] = []
            for exp in self._experiments:
                if self._breaker.is_open:
                    break
                res = exp.run(sample_count=sample_count)
                results.append(res)
                self._breaker.record(res.passed)
                if stop_on_failure and not res.passed:
                    break
            self._results = results
            return results

    def run_parallel(self, sample_count: int = 5) -> List[ChaosResult]:
        """并行执行所有实验"""
        results: List[ChaosResult] = []
        result_lock = threading.Lock()
        def worker(exp: ChaosExperiment) -> None:
            if self._breaker.is_open:
                return
            res = exp.run(sample_count=sample_count)
            with result_lock:
                results.append(res)
            self._breaker.record(res.passed)

        threads = [threading.Thread(target=worker, args=(e,))
                   for e in self._experiments]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self._results = results
        return results

    def results(self) -> List[ChaosResult]:
        with self._lock:
            return list(self._results)

    def pass_rate(self) -> float:
        with self._lock:
            if not self._results:
                return 0.0
            passed = sum(1 for r in self._results if r.passed)
            return passed / len(self._results)


# ============================================================
# 七、恢复验证器
# ============================================================
class RecoveryValidator:
    """恢复验证器
    通过多次采样验证系统是否真的从故障中恢复。
    """
    def __init__(self, max_attempts: int = 5, interval_s: float = 0.05):
        self.max_attempts = max_attempts
        self.interval_s = interval_s
        self._history: List[Dict[str, Any]] = []

    def validate(self, hypothesis: SteadyStateHypothesis) -> Dict[str, Any]:
        """执行恢复验证"""
        attempts = 0
        recovered = False
        for i in range(self.max_attempts):
            attempts += 1
            time.sleep(self.interval_s)
            if hypothesis.check():
                recovered = True
                break

        record = {
            "attempts": attempts,
            "recovered": recovered,
            "max_attempts": self.max_attempts,
        }
        self._history.append(record)
        return record

    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)


# ============================================================
# 八、弹性测试套件
# ============================================================
class ResilienceTest:
    """弹性测试
    端到端：执行故障 -> 监控稳态 -> 等待 -> 验证恢复。
    """
    def __init__(self, name: str, system_under_test: Callable,
                 hypothesis: SteadyStateHypothesis,
                 fault_type: ChaosType = ChaosType.LATENCY,
                 policy: Optional[ChaosPolicy] = None):
        self.name = name
        self.sut = system_under_test
        self.hypothesis = hypothesis
        self.fault_type = fault_type
        self.policy = policy or ChaosPolicy(probability=0.7, duration_s=0.01)
        self.injector = FaultInjector(self.policy)
        self.validator = RecoveryValidator()

    def run(self, sample_count: int = 10) -> Dict[str, Any]:
        start = time.time()
        steady_before = self.hypothesis.check()
        ok = 0
        err = 0
        for _ in range(sample_count):
            try:
                wrapped = self.injector.wrap(self.sut, self.fault_type)
                wrapped()
                ok += 1
            except Exception:
                err += 1
        recovery = self.validator.validate(self.hypothesis)
        duration_ms = (time.time() - start) * 1000
        return {
            "name": self.name,
            "steady_before": steady_before,
            "samples": sample_count,
            "ok": ok,
            "errors": err,
            "recovered": recovery["recovered"],
            "recovery_attempts": recovery["attempts"],
            "duration_ms": round(duration_ms, 3),
            "passed": steady_before and recovery["recovered"],
        }


# ============================================================
# 九、测试
# ============================================================
class TestChaosPolicy(unittest.TestCase):
    def test_default_policy(self):
        p = ChaosPolicy()
        self.assertTrue(p.validate())
        self.assertEqual(p.intensity_factor(), 0.5)

    def test_invalid_probability(self):
        self.assertFalse(ChaosPolicy(probability=-0.1).validate())
        self.assertFalse(ChaosPolicy(probability=1.5).validate())
        self.assertTrue(ChaosPolicy(probability=0.0).validate())
        self.assertTrue(ChaosPolicy(probability=1.0).validate())

    def test_intensity_factors(self):
        self.assertEqual(ChaosPolicy(intensity=ChaosIntensity.LOW).intensity_factor(), 0.25)
        self.assertEqual(ChaosPolicy(intensity=ChaosIntensity.EXTREME).intensity_factor(), 1.0)


class TestSteadyState(unittest.TestCase):
    def test_basic_check(self):
        h = SteadyStateHypothesis("a==1", lambda: True)
        self.assertTrue(h.check())
        self.assertFalse(h.is_violated())

    def test_violation(self):
        h = SteadyStateHypothesis("a==1", lambda: False)
        self.assertTrue(h.is_violated())

    def test_exception_in_predicate(self):
        def bad():
            raise RuntimeError("x")
        h = SteadyStateHypothesis("bad", bad)
        self.assertFalse(h.check())


class TestFaultInjector(unittest.TestCase):
    def test_inject_record(self):
        fi = FaultInjector(ChaosPolicy(probability=1.0))
        fi.inject(ChaosType.LATENCY)
        fi.inject(ChaosType.ERROR)
        st = fi.get_stats()
        self.assertEqual(st["injections"], 2)
        self.assertEqual(st["by_type"]["latency"], 1)
        self.assertEqual(st["by_type"]["error"], 1)

    def test_wrap_with_low_probability_passes_through(self):
        fi = FaultInjector(ChaosPolicy(probability=0.0))
        @fi.wrap
        def add(a, b):
            return a + b
        self.assertEqual(add(2, 3), 5)
        self.assertGreaterEqual(fi.get_stats()["skipped"], 1)

    def test_wrap_injects_error(self):
        fi = FaultInjector(ChaosPolicy(probability=1.0))
        @fi.wrap
        def f():
            return "x"
        self.assertIsNone(f())

    def test_wrap_injects_exception(self):
        fi = FaultInjector(ChaosPolicy(probability=1.0))
        def f():
            return 1
        wrapped = fi.wrap(f, ChaosType.EXCEPTION)
        with self.assertRaises(RuntimeError):
            wrapped()

    def test_wrap_injects_latency(self):
        fi = FaultInjector(ChaosPolicy(
            probability=1.0, duration_s=0.05,
            intensity=ChaosIntensity.EXTREME))
        def f():
            return 1
        wrapped = fi.wrap(f, ChaosType.LATENCY)
        start = time.time()
        result = wrapped()
        elapsed = time.time() - start
        self.assertEqual(result, 1)
        self.assertGreaterEqual(elapsed, 0.04)

    def test_set_policy_validates(self):
        fi = FaultInjector(ChaosPolicy())
        with self.assertRaises(ValueError):
            fi.set_policy(ChaosPolicy(probability=2.0))

    def test_reset(self):
        fi = FaultInjector(ChaosPolicy(probability=1.0))
        fi.inject(ChaosType.ERROR)
        fi.reset()
        self.assertEqual(fi.get_stats()["injections"], 0)


class TestChaosExperiment(unittest.TestCase):
    def test_run_latency(self):
        h = SteadyStateHypothesis("ok", lambda: True)
        exp = ChaosExperiment(
            "latency-test", ChaosType.LATENCY, h,
            policy=ChaosPolicy(probability=1.0, duration_s=0.001)
        )
        result = exp.run(sample_count=3)
        self.assertTrue(result.passed)
        self.assertTrue(result.steady_state_before)
        self.assertTrue(result.steady_state_after)
        self.assertEqual(result.samples, 3)

    def test_run_with_target_function(self):
        h = SteadyStateHypothesis("ok", lambda: True)
        counter = {"calls": 0}
        def target():
            counter["calls"] += 1
        exp = ChaosExperiment(
            "with-target", ChaosType.LATENCY, h,
            target=target,
            policy=ChaosPolicy(probability=1.0, duration_s=0.001)
        )
        result = exp.run(sample_count=4)
        self.assertTrue(result.passed)
        self.assertEqual(counter["calls"], 4)

    def test_run_unstable_hypothesis(self):
        h = SteadyStateHypothesis("flaky", lambda: False)
        exp = ChaosExperiment(
            "unstable", ChaosType.LATENCY, h,
            policy=ChaosPolicy(probability=1.0, duration_s=0.001)
        )
        result = exp.run(sample_count=2)
        self.assertFalse(result.passed)
        self.assertFalse(result.steady_state_before)


class TestCircuitBreaker(unittest.TestCase):
    def test_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record(False)
        cb.record(False)
        self.assertFalse(cb.is_open)
        cb.record(False)
        self.assertTrue(cb.is_open)

    def test_error_rate(self):
        cb = CircuitBreaker(failure_threshold=100, error_rate_threshold=0.5)
        for _ in range(6):
            cb.record(False)
        for _ in range(5):
            cb.record(True)
        self.assertTrue(cb.is_open)

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record(False)
        self.assertTrue(cb.is_open)
        cb.reset()
        self.assertFalse(cb.is_open)

    def test_status(self):
        cb = CircuitBreaker()
        cb.record(True)
        st = cb.status()
        self.assertEqual(st["total"], 1)
        self.assertEqual(st["error_rate"], 0.0)


class TestChaosRunner(unittest.TestCase):
    def test_run_all(self):
        runner = ChaosRunner()
        h = SteadyStateHypothesis("ok", lambda: True)
        for i in range(3):
            runner.add(ChaosExperiment(
                f"e{i}", ChaosType.LATENCY, h,
                policy=ChaosPolicy(probability=1.0, duration_s=0.001)
            ))
        results = runner.run_all(sample_count=2)
        self.assertEqual(len(results), 3)
        self.assertEqual(runner.pass_rate(), 1.0)

    def test_stop_on_failure(self):
        runner = ChaosRunner()
        h_stable = SteadyStateHypothesis("ok", lambda: True)
        h_unstable = SteadyStateHypothesis("bad", lambda: False)
        runner.add(ChaosExperiment("ok1", ChaosType.LATENCY, h_stable,
                                    policy=ChaosPolicy(probability=1.0, duration_s=0.001)))
        runner.add(ChaosExperiment("bad", ChaosType.LATENCY, h_unstable,
                                    policy=ChaosPolicy(probability=1.0, duration_s=0.001)))
        results = runner.run_all(sample_count=1, stop_on_failure=True)
        self.assertEqual(len(results), 2)
        # 第二个必然失败，但因为 stop_on_failure=True 我们已经运行了它
        self.assertFalse(results[1].passed)

    def test_run_parallel(self):
        runner = ChaosRunner()
        h = SteadyStateHypothesis("ok", lambda: True)
        for i in range(3):
            runner.add(ChaosExperiment(
                f"p{i}", ChaosType.LATENCY, h,
                policy=ChaosPolicy(probability=1.0, duration_s=0.001)
            ))
        results = runner.run_parallel(sample_count=2)
        self.assertEqual(len(results), 3)


class TestRecoveryValidator(unittest.TestCase):
    def test_recovery_immediate(self):
        v = RecoveryValidator(max_attempts=3, interval_s=0.01)
        h = SteadyStateHypothesis("ok", lambda: True)
        r = v.validate(h)
        self.assertTrue(r["recovered"])
        self.assertEqual(r["attempts"], 1)

    def test_no_recovery(self):
        v = RecoveryValidator(max_attempts=3, interval_s=0.01)
        h = SteadyStateHypothesis("bad", lambda: False)
        r = v.validate(h)
        self.assertFalse(r["recovered"])
        self.assertEqual(r["attempts"], 3)

    def test_history(self):
        v = RecoveryValidator()
        v.validate(SteadyStateHypothesis("a", lambda: True))
        self.assertEqual(len(v.history()), 1)


class TestResilienceTest(unittest.TestCase):
    def test_basic_resilience(self):
        h = SteadyStateHypothesis("ok", lambda: True)
        def svc():
            return "ok"
        rt = ResilienceTest("svc", svc, h,
                             fault_type=ChaosType.LATENCY,
                             policy=ChaosPolicy(probability=1.0, duration_s=0.001))
        result = rt.run(sample_count=5)
        self.assertTrue(result["passed"])
        self.assertEqual(result["samples"], 5)
        self.assertEqual(result["ok"], 5)
        self.assertEqual(result["errors"], 0)

    def test_exception_fault(self):
        h = SteadyStateHypothesis("ok", lambda: True)
        def svc():
            return 1
        rt = ResilienceTest("svc", svc, h,
                             fault_type=ChaosType.EXCEPTION,
                             policy=ChaosPolicy(probability=1.0))
        result = rt.run(sample_count=3)
        # 全部抛异常，errors=3
        self.assertEqual(result["errors"], 3)
        # 但恢复后稳态仍True，因为稳态不依赖svc本身
        self.assertTrue(result["recovered"])


# ============================================================
# 十、Demo
# ============================================================
def demo():
    """演示阶段132的功能"""
    print("=" * 60)
    print("阶段132演示：混沌工程")
    print("=" * 60)

    # 1. 故障注入器
    print("\n🔥 演示1：故障注入器")
    print("-" * 60)
    fi = FaultInjector(ChaosPolicy(probability=0.7, intensity=ChaosIntensity.MEDIUM))

    @fi.wrap
    def add(a, b):
        return a + b

    ok, err, latencies = 0, 0, []
    for i in range(10):
        start = time.time()
        try:
            r = add(i, 1)
            if r is not None:
                ok += 1
            else:
                err += 1
        except Exception:
            err += 1
        latencies.append((time.time() - start) * 1000)
    print(f"  成功: {ok}, 异常/None: {err}")
    print(f"  注入统计: {fi.get_stats()}")
    print(f"  平均延迟: {sum(latencies)/len(latencies):.2f}ms")

    # 2. 稳态假设
    print("\n📊 演示2：稳态假设")
    print("-" * 60)
    counter = [0]
    def check():
        return counter[0] >= 0
    h = SteadyStateHypothesis("counter>=0", check)
    print(f"  初始稳态: {h.check()}")
    counter[0] = -1
    print(f"  违反稳态: {h.is_violated()}")
    counter[0] = 0

    # 3. 混沌实验
    print("\n🧪 演示3：混沌实验")
    print("-" * 60)
    state = {"healthy": True}
    h = SteadyStateHypothesis("healthy", lambda: state["healthy"])

    def service():
        return "ok"

    for ft in [ChaosType.LATENCY, ChaosType.ERROR, ChaosType.EXCEPTION]:
        exp = ChaosExperiment(
            f"exp-{ft.value}", ft, h,
            target=service,
            policy=ChaosPolicy(probability=1.0, duration_s=0.001)
        )
        result = exp.run(sample_count=3)
        print(f"  {ft.value:20s} -> "
              f"pass={result.passed}, "
              f"steady_after={result.steady_state_after}, "
              f"recovered={result.recovered}")

    # 4. 熔断器
    print("\n⚡ 演示4：熔断器")
    print("-" * 60)
    cb = CircuitBreaker(failure_threshold=3)
    for i in range(5):
        cb.record(i < 2)  # 前面2次成功，后面3次失败
    print(f"  熔断器状态: {cb.status()}")

    # 5. 混沌运行器
    print("\n🏃 演示5：混沌运行器")
    print("-" * 60)
    runner = ChaosRunner(CircuitBreaker(failure_threshold=10))
    h = SteadyStateHypothesis("ok", lambda: True)
    for ft in [ChaosType.LATENCY, ChaosType.ERROR, ChaosType.EXCEPTION, ChaosType.MEMORY_PRESSURE]:
        runner.add(ChaosExperiment(
            f"r-{ft.value}", ft, h,
            target=lambda: 1,
            policy=ChaosPolicy(probability=1.0, duration_s=0.001)
        ))
    results = runner.run_all(sample_count=2)
    print(f"  实验数: {len(results)}")
    print(f"  通过率: {runner.pass_rate():.0%}")
    for r in results:
        s = r.summary()
        print(f"    [{s['fault']:10s}] "
              f"steady_during={s['steady_during']}, "
              f"steady_after={s['steady_after']}, "
              f"recovered={s['recovered']}")

    # 6. 弹性测试
    print("\n🛡️  演示6：端到端弹性测试")
    print("-" * 60)
    h = SteadyStateHypothesis("ok", lambda: True)
    def svc():
        return "ok"
    rt = ResilienceTest("svc-test", svc, h,
                        fault_type=ChaosType.LATENCY,
                        policy=ChaosPolicy(probability=1.0, duration_s=0.001))
    result = rt.run(sample_count=5)
    print(f"  测试: {result['name']}")
    print(f"  通过: {result['passed']}, 恢复: {result['recovered']}")
    print(f"  耗时: {result['duration_ms']}ms")

    print("\n" + "=" * 60)
    print("✅ 阶段132完成：混沌工程已实现！")
    print("=" * 60)
    print("\n【下阶段预告】阶段133：灰度发布")
    print("  - 流量切分")
    print("  - 版本路由")
    print("  - 自动回滚")


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    print()
    demo()
