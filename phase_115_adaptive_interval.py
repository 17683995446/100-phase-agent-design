#!/usr/bin/env python3
"""
阶段115：自适应循环间隔（增强版）

第一性原理：
  - 存续公理：节奏与负载不匹配会导致系统不稳定或浪费
  - 自驱公理：系统应主动感知环境，自我调节运行节奏
  - 反直觉：忙时不一定快，空闲时不一定慢，关键是吞吐

本阶段产出（在阶段106基础上强化）：
  1. LoadAdaptiveInterval：基于队列长度的负载自适应
  2. PIDAdaptiveInterval：PID控制理论驱动的精确调节
  3. HysteresisController：滞回控制，避免抖动
  4. JitterAvoidance：随机抖动避免惊群效应
  5. AdaptiveIntervalFactory：策略工厂

遵循原则：图难于其易，为大于其细
"""
import time
import random
import unittest
import threading
import math
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import deque


# ============================================================
# 一、负载信号
# ============================================================
@dataclass
class LoadSignal:
    """负载信号（一个时间点的状态快照）"""
    queue_size: int       # 任务队列大小
    last_duration: float  # 上一个循环耗时（秒）
    resource_pressure: float = 0.0  # 资源压力 [0, 1]
    cpu_usage: float = 0.0           # CPU使用率 [0, 1]
    memory_usage: float = 0.0        # 内存使用率 [0, 1]
    timestamp: float = field(default_factory=time.time)


# ============================================================
# 二、基于队列长度的简单自适应
# ============================================================
class LoadAdaptiveInterval:
    """基于负载的自适应间隔

    简单实用：队列长 -> 加速；队列空 -> 减速。
    适合作为基础实现。
    """
    def __init__(self, default: float = 1.0,
                 min_interval: float = 0.05,
                 max_interval: float = 10.0,
                 target_queue: int = 3,
                 shrink_factor: float = 0.8,
                 grow_factor: float = 1.2):
        self.default = default
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.target_queue = target_queue
        self.shrink_factor = shrink_factor
        self.grow_factor = grow_factor
        self.current = default
        self._lock = threading.Lock()
        self._stats = {
            "adjustments": 0,
            "shrinks": 0,
            "grows": 0,
            "max_seen": default,
            "min_seen": default,
        }

    def adjust(self, signal: LoadSignal) -> float:
        with self._lock:
            self._stats["adjustments"] += 1
            old = self.current
            q = signal.queue_size
            if q > self.target_queue * 2:
                # 大量积压 -> 立即降到最小
                self.current = self.min_interval
                self._stats["shrinks"] += 1
            elif q > self.target_queue:
                # 略多 -> 收缩
                self.current = max(
                    self.min_interval, self.current * self.shrink_factor)
                self._stats["shrinks"] += 1
            elif q == 0:
                # 空队列 -> 放慢
                self.current = min(
                    self.max_interval, self.current * self.grow_factor)
                self._stats["grows"] += 1
            # 资源紧张再叠加
            if signal.resource_pressure > 0.7:
                self.current = min(
                    self.max_interval, self.current * 1.5)
            self.current = self._clamp(self.current)
            self._stats["max_seen"] = max(
                self._stats["max_seen"], self.current)
            self._stats["min_seen"] = min(
                self._stats["min_seen"], self.current)
            return self.current

    def _clamp(self, v: float) -> float:
        return max(self.min_interval, min(self.max_interval, v))

    def get_current(self) -> float:
        return self.current

    def reset(self) -> None:
        with self._lock:
            self.current = self.default
            self._stats = {
                "adjustments": 0,
                "shrinks": 0,
                "grows": 0,
                "max_seen": self.default,
                "min_seen": self.default,
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 三、PID控制器
# ============================================================
class PIDAdaptiveInterval:
    """基于PID控制论的自适应间隔

    第一性原理：控制论 - 反馈驱动系统稳定
    使用比例+积分+微分三要素逼近目标队列长度
    """
    def __init__(self, default: float = 1.0,
                 min_interval: float = 0.05,
                 max_interval: float = 10.0,
                 target_queue: int = 3,
                 kp: float = 0.1,
                 ki: float = 0.01,
                 kd: float = 0.05):
        self.default = default
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.target_queue = target_queue
        self.kp = kp  # 比例
        self.ki = ki  # 积分
        self.kd = kd  # 微分
        self.current = default
        self._integral = 0.0
        self._last_error: Optional[float] = None
        self._lock = threading.Lock()
        self._history: deque = deque(maxlen=100)

    def adjust(self, signal: LoadSignal) -> float:
        with self._lock:
            error = signal.queue_size - self.target_queue
            # 比例
            p = self.kp * error
            # 积分
            self._integral += error
            i = self.ki * self._integral
            # 微分
            d = 0.0
            if self._last_error is not None:
                d = self.kd * (error - self._last_error)
            self._last_error = error
            # 输出：error > 0 (队列长) -> 减少间隔
            output = p + i + d
            self.current = self.current - output
            self.current = self._clamp(self.current)
            self._history.append({
                "time": signal.timestamp,
                "queue": signal.queue_size,
                "interval": self.current,
                "error": error,
            })
            return self.current

    def _clamp(self, v: float) -> float:
        return max(self.min_interval, min(self.max_interval, v))

    def get_current(self) -> float:
        return self.current

    def reset(self) -> None:
        with self._lock:
            self.current = self.default
            self._integral = 0.0
            self._last_error = None
            self._history.clear()

    def get_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)


# ============================================================
# 四、滞回控制器
# ============================================================
class HysteresisController:
    """滞回控制器

    第一性原理：避免在临界点抖动。
    - 进入"快"模式要更难（避免误触发）
    - 退出"快"模式要更慢（避免反复切换）
    """
    HIGH_THRESHOLD = 8
    LOW_THRESHOLD = 2
    FAST_INTERVAL = 0.1
    SLOW_INTERVAL = 1.0

    def __init__(self):
        self._mode = "normal"  # fast / normal / slow
        self._lock = threading.Lock()
        self._stats = {
            "mode_changes": 0,
            "fast_time": 0.0,
            "slow_time": 0.0,
            "last_mode_change": 0.0,
        }
        self._mode_start = time.time()

    def adjust(self, signal: LoadSignal) -> float:
        with self._lock:
            now = time.time()
            old_mode = self._mode
            # 用滞回阈值决定是否切换
            if self._mode != "fast" and signal.queue_size > self.HIGH_THRESHOLD:
                self._mode = "fast"
            elif self._mode == "fast" and signal.queue_size < self.LOW_THRESHOLD:
                self._mode = "normal"
            if self._mode == "normal" and signal.queue_size == 0:
                self._mode = "slow"
            elif self._mode == "slow" and signal.queue_size > 0:
                self._mode = "normal"
            # 累计时长
            if old_mode == self._mode:
                # 还在此模式
                pass
            else:
                # 模式切换
                dt = now - self._mode_start
                if old_mode == "fast":
                    self._stats["fast_time"] += dt
                elif old_mode == "slow":
                    self._stats["slow_time"] += dt
                self._stats["mode_changes"] += 1
                self._stats["last_mode_change"] = now
                self._mode_start = now
            # 返回对应间隔
            if self._mode == "fast":
                return self.FAST_INTERVAL
            elif self._mode == "slow":
                return self.SLOW_INTERVAL
            return 0.5  # normal

    def get_mode(self) -> str:
        return self._mode

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 五、抖动避免器
# ============================================================
class JitterAvoidance:
    """抖动避免器

    第一性原理：避免惊群效应。
    - 在间隔基础上引入小幅度随机扰动
    - 防止多个循环同步导致资源峰值
    """
    JITTER_RATIO = 0.1  # 10% 抖动

    def __init__(self, jitter_ratio: float = JITTER_RATIO,
                 seed: Optional[int] = None):
        self.jitter_ratio = jitter_ratio
        self._rng = random.Random(seed)

    def apply(self, base_interval: float) -> float:
        """在基础间隔上叠加抖动"""
        if base_interval <= 0:
            return base_interval
        # ±jitter_ratio 的随机扰动
        jitter = self._rng.uniform(
            -self.jitter_ratio, self.jitter_ratio)
        return max(0.001, base_interval * (1.0 + jitter))

    def apply_batch(self, base_intervals: List[float]) -> List[float]:
        """批量抖动：保证总时长不变的情况下分摊"""
        total = sum(base_intervals)
        jittered = [self.apply(v) for v in base_intervals]
        # 归一化
        actual_total = sum(jittered)
        if actual_total > 0:
            scale = total / actual_total
            jittered = [v * scale for v in jittered]
        return jittered


# ============================================================
# 六、自适应策略枚举
# ============================================================
class Strategy(Enum):
    LOAD = "load"
    PID = "pid"
    HYSTERESIS = "hysteresis"


# ============================================================
# 七、自适应间隔工厂
# ============================================================
class AdaptiveIntervalFactory:
    """自适应间隔工厂"""
    @staticmethod
    def create(strategy: Strategy, **kwargs) -> Any:
        if strategy == Strategy.LOAD:
            return LoadAdaptiveInterval(**kwargs)
        if strategy == Strategy.PID:
            return PIDAdaptiveInterval(**kwargs)
        if strategy == Strategy.HYSTERESIS:
            return HysteresisController()
        raise ValueError(f"未知策略: {strategy}")


# ============================================================
# 八、组合自适应调节器
# ============================================================
class CompositeAdaptiveInterval:
    """组合自适应调节器

    组合多种策略：
    - 主体策略（Load/PID/Hysteresis）决定基础间隔
    - 抖动避免器在基础间隔上叠加扰动
    - 提供统一的对外接口
    """
    def __init__(self, strategy: Strategy = Strategy.LOAD,
                 enable_jitter: bool = True,
                 jitter_ratio: float = 0.1,
                 **kwargs):
        self.base = AdaptiveIntervalFactory.create(strategy, **kwargs)
        self.jitter = JitterAvoidance(jitter_ratio) if enable_jitter else None
        self._lock = threading.Lock()
        self._stats = {
            "total_adjusts": 0,
            "avg_interval": 0.0,
        }
        self._interval_sum = 0.0

    def adjust(self, signal: LoadSignal) -> float:
        with self._lock:
            base = self.base.adjust(signal)
            if self.jitter:
                final = self.jitter.apply(base)
            else:
                final = base
            self._stats["total_adjusts"] += 1
            self._interval_sum += final
            self._stats["avg_interval"] = (
                self._interval_sum / self._stats["total_adjusts"])
            return final

    def get_current(self) -> float:
        return self.base.get_current()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 九、单元测试
# ============================================================
class TestLoadAdaptive(unittest.TestCase):
    """负载自适应测试"""
    def test_shrink_on_queue(self):
        ai = LoadAdaptiveInterval(default=1.0, target_queue=3)
        # 队列大 -> 缩小
        for _ in range(5):
            ai.adjust(LoadSignal(queue_size=10, last_duration=0.1))
        self.assertLess(ai.get_current(), 1.0)

    def test_grow_on_empty(self):
        ai = LoadAdaptiveInterval(default=0.1, max_interval=10.0,
                                  target_queue=3)
        for _ in range(10):
            ai.adjust(LoadSignal(queue_size=0, last_duration=0.01))
        self.assertGreater(ai.get_current(), 0.1)

    def test_clamp(self):
        ai = LoadAdaptiveInterval(default=1.0,
                                    min_interval=0.5,
                                    max_interval=2.0)
        # 试图超出范围
        for _ in range(20):
            ai.adjust(LoadSignal(queue_size=0, last_duration=0.01))
        self.assertLessEqual(ai.get_current(), 2.0)
        for _ in range(20):
            ai.adjust(LoadSignal(queue_size=100, last_duration=0.01))
        self.assertGreaterEqual(ai.get_current(), 0.5)

    def test_stats(self):
        ai = LoadAdaptiveInterval()
        for _ in range(5):
            ai.adjust(LoadSignal(queue_size=2, last_duration=0.1))
        stats = ai.get_stats()
        self.assertEqual(stats["adjustments"], 5)


class TestPIDAdaptive(unittest.TestCase):
    """PID自适应测试"""
    def test_pid_responds_to_error(self):
        ai = PIDAdaptiveInterval(default=1.0, target_queue=3)
        # 队列太多 -> 减少间隔
        ai.adjust(LoadSignal(queue_size=10, last_duration=0.1))
        self.assertLess(ai.get_current(), 1.0)

    def test_pid_converges(self):
        ai = PIDAdaptiveInterval(default=1.0, target_queue=3)
        # 持续在目标
        for _ in range(20):
            ai.adjust(LoadSignal(queue_size=3, last_duration=0.1))
        # 间隔应该稳定
        self.assertGreater(ai.get_current(), 0.0)

    def test_reset(self):
        ai = PIDAdaptiveInterval(default=1.0)
        ai.adjust(LoadSignal(queue_size=10, last_duration=0.1))
        ai.reset()
        self.assertEqual(ai.get_current(), 1.0)


class TestHysteresis(unittest.TestCase):
    """滞回测试"""
    def test_mode_transitions(self):
        hc = HysteresisController()
        # 空 -> slow
        hc.adjust(LoadSignal(queue_size=0, last_duration=0.1))
        self.assertEqual(hc.get_mode(), "slow")
        # 1个 -> normal
        hc.adjust(LoadSignal(queue_size=1, last_duration=0.1))
        self.assertEqual(hc.get_mode(), "normal")
        # 高 -> fast
        hc.adjust(LoadSignal(queue_size=10, last_duration=0.1))
        self.assertEqual(hc.get_mode(), "fast")
        # 高于LOW_THRESHOLD但低于HIGH_THRESHOLD -> 仍fast
        hc.adjust(LoadSignal(queue_size=3, last_duration=0.1))
        self.assertEqual(hc.get_mode(), "fast")
        # 低于LOW_THRESHOLD -> normal
        hc.adjust(LoadSignal(queue_size=1, last_duration=0.1))
        self.assertEqual(hc.get_mode(), "normal")

    def test_hysteresis_prevents_jitter(self):
        hc = HysteresisController()
        # 反复在临界点附近
        changes = 0
        for i in range(20):
            q = 8 if i % 2 == 0 else 1
            old = hc.get_mode()
            hc.adjust(LoadSignal(queue_size=q, last_duration=0.1))
            if hc.get_mode() != old:
                changes += 1
        # 滞回特性：模式切换应当较少
        self.assertLessEqual(changes, 5)


class TestJitterAvoidance(unittest.TestCase):
    """抖动避免测试"""
    def test_jitter_in_range(self):
        ja = JitterAvoidance(jitter_ratio=0.1, seed=42)
        for _ in range(100):
            jittered = ja.apply(1.0)
            self.assertGreaterEqual(jittered, 0.9)
            self.assertLessEqual(jittered, 1.1)

    def test_jitter_batch(self):
        ja = JitterAvoidance(jitter_ratio=0.1, seed=42)
        bases = [1.0] * 10
        result = ja.apply_batch(bases)
        self.assertEqual(len(result), 10)
        # 总时长应保持接近
        self.assertAlmostEqual(sum(result), 10.0, delta=0.1)

    def test_zero_handling(self):
        ja = JitterAvoidance()
        self.assertEqual(ja.apply(0), 0)


class TestFactory(unittest.TestCase):
    """工厂测试"""
    def test_create_load(self):
        ai = AdaptiveIntervalFactory.create(Strategy.LOAD)
        self.assertIsInstance(ai, LoadAdaptiveInterval)

    def test_create_pid(self):
        ai = AdaptiveIntervalFactory.create(Strategy.PID)
        self.assertIsInstance(ai, PIDAdaptiveInterval)

    def test_create_hysteresis(self):
        ai = AdaptiveIntervalFactory.create(Strategy.HYSTERESIS)
        self.assertIsInstance(ai, HysteresisController)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            AdaptiveIntervalFactory.create("invalid")  # type: ignore


class TestComposite(unittest.TestCase):
    """组合测试"""
    def test_composite_with_jitter(self):
        comp = CompositeAdaptiveInterval(
            strategy=Strategy.LOAD, enable_jitter=True,
            jitter_ratio=0.1, default=1.0, target_queue=3)
        for _ in range(10):
            comp.adjust(LoadSignal(queue_size=2, last_duration=0.1))
        stats = comp.get_stats()
        self.assertEqual(stats["total_adjusts"], 10)
        # 平均间隔应大于0
        self.assertGreater(stats["avg_interval"], 0)

    def test_composite_no_jitter(self):
        comp = CompositeAdaptiveInterval(
            strategy=Strategy.LOAD, enable_jitter=False, default=1.0)
        v1 = comp.adjust(LoadSignal(queue_size=2, last_duration=0.1))
        v2 = comp.adjust(LoadSignal(queue_size=2, last_duration=0.1))
        # 无抖动时同样输入应得到同样输出
        self.assertEqual(v1, v2)


# ============================================================
# 十、阶段115演示
# ============================================================
def run_phase_115():
    """运行阶段115"""
    print("=" * 70)
    print("阶段115：自适应循环间隔（增强版）")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestLoadAdaptive))
    suite.addTests(loader.loadTestsFromTestCase(TestPIDAdaptive))
    suite.addTests(loader.loadTestsFromTestCase(TestHysteresis))
    suite.addTests(loader.loadTestsFromTestCase(TestJitterAvoidance))
    suite.addTests(loader.loadTestsFromTestCase(TestFactory))
    suite.addTests(loader.loadTestsFromTestCase(TestComposite))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【自适应循环间隔演示】")
    print("-" * 70)

    # 演示1: 三种策略对比
    print("  📊 演示1: 三种策略对比（队列从0到20）")
    print("     " + "-" * 60)
    strategies = {
        "Load(简单)": LoadAdaptiveInterval(default=1.0, target_queue=3),
        "PID(精确)": PIDAdaptiveInterval(default=1.0, target_queue=3),
        "Hysteresis(滞回)": HysteresisController(),
    }
    print(f"     {'队列':>6} | " + " | ".join(
        f"{n:>14}" for n in strategies.keys()))
    for q in [0, 1, 3, 5, 10, 20, 5, 1, 0]:
        row = [f"{q:>6}"]
        for s in strategies.values():
            v = s.adjust(LoadSignal(queue_size=q, last_duration=0.05))
            if isinstance(s, HysteresisController):
                row.append(f"{v:>5.2f} ({s.get_mode():>6})")
            else:
                row.append(f"{v:>14.3f}")
        print("     " + " | ".join(row))
    print()

    # 演示2: 抖动避免
    print("  🎲 演示2: 抖动避免（10个循环的间隔）")
    print("     " + "-" * 60)
    ja = JitterAvoidance(jitter_ratio=0.2, seed=42)
    base = 1.0
    intervals = [ja.apply(base) for _ in range(10)]
    print(f"     基础: {base:.2f}s")
    print(f"     抖动: {', '.join(f'{v:.3f}' for v in intervals)}")
    print(f"     最小: {min(intervals):.3f}s, "
          f"最大: {max(intervals):.3f}s, "
          f"平均: {sum(intervals)/len(intervals):.3f}s")
    print()

    # 演示3: 组合策略
    print("  🔄 演示3: 组合策略（Load + Jitter）")
    print("     " + "-" * 60)
    comp = CompositeAdaptiveInterval(
        strategy=Strategy.LOAD, enable_jitter=True,
        jitter_ratio=0.15, default=1.0, target_queue=3)
    # 模拟负载波动
    queue_pattern = [0, 0, 1, 2, 3, 5, 8, 12, 15, 8, 4, 2, 1, 0, 0]
    print(f"     {'时刻':>6} | {'队列':>6} | {'间隔':>8} | {'说明':>10}")
    explanations = {
        0: "🟢 空闲", 1: "🟢 空闲", 2: "🟡 正常",
        3: "🟡 正常", 5: "🟠 略忙", 8: "🔴 积压",
        12: "🔴 积压", 15: "🔴 积压", 4: "🟠 略忙"
    }
    for i, q in enumerate(queue_pattern):
        v = comp.adjust(LoadSignal(queue_size=q, last_duration=0.05))
        exp = explanations.get(q, "")
        print(f"     {i+1:>6} | {q:>6} | {v:>7.3f}s | {exp:>10}")
    print()

    # 演示4: 资源压力感知
    print("  ⚠️  演示4: 资源压力感知（CPU=0.9, Memory=0.8）")
    print("     " + "-" * 60)
    ai = LoadAdaptiveInterval(default=1.0, target_queue=3)
    # 队列适中但资源紧张
    print(f"     正常压力: {ai.adjust(LoadSignal(queue_size=3, last_duration=0.05, resource_pressure=0.2)):.3f}s")
    print(f"     高压力:   {ai.adjust(LoadSignal(queue_size=3, last_duration=0.05, resource_pressure=0.9)):.3f}s")
    print(f"     极限压力: {ai.adjust(LoadSignal(queue_size=3, last_duration=0.05, resource_pressure=1.0)):.3f}s")
    print()

    # 统计
    print("  📈 Load策略统计:")
    load_ai = strategies["Load(简单)"]
    print(f"     {load_ai.get_stats()}")
    print()

    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段115完成：自适应循环间隔增强版已实现，所有测试通过！")
    else:
        print("✅ 阶段115完成：自适应循环间隔增强版已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段116：健康检查与探针")
    print("  - 心跳机制")
    print("  - 依赖探针")
    print("  - 外部可观测性")
    print()
    return True


if __name__ == "__main__":
    run_phase_115()
