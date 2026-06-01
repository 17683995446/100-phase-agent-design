import sys
sys.path.insert(0, '/workspace')

import unittest
import tempfile
import os
import time
from core import EternalSelfAgent, KnowledgeGraph, TaskQueue


class TestFifthStageIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_kg = tempfile.mktemp(suffix='.json')
        self.temp_log = tempfile.mktemp(suffix='.txt')
        self.temp_config = tempfile.mktemp(suffix='.json')

    def tearDown(self):
        for f in [self.temp_kg, self.temp_log, self.temp_config]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

    def test_config_loading_and_saving(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        self.assertIsNotNone(agent.config)
        self.assertIn("version", agent.config)
        agent.save_config()
        self.assertTrue(os.path.exists(self.temp_config))
        agent.shutdown()

    def test_startup_recovery(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        agent.knowledge_graph.add_node("test_node")
        agent.knowledge_graph.add_edge("test_node", "target", "rel", 0.8)
        agent.knowledge_graph.save()
        node_count = agent.knowledge_graph.get_node_count()
        edge_count = agent.knowledge_graph.get_edge_count()
        agent.shutdown()
        
        agent2 = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        agent2.restore_state()
        self.assertEqual(agent2.knowledge_graph.get_node_count(), node_count)
        self.assertEqual(agent2.knowledge_graph.get_edge_count(), edge_count)
        agent2.shutdown()

    def test_system_status(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        agent.health_check()
        status = agent.get_system_status()
        self.assertIn("run_counter", status)
        self.assertIn("queue_size", status)
        self.assertIn("node_count", status)
        self.assertIn("edge_count", status)
        self.assertIn("system_alive", status)
        self.assertIn("uptime", status)
        self.assertIn("processed_history_size", status)
        agent.shutdown()

    def test_graceful_shutdown(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        self.assertTrue(agent.system_alive)
        agent.shutdown()
        self.assertFalse(agent.system_alive)

    def test_task_queue_history_cleanup(self):
        queue = TaskQueue(max_size=10, history_limit=20)
        for i in range(50):
            queue.add(f"task_{i}")
            queue.pop()
        self.assertLessEqual(len(queue.processed_history), 20)

    def test_log_generation(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        agent.log_event("TEST", "Test log entry")
        agent.shutdown()
        self.assertTrue(os.path.exists(self.temp_log))
        with open(self.temp_log, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn("TEST", log_content)
        self.assertIn("Test log entry", log_content)

    def test_self_repair_saves_state(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        agent.knowledge_graph.add_node("test_repair_node")
        agent.self_repair()
        agent.shutdown()
        
        agent2 = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        agent2.restore_state()
        self.assertTrue(agent2.knowledge_graph.has_node("test_repair_node"))
        agent2.shutdown()

    def test_task_execution_creates_new_tasks(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        agent.knowledge_graph.add_node("source_task")
        agent.knowledge_graph.add_edge("source_task", "derived_task", "rel", 0.8)
        agent.execute_task("source_task")
        self.assertTrue(len(agent.task_queue.get_all()) > 0)
        agent.shutdown()


if __name__ == '__main__':
    unittest.main()