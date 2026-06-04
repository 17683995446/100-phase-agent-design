#!/usr/bin/env python3
"""
阶段103：知识图谱CRUD完整实现

第一性原理：
  - CRUD = Create/Read/Update/Delete
  - 完整的查询能力是知识图谱的核心价值
  - 软删除是存续公理的具体体现

本阶段在阶段102的骨架上补充：
  1. 批量操作API
  2. 查询构造器（按属性、按关系、按权重）
  3. 子图提取
  4. 高级统计

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field

# 复用阶段102的类
import sys
sys.path.insert(0, '/workspace')
from phase_102_core_datastructure import (
    Node, Edge, KnowledgeGraph, NodeStatus, EdgeStatus
)


# ============================================================
# 一、查询构造器
# ============================================================
class QueryBuilder:
    """查询构造器 - 流式API构建复杂查询

    用法：
        qb = QueryBuilder(kg)
        results = qb.label("person").min_weight(0.5).limit(10).execute()
    """
    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg
        self._label: Optional[str] = None
        self._min_weight: float = 0.0
        self._max_weight: float = 1.0
        self._properties: Dict[str, Any] = {}
        self._status: Optional[str] = None
        self._limit: Optional[int] = None
        self._offset: int = 0
        self._order_by: Optional[str] = None
        self._reverse: bool = False

    def label(self, label: str) -> 'QueryBuilder':
        self._label = label
        return self

    def min_weight(self, w: float) -> 'QueryBuilder':
        self._min_weight = w
        return self

    def max_weight(self, w: float) -> 'QueryBuilder':
        self._max_weight = w
        return self

    def with_property(self, key: str, value: Any) -> 'QueryBuilder':
        self._properties[key] = value
        return self

    def status(self, status: str) -> 'QueryBuilder':
        self._status = status
        return self

    def limit(self, n: int) -> 'QueryBuilder':
        self._limit = n
        return self

    def offset(self, n: int) -> 'QueryBuilder':
        self._offset = n
        return self

    def order_by(self, field: str, reverse: bool = False) -> 'QueryBuilder':
        self._order_by = field
        self._reverse = reverse
        return self

    def execute_nodes(self) -> List[Node]:
        """执行节点查询"""
        results = []
        for node in self.kg.nodes.values():
            if self._label and node.label != self._label:
                continue
            if not (self._min_weight <= node.weight <= self._max_weight):
                continue
            if self._status and node.status != self._status:
                continue
            match = True
            for k, v in self._properties.items():
                if node.properties.get(k) != v:
                    match = False
                    break
            if match:
                results.append(node)

        if self._order_by:
            key = self._order_by
            results.sort(key=lambda n: getattr(n, key, 0),
                         reverse=self._reverse)

        if self._offset:
            results = results[self._offset:]
        if self._limit:
            results = results[:self._limit]
        return results

    def execute_edges(self) -> List[Edge]:
        """执行边查询"""
        results = []
        for edge in self.kg.edges.values():
            if not (self._min_weight <= edge.weight <= self._max_weight):
                continue
            if self._status and edge.status != self._status:
                continue
            if self._label and edge.relation != self._label:
                continue
            results.append(edge)
        if self._order_by:
            key = self._order_by
            results.sort(key=lambda e: getattr(e, key, 0),
                         reverse=self._reverse)
        if self._offset:
            results = results[self._offset:]
        if self._limit:
            results = results[:self._limit]
        return results


# ============================================================
# 二、CRUD扩展类
# ============================================================
class KnowledgeGraphCRUD(KnowledgeGraph):
    """知识图谱CRUD完整实现

    在基础骨架上扩展：
    - 批量操作
    - 子图提取
    - 高级统计
    - 路径查询（BFS）
    """
    # ---- 批量操作 ----
    def add_nodes(self, nodes: List[Node]) -> List[str]:
        """批量添加节点"""
        return [self.add_node(n) for n in nodes]

    def add_edges(self, edges: List[Edge]) -> List[str]:
        """批量添加边"""
        return [self.add_edge(e) for e in edges]

    def soft_delete_nodes(self, node_ids: List[str]) -> int:
        """批量软删除"""
        count = 0
        for nid in node_ids:
            if self.soft_delete_node(nid):
                count += 1
        return count

    def restore_nodes(self, node_ids: List[str]) -> int:
        """批量恢复"""
        count = 0
        for nid in node_ids:
            if self.restore_node(nid):
                count += 1
        return count

    # ---- 查询接口 ----
    def query(self) -> QueryBuilder:
        """获取查询构造器"""
        return QueryBuilder(self)

    def find_by_label(self, label: str) -> List[Node]:
        """按标签查找"""
        return self.query().label(label).execute_nodes()

    def find_by_property(self, key: str, value: Any) -> List[Node]:
        """按属性查找"""
        return self.query().with_property(key, value).execute_nodes()

    def find_edges_by_relation(self, relation: str) -> List[Edge]:
        """按关系类型查找边"""
        return self.query().label(relation).execute_edges()

    # ---- 高级操作 ----
    def extract_subgraph(self, root_id: str, depth: int = 2) -> 'KnowledgeGraphCRUD':
        """提取子图

        从root_id出发BFS depth层，返回包含的子图
        """
        sub = KnowledgeGraphCRUD()
        visited = {root_id}
        frontier = {root_id}
        node_map = {root_id: self.get_node(root_id)}
        edge_map = {}

        for d in range(depth):
            new_frontier = set()
            for nid in frontier:
                node = node_map.get(nid)
                if not node:
                    node = self.get_node(nid)
                    if node:
                        node_map[nid] = node
                if not node:
                    continue
                for neighbor, edge in self.get_neighbors(nid, "both"):
                    if neighbor.node_id not in visited:
                        visited.add(neighbor.node_id)
                        new_frontier.add(neighbor.node_id)
                        node_map[neighbor.node_id] = neighbor
                    edge_map[edge.edge_id] = edge
            frontier = new_frontier

        for node in node_map.values():
            if node:
                sub.add_node(node)
        for edge in edge_map.values():
            sub.add_edge(edge)
        return sub

    def find_path(self, from_id: str, to_id: str, max_depth: int = 5) -> Optional[List[str]]:
        """BFS查找两节点间路径

        返回节点ID列表，如果不可达返回None
        """
        if from_id == to_id:
            return [from_id]
        visited = {from_id}
        queue = [(from_id, [from_id])]
        while queue:
            current, path = queue.pop(0)
            if len(path) > max_depth:
                continue
            for neighbor, _ in self.get_neighbors(current, "out"):
                nid = neighbor.node_id
                if nid == to_id:
                    return path + [nid]
                if nid not in visited:
                    visited.add(nid)
                    queue.append((nid, path + [nid]))
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """详细统计"""
        node_weights = [n.weight for n in self.nodes.values() if n.is_active()]
        edge_weights = [e.weight for e in self.edges.values() if e.is_active()]

        labels = {}
        for n in self.nodes.values():
            if n.is_active():
                labels[n.label] = labels.get(n.label, 0) + 1

        relations = {}
        for e in self.edges.values():
            if e.is_active():
                relations[e.relation] = relations.get(e.relation, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "active_nodes": len(node_weights),
            "active_edges": len(edge_weights),
            "node_weight_avg": sum(node_weights) / len(node_weights) if node_weights else 0,
            "edge_weight_avg": sum(edge_weights) / len(edge_weights) if edge_weights else 0,
            "node_weight_max": max(node_weights) if node_weights else 0,
            "edge_weight_max": max(edge_weights) if edge_weights else 0,
            "labels": labels,
            "relations": relations,
        }

    def prune_weak_edges(self, threshold: float = 0.1) -> int:
        """清理弱关系边"""
        count = 0
        for edge in list(self.edges.values()):
            if edge.is_active() and edge.weight < threshold:
                self.soft_delete_edge(edge.edge_id)
                count += 1
        return count


# ============================================================
# 三、单元测试
# ============================================================
class TestQueryBuilder(unittest.TestCase):
    """查询构造器测试"""
    def setUp(self):
        self.kg = KnowledgeGraphCRUD()
        # 创建多种节点
        for i in range(10):
            label = "person" if i % 2 == 0 else "place"
            n = Node(content=f"item_{i}", label=label, weight=i/10)
            self.kg.add_node(n)
        # 创建边
        ids = list(self.kg.nodes.keys())
        for i in range(5):
            e = Edge(from_id=ids[i], to_id=ids[i+1], relation="near", weight=i/5)
            self.kg.add_edge(e)

    def test_label_filter(self):
        results = self.kg.query().label("person").execute_nodes()
        for n in results:
            self.assertEqual(n.label, "person")

    def test_weight_range(self):
        results = self.kg.query().min_weight(0.5).execute_nodes()
        for n in results:
            self.assertGreaterEqual(n.weight, 0.5)

    def test_property_filter(self):
        n = self.kg.nodes[list(self.kg.nodes.keys())[0]]
        n.set_property("color", "red")
        results = self.kg.query().with_property("color", "red").execute_nodes()
        self.assertGreater(len(results), 0)

    def test_limit_offset(self):
        all_results = self.kg.query().execute_nodes()
        limited = self.kg.query().limit(3).execute_nodes()
        self.assertEqual(len(limited), 3)
        offset = self.kg.query().offset(2).limit(3).execute_nodes()
        self.assertEqual(len(offset), 3)

    def test_order_by(self):
        results = self.kg.query().order_by("weight", reverse=True).execute_nodes()
        if len(results) >= 2:
            self.assertGreaterEqual(results[0].weight, results[1].weight)


class TestCRUDOperations(unittest.TestCase):
    """CRUD操作测试"""
    def setUp(self):
        self.kg = KnowledgeGraphCRUD()
        # 预置数据
        nodes = [Node(content=f"n{i}", node_id=f"n{i}") for i in range(5)]
        self.kg.add_nodes(nodes)
        edges = [
            Edge(from_id="n0", to_id="n1", relation="a"),
            Edge(from_id="n1", to_id="n2", relation="a"),
            Edge(from_id="n2", to_id="n3", relation="b"),
            Edge(from_id="n3", to_id="n4", relation="a"),
        ]
        self.kg.add_edges(edges)

    def test_batch_operations(self):
        new_nodes = [Node(content=f"x{i}") for i in range(3)]
        ids = self.kg.add_nodes(new_nodes)
        self.assertEqual(len(ids), 3)

    def test_find_by_label(self):
        for i in range(5):
            n = self.kg.nodes[f"n{i}"]
            n.label = "tag" if i % 2 == 0 else "untag"
        tagged = self.kg.find_by_label("tag")
        self.assertEqual(len(tagged), 3)

    def test_find_path(self):
        path = self.kg.find_path("n0", "n4")
        self.assertIsNotNone(path)
        self.assertEqual(path[0], "n0")
        self.assertEqual(path[-1], "n4")

    def test_find_path_unreachable(self):
        # 创建一个孤岛节点
        isolated = Node(content="isolated", node_id="iso")
        self.kg.add_node(isolated)
        path = self.kg.find_path("n0", "iso")
        self.assertIsNone(path)

    def test_extract_subgraph(self):
        sub = self.kg.extract_subgraph("n0", depth=2)
        self.assertIn("n0", sub.nodes)
        self.assertIn("n1", sub.nodes)
        self.assertIn("n2", sub.nodes)

    def test_statistics(self):
        stats = self.kg.get_statistics()
        self.assertEqual(stats["total_nodes"], 5)
        self.assertEqual(stats["total_edges"], 4)
        self.assertIn("labels", stats)
        self.assertIn("relations", stats)

    def test_prune_weak_edges(self):
        # 设置一个边的权重为0.05
        for eid, e in self.kg.edges.items():
            if e.relation == "b":
                e.weight = 0.05
        count = self.kg.prune_weak_edges(threshold=0.1)
        self.assertEqual(count, 1)
        stats = self.kg.get_statistics()
        self.assertEqual(stats["active_edges"], 3)


# ============================================================
# 四、阶段103演示
# ============================================================
def run_phase_103():
    """运行阶段103"""
    print("=" * 70)
    print("阶段103：知识图谱CRUD完整实现")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestQueryBuilder))
    suite.addTests(loader.loadTestsFromTestCase(TestCRUDOperations))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    print()
    print("-" * 70)
    print("【CRUD演示】")
    print("-" * 70)
    kg = KnowledgeGraphCRUD()
    # 添加10个节点
    nodes = [Node(content=f"知识{i}", label="concept",
                  properties={"idx": i, "category": "A" if i < 5 else "B"})
             for i in range(10)]
    kg.add_nodes(nodes)
    # 添加边
    ids = [n.node_id for n in nodes]
    edges = [Edge(from_id=ids[i], to_id=ids[(i+1) % 10],
                 relation="related_to", weight=0.5 + i*0.05)
             for i in range(10)]
    kg.add_edges(edges)
    print(f"  📊 节点数: {len(kg.nodes)}")
    print(f"  📊 边数:   {len(kg.edges)}")
    # 查询演示
    print()
    print("  🔍 查询 label='concept' 的前3个节点:")
    for n in kg.query().label("concept").limit(3).execute_nodes():
        print(f"     - {n.content} (weight={n.weight})")
    print()
    print("  🔍 查询 weight >= 0.8 的边:")
    for e in kg.query().min_weight(0.8).execute_edges()[:3]:
        print(f"     - {e.relation} ({e.weight})")
    print()
    print("  🔍 路径查询 n0 -> n5:")
    path = kg.find_path(ids[0], ids[5], max_depth=10)
    if path:
        print(f"     路径长度: {len(path)-1} 跳")
    print()
    print("  🔍 子图提取 (root=n0, depth=2):")
    sub = kg.extract_subgraph(ids[0], depth=2)
    print(f"     子图节点数: {len(sub.nodes)}, 边数: {len(sub.edges)}")
    print()
    stats = kg.get_statistics()
    print(f"  📊 统计: {stats['total_nodes']}节点/{stats['total_edges']}边")
    print(f"           平均权重: 节点={stats['node_weight_avg']:.2f} 边={stats['edge_weight_avg']:.2f}")
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ 阶段103完成：CRUD完整实现，所有单元测试通过！")
    else:
        print("❌ 阶段103失败")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段104：JSON持久化（原子化写入+损坏自愈）")
    print("  - 临时文件+原子重命名")
    print("  - 自动备份机制")
    print("  - 损坏文件检测与自愈")
    print()
    return result.wasSuccessful()


if __name__ == "__main__":
    run_phase_103()
