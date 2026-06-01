"""
相似度计算工具测试
"""

import pytest
import tempfile
from core import (
    KnowledgeGraph, Node,
    cosine_similarity, jaccard_similarity,
    node_to_vector, node_to_feature_set,
    find_similar_nodes_by_cosine, find_similar_nodes_by_jaccard,
    get_graph_statistics, get_node_statistics,
    find_nodes_by_attribute, find_relation_patterns,
    get_attribute_distribution,
    Rule, InferenceEngine,
    create_attribute_rule, create_relation_rule,
    find_subgraph_by_pattern, find_nodes_by_pattern,
    find_neighbors_by_relation
)


class TestCosineSimilarity:
    """测试余弦相似度"""
    
    def test_perfect_positive(self):
        """测试完全正相关的向量"""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [2.0, 4.0, 6.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(1.0)
    
    def test_perfect_negative(self):
        """测试完全负相关的向量"""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(-1.0)
    
    def test_orthogonal(self):
        """测试正交向量（相似度应该为0）"""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)
    
    def test_zero_vectors(self):
        """测试零向量"""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)
    
    def test_different_lengths(self):
        """测试不同长度的向量应该抛出错误"""
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError):
            cosine_similarity(vec1, vec2)
    
    def test_empty_vectors(self):
        """测试空向量应该抛出错误"""
        with pytest.raises(ValueError):
            cosine_similarity([], [])


class TestJaccardSimilarity:
    """测试Jaccard相似度"""
    
    def test_perfect_match(self):
        """测试完全相同的集合"""
        set1 = {1, 2, 3}
        set2 = {1, 2, 3}
        assert jaccard_similarity(set1, set2) == pytest.approx(1.0)
    
    def test_no_overlap(self):
        """测试没有交集的集合"""
        set1 = {1, 2, 3}
        set2 = {4, 5, 6}
        assert jaccard_similarity(set1, set2) == pytest.approx(0.0)
    
    def test_partial_overlap(self):
        """测试部分重叠"""
        set1 = {1, 2, 3, 4}
        set2 = {3, 4, 5, 6}
        expected = 2/6  # 交集大小/并集大小
        assert jaccard_similarity(set1, set2) == pytest.approx(expected)
    
    def test_empty_sets(self):
        """测试空集合"""
        assert jaccard_similarity(set(), set()) == pytest.approx(0.0)


class TestNodeToVector:
    """测试节点向量化"""
    
    def test_basic_conversion(self):
        """测试基本的节点转向量"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            node = Node("test", {})
            
            vec = node_to_vector(node, graph)
            
            # 向量长度应该是11（10个字符特征 + 1个边特征）
            assert len(vec) == 11
            assert all(isinstance(x, float) for x in vec)
        finally:
            import os
            os.remove(kg_path)
    
    def test_with_edges(self):
        """测试有边的节点转向量"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("a")
            graph.add_node("b")
            graph.add_edge("a", "b", "related", 0.5)
            
            node_a = graph.get_node("a")
            vec = node_to_vector(node_a, graph)
            
            assert len(vec) == 11
            # 边特征应该大于0
            assert vec[-1] > 0.0
        finally:
            import os
            os.remove(kg_path)


class TestNodeToFeatureSet:
    """测试节点转换为特征集合"""
    
    def test_basic_conversion(self):
        """测试基本的节点转特征集合"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            node = Node("test", {})
            
            features = node_to_feature_set(node, graph)
            
            assert isinstance(features, set)
            assert len(features) > 0
        finally:
            import os
            os.remove(kg_path)
    
    def test_with_edges(self):
        """测试有边的节点转特征集合"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("a")
            graph.add_node("b")
            graph.add_edge("a", "b", "related", 0.5)
            
            node_a = graph.get_node("a")
            features = node_to_feature_set(node_a, graph)
            
            # 应该包含邻居相关特征
            assert any("neighbor" in f for f in features)
            assert any("rel_" in f for f in features)
        finally:
            import os
            os.remove(kg_path)


class TestFindSimilarNodesByCosine:
    """测试基于余弦相似度查找相似节点"""
    
    def test_find_similar_nodes(self):
        """测试基本的查找相似节点"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("apple")
            graph.add_node("apples")  # 相似的名字
            graph.add_node("banana")  # 不相似的
            graph.add_node("app")     # 部分相似
            
            similar = find_similar_nodes_by_cosine(graph, "apple", top_k=3)
            
            assert len(similar) <= 3
            # 应该返回一个节点名和相似度的列表
            for name, score in similar:
                assert isinstance(name, str)
                assert isinstance(score, float)
        finally:
            import os
            os.remove(kg_path)
    
    def test_non_existent_node(self):
        """测试查找不存在的节点"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            similar = find_similar_nodes_by_cosine(graph, "nonexistent", top_k=5)
            assert len(similar) == 0
        finally:
            import os
            os.remove(kg_path)


class TestFindSimilarNodesByJaccard:
    """测试基于Jaccard相似度查找相似节点"""
    
    def test_find_similar_nodes(self):
        """测试基本的查找相似节点"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("apple")
            graph.add_node("apples")  # 相似的名字
            graph.add_node("banana")  # 不相似的
            graph.add_node("app")     # 部分相似
            
            similar = find_similar_nodes_by_jaccard(graph, "apple", top_k=3)
            
            assert len(similar) <= 3
            # 应该返回一个节点名和相似度的列表
            for name, score in similar:
                assert isinstance(name, str)
                assert isinstance(score, float)
        finally:
            import os
            os.remove(kg_path)
    
    def test_non_existent_node(self):
        """测试查找不存在的节点"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            similar = find_similar_nodes_by_jaccard(graph, "nonexistent", top_k=5)
            assert len(similar) == 0
        finally:
            import os
            os.remove(kg_path)


class TestGetGraphStatistics:
    """测试知识图谱统计功能"""
    
    def test_empty_graph(self):
        """测试空图的统计"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            stats = get_graph_statistics(graph)
            
            assert stats["node_count"] == 0
            assert stats["edge_count"] == 0
            assert stats["relation_types"] == []
            assert stats["avg_out_degree"] == 0
            assert stats["avg_in_degree"] == 0
        finally:
            import os
            os.remove(kg_path)
    
    def test_simple_graph(self):
        """测试简单图的统计"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("a")
            graph.add_node("b")
            graph.add_node("c")
            graph.add_edge("a", "b", "related", 0.5)
            graph.add_edge("b", "c", "connected", 0.7)
            graph.add_edge("a", "c", "related", 0.3)
            
            stats = get_graph_statistics(graph)
            
            assert stats["node_count"] == 3
            assert stats["edge_count"] == 3
            assert set(stats["relation_types"]) == {"related", "connected"}
            assert stats["relation_distribution"]["related"] == 2
            assert stats["relation_distribution"]["connected"] == 1
            assert stats["avg_out_degree"] == pytest.approx(1.0)
            assert stats["avg_in_degree"] == pytest.approx(1.0)
        finally:
            import os
            os.remove(kg_path)
    
    def test_top_nodes_by_degree(self):
        """测试高度节点统计"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("a")
            graph.add_node("b")
            graph.add_node("c")
            graph.add_node("d")
            graph.add_node("e")
            
            graph.add_edge("a", "b", "related", 0.5)
            graph.add_edge("a", "c", "related", 0.5)
            graph.add_edge("a", "d", "related", 0.5)
            graph.add_edge("a", "e", "related", 0.5)
            
            stats = get_graph_statistics(graph)
            
            top_nodes = stats["top_nodes_by_degree"]
            assert len(top_nodes) > 0
            assert top_nodes[0][0] == "a"
        finally:
            import os
            os.remove(kg_path)


class TestGetNodeStatistics:
    """测试节点统计功能"""
    
    def test_non_existent_node(self):
        """测试不存在的节点"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            stats = get_node_statistics(graph, "nonexistent")
            assert stats is None
        finally:
            import os
            os.remove(kg_path)
    
    def test_node_without_edges(self):
        """测试没有边的节点"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("a")
            
            stats = get_node_statistics(graph, "a")
            
            assert stats["node_name"] == "a"
            assert stats["out_edge_count"] == 0
            assert stats["in_edge_count"] == 0
            assert stats["total_edge_count"] == 0
            assert stats["neighbor_count"] == 0
        finally:
            import os
            os.remove(kg_path)
    
    def test_node_with_edges(self):
        """测试有边的节点"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("a")
            graph.add_node("b")
            graph.add_node("c")
            
            graph.add_edge("a", "b", "related", 0.5)
            graph.add_edge("a", "c", "connected", 0.7)
            graph.add_edge("b", "a", "linked", 0.6)
            
            stats = get_node_statistics(graph, "a")
            
            assert stats["node_name"] == "a"
            assert stats["out_edge_count"] == 2
            assert stats["in_edge_count"] == 1
            assert stats["total_edge_count"] == 3
            assert set(stats["outgoing_relations"]) == {"related", "connected"}
            assert stats["incoming_relations"] == ["linked"]
            assert stats["neighbor_count"] == 2
        finally:
            import os
            os.remove(kg_path)
    
    def test_node_with_attributes(self):
        """测试有属性的节点"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("a", {"type": "person", "age": 25})
            
            stats = get_node_statistics(graph, "a")
            
            assert stats["node_attributes"] == {"type": "person", "age": 25}
        finally:
            import os
            os.remove(kg_path)


class TestFindNodesByAttribute:
    """测试按属性查找节点"""
    
    def test_find_nodes_with_attribute(self):
        """测试查找具有特定属性的节点"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice", {"type": "person", "age": 30})
            graph.add_node("Bob", {"type": "person", "age": 35})
            graph.add_node("Python", {"type": "language"})
            graph.add_node("Paris", {"type": "city"})
            
            # 查找所有具有"type"属性的节点
            nodes_with_type = find_nodes_by_attribute(graph, "type")
            assert set(nodes_with_type) == {"Alice", "Bob", "Python", "Paris"}
            
            # 查找type="person"的节点
            persons = find_nodes_by_attribute(graph, "type", "person")
            assert set(persons) == {"Alice", "Bob"}
            
            # 查找type="language"的节点
            languages = find_nodes_by_attribute(graph, "type", "language")
            assert languages == ["Python"]
            
        finally:
            import os
            os.remove(kg_path)
    
    def test_find_nodes_no_matching(self):
        """测试查找不存在的属性或值"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice", {"type": "person"})
            
            # 查找不存在的属性
            result = find_nodes_by_attribute(graph, "nonexistent_attr")
            assert result == []
            
            # 查找存在的属性但不存在的值
            result = find_nodes_by_attribute(graph, "type", "animal")
            assert result == []
            
        finally:
            import os
            os.remove(kg_path)


class TestAttributeDistribution:
    """测试属性分布统计"""
    
    def test_get_attribute_distribution(self):
        """测试获取属性分布"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice", {"type": "person", "age": 30, "city": "New York"})
            graph.add_node("Bob", {"type": "person", "age": 35, "city": "London"})
            graph.add_node("Charlie", {"type": "person", "age": 30, "city": "New York"})
            graph.add_node("Python", {"type": "language", "version": "3.9"})
            graph.add_node("JavaScript", {"type": "language", "version": "ES6"})
            graph.add_node("Paris", {"type": "city"})
            
            dist = get_attribute_distribution(graph)
            
            # 检查type属性的分布
            assert "type" in dist
            assert dist["type"]["person"] == 3
            assert dist["type"]["language"] == 2
            assert dist["type"]["city"] == 1
            
            # 检查age属性的分布
            assert "age" in dist
            assert dist["age"]["30"] == 2
            assert dist["age"]["35"] == 1
            
            # 检查city属性的分布
            assert "city" in dist
            assert dist["city"]["New York"] == 2
            assert dist["city"]["London"] == 1
            
        finally:
            import os
            os.remove(kg_path)
    
    def test_empty_graph_distribution(self):
        """测试空图的属性分布"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            dist = get_attribute_distribution(graph)
            assert dist == {}
            
        finally:
            import os
            os.remove(kg_path)


class TestRelationPatterns:
    """测试关系模式识别"""
    
    def test_find_relation_patterns(self):
        """测试查找关系模式"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            
            # 添加具有属性的节点
            graph.add_node("Alice", {"type": "person"})
            graph.add_node("Bob", {"type": "person"})
            graph.add_node("Charlie", {"type": "person"})
            graph.add_node("David", {"type": "person"})
            graph.add_node("Python", {"type": "language"})
            graph.add_node("JavaScript", {"type": "language"})
            graph.add_node("AI", {"type": "field"})
            graph.add_node("ML", {"type": "field"})
            
            # 添加边，创建模式
            graph.add_edge("Alice", "Bob", "friend", 0.8)
            graph.add_edge("Alice", "Charlie", "friend", 0.7)
            graph.add_edge("Alice", "Python", "uses", 0.9)
            graph.add_edge("Bob", "David", "friend", 0.8)
            graph.add_edge("Bob", "JavaScript", "uses", 0.9)
            graph.add_edge("Charlie", "Python", "uses", 0.8)
            graph.add_edge("David", "JavaScript", "uses", 0.9)
            graph.add_edge("Alice", "AI", "interest", 0.7)
            graph.add_edge("Bob", "ML", "interest", 0.7)
            graph.add_edge("AI", "ML", "includes", 0.9)
            
            # 查找模式（min_occurrences=2）
            patterns = find_relation_patterns(graph, min_occurrences=2)
            
            # 应该能找到一些属性-关系模式
            assert "attribute_relation_patterns" in patterns
            assert len(patterns["attribute_relation_patterns"]) > 0
            
            # 应该能找到一些关系序列模式
            assert "relation_sequence_patterns" in patterns
            
        finally:
            import os
            os.remove(kg_path)
    
    def test_no_patterns_min_occurrences(self):
        """测试最小出现次数过高时没有模式"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("A", {"type": "x"})
            graph.add_node("B", {"type": "y"})
            graph.add_edge("A", "B", "rel", 0.5)
            
            # 设置很高的最小出现次数
            patterns = find_relation_patterns(graph, min_occurrences=100)
            assert len(patterns["attribute_relation_patterns"]) == 0
            assert len(patterns["relation_sequence_patterns"]) == 0
            
        finally:
            import os
            os.remove(kg_path)


class TestInferenceEngine:
    """测试推理引擎"""
    
    def test_rule_creation(self):
        """测试规则创建"""
        rule = Rule(
            name="test_rule",
            conditions=[{"type": "has_attribute", "attribute": "type", "value": "person"}],
            actions=[{"type": "set_attribute", "attribute": "is_human", "value": True}],
            confidence=0.8
        )
        assert rule.name == "test_rule"
        assert rule.confidence == 0.8
        assert len(rule.conditions) == 1
        assert len(rule.actions) == 1
    
    def test_create_attribute_rule(self):
        """测试快捷创建属性规则"""
        rule = create_attribute_rule(
            name="person_to_human",
            condition_attr="type",
            condition_value="person",
            action_attr="is_human",
            action_value=True,
            confidence=0.9
        )
        assert rule.name == "person_to_human"
        assert rule.conditions[0]["type"] == "has_attribute"
    
    def test_inference_basic(self):
        """测试基本推理功能"""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice", {"type": "person"})
            graph.add_node("Bob", {"type": "animal"})
            
            # 创建推理引擎和规则
            engine = InferenceEngine()
            rule = create_attribute_rule(
                name="person_rule",
                condition_attr="type",
                condition_value="person",
                action_attr="is_human",
                action_value=True
            )
            engine.add_rule(rule)
            
            # 对Alice进行推理
            results = engine.infer(graph, "Alice")
            assert len(results) == 1
            assert results[0]["rule"] == "person_rule"
            assert len(results[0]["actions"]) == 1
            
            # 验证属性被设置
            alice = graph.get_node("Alice")
            assert alice.attributes.get("is_human") is True
            
        finally:
            os.remove(kg_path)
    
    def test_inference_all(self):
        """测试对所有节点推理"""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice", {"type": "person"})
            graph.add_node("Bob", {"type": "person"})
            graph.add_node("Charlie", {"type": "animal"})
            
            engine = InferenceEngine()
            rule = create_attribute_rule(
                name="person_rule",
                condition_attr="type",
                condition_value="person",
                action_attr="is_human",
                action_value=True
            )
            engine.add_rule(rule)
            
            # 对所有节点推理
            all_results = engine.infer_all(graph)
            assert len(all_results) == 2
            assert "Alice" in all_results
            assert "Bob" in all_results
            assert "Charlie" not in all_results
            
        finally:
            os.remove(kg_path)
    
    def test_relation_condition(self):
        """测试关系条件"""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice")
            graph.add_node("Bob")
            graph.add_edge("Alice", "Bob", "friend", 0.9)
            
            engine = InferenceEngine()
            # 创建规则：如果有朋友关系，标记为社交活跃
            rule = Rule(
                name="social_active",
                conditions=[{"type": "has_relation", "relation": "friend"}],
                actions=[{"type": "set_attribute", "attribute": "social_active", "value": True}]
            )
            engine.add_rule(rule)
            
            results = engine.infer(graph, "Alice")
            assert len(results) == 1
            
            alice = graph.get_node("Alice")
            assert alice.attributes.get("social_active") is True
            
        finally:
            import os
            os.remove(kg_path)


class TestSubgraphMatching:
    """测试子图匹配功能"""
    
    def test_find_nodes_by_pattern(self):
        """测试通过属性模式查找节点"""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice", {"type": "person", "age": 30})
            graph.add_node("Bob", {"type": "person", "age": 35})
            graph.add_node("Python", {"type": "language"})
            
            # 查找所有 person 类型的节点
            persons = find_nodes_by_pattern(graph, {"type": "person"})
            assert len(persons) == 2
            assert set(persons) == {"Alice", "Bob"}
            
            # 查找特定 age 的节点
            age_30 = find_nodes_by_pattern(graph, {"type": "person", "age": 30})
            assert len(age_30) == 1
            assert age_30 == ["Alice"]
            
        finally:
            os.remove(kg_path)
    
    def test_find_subgraph_by_pattern(self):
        """测试完整的子图匹配"""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice", {"type": "person"})
            graph.add_node("Bob", {"type": "person"})
            graph.add_node("Python", {"type": "language"})
            graph.add_node("Java", {"type": "language"})
            
            graph.add_edge("Alice", "Python", "uses", 0.8)
            graph.add_edge("Bob", "Java", "uses", 0.9)
            graph.add_edge("Alice", "Bob", "friend", 0.7)
            
            # 定义子图模式：人 使用 语言
            pattern = {
                "nodes": [
                    {"name": "user", "attributes": {"type": "person"}},
                    {"name": "tool", "attributes": {"type": "language"}}
                ],
                "edges": [
                    {"source": "user", "target": "tool", "relation": "uses"}
                ]
            }
            
            results = find_subgraph_by_pattern(graph, pattern)
            assert len(results) == 2
            
            # 验证结果
            node_mappings = [result["node_mapping"] for result in results]
            assert {"user": "Alice", "tool": "Python"} in node_mappings
            assert {"user": "Bob", "tool": "Java"} in node_mappings
            
        finally:
            os.remove(kg_path)
    
    def test_find_neighbors_by_relation(self):
        """测试按关系查找邻居"""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice")
            graph.add_node("Bob")
            graph.add_node("Charlie")
            graph.add_node("Python")
            
            graph.add_edge("Alice", "Bob", "friend", 0.8)
            graph.add_edge("Alice", "Charlie", "friend", 0.7)
            graph.add_edge("Alice", "Python", "uses", 0.9)
            graph.add_edge("Bob", "Alice", "colleague", 0.6)
            
            # 查找 out 方向的朋友
            friends_out = find_neighbors_by_relation(graph, "Alice", "friend", "outgoing")
            assert set(friends_out) == {"Bob", "Charlie"}
            
            # 查找 in 方向的同事
            colleagues_in = find_neighbors_by_relation(graph, "Alice", "colleague", "incoming")
            assert colleagues_in == ["Bob"]
            
            # 查找双向所有关系
            all_neighbors = find_neighbors_by_relation(graph, "Alice", "friend", "both")
            assert set(all_neighbors) == {"Bob", "Charlie"}
            
        finally:
            os.remove(kg_path)
    
    def test_no_matching_pattern(self):
        """测试无匹配的情况"""
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice", {"type": "person"})
            
            # 查找不存在的模式
            results = find_nodes_by_pattern(graph, {"type": "animal"})
            assert len(results) == 0
            
            # 测试复杂子图无匹配
            pattern = {
                "nodes": [
                    {"name": "a", "attributes": {"type": "person"}},
                    {"name": "b", "attributes": {"type": "animal"}}
                ],
                "edges": [
                    {"source": "a", "target": "b", "relation": "owns"}
                ]
            }
            subgraphs = find_subgraph_by_pattern(graph, pattern)
            assert len(subgraphs) == 0
            
        finally:
            os.remove(kg_path)
