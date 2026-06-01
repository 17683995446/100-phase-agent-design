import sys
sys.path.insert(0, '/workspace')

import unittest
import time
import tempfile
import os
from core import EternalSelfAgent


class TestEternalSelfAgent(unittest.TestCase):
    def setUp(self):
        self.temp_kg = tempfile.mktemp(suffix='.json')
        self.temp_log = tempfile.mktemp(suffix='.txt')
        self.agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            loop_delay=0.01,
            evolve_step=10
        )

    def tearDown(self):
        self.agent.shutdown()
        if os.path.exists(self.temp_kg):
            os.remove(self.temp_kg)
        if os.path.exists(self.temp_log):
            os.remove(self.temp_log)

    def test_initialization(self):
        self.assertEqual(self.agent.run_counter, 0)
        self.assertTrue(self.agent.system_alive)
        self.assertEqual(self.agent.knowledge_graph.get_node_count(), 0)
        self.assertEqual(self.agent.task_queue.size(), 0)

    def test_health_check_increments_counter(self):
        initial_count = self.agent.run_counter
        self.agent.health_check()
        self.assertEqual(self.agent.run_counter, initial_count + 1)

    def test_get_current_task_returns_none_when_empty(self):
        task = self.agent.get_current_task()
        self.assertIsNone(task)

    def test_get_current_task_returns_task(self):
        self.agent.task_queue.add("test_task")
        task = self.agent.get_current_task()
        self.assertEqual(task, "test_task")

    def test_execute_task_adds_node(self):
        self.agent.execute_task("test_exec_task")
        self.assertTrue(self.agent.knowledge_graph.has_node("test_exec_task"))

    def test_execute_task_creates_derived_edge(self):
        self.agent.execute_task("source_task")
        edges = self.agent.knowledge_graph.get_edges_from_node("source_task")
        self.assertTrue(len(edges) > 0)

    def test_execute_task_adds_iteration_task(self):
        initial_queue_size = self.agent.task_queue.size()
        self.agent.execute_task("task_to_generate_next")
        # 至少应该添加一个任务（迭代任务）
        self.assertGreater(self.agent.task_queue.size(), initial_queue_size)

    def test_log_event_writes_to_file(self):
        self.agent.log_event("TEST", "test_message")
        self.assertTrue(os.path.exists(self.temp_log))
        with open(self.temp_log, 'r') as f:
            content = f.read()
            self.assertIn("TEST", content)
            self.assertIn("test_message", content)

    def test_repr(self):
        repr_str = repr(self.agent)
        self.assertIn("EternalSelfAgent", repr_str)

    def test_shutdown_stops_loop(self):
        self.agent.shutdown()
        self.assertFalse(self.agent.system_alive)

    def test_derive_tasks_from_existing_knowledge(self):
        self.agent.knowledge_graph.add_node("existing_node")
        self.agent.knowledge_graph.add_edge("existing_node", "target_node", "rel", 0.8)
        derive_tasks = self.agent.knowledge_graph.derive_new_tasks("existing_node")
        self.assertGreater(len(derive_tasks), 0)

    def test_task_chain_execution(self):
        self.agent.task_queue.add("task_1")
        
        # 执行任务1
        task = self.agent.get_current_task()
        self.agent.execute_task(task)
        
        # 验证知识沉淀
        self.assertTrue(self.agent.knowledge_graph.has_node("task_1"))
        
        # 验证新任务已添加
        self.assertGreater(self.agent.task_queue.size(), 0)

    def test_multiple_health_checks(self):
        for i in range(5):
            self.agent.health_check()
        self.assertEqual(self.agent.run_counter, 5)

    def test_trim_invalid_knowledge(self):
        self.agent.knowledge_graph.add_node("low_node")
        self.agent.knowledge_graph.add_edge("low_node", "target", "low_rel", 0.05)
        
        edge_count_before = self.agent.knowledge_graph.get_edge_count()
        self.agent.knowledge_graph.trim_invalid_knowledge(weight_threshold=0.1)
        edge_count_after = self.agent.knowledge_graph.get_edge_count()
        
        self.assertLess(edge_count_after, edge_count_before)

    def test_evolve_step_trims_knowledge(self):
        self.agent.knowledge_graph.add_node("n1")
        self.agent.knowledge_graph.add_edge("n1", "n2", "low_rel", 0.05)
        
        edge_count_before = self.agent.knowledge_graph.get_edge_count()
        
        for i in range(self.agent.evolve_step):
            self.agent.health_check()
        
        edge_count_after = self.agent.knowledge_graph.get_edge_count()
        self.assertLess(edge_count_after, edge_count_before)


if __name__ == '__main__':
    unittest.main()
