import sys
import tempfile
import os
import unittest

sys.path.insert(0, '/workspace')

from core.knowledge_graph import KnowledgeGraph, ConcurrentKnowledgeGraph


class TestStorageOptimization(unittest.TestCase):
    """
    阶段 14 存储优化功能测试
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
    
    def test_change_tracking_node_add(self):
        """测试节点添加的变更追踪"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 初始状态
        self.assertEqual(kg.get_version(), 0)
        self.assertEqual(kg.get_changes_since_last_save(), 0)
        self.assertFalse(kg.has_changes())
        
        # 添加节点
        kg.add_node("test_node")
        
        # 验证变更
        self.assertEqual(kg.get_version(), 1)
        self.assertEqual(kg.get_changes_since_last_save(), 1)
        self.assertTrue(kg.has_changes())
        
        # 验证变更日志
        changelog = kg.get_changelog()
        self.assertEqual(len(changelog), 1)
        self.assertEqual(changelog[0]["type"], "node_add")
        self.assertEqual(changelog[0]["data"]["node_name"], "test_node")
    
    def test_change_tracking_node_delete(self):
        """测试节点删除的变更追踪"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 添加并删除节点
        kg.add_node("test_node")
        kg.delete_node("test_node")
        
        # 验证变更
        self.assertEqual(kg.get_changes_since_last_save(), 2)
        changelog = kg.get_changelog()
        self.assertEqual(len(changelog), 2)
        
        # 验证最后一个变更是删除
        self.assertEqual(changelog[-1]["type"], "node_delete")
    
    def test_change_tracking_edge_add(self):
        """测试边添加的变更追踪"""
        kg = KnowledgeGraph(self.kg_path)
        
        kg.add_edge("A", "B", "related", 0.8)
        
        # 验证变更（两个节点 + 一个边）
        self.assertEqual(kg.get_changes_since_last_save(), 3)
        changelog = kg.get_changelog()
        
        # 检查是否有边添加的变更
        edge_added = any(change["type"] == "edge_add" for change in changelog)
        self.assertTrue(edge_added)
    
    def test_save_resets_change_counter(self):
        """测试保存会重置变更计数"""
        kg = KnowledgeGraph(self.kg_path)
        
        kg.add_node("test_node")
        self.assertEqual(kg.get_changes_since_last_save(), 1)
        self.assertTrue(kg.has_changes())
        
        # 保存后变更计数应该重置
        kg.save()
        self.assertEqual(kg.get_changes_since_last_save(), 0)
        self.assertFalse(kg.has_changes())
    
    def test_changelog_limit(self):
        """测试变更历史限制"""
        kg = KnowledgeGraph(self.kg_path)
        kg._max_changelog_size = 10
        
        # 添加 15 个节点
        for i in range(15):
            kg.add_node(f"node_{i}")
        
        # 变更历史应该只包含最后 10 个
        changelog = kg.get_changelog()
        self.assertEqual(len(changelog), 10)
    
    def test_load_preserves_version(self):
        """测试加载时保留版本号"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 添加一些内容并保存
        for i in range(5):
            kg.add_node(f"node_{i}")
        
        kg.save()
        version_after_save = kg.get_version()
        
        # 创建新实例并加载
        kg2 = KnowledgeGraph(self.kg_path)
        
        self.assertEqual(kg2.get_version(), version_after_save)
    
    def test_concurrent_graph_change_tracking(self):
        """测试并发安全图的变更追踪"""
        kg = ConcurrentKnowledgeGraph(self.kg_path)
        
        kg.add_node("test_node")
        
        self.assertEqual(kg.get_version(), 1)
        self.assertEqual(kg.get_changes_since_last_save(), 1)
        
        changelog = kg.get_changelog()
        self.assertEqual(len(changelog), 1)
    
    def test_changelog_query_limit(self):
        """测试变更日志查询的 limit 参数"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 添加多个节点
        for i in range(10):
            kg.add_node(f"node_{i}")
        
        # 只取最新的 5 个变更
        changelog = kg.get_changelog(limit=5)
        self.assertEqual(len(changelog), 5)
        
        # 验证是最新的 5 个 (版本号从 0 开始)
        versions = [change["version"] for change in changelog]
        self.assertEqual(versions, [5, 6, 7, 8, 9])
    
    def test_changelog_since_version(self):
        """测试变更日志查询的 since_version 参数"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 添加多个节点
        for i in range(5):
            kg.add_node(f"node_{i}")
        
        # 只获取版本 3 之后的变更
        changelog = kg.get_changelog(since_version=3)
        
        self.assertTrue(all(change["version"] >= 3 for change in changelog))


if __name__ == '__main__':
    unittest.main()
