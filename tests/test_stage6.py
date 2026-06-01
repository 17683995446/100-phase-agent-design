import sys
sys.path.insert(0, '/workspace')

import unittest
import tempfile
import os
import json
import time
from core import EternalSelfAgent, KnowledgeGraph, TaskQueue


class TestResilience(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_kg = os.path.join(self.temp_dir, "kg.json")
        self.temp_log = os.path.join(self.temp_dir, "agent.log")
        self.temp_config = os.path.join(self.temp_dir, "config.json")

    def tearDown(self):
        try:
            if os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except:
            pass

    def test_backup_and_restore(self):
        kg = KnowledgeGraph(self.temp_kg)
        kg.add_node("test_node_1")
        kg.add_edge("test_node_1", "test_node_2", "rel", 0.8)
        kg.save()
        
        self.assertTrue(os.path.exists(f"{self.temp_kg}.backup"))
        
        kg2 = KnowledgeGraph(self.temp_kg)
        self.assertTrue(kg2.has_node("test_node_1"))

    def test_corrupted_json_recovery(self):
        kg = KnowledgeGraph(self.temp_kg)
        kg.add_node("test_node_1")
        kg.save()
        
        with open(self.temp_kg, "w") as f:
            f.write("This is not valid JSON{{{{")
        
        kg2 = KnowledgeGraph(self.temp_kg)
        self.assertTrue(os.path.exists(f"{self.temp_kg}.backup"))

    def test_atomic_save(self):
        kg = KnowledgeGraph(self.temp_kg)
        kg.add_node("test_node")
        kg.save()
        
        self.assertFalse(os.path.exists(f"{self.temp_kg}.tmp"))

    def test_memory_cleanup_trigger(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        
        for i in range(15000):
            agent.task_queue.processed_history.add(f"task_{i}")
        
        self.assertGreater(agent.task_queue.get_history_size(), 10000)
        
        agent._force_memory_cleanup()
        
        self.assertLess(agent.task_queue.get_history_size(), 10000)
        agent.shutdown()

    def test_memory_usage_monitoring(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        
        memory_usage = agent._get_memory_usage()
        self.assertIsInstance(memory_usage, float)
        
        status = agent.get_system_status()
        self.assertIn("memory_usage", status)
        self.assertIsInstance(status["memory_usage"], float)
        agent.shutdown()

    def test_exception_type_classification(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        
        try:
            raise MemoryError("Test memory error")
        except MemoryError:
            agent.self_repair("MemoryError")
        
        try:
            raise json.JSONDecodeError("Test JSON error", "doc", 0)
        except json.JSONDecodeError:
            agent.self_repair("JSONDecodeError")
        
        agent.shutdown()
        self.assertTrue(os.path.exists(self.temp_log))

    def test_task_queue_history_limit(self):
        queue = TaskQueue(max_size=10, history_limit=20)
        
        for i in range(50):
            queue.add(f"task_{i}")
            queue.pop()
        
        self.assertLessEqual(len(queue.processed_history), 20)

    def test_disk_space_check(self):
        kg = KnowledgeGraph(self.temp_kg)
        has_space = kg._check_disk_space()
        self.assertIsInstance(has_space, bool)

    def test_graceful_shutdown(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        
        agent.knowledge_graph.add_node("important_data")
        agent.shutdown()
        
        kg2 = KnowledgeGraph(self.temp_kg)
        self.assertTrue(kg2.has_node("important_data"))

    def test_deep_reflection(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        
        agent.knowledge_graph.add_node("important_node")
        agent.knowledge_graph.add_edge("important_node", "target", "rel", 0.9)
        
        agent.perform_deep_reflection()
        
        edges = agent.knowledge_graph.get_edges_from_node("important_node")
        self.assertGreater(len(edges), 1)
        
        agent.shutdown()

    def test_system_status_reporting(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        
        status = agent.get_system_status()
        
        expected_keys = [
            "run_counter", "queue_size", "node_count", "edge_count",
            "system_alive", "uptime", "processed_history_size", "memory_usage"
        ]
        
        for key in expected_keys:
            self.assertIn(key, status)
        
        agent.shutdown()


if __name__ == '__main__':
    unittest.main()