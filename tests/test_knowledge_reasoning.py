import sys
import tempfile
import os
import unittest

sys.path.insert(0, '/workspace')

from core.knowledge_graph import KnowledgeGraph, ConcurrentKnowledgeGraph


class TestKnowledgeReasoning(unittest.TestCase):
    """
    知识推理功能测试
    """
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.kg_path = os.path.join(self.temp_dir, "kg_test.json")
    
    def tearDown(self):
        try:
            if os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass
    
    def test_similarity_computation(self):
        """测试相似度计算功能"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 创建测试图
        kg.add_node("A")
        kg.add_node("B")
        kg.add_node("C")
        kg.add_node("D")
        
        # A 和 B 有很多共享邻居
        kg.add_edge("A", "C", "related", 0.8)
        kg.add_edge("B", "C", "related", 0.7)
        kg.add_edge("A", "D", "related", 0.9)
        kg.add_edge("B", "D", "related", 0.6)
        
        # 直接连接 A 和 B
        kg.add_edge("A", "B", "connected", 0.5)
        
        # 计算相似度
        sim = kg.compute_similarity("A", "B")
        self.assertGreater(sim, 0.0)  # 相似度应该大于 0
        self.assertLessEqual(sim, 1.0)  # 相似度应该小于等于 1
        
        # 相同节点的相似度应该是 1
        self.assertEqual(kg.compute_similarity("A", "A"), 1.0)
        
        # 不存在的节点相似度为 0
        self.assertEqual(kg.compute_similarity("A", "non_existent"), 0.0)
    
    def test_find_similar_nodes(self):
        """测试查找相似节点功能"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 创建测试图
        kg.add_node("A")
        kg.add_node("B")
        kg.add_node("C")
        kg.add_node("D")
        kg.add_node("E")
        
        # A 和 B 有共享邻居
        kg.add_edge("A", "C", "related", 0.8)
        kg.add_edge("B", "C", "related", 0.7)
        
        # A 和 D 也有共享邻居
        kg.add_edge("A", "E", "related", 0.9)
        kg.add_edge("D", "E", "related", 0.6)
        
        # 找到与 A 相似的节点
        similar = kg.find_similar_nodes("A", top_k=5)
        
        # 应该返回相似节点列表
        self.assertIsInstance(similar, list)
        self.assertGreater(len(similar), 0)
        
        # 检查格式
        for node, score in similar:
            self.assertIsInstance(node, str)
            self.assertIsInstance(score, float)
    
    def test_node_importance(self):
        """测试节点重要性评估"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 创建测试图
        kg.add_node("A")  # 中心节点，很多连接
        kg.add_node("B")
        kg.add_node("C")
        kg.add_node("D")
        kg.add_node("E")
        
        # A 连接到很多节点
        kg.add_edge("A", "B", "link", 0.8)
        kg.add_edge("A", "C", "link", 0.7)
        kg.add_edge("A", "D", "link", 0.6)
        kg.add_edge("B", "E", "link", 0.5)  # B 只有一个连接
        
        # 计算节点重要性
        importance_a = kg.compute_node_importance("A")
        importance_b = kg.compute_node_importance("B")
        importance_e = kg.compute_node_importance("E")
        
        # A 的重要性应该比 B 和 E 高
        self.assertGreater(importance_a, importance_b)
        self.assertGreater(importance_a, importance_e)
        
        # 不存在的节点重要性为 0
        self.assertEqual(kg.compute_node_importance("non_existent"), 0.0)
    
    def test_most_important_nodes(self):
        """测试获取最重要节点"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 创建测试图
        kg.add_node("A")
        kg.add_node("B")
        kg.add_node("C")
        kg.add_node("D")
        
        kg.add_edge("A", "B", "link", 0.8)
        kg.add_edge("A", "C", "link", 0.7)
        kg.add_edge("B", "C", "link", 0.6)
        kg.add_edge("C", "D", "link", 0.5)
        
        # 获取最重要的节点
        important = kg.get_most_important_nodes(top_k=3)
        
        # 应该返回排序列表
        self.assertIsInstance(important, list)
        self.assertEqual(len(important), 3)
        
        # 检查重要性是否按降序排列
        for i in range(len(important) - 1):
            self.assertGreaterEqual(important[i][1], important[i + 1][1])
    
    def test_path_finding(self):
        """测试路径查找功能"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 创建链式连接
        kg.add_node("A")
        kg.add_node("B")
        kg.add_node("C")
        kg.add_node("D")
        
        kg.add_edge("A", "B", "path", 0.8)
        kg.add_edge("B", "C", "path", 0.7)
        kg.add_edge("C", "D", "path", 0.6)
        kg.add_edge("A", "D", "direct", 0.5)  # 直接路径
        
        # 查找路径
        paths = kg.find_paths("A", "D", max_depth=3)
        
        # 应该找到两条路径：A->B->C->D 和 A->D
        self.assertGreater(len(paths), 0)
        
        # 检查路径是否有效
        found_direct_path = False
        found_chain_path = False
        
        for path in paths:
            if path == ["A", "D"]:
                found_direct_path = True
            if path == ["A", "B", "C", "D"]:
                found_chain_path = True
        
        # 至少应该找到其中一条
        self.assertTrue(found_direct_path or found_chain_path)
    
    def test_path_weight_aggregation(self):
        """测试路径权重聚合"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 创建测试路径
        kg.add_node("A")
        kg.add_node("B")
        kg.add_node("C")
        
        kg.add_edge("A", "B", "link", 0.8)
        kg.add_edge("B", "C", "link", 0.5)
        
        # 计算路径权重
        path = ["A", "B", "C"]
        weight = kg.aggregate_path_weight(path)
        
        # 应该是 0.8 * 0.5 = 0.4
        self.assertAlmostEqual(weight, 0.4)
        
        # 单节点路径权重为 0
        self.assertEqual(kg.aggregate_path_weight(["A"]), 0.0)
        
        # 无效路径权重为 0
        self.assertEqual(kg.aggregate_path_weight(["A", "NonExistent"]), 0.0)
    
    def test_empty_graph_operations(self):
        """测试空图上的操作"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 空图上的相似度计算
        self.assertEqual(kg.compute_similarity("A", "B"), 0.0)
        
        # 空图上的相似节点查找
        self.assertEqual(kg.find_similar_nodes("A"), [])
        
        # 空图上的重要性计算
        self.assertEqual(kg.compute_node_importance("A"), 0.0)
        
        # 空图上的重要节点获取
        self.assertEqual(kg.get_most_important_nodes(), [])
        
        # 空图上的路径查找
        self.assertEqual(kg.find_paths("A", "B"), [])
    
    def test_concurrent_knowledge_reasoning(self):
        """测试并发安全的知识推理"""
        kg = ConcurrentKnowledgeGraph(self.kg_path)
        
        # 创建测试图
        kg.add_node("A")
        kg.add_node("B")
        kg.add_node("C")
        
        kg.add_edge("A", "B", "link", 0.8)
        kg.add_edge("B", "C", "link", 0.7)
        
        # 测试各种推理功能
        sim = kg.compute_similarity("A", "B")
        self.assertIsInstance(sim, float)
        
        similar_nodes = kg.find_similar_nodes("A")
        self.assertIsInstance(similar_nodes, list)
        
        importance = kg.compute_node_importance("A")
        self.assertIsInstance(importance, float)
        
        important_nodes = kg.get_most_important_nodes()
        self.assertIsInstance(important_nodes, list)
        
        paths = kg.find_paths("A", "C")
        self.assertIsInstance(paths, list)
        
        if paths:
            weight = kg.aggregate_path_weight(paths[0])
            self.assertIsInstance(weight, float)


if __name__ == '__main__':
    unittest.main()
