import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.knowledge_graph import KnowledgeGraph
from core.data_exchange import DataExchange


class TestDataExchange:
    @pytest.fixture
    def sample_graph(self):
        kg = KnowledgeGraph(save_path="test_exchange.json")
        kg.clear()
        kg.add_node("Alice", {"age": 30, "role": "engineer"})
        kg.add_node("Bob", {"age": 25, "role": "designer"})
        kg.add_node("Carol", {"age": 35, "role": "manager"})
        kg.add_edge("Alice", "Bob", "works_with", 0.8)
        kg.add_edge("Bob", "Carol", "reports_to", 0.9)
        kg.add_edge("Alice", "Carol", "knows", 0.6)
        return kg

    @pytest.fixture
    def exchange(self, sample_graph):
        return DataExchange(sample_graph)

    def test_creation(self, sample_graph):
        ex = DataExchange(sample_graph)
        assert ex.kg is sample_graph

    # CSV 测试
    def test_export_csv(self, exchange):
        nodes_csv, edges_csv = exchange.export_to_csv()
        assert "Alice" in nodes_csv
        assert "Bob" in nodes_csv
        assert "works_with" in edges_csv
        assert "0.8" in edges_csv
        # 检查表头
        assert "name" in nodes_csv
        assert "source" in edges_csv

    def test_import_csv(self, exchange):
        nodes_csv, edges_csv = exchange.export_to_csv()
        # 清空后重新导入
        exchange.kg.clear()
        n_count, e_count = exchange.import_from_csv(nodes_csv, edges_csv)
        assert n_count == 3
        assert e_count == 3
        assert "Alice" in exchange.kg.nodes
        assert exchange.kg.nodes["Alice"].attributes["role"] == "engineer"

    def test_import_csv_empty(self, exchange):
        n_count, e_count = exchange.import_from_csv("", "")
        assert n_count == 0
        assert e_count == 0

    def test_csv_roundtrip(self, exchange):
        nodes_csv, edges_csv = exchange.export_to_csv()
        exchange.kg.clear()
        exchange.import_from_csv(nodes_csv, edges_csv)
        assert len(exchange.kg.nodes) == 3
        assert len(exchange.kg.edges) == 3

    # RDF 测试
    def test_export_rdf(self, exchange):
        rdf = exchange.export_to_rdf()
        assert "@prefix" in rdf
        assert "Alice" in rdf
        assert "works_with" in rdf
        assert "rdf:type" in rdf

    def test_import_rdf(self, exchange):
        rdf = exchange.export_to_rdf()
        exchange.kg.clear()
        n_count, e_count = exchange.import_from_rdf(rdf)
        assert n_count >= 1
        assert e_count >= 1
        assert "Alice" in exchange.kg.nodes

    def test_rdf_roundtrip(self, exchange):
        rdf = exchange.export_to_rdf()
        exchange.kg.clear()
        exchange.import_from_rdf(rdf)
        # 节点和边应该被恢复
        assert "Alice" in exchange.kg.nodes

    # GraphML 测试
    def test_export_graphml(self, exchange):
        graphml = exchange.export_to_graphml()
        assert "<?xml" in graphml or "<graphml" in graphml
        assert "Alice" in graphml
        assert "works_with" in graphml
        assert "<node" in graphml
        assert "<edge" in graphml

    def test_import_graphml(self, exchange):
        graphml = exchange.export_to_graphml()
        exchange.kg.clear()
        n_count, e_count = exchange.import_from_graphml(graphml)
        assert n_count == 3
        assert e_count == 3
        assert "Alice" in exchange.kg.nodes
        assert "Bob" in exchange.kg.nodes

    def test_graphml_roundtrip(self, exchange):
        graphml = exchange.export_to_graphml()
        exchange.kg.clear()
        exchange.import_from_graphml(graphml)
        assert len(exchange.kg.nodes) == 3
        assert len(exchange.kg.edges) == 3
        # 验证属性
        assert exchange.kg.nodes["Alice"].attributes.get("role") == "engineer"

    def test_import_invalid_graphml(self, exchange):
        n_count, e_count = exchange.import_from_graphml("<invalid>")
        assert n_count == 0
        assert e_count == 0

    # 辅助方法测试
    def test_to_safe_identifier(self, exchange):
        assert exchange._to_safe_identifier("hello world") == "hello_world"
        assert exchange._to_safe_identifier("test-123") == "test-123"
        assert exchange._to_safe_identifier("a@b#c") == "a_b_c"

    def test_to_from_uri(self, exchange):
        uri = exchange._to_uri("Alice", "http://example.org/")
        assert "Alice" in uri
        name = exchange._from_uri(uri, "http://example.org/")
        assert name == "Alice"

    def test_from_uri_prefix(self, exchange):
        name = exchange._from_uri("kg:works_with", "http://example.org/")
        assert name == "works_with"


class TestDataExchangeIntegration:
    def test_cross_format_consistency(self):
        """测试不同格式导出的一致性"""
        kg = KnowledgeGraph(save_path="test_cross.json")
        kg.clear()
        kg.add_node("X", {"key": "value"})
        kg.add_node("Y")
        kg.add_edge("X", "Y", "test_rel", 0.75)

        ex = DataExchange(kg)

        # CSV
        nodes_csv, edges_csv = ex.export_to_csv()
        # RDF
        rdf = ex.export_to_rdf()
        # GraphML
        graphml = ex.export_to_graphml()

        # 所有格式都应该包含节点和边信息
        assert "X" in nodes_csv
        assert "Y" in nodes_csv
        assert "test_rel" in edges_csv

        assert "X" in rdf
        assert "Y" in rdf

        assert "X" in graphml
        assert "Y" in graphml
        assert "test_rel" in graphml

        # 清理
        import os
        if os.path.exists("test_cross.json"):
            os.remove("test_cross.json")

    def test_large_graph_export(self):
        """测试较大图的导出性能"""
        kg = KnowledgeGraph(save_path="test_large.json")
        kg.clear()
        for i in range(100):
            kg.add_node(f"node_{i}", {"index": i})
            if i > 0:
                kg.add_edge(f"node_{i-1}", f"node_{i}", "next", 0.9)

        ex = DataExchange(kg)
        nodes_csv, edges_csv = ex.export_to_csv()
        assert "node_0" in nodes_csv
        assert "node_99" in nodes_csv
        assert len(edges_csv.split("\n")) >= 100

        graphml = ex.export_to_graphml()
        assert "node_50" in graphml

        # 清理
        import os
        if os.path.exists("test_large.json"):
            os.remove("test_large.json")
