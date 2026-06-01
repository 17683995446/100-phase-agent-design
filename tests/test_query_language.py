import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.knowledge_graph import KnowledgeGraph
from core.query_language import (
    QueryParser, QueryExecutor, QueryEngine,
    QueryResult, QueryParseError
)


class TestQueryParser:
    def test_parse_simple_node_query(self):
        parser = QueryParser()
        result = parser.parse("MATCH (n) RETURN n")
        assert result["match_type"] == "nodes"
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["var"] == "n"
        assert result["return_vars"] == ["n"]

    def test_parse_labeled_node(self):
        parser = QueryParser()
        result = parser.parse("MATCH (n:Person) RETURN n")
        assert result["nodes"][0]["label"] == "Person"

    def test_parse_node_with_properties(self):
        parser = QueryParser()
        result = parser.parse("MATCH (n {name: 'Alice', age: 30}) RETURN n")
        assert result["nodes"][0]["properties"]["name"] == "Alice"
        assert result["nodes"][0]["properties"]["age"] == 30

    def test_parse_edge_query(self):
        parser = QueryParser()
        result = parser.parse("MATCH (a)-[r]->(b) RETURN a, b, r")
        assert result["match_type"] == "edges"
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1
        assert result["edges"][0]["var"] == "r"
        assert result["edges"][0]["direction"] == "->"

    def test_parse_typed_edge(self):
        parser = QueryParser()
        result = parser.parse("MATCH (a)-[r:KNOWS]->(b) RETURN a, b")
        assert result["edges"][0]["type"] == "KNOWS"

    def test_parse_where_clause(self):
        parser = QueryParser()
        result = parser.parse("MATCH (n) WHERE n.name = 'Alice' RETURN n")
        assert len(result["where"]) == 1
        assert result["where"][0]["field"] == "n.name"
        assert result["where"][0]["op"] == "="
        assert result["where"][0]["value"] == "Alice"

    def test_parse_multiple_where(self):
        parser = QueryParser()
        result = parser.parse("MATCH (n) WHERE n.age > 25 AND n.name = 'Bob' RETURN n")
        assert len(result["where"]) == 2

    def test_parse_limit(self):
        parser = QueryParser()
        result = parser.parse("MATCH (n) RETURN n LIMIT 10")
        assert result["limit"] == 10

    def test_parse_empty_query_raises(self):
        parser = QueryParser()
        with pytest.raises(QueryParseError):
            parser.parse("")

    def test_parse_missing_match_raises(self):
        parser = QueryParser()
        with pytest.raises(QueryParseError):
            parser.parse("RETURN n")

    def test_parse_path_query(self):
        parser = QueryParser()
        result = parser.parse("MATCH path = (a)-[*]->(b) RETURN path")
        assert result["match_type"] == "path"


class TestQueryExecutor:
    @pytest.fixture
    def sample_graph(self):
        kg = KnowledgeGraph(save_path="test_query.json")
        kg.clear()
        kg.add_node("Alice", {"age": 30, "role": "engineer"})
        kg.add_node("Bob", {"age": 25, "role": "designer"})
        kg.add_node("Carol", {"age": 35, "role": "manager"})
        kg.add_edge("Alice", "Bob", "works_with", 0.8)
        kg.add_edge("Bob", "Carol", "reports_to", 0.9)
        return kg

    @pytest.fixture
    def executor(self, sample_graph):
        return QueryExecutor(sample_graph)

    def test_execute_node_query(self, executor):
        query = {
            "match_type": "nodes",
            "nodes": [{"var": "n", "label": None, "properties": {}}],
            "where": [],
            "return_vars": ["n"],
            "limit": None
        }
        result = executor.execute(query)
        assert len(result) == 3
        assert "n" in result.columns

    def test_execute_node_query_with_where(self, executor):
        query = {
            "match_type": "nodes",
            "nodes": [{"var": "n", "label": None, "properties": {}}],
            "where": [{"field": "n.name", "op": "=", "value": "Alice"}],
            "return_vars": ["n"],
            "limit": None
        }
        result = executor.execute(query)
        assert len(result) == 1
        assert result.data[0]["n"]["name"] == "Alice"

    def test_execute_edge_query(self, executor):
        query = {
            "match_type": "edges",
            "nodes": [{"var": "a"}, {"var": "b"}],
            "edges": [{"var": "r", "type": None, "properties": {}, "direction": "->"}],
            "where": [],
            "return_vars": ["a", "r", "b"],
            "limit": None
        }
        result = executor.execute(query)
        assert len(result) == 2
        assert "a" in result.columns
        assert "r" in result.columns
        assert "b" in result.columns

    def test_execute_with_limit(self, executor):
        query = {
            "match_type": "nodes",
            "nodes": [{"var": "n"}],
            "where": [],
            "return_vars": ["n"],
            "limit": 2
        }
        result = executor.execute(query)
        assert len(result) == 2

    def test_compare_operators(self, executor):
        assert executor._compare(30, "=", 30) is True
        assert executor._compare(30, ">", 25) is True
        assert executor._compare(25, "<", 30) is True
        assert executor._compare(30, ">=", 30) is True
        assert executor._compare(30, "<=", 30) is True
        assert executor._compare(30, "!=", 25) is True


class TestQueryEngine:
    @pytest.fixture
    def sample_graph(self):
        kg = KnowledgeGraph(save_path="test_engine.json")
        kg.clear()
        kg.add_node("Alice", {"age": 30, "role": "engineer"})
        kg.add_node("Bob", {"age": 25, "role": "designer"})
        kg.add_node("Carol", {"age": 35, "role": "manager"})
        kg.add_edge("Alice", "Bob", "works_with", 0.8)
        kg.add_edge("Bob", "Carol", "reports_to", 0.9)
        return kg

    @pytest.fixture
    def engine(self, sample_graph):
        return QueryEngine(sample_graph)

    def test_query_all_nodes(self, engine):
        result = engine.query("MATCH (n) RETURN n")
        assert len(result) == 3

    def test_query_with_where(self, engine):
        result = engine.query("MATCH (n) WHERE n.name = 'Alice' RETURN n")
        assert len(result) == 1
        assert result.data[0]["n"]["name"] == "Alice"

    def test_query_edges(self, engine):
        result = engine.query("MATCH (a)-[r]->(b) RETURN a, b, r")
        assert len(result) == 2
        assert result.data[0]["r"]["relation"] in ["works_with", "reports_to"]

    def test_query_with_limit(self, engine):
        result = engine.query("MATCH (n) RETURN n LIMIT 2")
        assert len(result) == 2

    def test_find_nodes_simplified(self, engine):
        result = engine.find_nodes(properties={"role": "engineer"})
        assert len(result) == 1
        assert result.data[0]["n"]["name"] == "Alice"

    def test_find_neighbors(self, engine):
        result = engine.find_neighbors("Alice")
        assert len(result) == 1
        assert result.data[0]["target"]["name"] == "Bob"
        assert result.data[0]["relation"] == "works_with"

    def test_find_neighbors_with_relation_filter(self, engine):
        result = engine.find_neighbors("Alice", relation="works_with")
        assert len(result) == 1
        result2 = engine.find_neighbors("Alice", relation="nonexistent")
        assert len(result2) == 0

    def test_query_result_to_dict(self, engine):
        result = engine.query("MATCH (n) WHERE n.name = 'Alice' RETURN n")
        d = result.to_dict()
        assert "columns" in d
        assert "rows" in d
        assert "count" in d
        assert d["count"] == 1


class TestQueryLanguageIntegration:
    def test_complex_query_pipeline(self):
        kg = KnowledgeGraph(save_path="test_complex_query.json")
        kg.clear()
        kg.add_node("Alice", {"age": 30, "role": "engineer"})
        kg.add_node("Bob", {"age": 25, "role": "designer"})
        kg.add_node("Carol", {"age": 35, "role": "manager"})
        kg.add_node("David", {"age": 28, "role": "engineer"})
        kg.add_edge("Alice", "Bob", "works_with", 0.8)
        kg.add_edge("Bob", "Carol", "reports_to", 0.9)
        kg.add_edge("Alice", "David", "works_with", 0.7)

        engine = QueryEngine(kg)

        # 查询所有工程师
        result = engine.find_nodes(properties={"role": "engineer"})
        assert len(result) == 2

        # 查询 Alice 的同事
        result = engine.find_neighbors("Alice", relation="works_with")
        assert len(result) == 2

        # 使用查询语言
        result = engine.query("MATCH (a)-[r]->(b) WHERE r.weight > 0.75 RETURN a, b")
        assert len(result) == 2  # Alice->Bob (0.8), Bob->Carol (0.9)

        # 清理
        import os
        if os.path.exists("test_complex_query.json"):
            os.remove("test_complex_query.json")
