import sys
sys.path.insert(0, '/workspace')

import unittest
import tempfile
import os
from core import EternalSelfAgent, KnowledgeGraph


class TestStage10(unittest.TestCase):
    """
    第10阶段测试：性能优化、扩展接口和完整功能验证
    """
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "config.json")
        self.kg_path = os.path.join(self.temp_dir, "kg.json")
    
    def tearDown(self):
        try:
            if os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass
    
    def test_knowledge_graph_index_performance(self):
        """
        测试知识图谱索引性能
        """
        kg = KnowledgeGraph(self.kg_path)
        
        # 添加大量节点和边
        for i in range(100):
            kg.add_node(f"node_{i}")
        
        for i in range(100):  # 修复：给所有100个节点添加边
            kg.add_edge(f"node_{i}", f"node_{(i + 1) % 100}", "rel1", 0.7)
            kg.add_edge(f"node_{i}", f"node_{(i + 2) % 100}", "rel2", 0.5)
        
        # 测试查询性能
        edges = kg.get_edges_from_node("node_0")
        self.assertGreater(len(edges), 0)
        
        # 验证索引正确
        all_outgoing = kg.get_edges_from_node("node_50")
        self.assertGreater(len(all_outgoing), 0)
        
        # 验证查找功能
        related = kg.find_related_nodes("node_0", depth=3)
        self.assertGreater(len(related), 0)
    
    def test_external_knowledge_injection(self):
        """
        测试外部知识注入功能
        """
        kg = KnowledgeGraph(self.kg_path)
        
        # 注入外部知识
        kg.inject_external_knowledge(
            "external_source",
            [
                ("concept_a", "related_to", 0.8),
                ("concept_b", "similar_to", 0.6),
                ("concept_c", "derived_from", 0.9)
            ]
        )
        
        # 验证注入成功
        self.assertTrue(kg.has_node("external_source"))
        self.assertTrue(kg.has_node("concept_a"))
        
        edges = kg.get_edges_from_node("external_source")
        self.assertEqual(len(edges), 3)
    
    def test_task_handler_registration(self):
        """
        测试任务处理器注册功能
        """
        agent = EternalSelfAgent(self.config_path, loop_delay=0)
        
        handled_tasks = []
        
        def custom_handler(task: str, agent_ref):
            handled_tasks.append(task)
        
        # 注册自定义任务处理器
        agent.register_task_handler("custom", custom_handler)
        
        # 添加任务并执行
        agent.add_manual_task("custom:test_task_1")
        agent.add_manual_task("custom:test_task_2")
        
        # 执行任务
        for i in range(5):
            task = agent.get_current_task()
            if task:
                agent.execute_task(task)
        
        # 验证处理器被调用
        self.assertEqual(len(handled_tasks), 2)
        
        agent.shutdown()
    
    def test_related_tasks_finding(self):
        """
        测试相关任务查找功能
        """
        agent = EternalSelfAgent(self.config_path, loop_delay=0)
        
        # 创建一些知识连接
        agent.knowledge_graph.add_node("main_task")
        agent.knowledge_graph.add_edge("main_task", "related_task_1", "depends_on", 0.8)
        agent.knowledge_graph.add_edge("related_task_1", "related_task_2", "uses", 0.7)
        agent.knowledge_graph.add_edge("related_task_2", "final_task", "produces", 0.9)
        
        # 查找相关任务
        related = agent.find_related_tasks("main_task", depth=3)
        
        self.assertIn("related_task_1", related)
        self.assertIn("related_task_2", related)
        self.assertIn("final_task", related)
        
        agent.shutdown()
    
    def test_complete_system_workflow(self):
        """
        测试完整系统工作流程
        """
        agent = EternalSelfAgent(
            self.config_path,
            kg_save_path=self.kg_path,
            loop_delay=0
        )
        
        # 初始任务
        agent.add_manual_task("system_start")
        
        # 执行一些任务
        for i in range(20):
            task = agent.get_current_task()
            if task:
                agent.execute_task(task)
            agent.health_check()
        
        # 验证知识图谱有内容
        self.assertGreater(agent.knowledge_graph.get_node_count(), 5)
        self.assertGreater(agent.knowledge_graph.get_edge_count(), 5)
        
        # 验证统计信息
        status = agent.get_system_status()
        self.assertGreater(status["tasks_executed"], 0)
        
        # 保存状态
        agent.save_full_state()
        
        # 重启并验证恢复
        agent.shutdown()
        
        agent2 = EternalSelfAgent(
            self.config_path,
            kg_save_path=self.kg_path
        )
        restore_success = agent2.restore_state()
        
        self.assertTrue(restore_success)
        self.assertGreater(agent2.knowledge_graph.get_node_count(), 5)
        
        agent2.shutdown()


if __name__ == "__main__":
    unittest.main()