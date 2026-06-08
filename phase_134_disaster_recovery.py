#!/usr/bin/env python3
"""
阶段134：灾备与恢复

第一性原理：
  - 冗余公理：单点故障不可接受
  - 可恢复公理：所有数据必须可重建
  - 时空公理：恢复需要时间，RPO/RTO定义上限
  - 一致公理：备份必须可用
  - 演练公理：未演练的备份等于没备份

本阶段产出：
  1. Backup：备份定义
  2. BackupPolicy：备份策略
  3. BackupManager：备份管理器
  4. FailoverCluster：故障切换集群
  5. RecoveryPlan：恢复计划
  6. DisasterRecovery：灾备主控
  7. RPO/RTO跟踪器

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import random
import threading
import uuid
import json
import hashlib
import os
import tempfile
import shutil
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import deque, defaultdict
from contextlib import contextmanager


# ============================================================
# 一、备份类型与策略
# ============================================================
class BackupType(Enum):
    """备份类型"""
    FULL = "full"                  # 全量备份
    INCREMENTAL = "incremental"    # 增量备份
    DIFFERENTIAL = "differential"  # 差异备份
    SNAPSHOT = "snapshot"          # 快照


class BackupStatus(Enum):
    """备份状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    CORRUPTED = "corrupted"


@dataclass
class Backup:
    """备份"""
    backup_id: str
    backup_type: BackupType
    source: str
    size_bytes: int
    checksum: str
    created_at: float = field(default_factory=time.time)
    status: BackupStatus = BackupStatus.PENDING
    parent_id: Optional[str] = None   # 父备份（用于增量）
    data: Any = None                  # 实际数据（或引用）
    metadata: Dict[str, Any] = field(default_factory=dict)

    def verify(self) -> bool:
        """验证备份完整性"""
        if self.data is None:
            return False
        actual = hashlib.sha256(
            json.dumps(self.data, sort_keys=True, default=str).encode()
        ).hexdigest()
        ok = actual == self.checksum
        self.status = BackupStatus.VERIFIED if ok else BackupStatus.CORRUPTED
        return ok

    def summary(self) -> Dict[str, Any]:
        return {
            "id": self.backup_id,
            "type": self.backup_type.value,
            "source": self.source,
            "size": self.size_bytes,
            "status": self.status.value,
            "checksum": self.checksum[:12],
            "parent": self.parent_id,
        }


@dataclass
class BackupPolicy:
    """备份策略"""
    backup_type: BackupType = BackupType.FULL
    interval_s: float = 3600.0
    retention_count: int = 7
    max_age_s: float = 7 * 86400
    verify_after_backup: bool = True
    compress: bool = False
    encrypt: bool = False

    def validate(self) -> bool:
        return self.interval_s > 0 and self.retention_count >= 1


# ============================================================
# 二、备份管理器
# ============================================================
class BackupManager:
    """备份管理器
    执行全量/增量备份、维护备份链、自动清理过期。
    """
    def __init__(self, policy: Optional[BackupPolicy] = None):
        self._policy = policy or BackupPolicy()
        self._backups: Dict[str, Backup] = {}
        self._by_source: Dict[str, List[str]] = defaultdict(list)
        self._lock = threading.RLock()
        self._stats = {
            "total_backups": 0,
            "total_bytes": 0,
            "failures": 0,
        }
        self._last_full: Dict[str, str] = {}    # source -> last full backup id

    @property
    def policy(self) -> BackupPolicy:
        return self._policy

    def set_policy(self, policy: BackupPolicy) -> None:
        with self._lock:
            if not policy.validate():
                raise ValueError("Invalid backup policy")
            self._policy = policy

    def _compute_checksum(self, data: Any) -> str:
        s = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(s.encode()).hexdigest()

    def _estimate_size(self, data: Any) -> int:
        s = json.dumps(data, default=str)
        return len(s.encode())

    def create_backup(self, source: str, data: Any,
                      backup_type: Optional[BackupType] = None,
                      parent_id: Optional[str] = None) -> Backup:
        """创建备份"""
        with self._lock:
            bt = backup_type or self._policy.backup_type
            bid = str(uuid.uuid4())[:8]
            size = self._estimate_size(data)
            checksum = self._compute_checksum(data)
            backup = Backup(
                backup_id=bid,
                backup_type=bt,
                source=source,
                size_bytes=size,
                checksum=checksum,
                status=BackupStatus.IN_PROGRESS,
                parent_id=parent_id,
                data=data,
            )
            self._backups[bid] = backup
            self._by_source[source].append(bid)
            self._stats["total_backups"] += 1
            self._stats["total_bytes"] += size

            if bt == BackupType.FULL:
                self._last_full[source] = bid
                parent_id = None
            else:
                if not parent_id:
                    parent_id = self._last_full.get(source)

            # 完成
            backup.status = BackupStatus.COMPLETED
            backup.parent_id = parent_id
            if self._policy.verify_after_backup:
                backup.verify()

            # 清理过期
            self._cleanup(source)
            return backup

    def _cleanup(self, source: str) -> None:
        """清理过期备份，保留retention_count个"""
        ids = self._by_source.get(source, [])
        # 保留所有F+最近的增量
        if len(ids) > self._policy.retention_count:
            to_remove = ids[:-self._policy.retention_count]
            for bid in to_remove:
                b = self._backups.get(bid)
                if b and b.status != BackupStatus.VERIFIED:
                    continue
                self._backups.pop(bid, None)
            self._by_source[source] = ids[-self._policy.retention_count:]

    def get_backup(self, backup_id: str) -> Optional[Backup]:
        with self._lock:
            return self._backups.get(backup_id)

    def list_backups(self, source: Optional[str] = None) -> List[Backup]:
        with self._lock:
            if source:
                ids = self._by_source.get(source, [])
                return [self._backups[i] for i in ids if i in self._backups]
            return list(self._backups.values())

    def latest_for(self, source: str) -> Optional[Backup]:
        with self._lock:
            ids = self._by_source.get(source, [])
            if not ids:
                return None
            return self._backups.get(ids[-1])

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)

    def restore(self, backup_id: str) -> Any:
        """从备份恢复"""
        with self._lock:
            b = self._backups.get(backup_id)
            if b is None:
                raise KeyError(f"备份不存在: {backup_id}")
            if b.status == BackupStatus.CORRUPTED:
                raise RuntimeError("备份已损坏")
            return b.data


# ============================================================
# 三、故障切换集群
# ============================================================
class NodeRole(Enum):
    """节点角色"""
    PRIMARY = "primary"            # 主
    SECONDARY = "secondary"        # 备
    WITNESS = "witness"            # 见证
    OFFLINE = "offline"            # 离线


class NodeHealth(Enum):
    """节点健康"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class FailoverNode:
    """故障切换节点"""
    node_id: str
    role: NodeRole = NodeRole.SECONDARY
    health: NodeHealth = NodeHealth.HEALTHY
    last_heartbeat: float = field(default_factory=time.time)
    region: str = "default"
    priority: int = 0               # 选举优先级
    lag_s: float = 0.0              # 复制延迟
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_alive(self, timeout_s: float = 5.0) -> bool:
        return (time.time() - self.last_heartbeat) < timeout_s

    def touch(self) -> None:
        self.last_heartbeat = time.time()


class FailoverCluster:
    """故障切换集群
    心跳检测、主备选举、自动切换。
    """
    def __init__(self, heartbeat_timeout_s: float = 5.0):
        self._nodes: Dict[str, FailoverNode] = {}
        self._primary: Optional[str] = None
        self._lock = threading.RLock()
        self._heartbeat_timeout = heartbeat_timeout_s
        self._failover_history: List[Dict[str, Any]] = []

    def add_node(self, node: FailoverNode) -> None:
        with self._lock:
            self._nodes[node.node_id] = node
            # 总是重新评估主节点：选最优者
            self._elect_primary()

    def remove_node(self, node_id: str) -> bool:
        with self._lock:
            n = self._nodes.pop(node_id, None)
            if n is None:
                return False
            if self._primary == node_id:
                self._primary = None
                self._elect_primary()
            return True

    def heartbeat(self, node_id: str) -> None:
        with self._lock:
            n = self._nodes.get(node_id)
            if n:
                n.touch()
                if n.health != NodeHealth.HEALTHY:
                    n.health = NodeHealth.HEALTHY

    def report_health(self, node_id: str, health: NodeHealth) -> None:
        with self._lock:
            n = self._nodes.get(node_id)
            if n:
                n.health = health
                if health in (NodeHealth.UNHEALTHY, NodeHealth.DEGRADED):
                    self._check_failover(node_id)

    def _elect_primary(self) -> None:
        """选举主节点"""
        candidates = [
            n for n in self._nodes.values()
            if n.health == NodeHealth.HEALTHY
            and n.role in (NodeRole.SECONDARY, NodeRole.PRIMARY)
        ]
        if not candidates:
            return
        # 按priority和lag排序
        candidates.sort(key=lambda x: (-x.priority, x.lag_s, x.node_id))
        winner = candidates[0]
        # 降级旧主
        if self._primary and self._primary != winner.node_id:
            old = self._nodes.get(self._primary)
            if old:
                old.role = NodeRole.SECONDARY
        winner.role = NodeRole.PRIMARY
        self._primary = winner.node_id

    def _check_failover(self, failed_node_id: str) -> None:
        """检查并执行故障切换"""
        with self._lock:
            if failed_node_id != self._primary:
                return
            old_primary = self._primary
            self._elect_primary()
            if self._primary and self._primary != old_primary:
                self._failover_history.append({
                    "from": old_primary,
                    "to": self._primary,
                    "reason": "primary_unhealthy",
                    "ts": time.time(),
                })
                # 标记失败节点
                failed = self._nodes.get(failed_node_id)
                if failed:
                    failed.role = NodeRole.OFFLINE

    def primary(self) -> Optional[str]:
        with self._lock:
            return self._primary

    def nodes(self) -> List[FailoverNode]:
        with self._lock:
            return list(self._nodes.values())

    def failover_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._failover_history)

    def is_quorum(self) -> bool:
        with self._lock:
            alive = sum(1 for n in self._nodes.values() if n.is_alive(self._heartbeat_timeout))
            total = len(self._nodes)
            return alive > total // 2

    def manual_failover(self, to_node_id: str) -> bool:
        with self._lock:
            target = self._nodes.get(to_node_id)
            if target is None or target.health != NodeHealth.HEALTHY:
                return False
            old = self._primary
            if old and old != to_node_id:
                old_node = self._nodes.get(old)
                if old_node:
                    old_node.role = NodeRole.SECONDARY
            target.role = NodeRole.PRIMARY
            self._primary = to_node_id
            self._failover_history.append({
                "from": old,
                "to": to_node_id,
                "reason": "manual",
                "ts": time.time(),
            })
            return True


# ============================================================
# 四、恢复计划
# ============================================================
class RecoveryStepType(Enum):
    """恢复步骤类型"""
    RESTORE_BACKUP = "restore_backup"
    PROMOTE_NODE = "promote_node"
    VERIFY_HEALTH = "verify_health"
    REDIRECT_TRAFFIC = "redirect_traffic"
    NOTIFY = "notify"
    WAIT = "wait"


@dataclass
class RecoveryStep:
    """恢复步骤"""
    step_id: str
    step_type: RecoveryStepType
    params: Dict[str, Any] = field(default_factory=dict)
    timeout_s: float = 30.0
    description: str = ""
    executed: bool = False
    success: Optional[bool] = None


@dataclass
class RecoveryPlan:
    """恢复计划"""
    name: str
    steps: List[RecoveryStep] = field(default_factory=list)
    rto_s: float = 300.0             # 恢复时间目标
    rpo_s: float = 60.0              # 恢复点目标
    description: str = ""

    def add_step(self, step_type: RecoveryStepType, **params) -> RecoveryStep:
        s = RecoveryStep(
            step_id=str(uuid.uuid4())[:8],
            step_type=step_type,
            params=params,
        )
        self.steps.append(s)
        return s

    def validate(self) -> bool:
        return len(self.steps) > 0 and self.rto_s > 0 and self.rpo_s >= 0


class RecoveryExecutor:
    """恢复执行器
    按顺序执行恢复计划中的步骤。
    """
    def __init__(self, backup_manager: BackupManager,
                 cluster: FailoverCluster):
        self.backup_manager = backup_manager
        self.cluster = cluster
        self._lock = threading.RLock()
        self._history: List[Dict[str, Any]] = []

    def execute(self, plan: RecoveryPlan) -> Dict[str, Any]:
        """执行恢复计划"""
        with self._lock:
            if not plan.validate():
                return {"success": False, "reason": "plan_invalid"}
            start = time.time()
            results = []
            overall_success = True

            for step in plan.steps:
                step_result = self._execute_step(step)
                results.append(step_result)
                if not step_result["success"]:
                    overall_success = False
                    break

            duration_s = time.time() - start
            met_rto = duration_s <= plan.rto_s
            record = {
                "plan": plan.name,
                "success": overall_success,
                "duration_s": round(duration_s, 3),
                "rto_s": plan.rto_s,
                "met_rto": met_rto,
                "steps": results,
            }
            self._history.append(record)
            return record

    def _execute_step(self, step: RecoveryStep) -> Dict[str, Any]:
        """执行单个步骤"""
        try:
            if step.step_type == RecoveryStepType.RESTORE_BACKUP:
                bid = step.params.get("backup_id", "")
                data = self.backup_manager.restore(bid)
                step.success = True
                step.executed = True
                return {"step": step.step_id, "type": "restore",
                        "success": True, "size": len(json.dumps(data, default=str))}
            if step.step_type == RecoveryStepType.PROMOTE_NODE:
                nid = step.params.get("node_id", "")
                ok = self.cluster.manual_failover(nid)
                step.success = ok
                step.executed = True
                return {"step": step.step_id, "type": "promote",
                        "success": ok}
            if step.step_type == RecoveryStepType.VERIFY_HEALTH:
                ok = self.cluster.is_quorum()
                step.success = ok
                step.executed = True
                return {"step": step.step_id, "type": "verify",
                        "success": ok}
            if step.step_type == RecoveryStepType.WAIT:
                secs = step.params.get("seconds", 0.0)
                time.sleep(min(secs, 0.1))  # 演示用
                step.success = True
                step.executed = True
                return {"step": step.step_id, "type": "wait",
                        "success": True}
            if step.step_type == RecoveryStepType.NOTIFY:
                step.success = True
                step.executed = True
                return {"step": step.step_id, "type": "notify",
                        "success": True, "message": step.params.get("msg", "")}
            if step.step_type == RecoveryStepType.REDIRECT_TRAFFIC:
                step.success = True
                step.executed = True
                return {"step": step.step_id, "type": "redirect",
                        "success": True}
            step.success = False
            return {"step": step.step_id, "type": "unknown",
                    "success": False}
        except Exception as e:
            step.success = False
            return {"step": step.step_id, "type": str(step.step_type.value),
                    "success": False, "error": str(e)}

    def history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history)


# ============================================================
# 五、灾备主控
# ============================================================
@dataclass
class RPOTracker:
    """RPO跟踪器"""
    last_backup_ts: float = 0.0
    target_s: float = 60.0
    failures: int = 0

    def current_rpo_s(self) -> float:
        if self.last_backup_ts == 0:
            return float('inf')
        return time.time() - self.last_backup_ts

    def is_violated(self) -> bool:
        return self.current_rpo_s() > self.target_s


@dataclass
class RTOTracker:
    """RTO跟踪器"""
    last_recovery_duration_s: float = 0.0
    target_s: float = 300.0
    recovery_count: int = 0

    def is_violated(self) -> bool:
        return self.last_recovery_duration_s > self.target_s


class DisasterRecovery:
    """灾备主控
    统一管理备份、切换、恢复。
    """
    def __init__(self, backup_manager: BackupManager,
                 cluster: FailoverCluster,
                 executor: RecoveryExecutor):
        self.backup_manager = backup_manager
        self.cluster = cluster
        self.executor = executor
        self.rpo = RPOTracker()
        self.rto = RTOTracker()
        self._lock = threading.RLock()
        self._drills: List[Dict[str, Any]] = []

    def snapshot(self, source: str, data: Any) -> Backup:
        """创建快照（备份）"""
        with self._lock:
            b = self.backup_manager.create_backup(
                source, data, BackupType.FULL)
            self.rpo.last_backup_ts = b.created_at
            return b

    def incremental(self, source: str, data: Any,
                    parent_id: Optional[str] = None) -> Backup:
        """增量备份"""
        with self._lock:
            b = self.backup_manager.create_backup(
                source, data, BackupType.INCREMENTAL, parent_id)
            return b

    def failover_to(self, node_id: str, plan: Optional[RecoveryPlan] = None) -> Dict[str, Any]:
        """故障切换到指定节点"""
        with self._lock:
            start = time.time()
            if plan is None:
                plan = RecoveryPlan(name="auto-failover", rto_s=60.0, rpo_s=10.0)
                plan.add_step(RecoveryStepType.PROMOTE_NODE, node_id=node_id)
                plan.add_step(RecoveryStepType.VERIFY_HEALTH)
                plan.add_step(RecoveryStepType.REDIRECT_TRAFFIC)
            result = self.executor.execute(plan)
            self.rto.last_recovery_duration_s = time.time() - start
            self.rto.recovery_count += 1
            return result

    def restore_from(self, backup_id: str,
                     plan: Optional[RecoveryPlan] = None) -> Dict[str, Any]:
        """从备份恢复"""
        with self._lock:
            start = time.time()
            if plan is None:
                plan = RecoveryPlan(name="auto-restore", rto_s=120.0, rpo_s=0.0)
                plan.add_step(RecoveryStepType.RESTORE_BACKUP, backup_id=backup_id)
                plan.add_step(RecoveryStepType.VERIFY_HEALTH)
            result = self.executor.execute(plan)
            self.rto.last_recovery_duration_s = time.time() - start
            self.rto.recovery_count += 1
            return result

    def drill(self, plan: RecoveryPlan) -> Dict[str, Any]:
        """灾备演练"""
        with self._lock:
            start = time.time()
            result = self.executor.execute(plan)
            duration = time.time() - start
            drill_record = {
                "plan": plan.name,
                "success": result.get("success", False),
                "duration_s": round(duration, 3),
                "met_rto": result.get("met_rto", False),
                "ts": start,
            }
            self._drills.append(drill_record)
            return drill_record

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "rpo": {
                    "target_s": self.rpo.target_s,
                    "current_s": round(self.rpo.current_rpo_s(), 2),
                    "violated": self.rpo.is_violated(),
                    "last_backup_ts": self.rpo.last_backup_ts,
                },
                "rto": {
                    "target_s": self.rto.target_s,
                    "last_duration_s": round(self.rto.last_recovery_duration_s, 3),
                    "violated": self.rto.is_violated(),
                    "recovery_count": self.rto.recovery_count,
                },
                "primary": self.cluster.primary(),
                "quorum": self.cluster.is_quorum(),
                "backups": len(self.backup_manager.list_backups()),
                "drills": len(self._drills),
            }


# ============================================================
# 六、测试
# ============================================================
class TestBackup(unittest.TestCase):
    def test_verify(self):
        b = Backup(
            backup_id="b1", backup_type=BackupType.FULL,
            source="kg", size_bytes=10, checksum="x",
            data={"a": 1}, status=BackupStatus.COMPLETED)
        # 错误checksum
        self.assertFalse(b.verify())
        # 修正checksum
        b.checksum = hashlib.sha256(
            json.dumps(b.data, sort_keys=True).encode()).hexdigest()
        self.assertTrue(b.verify())

    def test_summary(self):
        b = Backup(backup_id="b1", backup_type=BackupType.FULL,
                    source="kg", size_bytes=100, checksum="abc")
        s = b.summary()
        self.assertEqual(s["id"], "b1")
        self.assertEqual(s["type"], "full")


class TestBackupManager(unittest.TestCase):
    def test_create_backup(self):
        m = BackupManager(BackupPolicy(verify_after_backup=True))
        b = m.create_backup("kg", {"nodes": []})
        self.assertEqual(b.status, BackupStatus.VERIFIED)
        self.assertEqual(m.get_stats()["total_backups"], 1)

    def test_restore(self):
        m = BackupManager(BackupPolicy(verify_after_backup=True))
        data = {"nodes": [{"id": "n1"}]}
        b = m.create_backup("kg", data)
        restored = m.restore(b.backup_id)
        self.assertEqual(restored, data)

    def test_restore_corrupted(self):
        m = BackupManager(BackupPolicy(verify_after_backup=False))
        b = m.create_backup("kg", {"x": 1})
        b.status = BackupStatus.CORRUPTED
        with self.assertRaises(RuntimeError):
            m.restore(b.backup_id)

    def test_incremental_with_parent(self):
        m = BackupManager(BackupPolicy(verify_after_backup=True))
        b1 = m.create_backup("kg", {"v": 1}, BackupType.FULL)
        b2 = m.create_backup("kg", {"v": 2}, BackupType.INCREMENTAL,
                              parent_id=b1.backup_id)
        self.assertEqual(b2.parent_id, b1.backup_id)

    def test_latest_for(self):
        m = BackupManager(BackupPolicy(verify_after_backup=True))
        b1 = m.create_backup("kg", {"v": 1})
        b2 = m.create_backup("kg", {"v": 2})
        latest = m.latest_for("kg")
        self.assertEqual(latest.backup_id, b2.backup_id)

    def test_list_backups(self):
        m = BackupManager(BackupPolicy(verify_after_backup=True))
        m.create_backup("kg1", {"v": 1})
        m.create_backup("kg2", {"v": 2})
        self.assertEqual(len(m.list_backups()), 2)
        self.assertEqual(len(m.list_backups("kg1")), 1)

    def test_retention(self):
        m = BackupManager(BackupPolicy(retention_count=2,
                                         verify_after_backup=True))
        for i in range(5):
            m.create_backup("kg", {"v": i})
        self.assertLessEqual(len(m.list_backups("kg")), 2)

    def test_set_policy_invalid(self):
        m = BackupManager()
        with self.assertRaises(ValueError):
            m.set_policy(BackupPolicy(interval_s=0))


class TestFailoverNode(unittest.TestCase):
    def test_is_alive(self):
        n = FailoverNode("n1")
        self.assertTrue(n.is_alive(5.0))
        n.last_heartbeat = time.time() - 10
        self.assertFalse(n.is_alive(5.0))

    def test_touch(self):
        n = FailoverNode("n1")
        n.last_heartbeat = 0
        n.touch()
        self.assertGreater(n.last_heartbeat, 0)


class TestFailoverCluster(unittest.TestCase):
    def test_add_node_elects_primary(self):
        c = FailoverCluster()
        c.add_node(FailoverNode("n1", role=NodeRole.SECONDARY, priority=5))
        c.add_node(FailoverNode("n2", role=NodeRole.SECONDARY, priority=10))
        # 优先级高的应被选为primary
        self.assertEqual(c.primary(), "n2")

    def test_remove_node_triggers_failover(self):
        c = FailoverCluster()
        c.add_node(FailoverNode("n1", role=NodeRole.SECONDARY, priority=10))
        c.add_node(FailoverNode("n2", role=NodeRole.SECONDARY, priority=5))
        primary = c.primary()
        c.remove_node(primary)
        self.assertNotEqual(c.primary(), primary)
        self.assertEqual(c.primary(), "n2")

    def test_heartbeat(self):
        c = FailoverCluster()
        c.add_node(FailoverNode("n1", role=NodeRole.SECONDARY, priority=10))
        c.heartbeat("n1")
        n = c.nodes()[0]
        self.assertEqual(n.health, NodeHealth.HEALTHY)

    def test_quorum(self):
        c = FailoverCluster()
        c.add_node(FailoverNode("n1"))
        c.add_node(FailoverNode("n2"))
        c.add_node(FailoverNode("n3"))
        self.assertTrue(c.is_quorum())
        # 让两个节点超时
        c.nodes()[0].last_heartbeat = 0
        c.nodes()[1].last_heartbeat = 0
        self.assertFalse(c.is_quorum())

    def test_manual_failover(self):
        c = FailoverCluster()
        c.add_node(FailoverNode("n1", role=NodeRole.SECONDARY, priority=10))
        c.add_node(FailoverNode("n2", role=NodeRole.SECONDARY, priority=5))
        ok = c.manual_failover("n1")
        self.assertTrue(ok)
        self.assertEqual(c.primary(), "n1")

    def test_failover_history(self):
        c = FailoverCluster()
        c.add_node(FailoverNode("n1", role=NodeRole.SECONDARY, priority=10))
        c.add_node(FailoverNode("n2", role=NodeRole.SECONDARY, priority=5))
        c.manual_failover("n2")
        h = c.failover_history()
        self.assertGreaterEqual(len(h), 1)


class TestRecoveryPlan(unittest.TestCase):
    def test_add_step(self):
        p = RecoveryPlan("p1")
        p.add_step(RecoveryStepType.RESTORE_BACKUP, backup_id="b1")
        self.assertEqual(len(p.steps), 1)

    def test_validate(self):
        p = RecoveryPlan("p1")
        self.assertFalse(p.validate())
        p.add_step(RecoveryStepType.VERIFY_HEALTH)
        self.assertTrue(p.validate())


class TestRecoveryExecutor(unittest.TestCase):
    def test_restore_step(self):
        bm = BackupManager(BackupPolicy(verify_after_backup=True))
        b = bm.create_backup("kg", {"x": 1})
        c = FailoverCluster()
        c.add_node(FailoverNode("n1"))
        exe = RecoveryExecutor(bm, c)
        plan = RecoveryPlan("p1", rto_s=10.0)
        plan.add_step(RecoveryStepType.RESTORE_BACKUP, backup_id=b.backup_id)
        result = exe.execute(plan)
        self.assertTrue(result["success"])

    def test_promote_step(self):
        bm = BackupManager(BackupPolicy(verify_after_backup=True))
        c = FailoverCluster()
        c.add_node(FailoverNode("n1", priority=10))
        c.add_node(FailoverNode("n2", priority=5))
        exe = RecoveryExecutor(bm, c)
        plan = RecoveryPlan("p1", rto_s=10.0)
        plan.add_step(RecoveryStepType.PROMOTE_NODE, node_id="n1")
        result = exe.execute(plan)
        self.assertTrue(result["success"])

    def test_failed_step_stops(self):
        bm = BackupManager(BackupPolicy(verify_after_backup=True))
        c = FailoverCluster()
        exe = RecoveryExecutor(bm, c)
        plan = RecoveryPlan("p1", rto_s=10.0)
        plan.add_step(RecoveryStepType.RESTORE_BACKUP, backup_id="nonexistent")
        plan.add_step(RecoveryStepType.VERIFY_HEALTH)
        result = exe.execute(plan)
        self.assertFalse(result["success"])
        # 第二步不应执行
        self.assertEqual(len(result["steps"]), 1)


class TestRPOTracker(unittest.TestCase):
    def test_initial(self):
        t = RPOTracker(target_s=60.0)
        self.assertTrue(t.is_violated())

    def test_after_backup(self):
        t = RPOTracker(target_s=3600.0)
        t.last_backup_ts = time.time()
        self.assertFalse(t.is_violated())


class TestDisasterRecovery(unittest.TestCase):
    def test_snapshot(self):
        bm = BackupManager(BackupPolicy(verify_after_backup=True))
        c = FailoverCluster()
        c.add_node(FailoverNode("n1"))
        exe = RecoveryExecutor(bm, c)
        dr = DisasterRecovery(bm, c, exe)
        b = dr.snapshot("kg", {"nodes": 10})
        self.assertEqual(b.source, "kg")
        self.assertGreater(dr.rpo.last_backup_ts, 0)

    def test_failover_to(self):
        bm = BackupManager(BackupPolicy(verify_after_backup=True))
        c = FailoverCluster()
        c.add_node(FailoverNode("n1", priority=10))
        c.add_node(FailoverNode("n2", priority=5))
        exe = RecoveryExecutor(bm, c)
        dr = DisasterRecovery(bm, c, exe)
        result = dr.failover_to("n1")
        self.assertTrue(result["success"])
        self.assertEqual(c.primary(), "n1")

    def test_restore_from(self):
        bm = BackupManager(BackupPolicy(verify_after_backup=True))
        c = FailoverCluster()
        c.add_node(FailoverNode("n1"))
        exe = RecoveryExecutor(bm, c)
        dr = DisasterRecovery(bm, c, exe)
        b = dr.snapshot("kg", {"v": 1})
        result = dr.restore_from(b.backup_id)
        self.assertTrue(result["success"])

    def test_drill(self):
        bm = BackupManager(BackupPolicy(verify_after_backup=True))
        c = FailoverCluster()
        c.add_node(FailoverNode("n1"))
        exe = RecoveryExecutor(bm, c)
        dr = DisasterRecovery(bm, c, exe)
        b = dr.snapshot("kg", {"v": 1})
        plan = RecoveryPlan("drill", rto_s=10.0)
        plan.add_step(RecoveryStepType.RESTORE_BACKUP, backup_id=b.backup_id)
        result = dr.drill(plan)
        self.assertTrue(result["success"])
        self.assertEqual(len(dr._drills), 1)

    def test_status(self):
        bm = BackupManager(BackupPolicy(verify_after_backup=True))
        c = FailoverCluster()
        c.add_node(FailoverNode("n1"))
        exe = RecoveryExecutor(bm, c)
        dr = DisasterRecovery(bm, c, exe)
        st = dr.status()
        self.assertIn("rpo", st)
        self.assertIn("rto", st)
        self.assertIn("primary", st)


# ============================================================
# 七、Demo
# ============================================================
def demo():
    """演示阶段134的功能"""
    print("=" * 60)
    print("阶段134演示：灾备与恢复")
    print("=" * 60)

    # 1. 备份
    print("\n💾 演示1：备份管理")
    print("-" * 60)
    bm = BackupManager(BackupPolicy(retention_count=3, verify_after_backup=True))
    data_v1 = {"nodes": [{"id": f"n{i}"} for i in range(10)]}
    data_v2 = {"nodes": [{"id": f"n{i}"} for i in range(15)]}
    b1 = bm.create_backup("kg", data_v1, BackupType.FULL)
    b2 = bm.create_backup("kg", data_v2, BackupType.INCREMENTAL,
                           parent_id=b1.backup_id)
    print(f"  全量备份: {b1.summary()}")
    print(f"  增量备份: {b2.summary()}")
    print(f"  备份统计: {bm.get_stats()}")

    # 2. 恢复
    print("\n♻️  演示2：数据恢复")
    print("-" * 60)
    restored = bm.restore(b1.backup_id)
    print(f"  恢复数据: 节点数 = {len(restored['nodes'])}")

    # 3. 故障切换
    print("\n🔄 演示3：故障切换")
    print("-" * 60)
    c = FailoverCluster()
    c.add_node(FailoverNode("node-a", role=NodeRole.SECONDARY,
                              priority=10, region="us-east"))
    c.add_node(FailoverNode("node-b", role=NodeRole.SECONDARY,
                              priority=5, region="us-west"))
    c.add_node(FailoverNode("node-c", role=NodeRole.WITNESS,
                              priority=0, region="eu"))
    print(f"  初始主节点: {c.primary()}")
    print(f"  仲裁满足: {c.is_quorum()}")

    # 模拟主节点故障
    primary = c.primary()
    c.report_health(primary, NodeHealth.UNHEALTHY)
    print(f"  报告{primary}不健康后，主节点: {c.primary()}")
    print(f"  切换历史: {c.failover_history()}")

    # 4. 灾备演练
    print("\n🏋️ 演示4：灾备演练")
    print("-" * 60)
    exe = RecoveryExecutor(bm, c)
    dr = DisasterRecovery(bm, c, exe)
    b3 = dr.snapshot("kg", {"drill": True})
    plan = RecoveryPlan("drill-001", rto_s=10.0, rpo_s=1.0)
    plan.add_step(RecoveryStepType.RESTORE_BACKUP, backup_id=b3.backup_id)
    plan.add_step(RecoveryStepType.VERIFY_HEALTH)
    result = dr.drill(plan)
    print(f"  演练结果: success={result['success']}, "
          f"duration={result['duration_s']}s, "
          f"met_rto={result['met_rto']}")

    # 5. 灾备主控
    print("\n🎛️  演示5：灾备主控状态")
    print("-" * 60)
    status = dr.status()
    print(f"  RPO: 当前 {status['rpo']['current_s']}s / 目标 {status['rpo']['target_s']}s")
    print(f"      违反 = {status['rpo']['violated']}")
    print(f"  RTO: 目标 {status['rto']['target_s']}s")
    print(f"  当前主: {status['primary']}")
    print(f"  仲裁: {status['quorum']}")
    print(f"  备份数: {status['backups']}")
    print(f"  演练数: {status['drills']}")

    print("\n" + "=" * 60)
    print("✅ 阶段134完成：灾备与恢复已实现！")
    print("=" * 60)
    print("\n【下阶段预告】阶段135：跨平台适配")
    print("  - 抽象层")
    print("  - 平台检测")
    print("  - 适配器")


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    print()
    demo()
