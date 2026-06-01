import sys
sys.path.insert(0, '/workspace')

import unittest
import tempfile
import os
from core import EternalSelfAgent, KnowledgeGraph


class TestKnowledgeEvolution(unittest.TestCase):
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

    def test_enhanced_knowledge_derivation(self):
        kg = KnowledgeGraph(self.temp_kg)
        kg.add_node("A")
        kg.add_edge("A", "B", "关联", 0.8)
        kg.add_edge("B", "C", "关联", 0.7)
        kg.add_edge("C", "D", "关联", 0.5)
        
        tasks_depth1 = kg.derive_new_tasks("A", depth=1)
        self.assertEqual(len(tasks_depth1), 1)
        
        tasks_depth2 = kg.derive_new_tasks("A", depth=2)
        self.assertGreaterEqual(len(tasks_depth2), 2)

    def test_edge_weight_update(self):
        kg = KnowledgeGraph(self.temp_kg)
        kg.add_node("A")
        kg.add_edge("A", "B", "关联", 0.5)
        
        edge = kg._find_existing_edge("A", "B", "关联")
        self.assertIsNotNone(edge)
        self.assertAlmostEqual(edge.weight, 0.5)
        
        updated = kg.update_edge_weight("A", "B", "关联", 0.2)
        self.assertTrue(updated)
        self.assertAlmostEqual(edge.weight, 0.7)
        
        updated = kg.update_edge_weight("A", "B", "关联", -0.3)
        self.assertTrue(updated)
        self.assertAlmostEqual(edge.weight, 0.4)

    def test_high_value_node_detection(self):
        kg = KnowledgeGraph(self.temp_kg)
        kg.add_node("A")
        kg.add_node("B")
        kg.add_node("C")
        kg.add_node("D")
        
        kg.add_edge("A", "B", "关联", 0.9)
        kg.add_edge("A", "C", "关联", 0.8)
        kg.add_edge("A", "D", "关联", 0.7)
        kg.add_edge("B", "C", "关联", 0.6)
        
        high_value = kg.find_highest_value_nodes(min_weight=0.6, limit=3)
        self.assertIn("A", high_value)
        self.assertGreater(len(high_value), 0)

    def test_existing_edge_update_on_add(self):
        kg = KnowledgeGraph(self.temp_kg)
        kg.add_node("A")
        kg.add_node("B")
        
        edge1 = kg.add_edge("A", "B", "关联", 0.5)
        edge2 = kg.add_edge("A", "B", "关联", 0.6)
        
        self.assertEqual(edge1, edge2)
        self.assertAlmostEqual(edge1.weight, 0.6)

    def test_knowledge_trimming_with_max_limit(self):
        kg = KnowledgeGraph(self.temp_kg)
        
        for i in range(20):
            kg.add_node(f"N{i}")
            kg.add_edge(f"N{i}", f"N{i+1}", "关联", 0.1 + i * 0.04)
        
        original_count = kg.get_edge_count()
        self.assertGreater(original_count, 10)
        
        removed = kg.trim_invalid_knowledge(weight_threshold=0.1, max_edges=10)
        self.assertGreater(removed, 0)
        self.assertLessEqual(kg.get_edge_count(), 10)

    def test_agent_deep_reflection(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        
        agent.knowledge_graph.add_node("重要知识")
        agent.knowledge_graph.add_edge("重要知识", "相关概念", "关联", 0.8)
        
        original_edges = agent.knowledge_graph.get_edge_count()
        agent.perform_deep_reflection()
        new_edges = agent.knowledge_graph.get_edge_count()
        
        self.assertGreater(new_edges, original_edges)
        agent.shutdown()

    def test_agent_knowledge_synthesis(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        
        agent.knowledge_graph.add_node("知识A")
        agent.knowledge_graph.add_node("知识B")
        agent.knowledge_graph.add_node("知识C")
        agent.knowledge_graph.add_edge("知识A", "知识B", "关联", 0.7)
        agent.knowledge_graph.add_edge("知识B", "知识C", "关联", 0.6)
        
        original_edges = agent.knowledge_graph.get_edge_count()
        agent.perform_knowledge_synthesis()
        new_edges = agent.knowledge_graph.get_edge_count()
        
        self.assertGreater(new_edges, original_edges)
        agent.shutdown()

    def test_task_execution_with_weight_boost(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        
        agent.execute_task("测试任务")
        
        edges = agent.knowledge_graph.get_edges_from_node("测试任务")
        self.assertGreater(len(edges), 0)
        
        edge = edges[0]
        initial_weight = edge.weight
        
        agent.execute_task("测试任务")
        
        self.assertGreater(edge.weight, initial_weight)
        agent.shutdown()

    def test_idle_evolution_triggers_reflection(self):
        agent = EternalSelfAgent(
            kg_save_path=self.temp_kg,
            log_path=self.temp_log,
            config_path=self.temp_config
        )
        
        agent.knowledge_graph.add_node("知识节点")
        agent.knowledge_graph.add_edge("知识节点", "概念", "关联", 0.8)
        
        original_edges = agent.knowledge_graph.get_edge_count()
        
        for i in range(100):
            agent.run_counter += 1
        
        agent.idle_self_evolve()
        
        new_edges = agent.knowledge_graph.get_edge_count()
        self.assertGreater(new_edges, original_edges)
        agent.shutdown()


if __name__ == '__main__':
    unittest.main()
