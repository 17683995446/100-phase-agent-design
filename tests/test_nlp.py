"""
自然语言处理接口模块测试

测试分词、实体提取、文本相似度和查询转换功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的测试开始。
"""

import pytest
import tempfile
import os
from core import (
    KnowledgeGraph,
    SimpleTokenizer, EntityExtractor, TextSimilarity,
    NLQueryConverter, text_to_knowledge_graph
)


class TestSimpleTokenizer:
    """测试简单分词器"""

    def test_tokenize_empty(self):
        """测试空文本分词"""
        assert SimpleTokenizer.tokenize("") == []

    def test_tokenize_simple(self):
        """测试简单分词"""
        tokens = SimpleTokenizer.tokenize("Hello world")
        assert tokens == ["hello", "world"]

    def test_tokenize_with_punctuation(self):
        """测试带标点的分词"""
        tokens = SimpleTokenizer.tokenize("Hello, world! How are you?")
        assert "hello" in tokens
        assert "world" in tokens
        assert "how" in tokens
        assert "," not in tokens
        assert "!" not in tokens

    def test_tokenize_chinese(self):
        """测试中文分词"""
        tokens = SimpleTokenizer.tokenize("你好，世界")
        assert "你好" in tokens
        assert "世界" in tokens

    def test_tokenize_with_positions(self):
        """测试带位置的分词"""
        result = SimpleTokenizer.tokenize_with_positions("a b c")
        assert result == [("a", 0), ("b", 1), ("c", 2)]


class TestEntityExtractor:
    """测试实体提取器"""

    def test_extract_entities_empty_graph(self):
        """测试空知识图谱实体提取"""
        extractor = EntityExtractor()
        entities = extractor.extract_entities("Hello world")
        assert entities == []

    def test_extract_entities_exact_match(self):
        """测试精确匹配实体"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice")
            graph.add_node("Bob")

            extractor = EntityExtractor(graph)
            entities = extractor.extract_entities("Alice and Bob are friends")

            entity_names = [e["name"] for e in entities]
            assert "Alice" in entity_names
            assert "Bob" in entity_names
        finally:
            os.remove(kg_path)

    def test_extract_entities_by_pattern(self):
        """测试模式匹配实体"""
        extractor = EntityExtractor()
        entities = extractor.extract_entities_by_pattern(
            "Hello World and PythonCode",
            patterns=[r"[A-Z][a-zA-Z]+"]
        )

        entity_names = [e["name"] for e in entities]
        assert "Hello" in entity_names
        assert "World" in entity_names

    def test_extract_entities_confidence(self):
        """测试实体置信度"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice")

            extractor = EntityExtractor(graph)
            entities = extractor.extract_entities("Alice is here")

            assert len(entities) > 0
            assert entities[0]["confidence"] == 1.0
        finally:
            os.remove(kg_path)


class TestTextSimilarity:
    """测试文本相似度"""

    def test_jaccard_similarity_identical(self):
        """测试相同文本的 Jaccard 相似度"""
        sim = TextSimilarity.jaccard_similarity("hello world", "hello world")
        assert sim == 1.0

    def test_jaccard_similarity_different(self):
        """测试不同文本的 Jaccard 相似度"""
        sim = TextSimilarity.jaccard_similarity("hello world", "foo bar")
        assert sim == 0.0

    def test_jaccard_similarity_partial(self):
        """测试部分相似的 Jaccard 相似度"""
        sim = TextSimilarity.jaccard_similarity("hello world", "hello foo")
        assert 0.0 < sim < 1.0

    def test_cosine_similarity_identical(self):
        """测试相同文本的余弦相似度"""
        sim = TextSimilarity.cosine_similarity("hello world", "hello world")
        assert abs(sim - 1.0) < 1e-9

    def test_cosine_similarity_orthogonal(self):
        """测试正交文本的余弦相似度"""
        sim = TextSimilarity.cosine_similarity("hello", "world")
        assert sim == 0.0

    def test_levenshtein_distance(self):
        """测试 Levenshtein 距离"""
        dist = TextSimilarity.levenshtein_distance("kitten", "sitting")
        assert dist == 3

    def test_levenshtein_distance_empty(self):
        """测试空字符串的 Levenshtein 距离"""
        dist = TextSimilarity.levenshtein_distance("", "abc")
        assert dist == 3

    def test_normalized_levenshtein(self):
        """测试归一化 Levenshtein 相似度"""
        sim = TextSimilarity.normalized_levenshtein("hello", "hello")
        assert sim == 1.0

        sim = TextSimilarity.normalized_levenshtein("hello", "world")
        assert 0.0 <= sim <= 1.0


class TestNLQueryConverter:
    """测试自然语言查询转换器"""

    def test_creation_without_graph(self):
        """测试无知识图谱创建"""
        converter = NLQueryConverter()
        assert converter.knowledge_graph is None

    def test_convert_find_query(self):
        """测试转换查找查询"""
        converter = NLQueryConverter()
        result = converter.convert("find Alice")

        assert result["type"] == "find"

    def test_convert_relation_query(self):
        """测试转换关系查询"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice")
            graph.add_node("Bob")
            graph.add_edge("Alice", "Bob", "friend", 0.8)

            converter = NLQueryConverter(graph)
            result = converter.convert("relation between Alice and Bob")

            assert result["type"] == "relation"
            assert "Alice" in result["entities"]
            assert "Bob" in result["entities"]
        finally:
            os.remove(kg_path)

    def test_convert_similar_query(self):
        """测试转换相似查询"""
        converter = NLQueryConverter()
        result = converter.convert("similar to Alice")

        assert result["type"] == "similar"

    def test_convert_unknown_query(self):
        """测试转换未知查询"""
        converter = NLQueryConverter()
        result = converter.convert("xyz abc")

        assert result["type"] == "unknown"

    def test_execute_find_query(self):
        """测试执行查找查询"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice", {"type": "person"})

            converter = NLQueryConverter(graph)
            result = converter.execute_query("find Alice")

            assert result["query_type"] == "find"
            assert result["found"] is True
            assert result["node"]["name"] == "Alice"
        finally:
            os.remove(kg_path)

    def test_execute_relation_query(self):
        """测试执行关系查询"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice")
            graph.add_node("Bob")
            graph.add_edge("Alice", "Bob", "friend", 0.8)

            converter = NLQueryConverter(graph)
            result = converter.execute_query("relation between Alice and Bob")

            assert result["query_type"] == "relation"
            assert len(result["relations"]) == 1
            assert result["relations"][0]["relation"] == "friend"
        finally:
            os.remove(kg_path)

    def test_execute_without_graph(self):
        """测试无知识图谱执行"""
        converter = NLQueryConverter()
        result = converter.execute_query("find Alice")

        assert "error" in result


class TestTextToKnowledgeGraph:
    """测试文本到知识图谱转换"""

    def test_text_to_kg(self):
        """测试文本转换"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice")

            result = text_to_knowledge_graph("Alice and Bob are here", graph)

            assert "Alice" in result["extracted_entities"]
            assert isinstance(result["added_nodes"], list)
        finally:
            os.remove(kg_path)
