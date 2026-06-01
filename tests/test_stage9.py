import sys
sys.path.insert(0, '/workspace')

import unittest
import tempfile
import os
import json
import time
import shutil
from core import EternalSelfAgent, KnowledgeGraph, ConfigManager


class TestIntegration(unittest.TestCase):
    """第9阶段集成测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "config.json")
        self.kg_path = os.path.join(self.temp_dir, "kg.json")
        self.log_path = os.path.join(self.temp_dir, "agent.log")
    
    def tearDown(self):
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass
    
    def test_cold_start(self):
        """测试场景1：冷启动 - 删除所有持久化文件后启动"""
        # 确保没有持久化文件
        if os.path.exists(self.kg_path):
            os.remove(self.kg_path)
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        
        # 启动
        agent = EternalSelfAgent(
            config_path=self.config_path,
            kg_save_path=self.kg_path
        )
        
        # 检查是否正常启动
        self.assertTrue(agent.system_alive)
        self.assertEqual(agent.run_counter, 0)
        
        agent.shutdown()
    
    def test_hot_recovery(self):
        """测试场景2：热恢复 - 正常运行后重启"""
        # 第一次运行
        agent1 = EternalSelfAgent(
            config_path=self.config_path,
            kg_save_path=self.kg_path
        )
        
        # 添加一些数据
        agent1.knowledge_graph.add_node("node1")
        agent1.knowledge_graph.add_node("node2")
        agent1.knowledge_graph.add_edge("node1", "node2", "rel1", 0.8)
        agent1.execute_task("test_task1")
        agent1.execute_task("test_task2")
        agent1.save_full_state()
        
        # 保存状态，用于比较
        node_count1 = agent1.knowledge_graph.get_node_count()
        edge_count1 = agent1.knowledge_graph.get_edge_count()
        agent1.shutdown()
        
        # 重新启动
        agent2 = EternalSelfAgent(
            config_path=self.config_path,
            kg_save_path=self.kg_path
        )
        restore_success = agent2.restore_state()
        
        # 验证恢复成功
        self.assertTrue(restore_success)
        self.assertEqual(agent2.knowledge_graph.get_node_count(), node_count1)
        self.assertEqual(agent2.knowledge_graph.get_edge_count(), edge_count1)
        
        agent2.shutdown()
    
    def test_exception_injection_and_recovery(self):
        """测试场景3：异常注入 - 模拟异常并测试恢复"""
        agent = EternalSelfAgent(
            config_path=self.config_path,
            kg_save_path=self.kg_path
        )
        
        # 执行一些任务建立状态
        agent.execute_task("test_task1")
        agent.execute_task("test_task2")
        
        # 保存初始错误计数
        initial_error_count = agent.error_count
        
        # 模拟异常调用（注意：这里我们不真正抛出异常，因为测试会终止）
        # 我们直接调用self_repair来测试
        agent.self_repair("TestException")
        
        # 验证错误计数增加，并且系统仍然存活
        self.assertEqual(agent.error_count, initial_error_count + 1)
        self.assertTrue(agent.system_alive)
        
        agent.shutdown()
    
    def test_high_load_task_queue(self):
        """测试场景4：高负载 - 快速添加大量任务"""
        agent = EternalSelfAgent(
            config_path=self.config_path,
            kg_save_path=self.kg_path,
            task_queue_max=200
        )
        
        # 尝试添加大量任务
        added_count = 0
        for i in range(300):  # 超过容量的任务
            success = agent.task_queue.add(f"task_{i}")
            if success:
                added_count += 1
        
        # 验证队列不超过最大容量
        self.assertLessEqual(agent.task_queue.size(), 200)
        
        agent.shutdown()
    
    def test_system_status_monitoring(self):
        """测试系统监控接口"""
        agent = EternalSelfAgent(
            config_path=self.config_path,
            kg_save_path=self.kg_path
        )
        
        # 执行一些操作
        agent.execute_task("task1")
        agent.execute_task("task2")
        
        # 获取状态
        status = agent.get_system_status()
        
        # 验证所有必要字段存在
        self.assertIn("run_counter", status)
        self.assertIn("queue_size", status)
        self.assertIn("node_count", status)
        self.assertIn("edge_count", status)
        self.assertIn("system_alive", status)
        self.assertIn("uptime", status)
        self.assertIn("tasks_executed", status)
        self.assertIn("error_count", status)
        self.assertIn("avg_task_time", status)
        
        # 验证一些值
        self.assertEqual(status["tasks_executed"], 2)
        
        agent.shutdown()
    
    def test_knowledge_graph_backup(self):
        """测试知识图谱备份机制"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 添加数据
        kg.add_node("test_node1")
        kg.add_edge("test_node1", "test_node2", "rel", 0.5)
        kg.save()
        
        # 验证备份文件存在
        backup_path = f"{self.kg_path}.backup"
        self.assertTrue(os.path.exists(backup_path))
        
        # 验证备份内容
        with open(backup_path, "r") as f:
            backup_data = json.load(f)
        self.assertIn("nodes", backup_data)
        self.assertIn("edges", backup_data)


class TestStress(unittest.TestCase):
    """压力测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "config.json")
    
    def tearDown(self):
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass
    
    def test_many_tasks(self):
        """测试大量任务处理"""
        agent = EternalSelfAgent(config_path=self.config_path, loop_delay=0)
        
        task_count = 500
        start_time = time.time()
        
        for i in range(task_count):
            agent.execute_task(f"stress_task_{i}")
        
        elapsed = time.time() - start_time
        
        # 验证任务执行成功
        self.assertEqual(agent.tasks_executed, task_count)
        self.assertTrue(elapsed < 30)  # 应该在30秒内完成500个任务
        
        agent.shutdown()
    
    def test_large_knowledge_graph(self):
        """测试大型知识图谱"""
        kg_path = os.path.join(self.temp_dir, "large_kg.json")
        kg = KnowledgeGraph(kg_path)
        
        # 添加大量节点和边
        node_count = 200
        edge_count = 300
        
        for i in range(node_count):
            kg.add_node(f"node_{i}")
        
        for i in range(edge_count):
            source = f"node_{i % node_count}"
            target = f"node_{(i+1) % node_count}"
            kg.add_edge(source, target, f"rel_{i}", 0.5)
        
        # 保存和加载
        kg.save()
        
        kg2 = KnowledgeGraph(kg_path)
        self.assertEqual(kg2.get_node_count(), node_count)
        self.assertEqual(kg2.get_edge_count(), edge_count)


if __name__ == "__main__":
    unittest.main()