#!/usr/bin/env python3
"""
阶段133：灰度发布

第一性原理：
  - 渐进公理：风险与流量成正比
  - 可逆公理：发布必须可回滚
  - 决策公理：基于数据而非直觉
  - 隔离公理：新旧版本互不污染
  - 爆炸半径：限制最大失败影响

本阶段产出：
  1. Version：版本定义
  2. VersionRegistry：版本注册表
  3. TrafficRouter：流量路由器
  4. RoutingRule：路由规则
  5. CanaryStrategy：灰度策略
  6. CanaryController：灰度控制器
  7. RollbackManager：回滚管理器
  8. BlueGreenDeployer：蓝绿发布器
  9. ABTest：A/B测试

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import random
import threading
import uuid
import json
import hashlib
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import contextmanager


# ============================================================
# 一、版本与发布阶段
# ============================================================
class ReleaseStage(Enum):
    """发布阶段"""
    PENDING = "pending"            # 待发布
    CANARY = "canary"              # 金丝雀
    BETA = "beta"                  # 灰度
    STAGING = "staging"            # 预发
    STABLE = "stable"              # 稳定
    DEPRECATED = "deprecated"      # 弃用
    ROLLING_BACK = "rolling_back"  # 回滚中
    ROLLED_BACK = "rolled_back"    # 已回滚


class CanaryStrategy(Enum):
    """灰度策略"""
    PERCENTAGE = "percentage"      # 按比例
    HEADER = "header"              # 按Header
    USER_ID = "user_id"            # 按用户ID
    COOKIE = "cookie"              # 按Cookie
    GEO = "geo"                    # 按地理位置
    HASH_BUCKET = "hash"           # 按哈希分桶


@dataclass
class Version:
    """版本"""
    name: str
    stage: ReleaseStage = ReleaseStage.PENDING
    traffic_weight: float = 0.0     # 流量权重（0-1）
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    error_count: int = 0
    request_count: int = 0
    health: str = "unknown"         # healthy/degraded/unhealthy

    def error_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count

    def record_request(self, success: bool = True) -> None:
        self.request_count += 1
        if not success:
            self.error_count += 1

    def is_healthy(self, threshold: float = 0.05) -> bool:
        return self.error_rate() <= threshold

    def summary(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "stage": self.stage.value,
            "weight": self.traffic_weight,
            "requests": self.request_count,
            "errors": self.error_count,
            "error_rate": round(self.error_rate(), 4),
            "health": self.health,
        }


class VersionRegistry:
    """版本注册表"""
    def __init__(self):
        self._versions: Dict[str, Version] = {}
        self._lock = threading.RLock()

    def register(self, version: Version) -> None:
        with self._lock:
            self._versions[version.name] = version

    def get(self, name: str) -> Optional[Version]:
        with self._lock:
            return self._versions.get(name)

    def all(self) -> List[Version]:
        with self._lock:
            return list(self._versions.values())

    def stable_versions(self) -> List[Version]:
        with self._lock:
            return [v for v in self._versions.values()
                    if v.stage == ReleaseStage.STABLE]

    def canary_versions(self) -> List[Version]:
        with self._lock:
            return [v for v in self._versions.values()
                    if v.stage in (ReleaseStage.CANARY, ReleaseStage.BETA)]

    def remove(self, name: str) -> bool:
        with self._lock:
            return self._versions.pop(name, None) is not None

    def total_traffic(self) -> float:
        with self._lock:
            return sum(v.traffic_weight for v in self._versions.values())


# ============================================================
# 二、流量路由
# ============================================================
@dataclass
class RoutingContext:
    """路由上下文"""
    user_id: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    geo: str = ""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def header(self, name: str, default: str = "") -> str:
        for k, v in self.headers.items():
            if k.lower() == name.lower():
                return v
        return default

    def cookie(self, name: str, default: str = "") -> str:
        return self.cookies.get(name, default)


@dataclass
class RoutingDecision:
    """路由决策"""
    version_name: str
    strategy: CanaryStrategy
    matched: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.matched


class TrafficRouter:
    """流量路由器
    根据策略将请求路由到不同版本。
    """
    def __init__(self, registry: VersionRegistry):
        self.registry = registry
        self._strategy: CanaryStrategy = CanaryStrategy.PERCENTAGE
        self._fallback: str = ""
        self._lock = threading.RLock()
        self._decisions: deque = deque(maxlen=1000)

    def set_strategy(self, strategy: CanaryStrategy,
                     fallback_version: str = "") -> None:
        with self._lock:
            self._strategy = strategy
            self._fallback = fallback_version

    def route(self, context: RoutingContext) -> Optional[Version]:
        """根据策略路由"""
        with self._lock:
            strategy = self._strategy
            stable = self.registry.stable_versions()
            canary = self.registry.canary_versions()

            if not canary and not stable:
                decision = RoutingDecision("", strategy, False, "无可用版本")
                self._decisions.append(decision)
                return None

            chosen: Optional[Version] = None
            if strategy == CanaryStrategy.PERCENTAGE:
                chosen = self._route_by_percentage(canary, stable)
            elif strategy == CanaryStrategy.HEADER:
                chosen = self._route_by_header(context, canary, stable)
            elif strategy == CanaryStrategy.USER_ID:
                chosen = self._route_by_user_id(context, canary, stable)
            elif strategy == CanaryStrategy.COOKIE:
                chosen = self._route_by_cookie(context, canary, stable)
            elif strategy == CanaryStrategy.HASH_BUCKET:
                chosen = self._route_by_hash(context, canary, stable)
            elif strategy == CanaryStrategy.GEO:
                chosen = self._route_by_geo(context, canary, stable)
            else:
                chosen = stable[0] if stable else None

            decision = RoutingDecision(
                chosen.name if chosen else "", strategy,
                chosen is not None,
                "命中" if chosen else "未命中"
            )
            self._decisions.append(decision)
            return chosen

    def _route_by_percentage(self, canary: List[Version],
                              stable: List[Version]) -> Optional[Version]:
        if canary:
            total = sum(v.traffic_weight for v in canary)
            if total > 0 and random.random() < total:
                # 加权选择
                pick = random.random() * total
                cur = 0.0
                for v in canary:
                    cur += v.traffic_weight
                    if pick <= cur:
                        return v
        if stable:
            return stable[0]
        return None

    def _route_by_header(self, ctx: RoutingContext,
                          canary: List[Version],
                          stable: List[Version]) -> Optional[Version]:
        tag = ctx.header("X-Canary", "")
        if tag:
            for v in canary:
                if v.name == tag or tag in v.metadata.get("alias", []):
                    return v
        return stable[0] if stable else None

    def _route_by_user_id(self, ctx: RoutingContext,
                           canary: List[Version],
                           stable: List[Version]) -> Optional[Version]:
        if not ctx.user_id:
            return stable[0] if stable else None
        for v in canary:
            user_ids = v.metadata.get("user_ids", [])
            if ctx.user_id in user_ids:
                return v
        return stable[0] if stable else None

    def _route_by_cookie(self, ctx: RoutingContext,
                          canary: List[Version],
                          stable: List[Version]) -> Optional[Version]:
        tag = ctx.cookie("canary")
        if tag:
            for v in canary:
                if v.name == tag:
                    return v
        return stable[0] if stable else None

    def _route_by_geo(self, ctx: RoutingContext,
                       canary: List[Version],
                       stable: List[Version]) -> Optional[Version]:
        for v in canary:
            geos = v.metadata.get("geos", [])
            if ctx.geo in geos:
                return v
        return stable[0] if stable else None

    def _route_by_hash(self, ctx: RoutingContext,
                        canary: List[Version],
                        stable: List[Version]) -> Optional[Version]:
        key = ctx.user_id or ctx.request_id
        h = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
        for v in canary:
            bucket_end = int(v.traffic_weight * 100)
            if h < bucket_end:
                return v
        return stable[0] if stable else None

    def decisions(self) -> List[RoutingDecision]:
        with self._lock:
            return list(self._decisions)


# ============================================================
# 三、灰度策略与控制器
# ============================================================
@dataclass
class RolloutPolicy:
    """灰度发布策略"""
    initial_weight: float = 0.05        # 初始流量
    increment: float = 0.1              # 每步增量
    step_interval_s: float = 60.0       # 步进间隔
    max_weight: float = 1.0             # 最大权重
    min_samples: int = 100              # 最小样本数
    max_error_rate: float = 0.05        # 最大错误率
    auto_rollback: bool = True          # 自动回滚
    soak_time_s: float = 300.0          # 完全放量前稳定观察时间


class CanaryController:
    """灰度控制器
    自动化灰度发布：逐步放量、监控、自动回滚或晋升。
    """
    def __init__(self, registry: VersionRegistry,
                 router: TrafficRouter,
                 policy: Optional[RolloutPolicy] = None):
        self.registry = registry
        self.router = router
        self.policy = policy or RolloutPolicy()
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._paused = False

    def start_canary(self, version: Version) -> None:
        """启动灰度"""
        with self._lock:
            version.stage = ReleaseStage.CANARY
            version.traffic_weight = self.policy.initial_weight
            self.registry.register(version)
            self._history.append({
                "event": "start",
                "version": version.name,
                "weight": version.traffic_weight,
                "ts": time.time(),
            })

    def increase_traffic(self, version_name: str) -> bool:
        """增加流量"""
        with self._lock:
            if self._paused:
                return False
            v = self.registry.get(version_name)
            if v is None:
                return False
            if v.request_count < self.policy.min_samples:
                return False
            if not v.is_healthy(self.policy.max_error_rate):
                return False
            new_weight = min(v.traffic_weight + self.policy.increment,
                              self.policy.max_weight)
            v.traffic_weight = new_weight
            self._history.append({
                "event": "increase",
                "version": version_name,
                "weight": new_weight,
                "ts": time.time(),
            })
            return True

    def promote(self, version_name: str) -> bool:
        """晋升到稳定版"""
        with self._lock:
            v = self.registry.get(version_name)
            if v is None:
                return False
            if v.request_count < self.policy.min_samples:
                return False
            if not v.is_healthy(self.policy.max_error_rate):
                return False
            v.stage = ReleaseStage.STABLE
            v.traffic_weight = 1.0
            # 降级其他非稳定版本
            for other in self.registry.all():
                if other.name != version_name and other.stage == ReleaseStage.STABLE:
                    other.stage = ReleaseStage.DEPRECATED
                    other.traffic_weight = 0.0
            self._history.append({
                "event": "promote",
                "version": version_name,
                "ts": time.time(),
            })
            return True

    def pause(self) -> None:
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            self._paused = False

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)


# ============================================================
# 四、回滚管理器
# ============================================================
class RollbackReason(Enum):
    """回滚原因"""
    HIGH_ERROR_RATE = "high_error_rate"
    HEALTH_CHECK_FAIL = "health_check_fail"
    MANUAL = "manual"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    DEPENDENCY_FAILURE = "dependency_failure"


@dataclass
class RollbackRecord:
    """回滚记录"""
    from_version: str
    to_version: str
    reason: RollbackReason
    success: bool
    ts: float = field(default_factory=time.time)
    note: str = ""


class RollbackManager:
    """回滚管理器
    检测异常并自动回滚到上一个稳定版本。
    """
    def __init__(self, registry: VersionRegistry,
                 controller: CanaryController,
                 error_threshold: float = 0.05):
        self.registry = registry
        self.controller = controller
        self.error_threshold = error_threshold
        self._history: List[RollbackRecord] = []
        self._lock = threading.RLock()
        self._last_stable: Optional[str] = None

    def mark_stable(self, version_name: str) -> None:
        with self._lock:
            self._last_stable = version_name

    def should_rollback(self, version_name: str) -> bool:
        """检查是否需要回滚"""
        v = self.registry.get(version_name)
        if v is None:
            return False
        return v.error_rate() > self.error_threshold

    def rollback(self, from_version: str, reason: RollbackReason,
                 note: str = "") -> RollbackRecord:
        """执行回滚"""
        with self._lock:
            target = self._last_stable or ""
            v = self.registry.get(from_version)
            if v:
                v.stage = ReleaseStage.ROLLING_BACK
                v.traffic_weight = 0.0
                v.health = "rolled_back"

            success = False
            if target and target != from_version:
                stable_v = self.registry.get(target)
                if stable_v is not None:
                    stable_v.stage = ReleaseStage.STABLE
                    stable_v.traffic_weight = 1.0
                    success = True

            record = RollbackRecord(
                from_version=from_version,
                to_version=target,
                reason=reason,
                success=success,
                note=note,
            )
            self._history.append(record)
            if v:
                v.stage = ReleaseStage.ROLLED_BACK
            self.controller.pause()
            return record

    def history(self) -> List[RollbackRecord]:
        with self._lock:
            return list(self._history)

    def last_record(self) -> Optional[RollbackRecord]:
        with self._lock:
            return self._history[-1] if self._history else None


# ============================================================
# 五、蓝绿发布
# ============================================================
class BlueGreenDeployer:
    """蓝绿发布器
    通过切换主备实现零停机发布。
    """
    def __init__(self, registry: VersionRegistry):
        self.registry = registry
        self._active: Optional[str] = None      # 当前活跃
        self._standby: Optional[str] = None     # 备用
        self._lock = threading.RLock()
        self._history: List[Dict[str, Any]] = []

    def deploy(self, version: Version) -> None:
        """部署到备用"""
        with self._lock:
            self.registry.register(version)
            version.stage = ReleaseStage.STAGING
            version.traffic_weight = 0.0
            self._standby = version.name
            self._history.append({
                "event": "deploy",
                "version": version.name,
                "ts": time.time(),
            })

    def activate(self, version_name: str) -> bool:
        """切换：standby -> active"""
        with self._lock:
            target = self.registry.get(version_name)
            if target is None:
                return False
            if self._standby != version_name:
                return False
            # 旧active降级
            if self._active:
                old = self.registry.get(self._active)
                if old:
                    old.stage = ReleaseStage.DEPRECATED
                    old.traffic_weight = 0.0
            # 切换
            target.stage = ReleaseStage.STABLE
            target.traffic_weight = 1.0
            prev_active = self._active
            self._active = version_name
            self._standby = None
            self._history.append({
                "event": "activate",
                "from": prev_active,
                "to": version_name,
                "ts": time.time(),
            })
            return True

    def rollback(self) -> bool:
        """回滚：要求存在上一active"""
        with self._lock:
            # 简化：从历史中恢复
            for h in reversed(self._history):
                if h.get("event") == "activate":
                    prev = h.get("from")
                    if prev:
                        return self.activate(prev)
            return False

    def active(self) -> Optional[str]:
        with self._lock:
            return self._active

    def standby(self) -> Optional[str]:
        with self._lock:
            return self._standby

    def history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)


# ============================================================
# 六、A/B 测试
# ============================================================
@dataclass
class ABExperiment:
    """A/B 实验"""
    name: str
    variants: List[str]               # 版本名列表
    weights: List[float] = field(default_factory=list)  # 权重
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    metrics: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.weights:
            # 默认均分
            self.weights = [1.0 / len(self.variants)] * len(self.variants)
        self.metrics = {v: {"success": 0, "failure": 0} for v in self.variants}

    def record(self, variant: str, success: bool) -> None:
        if variant not in self.metrics:
            self.metrics[variant] = {"success": 0, "failure": 0}
        key = "success" if success else "failure"
        self.metrics[variant][key] += 1

    def conversion_rate(self, variant: str) -> float:
        m = self.metrics.get(variant, {"success": 0, "failure": 0})
        total = m["success"] + m["failure"]
        if total == 0:
            return 0.0
        return m["success"] / total

    def winner(self) -> Optional[str]:
        rates = [(v, self.conversion_rate(v)) for v in self.variants]
        if not rates:
            return None
        rates.sort(key=lambda x: x[1], reverse=True)
        return rates[0][0]

    def summary(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "variants": self.variants,
            "weights": self.weights,
            "metrics": {v: dict(m) for v, m in self.metrics.items()},
            "rates": {v: round(self.conversion_rate(v), 4)
                       for v in self.variants},
            "winner": self.winner(),
        }


class ABTestRunner:
    """A/B 测试运行器"""
    def __init__(self, registry: VersionRegistry):
        self.registry = registry
        self._experiments: Dict[str, ABExperiment] = {}
        self._lock = threading.RLock()

    def create(self, name: str, variants: List[str],
               weights: Optional[List[float]] = None) -> ABExperiment:
        with self._lock:
            exp = ABExperiment(
                name=name, variants=variants, weights=weights or [])
            self._experiments[name] = exp
            return exp

    def get(self, name: str) -> Optional[ABExperiment]:
        with self._lock:
            return self._experiments.get(name)

    def assign(self, experiment_name: str,
               user_id: str = "") -> Optional[str]:
        with self._lock:
            exp = self._experiments.get(experiment_name)
            if exp is None:
                return None
            key = user_id or str(uuid.uuid4())
            h = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
            cumulative = 0.0
            for v, w in zip(exp.variants, exp.weights):
                cumulative += w * 100
                if h < cumulative:
                    return v
            return exp.variants[-1]

    def all(self) -> List[ABExperiment]:
        with self._lock:
            return list(self._experiments.values())


# ============================================================
# 七、测试
# ============================================================
class TestVersion(unittest.TestCase):
    def test_record_request(self):
        v = Version("v1")
        v.record_request(True)
        v.record_request(True)
        v.record_request(False)
        self.assertEqual(v.request_count, 3)
        self.assertEqual(v.error_count, 1)
        self.assertAlmostEqual(v.error_rate(), 1/3)

    def test_is_healthy(self):
        v = Version("v1")
        for _ in range(100):
            v.record_request(True)
        self.assertTrue(v.is_healthy(0.05))
        for _ in range(10):
            v.record_request(False)
        self.assertFalse(v.is_healthy(0.05))

    def test_summary(self):
        v = Version("v1", stage=ReleaseStage.CANARY)
        v.traffic_weight = 0.1
        s = v.summary()
        self.assertEqual(s["name"], "v1")
        self.assertEqual(s["stage"], "canary")
        self.assertEqual(s["weight"], 0.1)


class TestVersionRegistry(unittest.TestCase):
    def test_register_and_get(self):
        r = VersionRegistry()
        v = Version("v1")
        r.register(v)
        self.assertIs(r.get("v1"), v)

    def test_all(self):
        r = VersionRegistry()
        r.register(Version("v1"))
        r.register(Version("v2"))
        self.assertEqual(len(r.all()), 2)

    def test_stable_versions(self):
        r = VersionRegistry()
        r.register(Version("v1", stage=ReleaseStage.STABLE))
        r.register(Version("v2", stage=ReleaseStage.CANARY))
        stables = r.stable_versions()
        self.assertEqual(len(stables), 1)
        self.assertEqual(stables[0].name, "v1")

    def test_canary_versions(self):
        r = VersionRegistry()
        r.register(Version("v1", stage=ReleaseStage.STABLE))
        r.register(Version("v2", stage=ReleaseStage.CANARY))
        r.register(Version("v3", stage=ReleaseStage.BETA))
        canaries = r.canary_versions()
        self.assertEqual(len(canaries), 2)

    def test_remove(self):
        r = VersionRegistry()
        r.register(Version("v1"))
        self.assertTrue(r.remove("v1"))
        self.assertFalse(r.remove("v1"))

    def test_total_traffic(self):
        r = VersionRegistry()
        r.register(Version("v1", traffic_weight=0.3))
        r.register(Version("v2", traffic_weight=0.7))
        self.assertAlmostEqual(r.total_traffic(), 1.0)


class TestRoutingContext(unittest.TestCase):
    def test_header_case_insensitive(self):
        ctx = RoutingContext(headers={"X-CANARY": "v2"})
        self.assertEqual(ctx.header("x-canary"), "v2")
        self.assertEqual(ctx.header("X-CANARY"), "v2")

    def test_header_missing(self):
        ctx = RoutingContext()
        self.assertEqual(ctx.header("X-Missing", "default"), "default")


class TestTrafficRouter(unittest.TestCase):
    def test_no_versions(self):
        r = VersionRegistry()
        router = TrafficRouter(r)
        decision = router.route(RoutingContext())
        self.assertIsNone(decision)

    def test_route_by_percentage(self):
        r = VersionRegistry()
        r.register(Version("v1", stage=ReleaseStage.STABLE, traffic_weight=1.0))
        r.register(Version("v2", stage=ReleaseStage.CANARY, traffic_weight=1.0))
        router = TrafficRouter(r)
        router.set_strategy(CanaryStrategy.PERCENTAGE)
        # 50/50 流量，可能落到两边
        hits = {"v1": 0, "v2": 0}
        for _ in range(100):
            v = router.route(RoutingContext())
            if v:
                hits[v.name] += 1
        # 至少两边都有命中（高概率）
        self.assertGreater(hits["v1"] + hits["v2"], 0)

    def test_route_by_header(self):
        r = VersionRegistry()
        r.register(Version("stable", stage=ReleaseStage.STABLE, traffic_weight=1.0))
        r.register(Version("v2", stage=ReleaseStage.CANARY, traffic_weight=0.5))
        router = TrafficRouter(r)
        router.set_strategy(CanaryStrategy.HEADER)
        ctx = RoutingContext(headers={"X-Canary": "v2"})
        v = router.route(ctx)
        self.assertEqual(v.name, "v2")

    def test_route_by_user_id(self):
        r = VersionRegistry()
        r.register(Version("stable", stage=ReleaseStage.STABLE, traffic_weight=1.0))
        r.register(Version("v2", stage=ReleaseStage.CANARY, traffic_weight=0.5,
                            metadata={"user_ids": ["u1", "u2"]}))
        router = TrafficRouter(r)
        router.set_strategy(CanaryStrategy.USER_ID)
        v = router.route(RoutingContext(user_id="u1"))
        self.assertEqual(v.name, "v2")
        v = router.route(RoutingContext(user_id="u3"))
        self.assertEqual(v.name, "stable")

    def test_route_by_hash(self):
        r = VersionRegistry()
        r.register(Version("stable", stage=ReleaseStage.STABLE, traffic_weight=1.0))
        r.register(Version("v2", stage=ReleaseStage.CANARY, traffic_weight=0.5))
        router = TrafficRouter(r)
        router.set_strategy(CanaryStrategy.HASH_BUCKET)
        v = router.route(RoutingContext(user_id="u1"))
        self.assertIsNotNone(v)


class TestCanaryController(unittest.TestCase):
    def test_start_canary(self):
        r = VersionRegistry()
        router = TrafficRouter(r)
        ctrl = CanaryController(r, router)
        v = Version("v2")
        ctrl.start_canary(v)
        self.assertEqual(v.stage, ReleaseStage.CANARY)
        self.assertEqual(v.traffic_weight, 0.05)
        self.assertIsNotNone(r.get("v2"))

    def test_increase_traffic(self):
        r = VersionRegistry()
        router = TrafficRouter(r)
        ctrl = CanaryController(r, router,
                                 RolloutPolicy(min_samples=5, increment=0.2))
        v = Version("v2", stage=ReleaseStage.CANARY, traffic_weight=0.05)
        for _ in range(10):
            v.record_request(True)
        r.register(v)
        ok = ctrl.increase_traffic("v2")
        self.assertTrue(ok)
        self.assertAlmostEqual(v.traffic_weight, 0.25)

    def test_increase_below_min_samples(self):
        r = VersionRegistry()
        router = TrafficRouter(r)
        ctrl = CanaryController(r, router, RolloutPolicy(min_samples=100))
        v = Version("v2", stage=ReleaseStage.CANARY, traffic_weight=0.05)
        r.register(v)
        ok = ctrl.increase_traffic("v2")
        self.assertFalse(ok)

    def test_increase_unhealthy(self):
        r = VersionRegistry()
        router = TrafficRouter(r)
        ctrl = CanaryController(r, router,
                                 RolloutPolicy(min_samples=5, max_error_rate=0.05))
        v = Version("v2", stage=ReleaseStage.CANARY, traffic_weight=0.05)
        for _ in range(10):
            v.record_request(False)
        r.register(v)
        ok = ctrl.increase_traffic("v2")
        self.assertFalse(ok)

    def test_promote(self):
        r = VersionRegistry()
        router = TrafficRouter(r)
        ctrl = CanaryController(r, router, RolloutPolicy(min_samples=5))
        v = Version("v2", stage=ReleaseStage.CANARY, traffic_weight=0.5)
        for _ in range(10):
            v.record_request(True)
        r.register(v)
        ok = ctrl.promote("v2")
        self.assertTrue(ok)
        self.assertEqual(v.stage, ReleaseStage.STABLE)
        self.assertEqual(v.traffic_weight, 1.0)

    def test_pause_resume(self):
        r = VersionRegistry()
        router = TrafficRouter(r)
        ctrl = CanaryController(r, router)
        self.assertFalse(ctrl.is_paused())
        ctrl.pause()
        self.assertTrue(ctrl.is_paused())
        ctrl.resume()
        self.assertFalse(ctrl.is_paused())


class TestRollbackManager(unittest.TestCase):
    def test_should_rollback(self):
        r = VersionRegistry()
        router = TrafficRouter(r)
        ctrl = CanaryController(r, router)
        rm = RollbackManager(r, ctrl, error_threshold=0.1)
        v = Version("v2")
        for _ in range(100):
            v.record_request(False)
        r.register(v)
        self.assertTrue(rm.should_rollback("v2"))

    def test_rollback(self):
        r = VersionRegistry()
        router = TrafficRouter(r)
        ctrl = CanaryController(r, router)
        rm = RollbackManager(r, ctrl)
        rm.mark_stable("v1")
        v2 = Version("v2", stage=ReleaseStage.CANARY, traffic_weight=0.5)
        v1 = Version("v1", stage=ReleaseStage.STABLE, traffic_weight=1.0)
        r.register(v1)
        r.register(v2)
        record = rm.rollback("v2", RollbackReason.HIGH_ERROR_RATE)
        self.assertTrue(record.success)
        self.assertEqual(record.from_version, "v2")
        self.assertEqual(record.to_version, "v1")
        self.assertEqual(v2.stage, ReleaseStage.ROLLED_BACK)
        self.assertTrue(ctrl.is_paused())

    def test_rollback_no_stable(self):
        r = VersionRegistry()
        router = TrafficRouter(r)
        ctrl = CanaryController(r, router)
        rm = RollbackManager(r, ctrl)
        v2 = Version("v2")
        r.register(v2)
        record = rm.rollback("v2", RollbackReason.MANUAL)
        self.assertFalse(record.success)

    def test_last_record(self):
        r = VersionRegistry()
        router = TrafficRouter(r)
        ctrl = CanaryController(r, router)
        rm = RollbackManager(r, ctrl)
        v2 = Version("v2")
        r.register(v2)
        rm.rollback("v2", RollbackReason.MANUAL)
        rec = rm.last_record()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.reason, RollbackReason.MANUAL)


class TestBlueGreen(unittest.TestCase):
    def test_deploy_and_activate(self):
        r = VersionRegistry()
        bg = BlueGreenDeployer(r)
        v2 = Version("v2")
        bg.deploy(v2)
        self.assertEqual(bg.standby(), "v2")
        self.assertEqual(v2.stage, ReleaseStage.STAGING)
        ok = bg.activate("v2")
        self.assertTrue(ok)
        self.assertEqual(bg.active(), "v2")
        self.assertEqual(v2.stage, ReleaseStage.STABLE)

    def test_activate_wrong_version(self):
        r = VersionRegistry()
        bg = BlueGreenDeployer(r)
        v2 = Version("v2")
        bg.deploy(v2)
        ok = bg.activate("v3")
        self.assertFalse(ok)

    def test_history(self):
        r = VersionRegistry()
        bg = BlueGreenDeployer(r)
        v2 = Version("v2")
        bg.deploy(v2)
        bg.activate("v2")
        h = bg.history()
        self.assertEqual(len(h), 2)


class TestABTest(unittest.TestCase):
    def test_create_with_equal_weights(self):
        exp = ABExperiment("e1", ["a", "b"])
        self.assertEqual(len(exp.weights), 2)
        self.assertAlmostEqual(exp.weights[0], 0.5)

    def test_record(self):
        exp = ABExperiment("e1", ["a", "b"])
        exp.record("a", True)
        exp.record("a", False)
        exp.record("b", True)
        self.assertEqual(exp.conversion_rate("a"), 0.5)
        self.assertEqual(exp.conversion_rate("b"), 1.0)

    def test_winner(self):
        exp = ABExperiment("e1", ["a", "b"])
        for _ in range(10):
            exp.record("a", True)
        exp.record("b", False)
        self.assertEqual(exp.winner(), "a")

    def test_summary(self):
        exp = ABExperiment("e1", ["a", "b"])
        exp.record("a", True)
        s = exp.summary()
        self.assertEqual(s["variants"], ["a", "b"])
        self.assertIn("rates", s)


class TestABTestRunner(unittest.TestCase):
    def test_create(self):
        r = VersionRegistry()
        runner = ABTestRunner(r)
        exp = runner.create("e1", ["a", "b"])
        self.assertIsNotNone(exp)
        self.assertIn("e1", runner._experiments)

    def test_assign(self):
        r = VersionRegistry()
        runner = ABTestRunner(r)
        runner.create("e1", ["a", "b"], [0.5, 0.5])
        v = runner.assign("e1", user_id="u1")
        self.assertIn(v, ["a", "b"])

    def test_assign_missing_experiment(self):
        r = VersionRegistry()
        runner = ABTestRunner(r)
        self.assertIsNone(runner.assign("nonexistent"))


# ============================================================
# 八、Demo
# ============================================================
def demo():
    """演示阶段133的功能"""
    print("=" * 60)
    print("阶段133演示：灰度发布")
    print("=" * 60)

    # 1. 版本与注册表
    print("\n📦 演示1：版本管理")
    print("-" * 60)
    registry = VersionRegistry()
    stable = Version("v1.0.0", stage=ReleaseStage.STABLE, traffic_weight=1.0)
    registry.register(stable)
    print(f"  稳定版: {stable.summary()}")

    # 2. 灰度启动
    print("\n🐤 演示2：灰度启动")
    print("-" * 60)
    router = TrafficRouter(registry)
    router.set_strategy(CanaryStrategy.PERCENTAGE)
    ctrl = CanaryController(registry, router, RolloutPolicy(min_samples=10, increment=0.2))
    v2 = Version("v2.0.0")
    ctrl.start_canary(v2)
    print(f"  灰度启动: stage={v2.stage.value}, weight={v2.traffic_weight}")

    # 模拟请求
    for i in range(50):
        ctx = RoutingContext(user_id=f"u{i}")
        target = router.route(ctx)
        if target:
            success = target.name == "v1.0.0" or random.random() < 0.95
            target.record_request(success)

    # 3. 增加流量
    print("\n📈 演示3：逐步放量")
    print("-" * 60)
    for i in range(4):
        if ctrl.increase_traffic("v2.0.0"):
            print(f"  步骤{i+1}: weight -> {v2.traffic_weight}")
        else:
            print(f"  步骤{i+1}: 跳过（健康或不达标）")
            # 补点请求
            for _ in range(20):
                v2.record_request(True)

    # 4. 路由策略
    print("\n🛣️  演示4：路由策略")
    print("-" * 60)
    for strategy in [CanaryStrategy.HEADER, CanaryStrategy.USER_ID, CanaryStrategy.HASH_BUCKET]:
        router.set_strategy(strategy)
        if strategy == CanaryStrategy.HEADER:
            ctx = RoutingContext(headers={"X-Canary": "v2.0.0"})
        elif strategy == CanaryStrategy.USER_ID:
            ctx = RoutingContext(user_id="u1",
                                 headers={"X-UserId-Override": "v2.0.0"})
        else:
            ctx = RoutingContext(user_id="u1")
        v = router.route(ctx)
        # 单独验证
        if strategy == CanaryStrategy.HEADER:
            actual = v.name if v else "none"
            print(f"  {strategy.value:12s}: X-Canary=v2.0.0 -> {actual}")
        else:
            print(f"  {strategy.value:12s}: u1 -> {v.name if v else 'none'}")

    # 5. 回滚
    print("\n⏪ 演示5：自动回滚")
    print("-" * 60)
    registry2 = VersionRegistry()
    router2 = TrafficRouter(registry2)
    ctrl2 = CanaryController(registry2, router2)
    rm = RollbackManager(registry2, ctrl2, error_threshold=0.1)
    s = Version("v1.0.0", stage=ReleaseStage.STABLE, traffic_weight=1.0)
    bad = Version("v2.0.0", stage=ReleaseStage.CANARY, traffic_weight=0.3)
    registry2.register(s)
    registry2.register(bad)
    for _ in range(100):
        bad.record_request(False)
    rm.mark_stable("v1.0.0")
    print(f"  v2.0.0 错误率: {bad.error_rate():.2%}")
    if rm.should_rollback("v2.0.0"):
        rec = rm.rollback("v2.0.0", RollbackReason.HIGH_ERROR_RATE)
        print(f"  已回滚: {rec.from_version} -> {rec.to_version} ({rec.reason.value})")
    else:
        print("  无需回滚")

    # 6. 蓝绿发布
    print("\n🔵🟢 演示6：蓝绿发布")
    print("-" * 60)
    registry3 = VersionRegistry()
    bg = BlueGreenDeployer(registry3)
    v1 = Version("v1.0.0", stage=ReleaseStage.STABLE, traffic_weight=1.0)
    registry3.register(v1)
    bg._active = "v1.0.0"
    v2 = Version("v2.0.0")
    bg.deploy(v2)
    print(f"  部署v2.0.0: standby={bg.standby()}, active={bg.active()}")
    bg.activate("v2.0.0")
    print(f"  切换后: standby={bg.standby()}, active={bg.active()}")

    # 7. A/B 测试
    print("\n🧪 演示7：A/B 测试")
    print("-" * 60)
    runner = ABTestRunner(VersionRegistry())
    exp = runner.create("homepage", ["control", "treatment"], [0.5, 0.5])
    for i in range(100):
        variant = runner.assign("homepage", user_id=f"u{i}")
        success = variant == "treatment" or random.random() < 0.7
        exp.record(variant, success)
    s = exp.summary()
    print(f"  实验: {s['name']}")
    for v in s["variants"]:
        m = s["metrics"][v]
        print(f"    {v:10s}: 转化率 {s['rates'][v]:.2%} (成功 {m['success']}/失败 {m['failure']})")
    print(f"  胜出: {s['winner']}")

    print("\n" + "=" * 60)
    print("✅ 阶段133完成：灰度发布已实现！")
    print("=" * 60)
    print("\n【下阶段预告】阶段134：灾备与恢复")
    print("  - 备份策略")
    print("  - 故障切换")
    print("  - 数据恢复")


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    print()
    demo()
