#!/usr/bin/env python3
"""
相似度计算工具使用示例
"""

import tempfile
import os
from core import (
    KnowledgeGraph,
    cosine_similarity, jaccard_similarity,
    find_similar_nodes_by_cosine, find_similar_nodes_by_jaccard,
    get_graph_statistics, get_node_statistics,
    find_nodes_by_attribute, find_relation_patterns,
    get_attribute_distribution,
    Rule, InferenceEngine,
    create_attribute_rule, create_relation_rule,
    find_subgraph_by_pattern, find_nodes_by_pattern,
    find_neighbors_by_relation
)


def example_cosine_similarity():
    """余弦相似度示例"""
    print("=" * 70)
    print("余弦相似度示例")
    print("=" * 70)
    
    vec1 = [1.0, 2.0, 3.0]
    vec2 = [2.0, 4.0, 6.0]
    vec3 = [1.0, -2.0, 3.0]
    
    print(f"vec1: {vec1}")
    print(f"vec2: {vec2}")
    print(f"vec3: {vec3}")
    print()
    
    sim1_2 = cosine_similarity(vec1, vec2)
    sim1_3 = cosine_similarity(vec1, vec3)
    
    print(f"vec1 和 vec2 的余弦相似度: {sim1_2}")
    print(f"vec1 和 vec3 的余弦相似度: {sim1_3}")


def example_jaccard_similarity():
    """Jaccard相似度示例"""
    print("\n" + "=" * 70)
    print("Jaccard相似度示例")
    print("=" * 70)
    
    set1 = {1, 2, 3, 4}
    set2 = {3, 4, 5, 6}
    set3 = {7, 8, 9}
    
    print(f"set1: {set1}")
    print(f"set2: {set2}")
    print(f"set3: {set3}")
    print()
    
    sim1_2 = jaccard_similarity(set1, set2)
    sim1_3 = jaccard_similarity(set1, set3)
    
    print(f"set1 和 set2 的Jaccard相似度: {sim1_2}")
    print(f"set1 和 set3 的Jaccard相似度: {sim1_3}")


def example_find_similar_nodes():
    """查找相似节点示例"""
    print("\n" + "=" * 70)
    print("查找相似节点示例")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        kg_path = f.name
    try:
        # 创建知识图谱
        graph = KnowledgeGraph(kg_path)
        
        # 添加一些节点
        nodes = ["apple", "apples", "app", "banana", "orange", "orange_fruit", "test", "testing"]
        for node in nodes:
            graph.add_node(node)
        
        # 添加一些边
        graph.add_edge("apple", "apples", "plural", 0.9)
        graph.add_edge("app", "apple", "prefix", 0.7)
        graph.add_edge("banana", "orange", "fruit", 0.6)
        graph.add_edge("orange", "orange_fruit", "related", 0.8)
        graph.add_edge("test", "testing", "related", 0.7)
        
        print(f"知识图谱中的节点: {list(graph.nodes.keys())}")
        print()
        
        # 余弦相似度查找与"apple"相似的节点
        print("余弦相似度 - 查找与 'apple' 相似的节点:")
        similar = find_similar_nodes_by_cosine(graph, "apple", top_k=3)
        for name, score in similar:
            print(f"  - {name}: {score:.4f}")
        
        print()
        
        # Jaccard相似度查找与"apple"相似的节点
        print("Jaccard相似度 - 查找与 'apple' 相似的节点:")
        similar = find_similar_nodes_by_jaccard(graph, "apple", top_k=3)
        for name, score in similar:
            print(f"  - {name}: {score:.4f}")
        
        print()
        
        # 余弦相似度查找与"test"相似的节点
        print("余弦相似度 - 查找与 'test' 相似的节点:")
        similar = find_similar_nodes_by_cosine(graph, "test", top_k=2)
        for name, score in similar:
            print(f"  - {name}: {score:.4f}")
        
        print()
        
        # Jaccard相似度查找与"test"相似的节点
        print("Jaccard相似度 - 查找与 'test' 相似的节点:")
        similar = find_similar_nodes_by_jaccard(graph, "test", top_k=2)
        for name, score in similar:
            print(f"  - {name}: {score:.4f}")
            
    finally:
        os.remove(kg_path)


def example_graph_statistics():
    """知识图谱统计示例"""
    print("\n" + "=" * 70)
    print("知识图谱统计示例")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        kg_path = f.name
    try:
        # 创建一个更复杂的知识图谱
        graph = KnowledgeGraph(kg_path)
        
        # 添加节点（包括有属性的节点）
        graph.add_node("Alice", {"type": "person", "age": 30})
        graph.add_node("Bob", {"type": "person", "age": 35})
        graph.add_node("Charlie", {"type": "person", "age": 28})
        graph.add_node("David", {"type": "person", "age": 40})
        graph.add_node("Eve", {"type": "person", "age": 25})
        graph.add_node("Python", {"type": "language", "paradigm": "multi-paradigm"})
        graph.add_node("JavaScript", {"type": "language", "paradigm": "multi-paradigm"})
        graph.add_node("AI", {"type": "field", "description": "Artificial Intelligence"})
        graph.add_node("Machine Learning", {"type": "field", "description": "Subfield of AI"})
        graph.add_node("Deep Learning", {"type": "field", "description": "Subfield of ML"})
        
        # 添加边
        graph.add_edge("Alice", "Bob", "friend", 0.8)
        graph.add_edge("Alice", "Charlie", "friend", 0.7)
        graph.add_edge("Bob", "David", "colleague", 0.9)
        graph.add_edge("Charlie", "Eve", "friend", 0.6)
        graph.add_edge("David", "Eve", "colleague", 0.7)
        graph.add_edge("Alice", "Python", "uses", 0.8)
        graph.add_edge("Bob", "JavaScript", "uses", 0.9)
        graph.add_edge("Charlie", "Python", "uses", 0.7)
        graph.add_edge("David", "AI", "researcher", 0.9)
        graph.add_edge("Eve", "Machine Learning", "interest", 0.8)
        graph.add_edge("AI", "Machine Learning", "includes", 0.9)
        graph.add_edge("Machine Learning", "Deep Learning", "includes", 0.8)
        graph.add_edge("Alice", "Machine Learning", "study", 0.7)
        
        print(f"知识图谱中的节点数量: {len(graph.nodes)}")
        print(f"知识图谱中的边数量: {len(graph.edges)}")
        print()
        
        # 获取图的统计信息
        print("知识图谱整体统计:")
        graph_stats = get_graph_statistics(graph)
        print(f"  节点总数: {graph_stats['node_count']}")
        print(f"  边总数: {graph_stats['edge_count']}")
        print(f"  关系类型: {', '.join(graph_stats['relation_types'])}")
        print(f"  关系分布:")
        for rel, count in graph_stats['relation_distribution'].items():
            print(f"    - {rel}: {count}")
        print(f"  平均出度: {graph_stats['avg_out_degree']:.2f}")
        print(f"  平均入度: {graph_stats['avg_in_degree']:.2f}")
        print(f"  高度节点:")
        for node, degree in graph_stats['top_nodes_by_degree'][:5]:
            print(f"    - {node}: {degree} 条边")
        
        print()
        
        # 获取单个节点的统计信息
        print("Alice 节点统计:")
        alice_stats = get_node_statistics(graph, "Alice")
        if alice_stats:
            print(f"  节点名称: {alice_stats['node_name']}")
            print(f"  节点属性: {alice_stats['node_attributes']}")
            print(f"  出边数: {alice_stats['out_edge_count']}")
            print(f"  入边数: {alice_stats['in_edge_count']}")
            print(f"  总边数: {alice_stats['total_edge_count']}")
            print(f"  出边关系类型: {', '.join(alice_stats['outgoing_relations'])}")
            print(f"  入边关系类型: {', '.join(alice_stats['incoming_relations'])}")
            print(f"  邻居数: {alice_stats['neighbor_count']}")
        
        print()
        
        # 获取AI节点的统计信息
        print("AI 节点统计:")
        ai_stats = get_node_statistics(graph, "AI")
        if ai_stats:
            print(f"  节点名称: {ai_stats['node_name']}")
            print(f"  节点属性: {ai_stats['node_attributes']}")
            print(f"  出边数: {ai_stats['out_edge_count']}")
            print(f"  总边数: {ai_stats['total_edge_count']}")
            print(f"  邻居数: {ai_stats['neighbor_count']}")
            
    finally:
        os.remove(kg_path)


def example_pattern_recognition():
    """模式识别示例"""
    print("\n" + "=" * 70)
    print("模式识别示例")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        kg_path = f.name
    try:
        # 创建知识图谱
        graph = KnowledgeGraph(kg_path)
        
        # 添加具有属性的节点
        graph.add_node("Alice", {"type": "person", "age": 30, "city": "New York"})
        graph.add_node("Bob", {"type": "person", "age": 35, "city": "London"})
        graph.add_node("Charlie", {"type": "person", "age": 30, "city": "New York"})
        graph.add_node("David", {"type": "person", "age": 40, "city": "Paris"})
        graph.add_node("Python", {"type": "language", "paradigm": "multi-paradigm"})
        graph.add_node("JavaScript", {"type": "language", "paradigm": "multi-paradigm"})
        graph.add_node("Java", {"type": "language", "paradigm": "object-oriented"})
        graph.add_node("AI", {"type": "field", "description": "Artificial Intelligence"})
        graph.add_node("Machine Learning", {"type": "field", "description": "Subfield of AI"})
        
        # 添加边
        graph.add_edge("Alice", "Bob", "friend", 0.8)
        graph.add_edge("Alice", "Charlie", "friend", 0.7)
        graph.add_edge("Alice", "Python", "uses", 0.9)
        graph.add_edge("Bob", "David", "colleague", 0.9)
        graph.add_edge("Bob", "JavaScript", "uses", 0.9)
        graph.add_edge("Charlie", "Python", "uses", 0.8)
        graph.add_edge("David", "Java", "uses", 0.9)
        graph.add_edge("Charlie", "AI", "interest", 0.7)
        graph.add_edge("Alice", "Machine Learning", "interest", 0.8)
        graph.add_edge("AI", "Machine Learning", "includes", 0.9)
        
        print(f"知识图谱中的节点数量: {len(graph.nodes)}")
        print(f"知识图谱中的边数量: {len(graph.edges)}")
        print()
        
        # 1. 属性查找示例
        print("1. 按属性查找节点:")
        print("   查找所有 type='person' 的节点:")
        persons = find_nodes_by_attribute(graph, "type", "person")
        for name in persons:
            print(f"   - {name}")
        
        print()
        print("   查找所有具有 'type' 属性的节点:")
        all_typed = find_nodes_by_attribute(graph, "type")
        for name in all_typed:
            print(f"   - {name}")
        
        print()
        
        # 2. 属性分布示例
        print("2. 属性分布统计:")
        dist = get_attribute_distribution(graph)
        for attr, value_counts in dist.items():
            print(f"   {attr}:")
            for value, count in value_counts.items():
                print(f"     - {value}: {count}")
        
        print()
        
        # 3. 关系模式识别示例
        print("3. 关系模式识别 (出现次数 >= 2):")
        patterns = find_relation_patterns(graph, min_occurrences=2)
        
        print("   属性-关系模式:")
        if patterns['attribute_relation_patterns']:
            for pattern_info in patterns['attribute_relation_patterns'][:3]:  # 只显示前3个
                pattern = pattern_info['pattern']
                count = pattern_info['count']
                print(f"     [{count}次] {pattern[0]} -> {pattern[1]} -> {pattern[2]}")
        else:
            print("     无高频模式")
        
        print()
        
        print("   关系序列模式:")
        if patterns['relation_sequence_patterns']:
            for pattern_info in patterns['relation_sequence_patterns']:
                pattern = pattern_info['pattern']
                count = pattern_info['count']
                print(f"     [{count}次] 节点同时有边: {', '.join(pattern)}")
        else:
            print("     无高频模式")
            
    finally:
        os.remove(kg_path)


def example_inference_engine():
    """推理引擎示例"""
    print("\n" + "=" * 70)
    print("推理引擎示例")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        kg_path = f.name
    try:
        # 创建知识图谱
        graph = KnowledgeGraph(kg_path)
        
        # 添加节点
        graph.add_node("Alice", {"type": "person", "age": 30})
        graph.add_node("Bob", {"type": "person", "age": 35})
        graph.add_node("Charlie", {"type": "animal", "species": "dog"})
        graph.add_node("Python", {"type": "language", "paradigm": "multi-paradigm"})
        graph.add_node("MachineLearning", {"type": "field"})
        
        # 添加关系
        graph.add_edge("Alice", "Bob", "friend", 0.9)
        graph.add_edge("Alice", "Python", "uses", 0.8)
        graph.add_edge("Bob", "MachineLearning", "works_in", 0.9)
        
        # 创建推理引擎
        engine = InferenceEngine()
        
        # 规则1：人是人类
        rule1 = create_attribute_rule(
            name="person_is_human",
            condition_attr="type",
            condition_value="person",
            action_attr="is_human",
            action_value=True
        )
        engine.add_rule(rule1)
        
        # 规则2：使用编程语言的是开发者
        rule2 = Rule(
            name="programmer_detection",
            conditions=[
                {"type": "has_attribute", "attribute": "type", "value": "person"},
                {"type": "has_relation", "relation": "uses"}
            ],
            actions=[
                {"type": "set_attribute", "attribute": "is_programmer", "value": True}
            ]
        )
        engine.add_rule(rule2)
        
        # 规则3：有朋友关系的是社交活跃
        rule3 = Rule(
            name="social_active",
            conditions=[
                {"type": "has_relation", "relation": "friend"}
            ],
            actions=[
                {"type": "set_attribute", "attribute": "social_active", "value": True}
            ]
        )
        engine.add_rule(rule3)
        
        # 对所有节点进行推理
        print("对所有节点进行推理...")
        all_results = engine.infer_all(graph)
        
        print(f"\n推理影响了 {len(all_results)} 个节点")
        for node_name, results in all_results.items():
            print(f"\n  {node_name}:")
            for result in results:
                print(f"    - 规则: {result['rule']} (置信度: {result['confidence']})")
                for action in result['actions']:
                    print(f"      动作: {action['action']}")
                    if 'attribute' in action:
                        print(f"        属性: {action['attribute']} = {action['value']}")
        
        # 查看推理后的节点属性
        print("\n推理后节点属性:")
        for node_name in graph.nodes:
            node = graph.get_node(node_name)
            print(f"\n  {node_name}:")
            for key, value in node.attributes.items():
                print(f"    {key}: {value}")
        
    finally:
        os.remove(kg_path)


def example_subgraph_matching():
    """子图匹配示例"""
    print("\n" + "=" * 70)
    print("子图匹配示例")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        kg_path = f.name
    try:
        # 创建知识图谱
        graph = KnowledgeGraph(kg_path)
        
        # 添加节点
        graph.add_node("Alice", {"type": "person", "role": "developer"})
        graph.add_node("Bob", {"type": "person", "role": "developer"})
        graph.add_node("Charlie", {"type": "person", "role": "designer"})
        graph.add_node("Python", {"type": "language", "level": "high"})
        graph.add_node("JavaScript", {"type": "language", "level": "high"})
        graph.add_node("C", {"type": "language", "level": "low"})
        graph.add_node("React", {"type": "framework", "language": "JavaScript"})
        graph.add_node("Django", {"type": "framework", "language": "Python"})
        graph.add_node("ProjectX", {"type": "project", "status": "active"})
        graph.add_node("ProjectY", {"type": "project", "status": "active"})
        
        # 添加边
        graph.add_edge("Alice", "Python", "uses", 0.9)
        graph.add_edge("Alice", "Django", "uses", 0.8)
        graph.add_edge("Alice", "ProjectX", "works_on", 0.85)
        graph.add_edge("Bob", "JavaScript", "uses", 0.9)
        graph.add_edge("Bob", "React", "uses", 0.85)
        graph.add_edge("Bob", "ProjectY", "works_on", 0.9)
        graph.add_edge("Charlie", "JavaScript", "uses", 0.7)
        graph.add_edge("Charlie", "ProjectX", "works_on", 0.75)
        graph.add_edge("Python", "Django", "used_for", 0.95)
        graph.add_edge("JavaScript", "React", "used_for", 0.95)
        
        print(f"知识图谱中的节点数量: {len(graph.nodes)}")
        print(f"知识图谱中的边数量: {len(graph.edges)}")
        print()
        
        # 1. 按节点属性模式查找:
        print("1. 按节点属性模式查找:")
        print("   查找所有 role='developer' 的人员:")
        dev_pattern = {"type": "person", "role": "developer"}
        devs = find_nodes_by_pattern(graph, dev_pattern)
        for name in devs:
            print(f"   - {name}")
        
        print()
        print("   查找所有 type='language' 的编程语言:")
        lang_pattern = {"type": "language"}
        langs = find_nodes_by_pattern(graph, lang_pattern)
        for name in langs:
            print(f"   - {name}")
        
        print()
        
        # 2. 按关系类型查找邻居:
        print("2. 按关系类型查找邻居:")
        print("   Alice 使用的技术:")
        alice_uses = find_neighbors_by_relation(graph, "Alice", "uses", return_weights=True)
        for neighbor, weight in alice_uses:
            print(f"   - {neighbor} (权重: {weight})")
        
        print()
        print("   参与 ProjectX 的人员:")
        projectx_workers = find_neighbors_by_relation(graph, "ProjectX", "works_on", direction="incoming", return_weights=True)
        for neighbor, weight in projectx_workers:
            print(f"   - {neighbor} (权重: {weight})")
        
        print()
        
        # 3. 完整子图匹配
        print("3. 完整子图匹配:")
        print("   模式：开发者 使用 语言 和 框架，且语言用于框架")
        
        pattern = {
            "nodes": [
                {"name": "dev", "attributes": {"type": "person", "role": "developer"}},
                {"name": "lang", "attributes": {"type": "language"}},
                {"name": "fw", "attributes": {"type": "framework"}}
            ],
            "edges": [
                {"source": "dev", "target": "lang", "relation": "uses"},
                {"source": "dev", "target": "fw", "relation": "uses"},
                {"source": "lang", "target": "fw", "relation": "used_for"}
            ]
        }
        
        matches = find_subgraph_by_pattern(graph, pattern)
        print(f"   找到 {len(matches)} 个匹配:")
        for i, match in enumerate(matches, 1):
            print(f"   匹配 {i}:")
            for pattern_node, real_node in match["node_mapping"].items():
                print(f"     {pattern_node} -> {real_node}")
            print(f"     匹配的边: {len(match['matched_edges'])} 条")
        
    finally:
        os.remove(kg_path)


def main():
    print("\n" + "=" * 70)
    print("    第一原理轻量级永动机知识图谱智能体")
    print("    相似度计算工具使用示例")
    print("=" * 70 + "\n")
    
    example_cosine_similarity()
    example_jaccard_similarity()
    example_find_similar_nodes()
    example_graph_statistics()
    example_pattern_recognition()
    example_inference_engine()
    example_subgraph_matching()
    
    print("\n" + "=" * 70)
    print("示例执行完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
