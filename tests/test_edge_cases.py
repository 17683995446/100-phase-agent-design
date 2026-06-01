import sys
sys.path.insert(0, '/workspace')

import unittest
import tempfile
import os
import time
from core import EternalSelfAgent, KnowledgeGraph, TaskQueue, Node, Edge


class TestEdgeCases(unittest.TestCase):
    """
    边界情况和极端条件测试
    """
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "config_test.json")
        self.kg_path = os.path.join(self.temp_dir, "kg_test.json")
    
    def tearDown(self):
        try:
            if os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass
    
    def test_empty_strings(self):
        """测试空字符串处理"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 空节点名
        kg.add_node("")
        self.assertTrue(kg.has_node(""))
        
        # 空关系
        kg.add_edge("", "", "", 0.5)
        edges = kg.get_edges_from_node("")
        self.assertGreater(len(edges), 0)
    
    def test_extreme_weights(self):
        """测试极端权重值"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 有效边界值
        kg.add_node("n1")
        kg.add_node("n2")
        
        edge1 = kg.add_edge("n1", "n2", "test", 0.0)
        self.assertEqual(edge1.weight, 0.0)
        
        edge2 = kg.add_edge("n1", "n2", "test2", 1.0)
        self.assertEqual(edge2.weight, 1.0)
        
        # 无效权重应抛出异常
        with self.assertRaises(ValueError):
            kg.add_edge("n1", "n2", "test3", -0.1)
        
        with self.assertRaises(ValueError):
            kg.add_edge("n1", "n2", "test4", 1.1)
    
    def test_massive_task_queue_operations(self):
        """测试大规模任务队列操作"""
        queue = TaskQueue(max_size=100000)
        
        # 添加大量任务
        added = 0
        for i in range(50000):
            if queue.add(f"task_{i}"):
                added += 1
        
        self.assertEqual(queue.size(), min(50000, queue.max_size))
        
        # 快速弹出
        popped = 0
        while not queue.is_empty():
            task = queue.pop()
            self.assertIsNotNone(task)
            popped += 1
        
        self.assertEqual(popped, added)
    
    def test_rapid_save_load_cycles(self):
        """测试快速保存加载循环"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 快速重复保存
        for i in range(100):
            kg.add_node(f"quick_node_{i}")
            kg.add_edge(f"quick_node_{i}", f"quick_node_{(i+1)%100}", "link", 0.5)
            if i % 10 == 0:
                kg.save()
        
        # 最后再保存一次，确保所有数据都被保存
        kg.save()
        
        # 重新加载
        kg2 = KnowledgeGraph(self.kg_path)
        self.assertEqual(kg2.get_node_count(), 100)
    
    def test_duplicate_operations(self):
        """测试重复操作"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 重复添加相同节点
        for i in range(100):
            kg.add_node("dup_node")
        
        self.assertEqual(kg.get_node_count(), 1)
        
        # 重复添加相同边
        for i in range(100):
            kg.add_edge("dup_node", "dup_node2", "dup_rel", 0.5)
        
        edges = kg.get_edges_from_node("dup_node")
        self.assertEqual(len(edges), 1)
    
    def test_special_characters(self):
        """测试特殊字符处理"""
        kg = KnowledgeGraph(self.kg_path)
        
        special_chars = "!@#$%^&*()_+-=[]{}|;:\"'<>,.?/~` \n\t\r"
        special_node = f"node_{special_chars}"
        
        kg.add_node(special_node)
        self.assertTrue(kg.has_node(special_node))
        
        # 保存和重新加载
        kg.save()
        kg2 = KnowledgeGraph(self.kg_path)
        self.assertTrue(kg2.has_node(special_node))
    
    def test_deep_knowledge_evolution(self):
        """测试深度知识演化"""
        agent = EternalSelfAgent(self.config_path, kg_save_path=self.kg_path, loop_delay=0)
        
        # 添加初始知识
        agent.knowledge_graph.add_node("root")
        for i in range(100):
            agent.knowledge_graph.add_edge("root", f"node_{i}", "link", random.random())
        
        # 执行多次知识演化
        for i in range(200):
            agent.health_check()
            if i % 50 == 0:
                agent.perform_deep_reflection()
                agent.perform_knowledge_synthesis()
        
        self.assertTrue(agent.knowledge_graph.get_node_count() > 100)
        agent.shutdown()
    
    def test_concurrent_like_operations(self):
        """模拟并发式操作"""
        kg = KnowledgeGraph(self.kg_path)
        
        # 混合读写操作
        for i in range(500):
            kg.add_node(f"mixed_{i}")
            if i % 2 == 0:
                kg.add_edge(f"mixed_{i}", f"mixed_{(i+1)%500}", "rel", 0.5)
            if i % 3 == 0:
                edges = kg.get_edges_from_node(f"mixed_{i}")
            if i % 5 == 0:
                kg.save()
        
        self.assertEqual(kg.get_node_count(), 500)
    
    def test_task_handler_extremes(self):
        """测试任务处理器的极端情况"""
        agent = EternalSelfAgent(self.config_path, kg_save_path=self.kg_path, loop_delay=0)
        
        handled = []
        
        def error_handler(task, agent_ref):
            raise Exception(f"Intentional error for {task}")
        
        def normal_handler(task, agent_ref):
            handled.append(task)
        
        # 注册多个处理器
        agent.register_task_handler("error", error_handler)
        agent.register_task_handler("normal", normal_handler)
        
        # 混合任务执行
        agent.add_manual_task("normal:task1")
        agent.add_manual_task("error:task2")
        agent.add_manual_task("normal:task3")
        
        # 执行任务（系统应能从错误中恢复）
        for _ in range(5):
            task = agent.get_current_task()
            if task:
                try:
                    agent.execute_task(task)
                except Exception:
                    pass
        
        self.assertIn("normal:task1", handled)
        agent.shutdown()


import random


class TestPerformanceScalability(unittest.TestCase):
    """
    性能和可扩展性测试
    """
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "config_perf.json")
        self.kg_path = os.path.join(self.temp_dir, "kg_perf.json")
    
    def tearDown(self):
        try:
            if os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass
    
    def test_graph_query_performance_scaling(self):
        """测试图谱查询性能随规模的变化"""
        kg = KnowledgeGraph(self.kg_path)
        
        sizes = [100, 500, 1000, 2000]
        
        for size in sizes:
            # 创建规模为 size 的图
            for i in range(size):
                kg.add_node(f"perf_node_{i}")
            
            for i in range(size):
                kg.add_edge(
                    f"perf_node_{i}",
                    f"perf_node_{(i + 1) % size}",
                    "perf_link",
                    0.5
                )
            
            # 测试查询时间
            start = time.time()
            for _ in range(100):
                node = f"perf_node_{random.randint(0, size - 1)}"
                kg.get_edges_from_node(node)
            query_time = time.time() - start
            
            # 确保查询时间增长是合理的（线性增长）
            self.assertLess(query_time, 5.0,
                          f"查询时间过长: {query_time}s 对于 size={size}")
            
            kg.clear()


if __name__ == "__main__":
    unittest.main()
