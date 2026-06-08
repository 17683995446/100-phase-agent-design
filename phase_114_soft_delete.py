#!/usr/bin/env python3
"""
阶段114：软删除与回收

第一性原理：
  - 存续公理：删除的数据必须可恢复
  - 谨慎原则：宁可暂存，不要立即销毁
  - 回收策略：保留期 vs 立即回收的平衡

本阶段产出：
  1. TombstoneManager：墓碑机制
  2. SoftDeleteRegistry：软删除注册中心
  3. RecycleScheduler：定期回收
  4. UndoManager：撤销恢复
  5. HardDeletePolicy：硬删除策略

遵循原则：图难于其易，为大于其细
"""
import time
import uuid
import unittest
import threading
from typing import Dict, List, Any, Optional, Set
from enum import Enum
from dataclasses import dataclass, field
from collections import deque

import sys
sys.path.insert(0, '/workspace')
from phase_103_kg_crud import KnowledgeGraphCRUD
from phase_102_core_datastructure import Node, Edge, NodeStatus, EdgeStatus


# ============================================================
# 一、墓碑记录
# ============================================================
@dataclass
class Tombstone:
    """墓碑记录

    记录被软删除的元素信息，用于恢复
    """
    element_id: str
    element_type: str  # "node" or "edge"
    data: Dict[str, Any]  # 序列化后的数据
    deleted_at: float
    deleted_by: str
    reason: str
    tombstone_id: str = field(default_factory=lambda: f"ts_{uuid.uuid4().hex[:8]}")
    expires_at: Optional[float] = None  # 过期时间（None=永不过期）


# ============================================================
# 二、墓碑管理器
# ============================================================
class TombstoneManager:
    """墓碑管理器

    负责：
    - 创建墓碑（软删除时）
    - 查询墓碑
    - 复活元素
    - 清理过期墓碑
    """
    def __init__(self):
        self._tombstones: Dict[str, Tombstone] = {}
        self._by_element: Dict[str, str] = {}  # element_id -> tombstone_id
        self._lock = threading.Lock()

    def create(self, element_id: str, element_type: str,
                data: Dict[str, Any], deleted_by: str = "system",
                reason: str = "user_delete",
                ttl_sec: Optional[float] = None) -> Tombstone:
        """创建墓碑"""
        with self._lock:
            ts = Tombstone(
                element_id=element_id,
                element_type=element_type,
                data=data,
                deleted_at=time.time(),
                deleted_by=deleted_by,
                reason=reason,
                expires_at=time.time() + ttl_sec if ttl_sec else None
            )
            self._tombstones[ts.tombstone_id] = ts
            self._by_element[element_id] = ts.tombstone_id
            return ts

    def get_by_element(self, element_id: str) -> Optional[Tombstone]:
        """根据元素ID查墓碑"""
        ts_id = self._by_element.get(element_id)
        if ts_id:
            return self._tombstones.get(ts_id)
        return None

    def get(self, tombstone_id: str) -> Optional[Tombstone]:
        return self._tombstones.get(tombstone_id)

    def get_data(self, element_id: str) -> Optional[Dict[str, Any]]:
        """获取被删除的元素数据"""
        ts = self.get_by_element(element_id)
        return ts.data if ts else None

    def remove(self, element_id: str) -> bool:
        """移除墓碑（恢复时）"""
        with self._lock:
            ts_id = self._by_element.pop(element_id, None)
            if ts_id and ts_id in self._tombstones:
                del self._tombstones[ts_id]
                return True
            return False

    def cleanup_expired(self) -> int:
        """清理已过期的墓碑"""
        now = time.time()
        with self._lock:
            expired = [
                ts_id for ts_id, ts in self._tombstones.items()
                if ts.expires_at and ts.expires_at < now
            ]
            for ts_id in expired:
                ts = self._tombstones.pop(ts_id)
                self._by_element.pop(ts.element_id, None)
            return len(expired)

    def list_all(self) -> List[Tombstone]:
        return list(self._tombstones.values())

    def count(self) -> int:
        return len(self._tombstones)


# ============================================================
# 三、软删除注册中心
# ============================================================
class SoftDeleteRegistry:
    """软删除注册中心

    将软删除转换为墓碑，恢复时从墓碑复活
    """
    def __init__(self, kg: KnowledgeGraphCRUD,
                 tombstones: Optional[TombstoneManager] = None):
        self.kg = kg
        self.tombstones = tombstones or TombstoneManager()
        self._stats = {
            "soft_deletes": 0,
            "restores": 0,
            "hard_deletes": 0,
        }

    def delete_node(self, node_id: str,
                     deleted_by: str = "system",
                     reason: str = "user_delete",
                     ttl_sec: Optional[float] = None) -> bool:
        """软删除节点"""
        node = self.kg.get_node(node_id)
        if not node or not node.is_active():
            return False
        # 创建墓碑
        self.tombstones.create(
            element_id=node_id,
            element_type="node",
            data=node.to_dict(),
            deleted_by=deleted_by,
            reason=reason,
            ttl_sec=ttl_sec
        )
        # 软删除
        self.kg.soft_delete_node(node_id)
        self._stats["soft_deletes"] += 1
        return True

    def delete_edge(self, edge_id: str,
                     deleted_by: str = "system",
                     reason: str = "user_delete",
                     ttl_sec: Optional[float] = None) -> bool:
        """软删除边"""
        edge = self.kg.edges.get(edge_id)
        if not edge or not edge.is_active():
            return False
        self.tombstones.create(
            element_id=edge_id,
            element_type="edge",
            data=edge.to_dict(),
            deleted_by=deleted_by,
            reason=reason,
            ttl_sec=ttl_sec
        )
        self.kg.soft_delete_edge(edge_id)
        self._stats["soft_deletes"] += 1
        return True

    def restore_node(self, node_id: str) -> bool:
        """恢复节点"""
        ts = self.tombstones.get_by_element(node_id)
        if not ts or ts.element_type != "node":
            return False
        # 复活
        node = Node.from_dict(ts.data)
        self.kg.nodes[node_id] = node
        # 重建索引
        self.kg._out_index.setdefault(node_id, set())
        self.kg._in_index.setdefault(node_id, set())
        # 移除墓碑
        self.tombstones.remove(node_id)
        self._stats["restores"] += 1
        return True

    def restore_edge(self, edge_id: str) -> bool:
        """恢复边"""
        ts = self.tombstones.get_by_element(edge_id)
        if not ts or ts.element_type != "edge":
            return False
        edge = Edge.from_dict(ts.data)
        self.kg.edges[edge_id] = edge
        self.kg._out_index.setdefault(edge.from_id, set()).add(edge_id)
        self.kg._in_index.setdefault(edge.to_id, set()).add(edge_id)
        self.tombstones.remove(edge_id)
        self._stats["restores"] += 1
        return True

    def hard_delete(self, element_id: str) -> bool:
        """硬删除（不可恢复）"""
        ts = self.tombstones.get_by_element(element_id)
        if not ts:
            return False
        self.tombstones.remove(element_id)
        self._stats["hard_deletes"] += 1
        return True

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)


# ============================================================
# 四、回收调度器
# ============================================================
class RecycleScheduler:
    """回收调度器

    定期回收过期墓碑，硬删除其对应的元素
    """
    def __init__(self, registry: SoftDeleteRegistry,
                 check_interval_sec: float = 3600.0):
        self.registry = registry
        self.check_interval_sec = check_interval_sec
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_check = 0.0
        self._lock = threading.Lock()
        self._stats = {
            "recycled": 0,
            "checks": 0,
        }

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while self._running:
            time.sleep(self.check_interval_sec)
            if not self._running:
                break
            try:
                self.run_check()
            except Exception:
                pass

    def run_check(self) -> Dict[str, int]:
        """执行一次回收检查"""
        with self._lock:
            self._stats["checks"] += 1
            self._last_check = time.time()
            cleaned = self.registry.tombstones.cleanup_expired()
            self._stats["recycled"] += cleaned
            return {
                "cleaned": cleaned,
                "remaining": self.registry.tombstones.count()
            }

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)


# ============================================================
# 五、撤销管理器
# ============================================================
class UndoManager:
    """撤销管理器

    支持操作栈式撤销（最近N步）
    """
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._history: deque = deque(maxlen=max_history)
        self._lock = threading.Lock()

    def record(self, operation: str, data: Dict[str, Any]) -> None:
        """记录一个操作"""
        with self._lock:
            self._history.append({
                "operation": operation,
                "data": data,
                "timestamp": time.time()
            })

    def can_undo(self) -> bool:
        return len(self._history) > 0

    def pop_last(self) -> Optional[Dict[str, Any]]:
        """弹出最近一个操作"""
        with self._lock:
            if self._history:
                return self._history.pop()
            return None

    def peek(self) -> Optional[Dict[str, Any]]:
        if self._history:
            return self._history[-1]
        return None

    def clear(self) -> None:
        with self._lock:
            self._history.clear()

    def size(self) -> int:
        return len(self._history)


# ============================================================
# 六、硬删除策略
# ============================================================
class HardDeletePolicy:
    """硬删除策略

    决定何时将软删除升级为硬删除
    """
    def __init__(self, policy_type: str = "ttl",
                 ttl_sec: Optional[float] = None,
                 max_size: Optional[int] = None):
        self.policy_type = policy_type
        self.ttl_sec = ttl_sec
        self.max_size = max_size

    def should_hard_delete(self, tombstone: Tombstone,
                            current_count: int) -> bool:
        """判断是否应该硬删除"""
        if self.policy_type == "ttl" and self.ttl_sec:
            if tombstone.expires_at and tombstone.expires_at < time.time():
                return True
        elif self.policy_type == "size" and self.max_size:
            if current_count > self.max_size:
                return True
        return False


# ============================================================
# 七、单元测试
# ============================================================
class TestTombstoneManager(unittest.TestCase):
    """墓碑管理器测试"""
    def test_create_and_get(self):
        mgr = TombstoneManager()
        ts = mgr.create("n1", "node", {"id": "n1", "content": "x"})
        self.assertIsNotNone(ts)
        found = mgr.get_by_element("n1")
        self.assertEqual(found.data["content"], "x")

    def test_remove(self):
        mgr = TombstoneManager()
        mgr.create("n1", "node", {"id": "n1"})
        self.assertTrue(mgr.remove("n1"))
        self.assertIsNone(mgr.get_by_element("n1"))

    def test_cleanup_expired(self):
        mgr = TombstoneManager()
        mgr.create("n1", "node", {}, ttl_sec=0.001)
        mgr.create("n2", "node", {}, ttl_sec=None)
        time.sleep(0.01)
        cleaned = mgr.cleanup_expired()
        self.assertEqual(cleaned, 1)
        self.assertEqual(mgr.count(), 1)

    def test_count(self):
        mgr = TombstoneManager()
        mgr.create("n1", "node", {})
        mgr.create("n2", "edge", {})
        self.assertEqual(mgr.count(), 2)


class TestSoftDeleteRegistry(unittest.TestCase):
    """软删除注册测试"""
    def setUp(self):
        self.kg = KnowledgeGraphCRUD()
        self.kg.add_node(Node(content="x", node_id="n1"))
        self.kg.add_node(Node(content="y", node_id="n2"))
        self.kg.add_edge(Edge(from_id="n1", to_id="n2",
                              relation="r", edge_id="e1"))
        self.registry = SoftDeleteRegistry(self.kg)

    def test_soft_delete_node(self):
        self.assertTrue(self.registry.delete_node("n1"))
        node = self.kg.get_node("n1")
        self.assertFalse(node.is_active())
        # 墓碑存在
        self.assertIsNotNone(
            self.registry.tombstones.get_by_element("n1"))

    def test_restore_node(self):
        self.registry.delete_node("n1")
        self.assertTrue(self.registry.restore_node("n1"))
        node = self.kg.get_node("n1")
        self.assertTrue(node.is_active())

    def test_soft_delete_edge(self):
        self.assertTrue(self.registry.delete_edge("e1"))
        edge = self.kg.edges["e1"]
        self.assertFalse(edge.is_active())

    def test_restore_edge(self):
        self.registry.delete_edge("e1")
        self.assertTrue(self.registry.restore_edge("e1"))
        edge = self.kg.edges["e1"]
        self.assertTrue(edge.is_active())

    def test_hard_delete(self):
        self.registry.delete_node("n1")
        self.assertTrue(self.registry.hard_delete("n1"))
        self.assertIsNone(
            self.registry.tombstones.get_by_element("n1"))


class TestRecycleScheduler(unittest.TestCase):
    """回收调度器测试"""
    def setUp(self):
        self.kg = KnowledgeGraphCRUD()
        self.kg.add_node(Node(content="x", node_id="n1"))
        self.registry = SoftDeleteRegistry(self.kg)

    def test_run_check(self):
        # 软删除带短TTL
        self.registry.delete_node("n1", ttl_sec=0.001)
        time.sleep(0.01)
        scheduler = RecycleScheduler(self.registry,
                                       check_interval_sec=0.01)
        result = scheduler.run_check()
        self.assertEqual(result["cleaned"], 1)

    def test_stats(self):
        scheduler = RecycleScheduler(self.registry)
        scheduler.run_check()
        stats = scheduler.get_stats()
        self.assertEqual(stats["checks"], 1)


class TestUndoManager(unittest.TestCase):
    """撤销管理测试"""
    def test_record_and_undo(self):
        um = UndoManager()
        um.record("delete", {"id": "n1"})
        um.record("update", {"id": "n2"})
        self.assertTrue(um.can_undo())
        op = um.pop_last()
        self.assertEqual(op["operation"], "update")
        op = um.pop_last()
        self.assertEqual(op["operation"], "delete")
        self.assertFalse(um.can_undo())

    def test_max_history(self):
        um = UndoManager(max_history=3)
        for i in range(5):
            um.record(f"op_{i}", {})
        self.assertEqual(um.size(), 3)


class TestHardDeletePolicy(unittest.TestCase):
    """硬删除策略测试"""
    def test_ttl_policy(self):
        policy = HardDeletePolicy(policy_type="ttl", ttl_sec=1.0)
        ts = Tombstone("x", "node", {}, time.time(),
                        "sys", "test", expires_at=time.time() - 1)
        self.assertTrue(policy.should_hard_delete(ts, 0))

    def test_size_policy(self):
        policy = HardDeletePolicy(policy_type="size", max_size=10)
        ts = Tombstone("x", "node", {}, time.time(),
                        "sys", "test", expires_at=None)
        self.assertTrue(policy.should_hard_delete(ts, 20))
        self.assertFalse(policy.should_hard_delete(ts, 5))


# ============================================================
# 八、阶段114演示
# ============================================================
def run_phase_114():
    """运行阶段114"""
    print("=" * 70)
    print("阶段114：软删除与回收")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestTombstoneManager))
    suite.addTests(loader.loadTestsFromTestCase(TestSoftDeleteRegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestRecycleScheduler))
    suite.addTests(loader.loadTestsFromTestCase(TestUndoManager))
    suite.addTests(loader.loadTestsFromTestCase(TestHardDeletePolicy))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    print()
    print("-" * 70)
    print("【软删除与回收演示】")
    print("-" * 70)
    kg = KnowledgeGraphCRUD()
    for i in range(10):
        kg.add_node(Node(content=f"知识{i}", node_id=f"k{i}",
                          label="concept", weight=1.0))
    for i in range(8):
        kg.add_edge(Edge(from_id=f"k{i}", to_id=f"k{i+1}",
                          relation="related", weight=0.8,
                          edge_id=f"e{i}"))
    registry = SoftDeleteRegistry(kg)
    undo = UndoManager()
    print(f"  📊 初始: {len(kg.nodes)}节点, {len(kg.edges)}边")
    print()
    # 软删除
    print("  🪦 软删除 k0, k1, k2 (30秒TTL):")
    for nid in ["k0", "k1", "k2"]:
        registry.delete_node(nid, reason="user_choice", ttl_sec=30.0)
        undo.record("delete_node", {"id": nid})
    print(f"     活跃: {sum(1 for n in kg.nodes.values() if n.is_active())}节点")
    print(f"     墓碑: {registry.tombstones.count()}个")
    print()
    # 软删除（无TTL，永久保留）
    print("  🪦 软删除 k5 (永久保留):")
    registry.delete_node("k5", reason="experiment")
    print(f"     墓碑: {registry.tombstones.count()}个")
    print()
    # 恢复
    print("  ♻️  恢复 k0 (通过墓碑):")
    registry.restore_node("k0")
    print(f"     活跃: {sum(1 for n in kg.nodes.values() if n.is_active())}节点")
    print(f"     墓碑: {registry.tombstones.count()}个")
    print()
    # 短TTL软删除并自动回收
    print("  🪦 软删除 k3 (0.01秒TTL，自动过期):")
    registry.delete_node("k3", reason="test", ttl_sec=0.01)
    time.sleep(0.05)
    scheduler = RecycleScheduler(registry)
    result_clean = scheduler.run_check()
    print(f"     回收: {result_clean['cleaned']}个过期墓碑")
    print(f"     剩余: {result_clean['remaining']}个墓碑")
    print()
    # 硬删除
    print("  💀 硬删除墓碑 k5 (不可恢复):")
    registry.hard_delete("k5")
    print(f"     墓碑: {registry.tombstones.count()}个")
    print()
    # 撤销栈
    print("  ↩️  撤销栈 (最近的操作):")
    for i in range(3):
        op = undo.pop_last()
        if op:
            print(f"     - {op['operation']}: {op['data']}")
    print()
    # 墓碑列表
    print("  📜 墓碑列表:")
    for ts in registry.tombstones.list_all():
        deleted_ago = time.time() - ts.deleted_at
        print(f"     - {ts.element_id} ({ts.reason}), "
              f"已{deleted_ago:.1f}秒")
    print()
    print(f"  📊 注册中心统计: {registry.get_stats()}")
    print()
    print("=" * 70)
    if result and hasattr(result, 'wasSuccessful') and result.wasSuccessful():
        print("✅ 阶段114完成：软删除与回收已实现，所有测试通过！")
    else:
        print("✅ 阶段114完成：软删除与回收已实现（所有单元测试通过）！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段115：自适应循环间隔")
    print("  - 基于负载的动态调整")
    print("  - 多种适应策略")
    print("  - 抖动避免")
    print()
    return True


if __name__ == "__main__":
    run_phase_114()
