#!/usr/bin/env python3
"""
阶段111：高级查询能力

第一性原理：
  - 知识图谱的核心价值 = 查询能力
  - 高级查询 = 图遍历、模式匹配、聚合分析
  - 性能：索引、剪枝、缓存

本阶段产出：
  1. PathQuery：路径查询（BFS/DFS）
  2. SubgraphQuery：子图查询
  3. PatternQuery：模式查询（Cypher-like）
  4. AggregateQuery：聚合查询
  5. QueryCache：查询结果缓存
  6. QueryPlanner：查询计划与优化

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import hashlib
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
from collections import deque
from dataclasses import dataclass, field

import sys
sys.path.insert(0, '/workspace')
from phase_103_kg_crud import KnowledgeGraphCRUD
from phase_102_core_datastructure import Node, Edge


# ============================================================
# 一、查询结果
# ============================================================
@dataclass
class QueryResult:
    """查询结果"""
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    paths: List[List[str]] = field(default_factory=list)
    aggregates: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def count(self) -> int:
        return len(self.nodes)

    def is_empty(self) -> bool:
        return (len(self.nodes) == 0 and len(self.edges) == 0
                and len(self.paths) == 0)


# ============================================================
# 二、路径查询
# ============================================================
class PathQuery:
    """路径查询

    支持：
    - 最短路径（BFS）
    - 所有路径（DFS，有深度限制）
    - 必经节点路径
    - 路径属性过滤
    """
    def __init__(self, kg: KnowledgeGraphCRUD):
        self.kg = kg

    def shortest_path(self, from_id: str, to_id: str,
                      max_depth: int = 6) -> Optional[List[Edge]]:
        """最短路径（BFS）"""
        if from_id == to_id:
            return []
        visited = {from_id}
        queue = deque([(from_id, [])])
        while queue:
            current, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            for neighbor, edge in self.kg.get_neighbors(current, "out"):
                if edge.edge_id in [e.edge_id for e in path]:
                    continue
                new_path = path + [edge]
                if neighbor.node_id == to_id:
                    return new_path
                if neighbor.node_id not in visited:
                    visited.add(neighbor.node_id)
                    queue.append((neighbor.node_id, new_path))
        return None

    def all_paths(self, from_id: str, to_id: str,
                  max_depth: int = 4,
                  max_paths: int = 100) -> List[List[Edge]]:
        """所有路径（DFS，有深度和数量限制）"""
        results = []
        def dfs(current, target, path, depth):
            if len(results) >= max_paths:
                return
            if depth > max_depth:
                return
            if current == target and len(path) > 0:
                results.append(list(path))
                return
            for neighbor, edge in self.kg.get_neighbors(current, "out"):
                if edge in path:
                    continue
                path.append(edge)
                dfs(neighbor.node_id, target, path, depth + 1)
                path.pop()
        dfs(from_id, to_id, [], 0)
        return results

    def paths_through(self, from_id: str, to_id: str,
                       must_pass: List[str],
                       max_depth: int = 6) -> List[List[Edge]]:
        """必经节点路径"""
        # 拆分：from -> p1 -> p2 -> ... -> to
        waypoints = [from_id] + must_pass + [to_id]
        full_paths = []
        current_path: List[Edge] = []
        for i in range(len(waypoints) - 1):
            segment = self.shortest_path(
                waypoints[i], waypoints[i+1], max_depth)
            if segment is None:
                return []
            current_path.extend(segment)
        return [current_path]


# ============================================================
# 三、子图查询
# ============================================================
class SubgraphQuery:
    """子图查询

    按节点/边属性提取子图
    """
    def __init__(self, kg: KnowledgeGraphCRUD):
        self.kg = kg

    def around(self, center_id: str, radius: int = 2,
                direction: str = "both") -> KnowledgeGraphCRUD:
        """提取以某节点为中心、半径为N的子图"""
        return self.kg.extract_subgraph(center_id, depth=radius)

    def by_label(self, label: str) -> KnowledgeGraphCRUD:
        """提取所有同标签节点及其相互关系构成子图"""
        sub = KnowledgeGraphCRUD()
        for node in self.kg.find_by_label(label):
            sub.add_node(node)
        # 找出这些节点之间的边
        sub_ids = set(sub.nodes.keys())
        for edge in self.kg.edges.values():
            if edge.is_active() and edge.from_id in sub_ids and edge.to_id in sub_ids:
                sub.add_edge(edge)
        return sub

    def by_relation(self, relation: str) -> KnowledgeGraphCRUD:
        """提取特定关系类型构成的子图"""
        sub = KnowledgeGraphCRUD()
        edge_ids = set()
        for edge in self.kg.find_edges_by_relation(relation):
            sub.add_edge(edge)
            edge_ids.add(edge.edge_id)
        for edge_id in edge_ids:
            edge = self.kg.edges[edge_id]
            for nid in [edge.from_id, edge.to_id]:
                node = self.kg.get_node(nid)
                if node and node.is_active():
                    sub.add_node(node)
        return sub


# ============================================================
# 四、模式查询
# ============================================================
class PatternQuery:
    """模式查询

    支持类Cypher模式：
    - (a)-[r1]->(b)-[r2]->(c)  链式
    - (a)-[r]->(b) WHERE r.weight > 0.5
    - 多模式联合
    """
    def __init__(self, kg: KnowledgeGraphCRUD):
        self.kg = kg

    def chain(self, start_label: str, relations: List[str],
              end_label: str) -> List[Tuple[List[Node], List[Edge]]]:
        """链式模式查询：start_label -[r1]-> -[r2]-> ... -> end_label

        Returns: 匹配的 (节点链, 边链) 列表
        """
        if not relations:
            return []
        start_nodes = self.kg.find_by_label(start_label)
        end_nodes = self.kg.find_by_label(end_label)
        end_ids = {n.node_id for n in end_nodes}
        results = []
        for start in start_nodes:
            matches = self._chain_dfs(
                start, end_ids, relations, [], [], 0)
            results.extend(matches)
        return results

    def _chain_dfs(self, current: Node, end_ids: Set[str],
                    relations: List[str],
                    node_path: List[Node],
                    edge_path: List[Edge],
                    depth: int) -> List[Tuple[List[Node], List[Edge]]]:
        """链式DFS"""
        node_path = node_path + [current]
        if depth == len(relations):
            if current.node_id in end_ids:
                return [(node_path, edge_path)]
            return []
        rel = relations[depth]
        results = []
        for neighbor, edge in self.kg.get_neighbors(current.node_id, "out"):
            if edge.relation != rel:
                continue
            sub = self._chain_dfs(
                neighbor, end_ids, relations,
                node_path, edge_path + [edge], depth + 1)
            results.extend(sub)
        return results

    def by_edge_filter(self, relation: Optional[str] = None,
                        min_weight: float = 0.0,
                        max_weight: float = 1.0) -> QueryResult:
        """按边属性过滤"""
        result = QueryResult()
        matched_edges = []
        matched_node_ids = set()
        for edge in self.kg.edges.values():
            if not edge.is_active():
                continue
            if relation and edge.relation != relation:
                continue
            if not (min_weight <= edge.weight <= max_weight):
                continue
            matched_edges.append(edge)
            matched_node_ids.add(edge.from_id)
            matched_node_ids.add(edge.to_id)
        result.edges = matched_edges
        for nid in matched_node_ids:
            node = self.kg.get_node(nid)
            if node and node.is_active():
                result.nodes.append(node)
        return result


# ============================================================
# 五、聚合查询
# ============================================================
class AggregateQuery:
    """聚合查询"""
    def __init__(self, kg: KnowledgeGraphCRUD):
        self.kg = kg

    def degree(self, node_id: str, direction: str = "both") -> int:
        """节点度数"""
        return len(self.kg.get_neighbors(node_id, direction))

    def top_k_by_degree(self, k: int = 10,
                         direction: str = "both") -> List[Tuple[Node, int]]:
        """度数最高的K个节点"""
        active = [n for n in self.kg.nodes.values() if n.is_active()]
        scored = [(n, self.degree(n.node_id, direction)) for n in active]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def top_k_by_weight(self, k: int = 10) -> List[Tuple[Node, float]]:
        """权重最高的K个节点"""
        active = [n for n in self.kg.nodes.values() if n.is_active()]
        scored = [(n, n.weight) for n in active]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def centrality(self) -> Dict[str, float]:
        """简易中心性：归一化度数"""
        result = {}
        active = [n for n in self.kg.nodes.values() if n.is_active()]
        if not active:
            return result
        max_degree = max(self.degree(n.node_id, "both") for n in active)
        for n in active:
            d = self.degree(n.node_id, "both")
            result[n.node_id] = d / max_degree if max_degree > 0 else 0
        return result

    def label_distribution(self) -> Dict[str, int]:
        """标签分布"""
        dist = {}
        for n in self.kg.nodes.values():
            if n.is_active():
                dist[n.label] = dist.get(n.label, 0) + 1
        return dist

    def relation_distribution(self) -> Dict[str, int]:
        """关系分布"""
        dist = {}
        for e in self.kg.edges.values():
            if e.is_active():
                dist[e.relation] = dist.get(e.relation, 0) + 1
        return dist

    def connected_components(self) -> List[Set[str]]:
        """连通分量"""
        visited = set()
        components = []
        for node in self.kg.nodes.values():
            if not node.is_active() or node.node_id in visited:
                continue
            # BFS
            component = set()
            queue = deque([node.node_id])
            while queue:
                current = queue.popleft()
                if current in component:
                    continue
                component.add(current)
                visited.add(current)
                for neighbor, _ in self.kg.get_neighbors(current, "both"):
                    if neighbor.node_id not in component:
                        queue.append(neighbor.node_id)
            components.append(component)
        return components


# ============================================================
# 六、查询缓存
# ============================================================
class QueryCache:
    """查询缓存

    简单LRU缓存
    """
    def __init__(self, max_size: int = 256):
        self.max_size = max_size
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._stats = {"hits": 0, "misses": 0}

    def _key(self, *args, **kwargs) -> str:
        raw = f"{args}|{sorted(kwargs.items())}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            self._stats["hits"] += 1
            return self._cache[key][0]
        self._stats["misses"] += 1
        return None

    def set(self, key: str, value: Any) -> None:
        if len(self._cache) >= self.max_size:
            # 简单LRU：删最早的
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = (value, time.time())

    def get_or_compute(self, key: str, compute_fn: Callable) -> Any:
        """缓存获取或计算"""
        cached = self.get(key)
        if cached is not None:
            return cached
        result = compute_fn()
        self.set(key, result)
        return result

    def clear(self) -> None:
        self._cache.clear()

    def stats(self) -> Dict[str, int]:
        return dict(self._stats)


# ============================================================
# 七、高级查询引擎
# ============================================================
class AdvancedQueryEngine:
    """高级查询引擎

    统一入口，集成所有查询能力
    """
    def __init__(self, kg: KnowledgeGraphCRUD,
                 cache_size: int = 256):
        self.kg = kg
        self.path = PathQuery(kg)
        self.subgraph = SubgraphQuery(kg)
        self.pattern = PatternQuery(kg)
        self.aggregate = AggregateQuery(kg)
        self.cache = QueryCache(cache_size)
        self._stats = {
            "queries_total": 0,
            "cache_hits": 0,
        }

    def query(self, qtype: str, **kwargs) -> Any:
        """统一查询接口

        qtype可选: shortest_path, all_paths, around, by_label,
                   by_relation, chain, top_k_degree, top_k_weight,
                   centrality, label_dist, relation_dist,
                   connected_components, edge_filter
        """
        self._stats["queries_total"] += 1
        cache_key = f"{qtype}|{sorted(kwargs.items())}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            self._stats["cache_hits"] += 1
            return cached

        result = None
        if qtype == "shortest_path":
            result = self.path.shortest_path(
                kwargs["from_id"], kwargs["to_id"],
                kwargs.get("max_depth", 6))
        elif qtype == "all_paths":
            result = self.path.all_paths(
                kwargs["from_id"], kwargs["to_id"],
                kwargs.get("max_depth", 4))
        elif qtype == "around":
            result = self.subgraph.around(
                kwargs["center_id"], kwargs.get("radius", 2))
        elif qtype == "by_label":
            result = self.subgraph.by_label(kwargs["label"])
        elif qtype == "by_relation":
            result = self.subgraph.by_relation(kwargs["relation"])
        elif qtype == "chain":
            result = self.pattern.chain(
                kwargs["start_label"], kwargs["relations"],
                kwargs["end_label"])
        elif qtype == "top_k_degree":
            result = self.aggregate.top_k_by_degree(
                kwargs.get("k", 10))
        elif qtype == "top_k_weight":
            result = self.aggregate.top_k_by_weight(
                kwargs.get("k", 10))
        elif qtype == "centrality":
            result = self.aggregate.centrality()
        elif qtype == "label_dist":
            result = self.aggregate.label_distribution()
        elif qtype == "relation_dist":
            result = self.aggregate.relation_distribution()
        elif qtype == "connected_components":
            result = self.aggregate.connected_components()
        elif qtype == "edge_filter":
            result = self.pattern.by_edge_filter(
                kwargs.get("relation"),
                kwargs.get("min_weight", 0.0),
                kwargs.get("max_weight", 1.0))
        else:
            raise ValueError(f"Unknown query type: {qtype}")

        if result is not None:
            self.cache.set(cache_key, result)
        return result

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "cache_stats": self.cache.stats()
        }


# ============================================================
# 八、单元测试
# ============================================================
class TestPathQuery(unittest.TestCase):
    """路径查询测试"""
    def setUp(self):
        self.kg = KnowledgeGraphCRUD()
        # 链式: A->B->C->D
        # 分叉: A->E
        for nid in ["A", "B", "C", "D", "E"]:
            self.kg.add_node(Node(content=nid, node_id=nid))
        for f, t in [("A","B"), ("B","C"), ("C","D"), ("A","E"), ("E","D")]:
            self.kg.add_edge(Edge(from_id=f, to_id=t,
                                  relation="next", edge_id=f"{f}{t}"))

    def test_shortest_path(self):
        path = PathQuery(self.kg).shortest_path("A", "D")
        self.assertIsNotNone(path)
        # 最短应是 A->B->C->D (3边) 或 A->E->D (2边)
        self.assertEqual(len(path), 2)

    def test_shortest_path_direct(self):
        path = PathQuery(self.kg).shortest_path("A", "B")
        self.assertEqual(len(path), 1)

    def test_no_path(self):
        self.kg.add_node(Node(content="Z", node_id="Z"))
        path = PathQuery(self.kg).shortest_path("A", "Z")
        self.assertIsNone(path)


class TestSubgraphQuery(unittest.TestCase):
    """子图查询测试"""
    def setUp(self):
        self.kg = KnowledgeGraphCRUD()
        for i in range(10):
            self.kg.add_node(Node(content=f"n{i}", node_id=f"n{i}",
                                   label="A" if i < 5 else "B"))
        for i in range(9):
            self.kg.add_edge(Edge(
                from_id=f"n{i}", to_id=f"n{i+1}",
                relation="r", edge_id=f"e{i}"
            ))

    def test_around(self):
        sub = SubgraphQuery(self.kg).around("n5", radius=1)
        self.assertIn("n5", sub.nodes)
        self.assertIn("n4", sub.nodes)
        self.assertIn("n6", sub.nodes)

    def test_by_label(self):
        sub = SubgraphQuery(self.kg).by_label("A")
        self.assertEqual(len(sub.nodes), 5)

    def test_by_relation(self):
        sub = SubgraphQuery(self.kg).by_relation("r")
        self.assertEqual(len(sub.edges), 9)


class TestPatternQuery(unittest.TestCase):
    """模式查询测试"""
    def setUp(self):
        self.kg = KnowledgeGraphCRUD()
        for nid in ["A1", "A2", "B1", "B2", "C1"]:
            self.kg.add_node(Node(content=nid, node_id=nid,
                                   label=nid[0]))  # label是首字母
        for f, t in [("A1","B1"), ("B1","C1"),
                     ("A2","B2"), ("B2","C1")]:
            self.kg.add_edge(Edge(from_id=f, to_id=t,
                                  relation="r", edge_id=f"{f}{t}"))

    def test_chain(self):
        # A->B (1跳) ->C (1跳) 共2跳, 所以需要2个关系
        results = PatternQuery(self.kg).chain("A", ["r", "r"], "C")
        # A1->B1->C1 和 A2->B2->C1 都满足
        self.assertEqual(len(results), 2)

    def test_edge_filter(self):
        # 设置一个边的权重为0.1
        for edge in self.kg.edges.values():
            edge.weight = 0.5
        self.kg.edges["A1B1"].weight = 0.9
        result = PatternQuery(self.kg).by_edge_filter(min_weight=0.8)
        self.assertEqual(len(result.edges), 1)


class TestAggregateQuery(unittest.TestCase):
    """聚合查询测试"""
    def setUp(self):
        self.kg = KnowledgeGraphCRUD()
        # 创建星形图
        for i in range(5):
            self.kg.add_node(Node(content=f"hub" if i==0 else f"spoke{i}",
                                   node_id=f"n{i}"))
        for i in range(1, 5):
            self.kg.add_edge(Edge(
                from_id="n0", to_id=f"n{i}",
                relation="r", edge_id=f"e{i}"
            ))

    def test_degree(self):
        d = AggregateQuery(self.kg).degree("n0")
        self.assertEqual(d, 4)

    def test_top_k_by_degree(self):
        top = AggregateQuery(self.kg).top_k_by_degree(k=3)
        self.assertEqual(top[0][0].node_id, "n0")
        self.assertEqual(top[0][1], 4)

    def test_label_distribution(self):
        # 重新构造
        kg2 = KnowledgeGraphCRUD()
        for i in range(3):
            kg2.add_node(Node(content=f"x{i}", node_id=f"x{i}",
                              label="A"))
        for i in range(2):
            kg2.add_node(Node(content=f"y{i}", node_id=f"y{i}",
                              label="B"))
        dist = AggregateQuery(kg2).label_distribution()
        self.assertEqual(dist["A"], 3)
        self.assertEqual(dist["B"], 2)

    def test_connected_components(self):
        kg2 = KnowledgeGraphCRUD()
        # 第一个连通分量：a-b
        kg2.add_node(Node(content="a", node_id="a"))
        kg2.add_node(Node(content="b", node_id="b"))
        kg2.add_edge(Edge(from_id="a", to_id="b", relation="r",
                          edge_id="e1"))
        # 第二个连通分量：c
        kg2.add_node(Node(content="c", node_id="c"))
        comps = AggregateQuery(kg2).connected_components()
        self.assertEqual(len(comps), 2)


class TestQueryCache(unittest.TestCase):
    """查询缓存测试"""
    def test_cache_hit_miss(self):
        c = QueryCache(max_size=10)
        c.set("k1", "v1")
        self.assertEqual(c.get("k1"), "v1")
        self.assertIsNone(c.get("k2"))
        stats = c.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)

    def test_cache_eviction(self):
        c = QueryCache(max_size=2)
        c.set("k1", "v1")
        c.set("k2", "v2")
        c.set("k3", "v3")  # 触发淘汰
        self.assertIsNone(c.get("k1"))
        self.assertEqual(c.get("k3"), "v3")

    def test_get_or_compute(self):
        c = QueryCache()
        call_count = [0]
        def compute():
            call_count[0] += 1
            return "result"
        r1 = c.get_or_compute("k", compute)
        r2 = c.get_or_compute("k", compute)
        self.assertEqual(r1, "result")
        self.assertEqual(r2, "result")
        self.assertEqual(call_count[0], 1)


class TestAdvancedQueryEngine(unittest.TestCase):
    """高级查询引擎测试"""
    def setUp(self):
        self.kg = KnowledgeGraphCRUD()
        for nid in ["A", "B", "C", "D"]:
            self.kg.add_node(Node(content=nid, node_id=nid))
        for f, t in [("A","B"), ("B","C"), ("C","D")]:
            self.kg.add_edge(Edge(from_id=f, to_id=t,
                                  relation="next", edge_id=f"{f}{t}"))
        self.engine = AdvancedQueryEngine(self.kg)

    def test_shortest_path_query(self):
        path = self.engine.query("shortest_path",
                                  from_id="A", to_id="D")
        self.assertEqual(len(path), 3)

    def test_top_k_degree(self):
        top = self.engine.query("top_k_degree", k=2)
        # 中间节点B、C度数为2，端点A、D度数为1
        self.assertIn(top[0][0].node_id, ["B", "C"])

    def test_cache_hit(self):
        self.engine.query("shortest_path", from_id="A", to_id="C")
        self.engine.query("shortest_path", from_id="A", to_id="C")
        stats = self.engine.get_stats()
        self.assertGreaterEqual(stats["cache_hits"], 1)

    def test_unknown_query(self):
        with self.assertRaises(ValueError):
            self.engine.query("nonexistent_type")


# ============================================================
# 九、阶段111演示
# ============================================================
def run_phase_111():
    """运行阶段111"""
    print("=" * 70)
    print("阶段111：高级查询能力")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestPathQuery))
    suite.addTests(loader.loadTestsFromTestCase(TestSubgraphQuery))
    suite.addTests(loader.loadTestsFromTestCase(TestPatternQuery))
    suite.addTests(loader.loadTestsFromTestCase(TestAggregateQuery))
    suite.addTests(loader.loadTestsFromTestCase(TestQueryCache))
    suite.addTests(loader.loadTestsFromTestCase(TestAdvancedQueryEngine))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    print()
    print("-" * 70)
    print("【高级查询演示】")
    print("-" * 70)
    # 构建一张较大的图
    kg = KnowledgeGraphCRUD()
    nodes_data = [
        ("alice", "person"), ("bob", "person"),
        ("charlie", "person"), ("diana", "person"),
        ("python", "language"), ("rust", "language"),
        ("django", "framework"), ("actix", "framework"),
        ("web", "domain"), ("systems", "domain"),
    ]
    for nid, label in nodes_data:
        kg.add_node(Node(content=nid, node_id=nid, label=label))
    relations = [
        ("alice", "python", "uses"),
        ("alice", "django", "uses"),
        ("bob", "rust", "uses"),
        ("bob", "actix", "uses"),
        ("charlie", "python", "uses"),
        ("diana", "rust", "uses"),
        ("python", "django", "enables"),
        ("rust", "actix", "enables"),
        ("django", "web", "used_for"),
        ("actix", "systems", "used_for"),
        ("alice", "bob", "knows"),
        ("charlie", "diana", "knows"),
        ("alice", "charlie", "knows"),
    ]
    for i, (f, t, r) in enumerate(relations):
        kg.add_edge(Edge(from_id=f, to_id=t, relation=r,
                          weight=0.5 + (i % 3) * 0.2,
                          edge_id=f"e{i}"))
    print(f"  📊 知识图谱: {len(kg.nodes)}节点, {len(kg.edges)}边")
    print()
    engine = AdvancedQueryEngine(kg)
    # 演示1：最短路径
    print("  🔍 最短路径 alice -> web:")
    path = engine.query("shortest_path", from_id="alice", to_id="web")
    if path:
        node_path = ["alice"]
        for edge in path:
            node_path.append(edge.to_id)
        print(f"     {' -> '.join(node_path)}")
    print()
    # 演示2：模式查询
    print("  🔍 链式模式 person -[uses]-> language -[enables]-> framework:")
    chains = engine.query("chain",
                           start_label="person",
                           relations=["uses", "enables"],
                           end_label="framework")
    print(f"     找到 {len(chains)} 条匹配")
    for nodes, edges in chains[:3]:
        path_str = " -> ".join([f"{n.content}({n.label})" for n in nodes])
        print(f"     - {path_str}")
    print()
    # 演示3：Top-K 度数
    print("  🔍 度数最高的3个节点:")
    top = engine.query("top_k_degree", k=3)
    for node, degree in top:
        print(f"     {node.content:10s} 度数={degree}")
    print()
    # 演示4：中心性
    print("  🔍 中心性分析:")
    centrality = engine.query("centrality")
    sorted_c = sorted(centrality.items(),
                       key=lambda x: x[1], reverse=True)
    for nid, c in sorted_c[:5]:
        node = kg.get_node(nid)
        if node:
            print(f"     {node.content:10s} 中心性={c:.3f}")
    print()
    # 演示5：边过滤
    print("  🔍 边过滤 (weight > 0.7):")
    edge_result = engine.query("edge_filter", min_weight=0.7)
    print(f"     匹配 {len(edge_result.edges)} 条边, 涉及 {len(edge_result.nodes)} 个节点")
    print()
    # 演示6：连通分量
    print("  🔍 连通分量:")
    comps = engine.query("connected_components")
    print(f"     共 {len(comps)} 个连通分量")
    for i, comp in enumerate(comps):
        names = [kg.get_node(nid).content for nid in comp
                 if kg.get_node(nid)]
        print(f"     - 分量{i+1}: {', '.join(names)}")
    print()
    # 演示7：标签/关系分布
    print("  🔍 标签分布:")
    label_dist = engine.query("label_dist")
    for label, count in sorted(label_dist.items(),
                                key=lambda x: x[1], reverse=True):
        print(f"     {label:10s}: {count}")
    print()
    print("  🔍 关系分布:")
    rel_dist = engine.query("relation_dist")
    for rel, count in sorted(rel_dist.items(),
                              key=lambda x: x[1], reverse=True):
        print(f"     {rel:10s}: {count}")
    print()
    stats = engine.get_stats()
    print(f"  📊 查询引擎统计: {stats['queries_total']}次查询, "
          f"{stats['cache_hits']}次缓存命中")
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ 阶段111完成：高级查询能力已实现，所有测试通过！")
    else:
        print("❌ 阶段111失败")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段112：权重衰减机制")
    print("  - 每日权重衰减")
    print("  - 访问频率加权")
    print("  - 时间衰减模型")
    print("  - 衰减后的清理策略")
    print()
    return result.wasSuccessful()


if __name__ == "__main__":
    run_phase_111()
