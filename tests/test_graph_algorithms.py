import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.knowledge_graph import KnowledgeGraph
from core.graph_algorithms import GraphAlgorithms


class TestGraphAlgorithms:
    @pytest.fixture
    def sample_graph(self):
        """创建一个示例知识图谱用于测试"""
        kg = KnowledgeGraph(save_path="test_algo_graph.json")
        kg.clear()
        # 构建一个简单的图：
        # A -> B (0.8), A -> C (0.6)
        # B -> C (0.9), B -> D (0.7)
        # C -> D (0.5)
        # D -> E (0.8)
        # E -> A (0.4) 形成环
        kg.add_edge("A", "B", "rel", 0.8)
        kg.add_edge("A", "C", "rel", 0.6)
        kg.add_edge("B", "C", "rel", 0.9)
        kg.add_edge("B", "D", "rel", 0.7)
        kg.add_edge("C", "D", "rel", 0.5)
        kg.add_edge("D", "E", "rel", 0.8)
        kg.add_edge("E", "A", "rel", 0.4)
        return kg

    @pytest.fixture
    def algo(self, sample_graph):
        return GraphAlgorithms(sample_graph)

    def test_creation(self, sample_graph):
        algo = GraphAlgorithms(sample_graph)
        assert algo.kg is sample_graph

    def test_dijkstra_basic(self, algo):
        distances = algo.dijkstra("A")
        assert "A" in distances
        assert distances["A"] == 0.0
        assert "B" in distances
        assert "C" in distances
        assert "D" in distances
        assert "E" in distances

    def test_dijkstra_to_end(self, algo):
        distances = algo.dijkstra("A", end="D")
        assert "D" in distances
        # A->B->D 应该是较短路径
        assert distances["D"] < float('inf')

    def test_dijkstra_nonexistent_start(self, algo):
        distances = algo.dijkstra("Z")
        assert distances == {}

    def test_shortest_path_basic(self, algo):
        path, dist = algo.shortest_path("A", "D")
        assert len(path) > 0
        assert path[0] == "A"
        assert path[-1] == "D"
        assert dist < float('inf')

    def test_shortest_path_same_node(self, algo):
        path, dist = algo.shortest_path("A", "A")
        assert path == ["A"]
        assert dist == 0.0

    def test_shortest_path_unreachable(self, algo):
        # 添加孤立节点
        algo.kg.add_node("Z")
        path, dist = algo.shortest_path("A", "Z")
        assert path == []
        assert dist == float('inf')

    def test_pagerank_basic(self, algo):
        pr = algo.pagerank(iterations=10)
        assert len(pr) == 5
        total = sum(pr.values())
        assert abs(total - 1.0) < 0.01
        # B 和 D 应该有较高的排名，因为连接较多
        assert "B" in pr
        assert "D" in pr

    def test_pagerank_empty_graph(self):
        kg = KnowledgeGraph(save_path="test_empty_pr.json")
        kg.clear()
        algo = GraphAlgorithms(kg)
        pr = algo.pagerank()
        assert pr == {}

    def test_label_propagation_basic(self, algo):
        labels = algo.label_propagation()
        assert len(labels) == 5
        # 所有节点应该被分配到某个社区
        assert all(isinstance(v, int) for v in labels.values())
        # 连通图中通常所有节点最终收敛到同一社区
        # 或者分为少量社区
        unique = set(labels.values())
        assert len(unique) >= 1

    def test_label_propagation_empty(self):
        kg = KnowledgeGraph(save_path="test_empty_lp.json")
        kg.clear()
        algo = GraphAlgorithms(kg)
        labels = algo.label_propagation()
        assert labels == {}

    def test_betweenness_centrality(self, algo):
        bc = algo.betweenness_centrality()
        assert len(bc) == 5
        # B 和 C 作为桥梁应该有较高中心性
        assert bc["B"] >= 0
        assert bc["C"] >= 0

    def test_betweenness_empty(self):
        kg = KnowledgeGraph(save_path="test_empty_bc.json")
        kg.clear()
        algo = GraphAlgorithms(kg)
        bc = algo.betweenness_centrality()
        assert bc == {}

    def test_degree_centrality(self, algo):
        dc = algo.degree_centrality()
        assert len(dc) == 5
        # B 有 A->B, B->C, B->D，度较高
        assert dc["B"] > dc["E"]
        assert all(0 <= v <= 1 for v in dc.values())

    def test_clustering_coefficient(self, algo):
        cc = algo.clustering_coefficient()
        assert len(cc) == 5
        assert all(0 <= v <= 1 for v in cc.values())

    def test_find_communities(self, algo):
        communities = algo.find_communities()
        assert len(communities) >= 1
        # 所有节点都应该被分配到社区
        all_nodes = set()
        for comm in communities:
            all_nodes.update(comm)
        assert all_nodes == set(algo.kg.nodes.keys())

    def test_get_top_nodes(self, algo):
        scores = {"A": 0.5, "B": 0.9, "C": 0.3, "D": 0.8, "E": 0.1}
        top = algo.get_top_nodes(scores, top_k=3)
        assert len(top) == 3
        assert top[0][0] == "B"
        assert top[1][0] == "D"
        assert top[2][0] == "A"

    def test_min_weight_filter(self, algo):
        # 使用高阈值过滤低权重边
        distances = algo.dijkstra("A", min_weight=0.7)
        # A->C (0.6) 应该被过滤
        # 但 A->B->C (0.8, 0.9) 可能仍可达
        assert "B" in distances

    def test_weighted_adjacency(self, algo):
        adj = algo._get_weighted_adjacency()
        assert "A" in adj
        assert len(adj["A"]) == 2
        targets = [t for t, _ in adj["A"]]
        assert "B" in targets
        assert "C" in targets


class TestGraphAlgorithmsIntegration:
    def test_full_pipeline(self):
        """测试完整算法流水线"""
        kg = KnowledgeGraph(save_path="test_pipeline.json")
        kg.clear()
        # 构建星型图
        for i in range(5):
            kg.add_edge("center", f"node_{i}", "connects", 0.8)
            kg.add_edge(f"node_{i}", "center", "connects", 0.8)

        algo = GraphAlgorithms(kg)

        # PageRank
        pr = algo.pagerank(iterations=20)
        assert pr["center"] > pr["node_0"]

        # 最短路径
        path, dist = algo.shortest_path("node_0", "node_1")
        assert path == ["node_0", "center", "node_1"]

        # 社区
        communities = algo.find_communities()
        assert len(communities) >= 1

        # 中心性
        dc = algo.degree_centrality()
        assert dc["center"] > dc["node_0"]

        # 清理
        import os
        if os.path.exists("test_pipeline.json"):
            os.remove("test_pipeline.json")
