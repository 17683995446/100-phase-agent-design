import sys
sys.path.insert(0, '/workspace')

import unittest
import tempfile
import os
import json
import time
from core import EternalSelfAgent, KnowledgeGraph, ConfigManager, TaskQueue


class TestEighthStage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        self.kg_path = os.path.join(self.temp_dir, "test_kg.json")
        self.log_path = os.path.join(self.temp_dir, "test_log.txt")

    def tearDown(self):
        try:
            if os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    def test_config_manager_initialization(self):
        """测试配置管理器初始化"""
        config_manager = ConfigManager(self.config_path)
        
        # 检查默认配置是否生成
        self.assertTrue(os.path.exists(self.config_path))
        
        # 检查默认配置值
        default_config = ConfigManager.get_default_config()
        self.assertEqual(config_manager.get("loop_delay"), default_config["loop_delay"])
        self.assertEqual(config_manager.get("evolve_step"), default_config["evolve_step"])
        self.assertEqual(config_manager.get("task_queue_max"), default_config["task_queue_max"])

    def test_config_manager_set_and_get(self):
        """测试配置设置和获取"""
        config_manager = ConfigManager(self.config_path)
        
        # 设置新值
        success = config_manager.set("loop_delay", 0.5)
        self.assertTrue(success)
        
        # 获取并验证
        self.assertEqual(config_manager.get("loop_delay"), 0.5)
        
        # 验证文件是否保存
        with open(self.config_path, "r") as f:
            saved_config = json.load(f)
        self.assertEqual(saved_config["loop_delay"], 0.5)

    def test_config_manager_validate(self):
        """测试配置验证"""
        config_manager = ConfigManager(self.config_path)
        
        # 验证有效配置
        self.assertTrue(config_manager.validate_config())

    def test_agent_config_integration(self):
        """测试智能体与配置管理器的集成"""
        # 创建测试配置
        test_config = {
            "version": "1.0.0",
            "loop_delay": 0.2,
            "evolve_step": 100,
            "task_queue_max": 300,
            "weight_threshold": 0.15,
            "kg_save_path": self.kg_path,
            "log_path": self.log_path
        }
        
        with open(self.config_path, "w") as f:
            json.dump(test_config, f)
        
        # 创建智能体
        agent = EternalSelfAgent(self.config_path)
        
        # 验证配置是否正确加载
        self.assertEqual(agent.loop_delay, 0.2)
        self.assertEqual(agent.evolve_step, 100)
        self.assertEqual(agent.task_queue.max_size, 300)
        
        agent.shutdown()

    def test_agent_runtime_config_update(self):
        """测试运行时配置更新"""
        agent = EternalSelfAgent(self.config_path)
        
        # 更新配置
        success = agent.update_config("loop_delay", 0.4)
        self.assertTrue(success)
        
        # 验证更新是否生效
        self.assertEqual(agent.loop_delay, 0.4)
        
        # 验证配置是否保存
        with open(self.config_path, "r") as f:
            saved_config = json.load(f)
        self.assertEqual(saved_config["loop_delay"], 0.4)
        
        agent.shutdown()

    def test_task_queue_max_size_update(self):
        """测试任务队列容量更新"""
        queue = TaskQueue(max_size=100)
        
        # 更新容量
        queue.max_size = 200
        self.assertEqual(queue.max_size, 200)
        
        # 验证容量更小的情况
        queue.max_size = 50
        self.assertEqual(queue.max_size, 50)
        
        # 验证无效值
        with self.assertRaises(ValueError):
            queue.max_size = 0

    def test_knowledge_graph_backup_restore(self):
        """测试知识图谱备份和恢复"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 添加测试数据
        kg.add_node("test_node")
        kg.add_edge("test_node", "target_node", "rel", 0.8)
        kg.save()
        
        # 验证备份文件存在
        backup_path = f"{self.kg_path}.backup"
        self.assertTrue(os.path.exists(backup_path))

    def test_knowledge_graph_file_integrity(self):
        """测试知识图谱文件完整性验证"""
        kg = KnowledgeGraph(self.kg_path)
        kg.add_node("test")
        kg.save()
        
        # 验证文件完整性
        self.assertTrue(kg._validate_file_integrity(self.kg_path))
        
        # 破坏文件
        with open(self.kg_path, "w") as f:
            f.write("invalid json data")
        
        # 验证完整性检查失败
        self.assertFalse(kg._validate_file_integrity(self.kg_path))

    def test_knowledge_graph_stats(self):
        """测试知识图谱统计信息"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 添加数据
        for i in range(5):
            kg.add_node(f"node_{i}")
        kg.add_edge("node_0", "node_1", "rel", 0.5)
        kg.add_edge("node_1", "node_2", "rel", 0.6)
        
        kg.save()
        
        # 获取统计信息
        stats = kg.get_stats()
        
        self.assertEqual(stats["node_count"], 5)
        self.assertEqual(stats["edge_count"], 2)
        self.assertGreater(stats["save_count"], 0)
        self.assertGreater(stats["load_count"], 0)

    def test_full_state_save_and_restore(self):
        """测试完整状态保存和恢复"""
        # 第一个智能体
        agent1 = EternalSelfAgent(self.config_path)
        agent1.knowledge_graph.add_node("persistent_node")
        agent1.knowledge_graph.add_edge("persistent_node", "related_node", "rel", 0.9)
        agent1.save_full_state()
        agent1.shutdown()
        
        # 第二个智能体
        agent2 = EternalSelfAgent(self.config_path)
        restore_success = agent2.restore_state()
        
        # 验证恢复成功
        self.assertTrue(restore_success)
        self.assertTrue(agent2.knowledge_graph.has_node("persistent_node"))
        
        agent2.shutdown()

    def test_knowledge_graph_version_metadata(self):
        """测试知识图谱版本和元数据"""
        kg = KnowledgeGraph(self.kg_path)
        kg.add_node("test")
        kg.save()
        
        # 读取文件并验证版本
        with open(self.kg_path, "r") as f:
            data = json.load(f)
        
        self.assertIn("version", data)
        self.assertIn("timestamp", data)
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["node_count"], 1)
        self.assertEqual(data["metadata"]["edge_count"], 0)


if __name__ == '__main__':
    unittest.main()