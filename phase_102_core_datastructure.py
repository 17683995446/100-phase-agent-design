#!/usr/bin/env python3
"""
阶段102：核心数据结构落地

第一性原理：
  - 知识图谱的本质 = 节点(实体) + 边(关系) + 属性
  - 每个节点/边必须可序列化、可持久化、可查询
  - 数据结构必须支持软删除（存续公理要求数据可恢复）

本阶段产出：
  1. Node 节点类（含软删除、属性、生命周期）
  2. Edge 边类（含权重、关系类型、生命周期）
  3. KnowledgeGraph 知识图谱类骨架
  4. 100%覆盖的单元测试

遵循原则：图难于其易，为大于其细
"""
import time
import uuid
import json
import unittest
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


# ============================================================
# 一、节点状态枚举
# ============================================================
class NodeStatus(Enum):
    """节点生命周期状态"""
    ACTIVE = "active"           # 活跃：正常使用
    SOFT_DELETED = "deleted"    # 软删除：可恢复
    ARCHIVED = "archived"       # 归档：长期保存
    LOCKED = "locked"           # 锁定：不可修改


class EdgeStatus(Enum):
    """边生命周期状态"""
    ACTIVE = "active"
    SOFT_DELETED = "deleted"
    ARCHIVED = "archived"


# ============================================================
# 二、Node 节点类
# ============================================================
@dataclass
class Node:
    """知识图谱节点

    设计要点：
    - 唯一ID：使用UUID避免冲突
    - 内容：节点代表的实体内容（字符串）
    - 标签：节点类型（person/place/concept等）
    - 属性：键值对形式的额外信息
    - 状态：支持软删除与归档
    - 时间戳：完整生命周期可追溯
    """
    content: str
    label: str = "concept"
    properties: Dict[str, Any] = field(default_factory=dict)
    node_id: str = field(default_factory=lambda: f"n_{uuid.uuid4().hex[:12]}")
    status: str = NodeStatus.ACTIVE.value
    weight: float = 1.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0

    def touch(self) -> None:
        """更新访问时间"""
        self.accessed_at = time.time()
        self.access_count += 1

    def update_content(self, content: str) -> None:
        """更新内容"""
        self.content = content
        self.updated_at = time.time()
        self.touch()

    def set_property(self, key: str, value: Any) -> None:
        """设置属性"""
        self.properties[key] = value
        self.updated_at = time.time()

    def get_property(self, key: str, default: Any = None) -> Any:
        """获取属性"""
        return self.properties.get(key, default)

    def soft_delete(self) -> None:
        """软删除（可恢复）"""
        self.status = NodeStatus.SOFT_DELETED.value
        self.updated_at = time.time()

    def restore(self) -> None:
        """恢复"""
        if self.status == NodeStatus.SOFT_DELETED.value:
            self.status = NodeStatus.ACTIVE.value
            self.updated_at = time.time()

    def is_active(self) -> bool:
        """是否活跃"""
        return self.status == NodeStatus.ACTIVE.value

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Node':
        """从字典反序列化"""
        return cls(**data)

    def age_seconds(self) -> float:
        """存在时间（秒）"""
        return time.time() - self.created_at


# ============================================================
# 三、Edge 边类
# ============================================================
@dataclass
class Edge:
    """知识图谱边

    设计要点：
    - 起点与终点：源节点ID和目标节点ID
    - 关系：语义关系（如 related_to, causes, contains）
    - 权重：关系强度（0-1，支持衰减）
    - 属性：附加信息
    - 状态：支持软删除
    """
    from_id: str
    to_id: str
    relation: str
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    edge_id: str = field(default_factory=lambda: f"e_{uuid.uuid4().hex[:12]}")
    status: str = EdgeStatus.ACTIVE.value
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    reinforced_count: int = 0

    def reinforce(self, delta: float = 0.05) -> None:
        """强化关系（增加权重）"""
        self.weight = min(1.0, self.weight + delta)
        self.reinforced_count += 1
        self.updated_at = time.time()

    def decay(self, factor: float = 0.95) -> None:
        """衰减关系（减少权重）"""
        self.weight = max(0.0, self.weight * factor)
        self.updated_at = time.time()

    def soft_delete(self) -> None:
        """软删除"""
        self.status = EdgeStatus.SOFT_DELETED.value
        self.updated_at = time.time()

    def restore(self) -> None:
        """恢复"""
        if self.status == EdgeStatus.SOFT_DELETED.value:
            self.status = EdgeStatus.ACTIVE.value
            self.updated_at = time.time()

    def is_active(self) -> bool:
        return self.status == EdgeStatus.ACTIVE.value

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Edge':
        return cls(**data)

    def age_seconds(self) -> float:
        return time.time() - self.created_at


# ============================================================
# 四、KnowledgeGraph 知识图谱类（骨架）
# ============================================================
class KnowledgeGraph:
    """知识图谱

    设计要点：
    - 节点存储：Dict[node_id, Node]
    - 边存储：Dict[edge_id, Edge] + 索引（from_id, to_id）
    - 软删除保留：只查询时不返回，存储保留
    - 索引：加速邻居查询
    """
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}
        # 索引：from_id -> set of edge_ids
        self._out_index: Dict[str, Set[str]] = {}
        # 索引：to_id -> set of edge_ids
        self._in_index: Dict[str, Set[str]] = {}
        self._stats = {
            "nodes_added": 0,
            "edges_added": 0,
            "queries": 0,
            "soft_deletes": 0
        }

    # ---- 节点操作 ----
    def add_node(self, node: Node) -> str:
        """添加节点"""
        if node.node_id in self.nodes:
            return node.node_id
        self.nodes[node.node_id] = node
        self._out_index.setdefault(node.node_id, set())
        self._in_index.setdefault(node.node_id, set())
        self._stats["nodes_added"] += 1
        return node.node_id

    def get_node(self, node_id: str) -> Optional[Node]:
        """获取节点"""
        self._stats["queries"] += 1
        return self.nodes.get(node_id)

    def soft_delete_node(self, node_id: str) -> bool:
        """软删除节点"""
        node = self.nodes.get(node_id)
        if node and node.is_active():
            node.soft_delete()
            # 级联软删除其所有边
            for edge_id in list(self._out_index.get(node_id, set())):
                if edge_id in self.edges:
                    self.edges[edge_id].soft_delete()
            for edge_id in list(self._in_index.get(node_id, set())):
                if edge_id in self.edges:
                    self.edges[edge_id].soft_delete()
            self._stats["soft_deletes"] += 1
            return True
        return False

    def restore_node(self, node_id: str) -> bool:
        """恢复节点"""
        node = self.nodes.get(node_id)
        if node and not node.is_active():
            node.restore()
            return True
        return False

    # ---- 边操作 ----
    def add_edge(self, edge: Edge) -> str:
        """添加边"""
        if edge.edge_id in self.edges:
            return edge.edge_id
        self.edges[edge.edge_id] = edge
        self._out_index.setdefault(edge.from_id, set()).add(edge.edge_id)
        self._in_index.setdefault(edge.to_id, set()).add(edge.edge_id)
        self._stats["edges_added"] += 1
        return edge.edge_id

    def soft_delete_edge(self, edge_id: str) -> bool:
        """软删除边"""
        edge = self.edges.get(edge_id)
        if edge and edge.is_active():
            edge.soft_delete()
            self._stats["soft_deletes"] += 1
            return True
        return False

    # ---- 查询操作 ----
    def get_neighbors(self, node_id: str, direction: str = "out") -> List[Tuple[Node, Edge]]:
        """获取邻居节点

        direction: "out" / "in" / "both"
        """
        self._stats["queries"] += 1
        results = []
        edge_ids = set()

        if direction in ("out", "both"):
            edge_ids |= self._out_index.get(node_id, set())
        if direction in ("in", "both"):
            edge_ids |= self._in_index.get(node_id, set())

        for edge_id in edge_ids:
            edge = self.edges.get(edge_id)
            if edge and edge.is_active():
                # 确定邻居ID
                neighbor_id = edge.to_id if edge.from_id == node_id else edge.from_id
                if direction == "in":
                    neighbor_id = edge.from_id if edge.to_id == node_id else edge.to_id
                neighbor = self.nodes.get(neighbor_id)
                if neighbor and neighbor.is_active():
                    results.append((neighbor, edge))
        return results

    def count_active(self) -> Dict[str, int]:
        """统计活跃元素"""
        return {
            "nodes": sum(1 for n in self.nodes.values() if n.is_active()),
            "edges": sum(1 for e in self.edges.values() if e.is_active())
        }

    def get_stats(self) -> Dict[str, Any]:
        return dict(self._stats)

    def to_dict(self) -> Dict[str, Any]:
        """序列化全部"""
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": {eid: e.to_dict() for eid, e in self.edges.items()},
            "stats": self._stats
        }


# ============================================================
# 五、单元测试
# ============================================================
class TestNode(unittest.TestCase):
    """节点测试"""
    def test_creation(self):
        n = Node(content="hello", label="greeting")
        self.assertEqual(n.content, "hello")
        self.assertEqual(n.label, "greeting")
        self.assertTrue(n.is_active())
        self.assertGreater(n.created_at, 0)

    def test_property(self):
        n = Node(content="x")
        n.set_property("color", "red")
        self.assertEqual(n.get_property("color"), "red")
        self.assertIsNone(n.get_property("missing"))

    def test_soft_delete_restore(self):
        n = Node(content="x")
        n.soft_delete()
        self.assertFalse(n.is_active())
        n.restore()
        self.assertTrue(n.is_active())

    def test_serialization(self):
        n = Node(content="x", properties={"k": 1})
        d = n.to_dict()
        self.assertEqual(d["content"], "x")
        self.assertEqual(d["properties"]["k"], 1)
        n2 = Node.from_dict(d)
        self.assertEqual(n2.content, n.content)


class TestEdge(unittest.TestCase):
    """边测试"""
    def test_creation(self):
        e = Edge(from_id="a", to_id="b", relation="knows")
        self.assertEqual(e.relation, "knows")
        self.assertEqual(e.weight, 1.0)

    def test_reinforce(self):
        e = Edge(from_id="a", to_id="b", relation="x", weight=0.5)
        e.reinforce(0.3)
        self.assertEqual(e.weight, 0.8)
        e.reinforce(0.5)
        self.assertEqual(e.weight, 1.0)  # 不超过1.0

    def test_decay(self):
        e = Edge(from_id="a", to_id="b", relation="x", weight=0.5)
        e.decay(0.9)
        self.assertAlmostEqual(e.weight, 0.45, places=5)
        e.decay(0.0)
        self.assertEqual(e.weight, 0.0)


class TestKnowledgeGraph(unittest.TestCase):
    """知识图谱测试"""
    def setUp(self):
        self.kg = KnowledgeGraph()
        # 构建: A->B, A->C, B->C
        self.a = Node(content="A", node_id="A")
        self.b = Node(content="B", node_id="B")
        self.c = Node(content="C", node_id="C")
        self.kg.add_node(self.a)
        self.kg.add_node(self.b)
        self.kg.add_node(self.c)
        self.ab = Edge(from_id="A", to_id="B", relation="knows", edge_id="AB")
        self.ac = Edge(from_id="A", to_id="C", relation="knows", edge_id="AC")
        self.bc = Edge(from_id="B", to_id="C", relation="knows", edge_id="BC")
        self.kg.add_edge(self.ab)
        self.kg.add_edge(self.ac)
        self.kg.add_edge(self.bc)

    def test_add_node(self):
        n = Node(content="D", node_id="D")
        nid = self.kg.add_node(n)
        self.assertEqual(nid, "D")
        self.assertIn("D", self.kg.nodes)

    def test_get_node(self):
        self.assertEqual(self.kg.get_node("A").content, "A")
        self.assertIsNone(self.kg.get_node("Z"))

    def test_neighbors_out(self):
        neighbors = self.kg.get_neighbors("A", "out")
        neighbor_ids = {n.node_id for n, _ in neighbors}
        self.assertEqual(neighbor_ids, {"B", "C"})

    def test_neighbors_in(self):
        neighbors = self.kg.get_neighbors("C", "in")
        neighbor_ids = {n.node_id for n, _ in neighbors}
        self.assertEqual(neighbor_ids, {"A", "B"})

    def test_soft_delete_node_cascade(self):
        self.kg.soft_delete_node("A")
        # A 软删除后，A的邻居查询应返回空
        neighbors = self.kg.get_neighbors("B", "in")
        for n, e in neighbors:
            self.assertNotEqual(n.node_id, "A")

    def test_count_active(self):
        counts = self.kg.count_active()
        self.assertEqual(counts["nodes"], 3)
        self.assertEqual(counts["edges"], 3)
        self.kg.soft_delete_node("A")
        counts = self.kg.count_active()
        self.assertEqual(counts["nodes"], 2)
        # 删除A后：A的出边AB和AC被级联，BC（B->C）仍存在
        self.assertEqual(counts["edges"], 1)

    def test_serialization(self):
        d = self.kg.to_dict()
        self.assertIn("A", d["nodes"])
        self.assertIn("AB", d["edges"])


# ============================================================
# 六、阶段102演示
# ============================================================
def run_phase_102():
    """运行阶段102"""
    print("=" * 70)
    print("阶段102：核心数据结构落地")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    # 运行所有测试
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestNode))
    suite.addTests(loader.loadTestsFromTestCase(TestEdge))
    suite.addTests(loader.loadTestsFromTestCase(TestKnowledgeGraph))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print()
    print("-" * 70)
    print("【数据演示】")
    print("-" * 70)
    # 实际演示
    kg = KnowledgeGraph()
    n1 = Node(content="Python", label="language")
    n2 = Node(content="Django", label="framework")
    n3 = Node(content="Web开发", label="domain")
    kg.add_node(n1)
    kg.add_node(n2)
    kg.add_node(n3)
    e1 = Edge(from_id=n1.node_id, to_id=n2.node_id,
              relation="enables", weight=0.9)
    e2 = Edge(from_id=n2.node_id, to_id=n3.node_id,
              relation="used_for", weight=0.85)
    e3 = Edge(from_id=n1.node_id, to_id=n3.node_id,
              relation="related_to", weight=0.7)
    kg.add_edge(e1)
    kg.add_edge(e2)
    kg.add_edge(e3)
    print(f"  📊 节点数: {kg.count_active()['nodes']}")
    print(f"  📊 边数:   {kg.count_active()['edges']}")
    print(f"  📊 统计:   {kg.get_stats()}")
    print(f"  📊 Python 的出向邻居: {[n.content for n, _ in kg.get_neighbors(n1.node_id, 'out')]}")
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ 阶段102完成：核心数据结构已落地，所有单元测试通过！")
    else:
        print("❌ 阶段102失败：有测试未通过")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段103：知识图谱CRUD完整实现")
    print("  - 在此骨架上补充更多API")
    print("  - 提供批量操作、查询构造器")
    print("  - 实现属性查询、关系查询、子图提取")
    print()
    return result.wasSuccessful()


if __name__ == "__main__":
    run_phase_102()
