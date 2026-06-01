import pytest
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.auto_evolution import (
    EvolutionState, EvolutionAction, EvolutionFeedback,
    PerceptionModule, DecisionEngine, ExecutionModule,
    LearningModule, MetaLearningModule, AutoEvolutionEngine
)
from core.knowledge_graph import KnowledgeGraph
from core.agent import EternalSelfAgent


class TestEvolutionState:
    def test_creation(self):
        state = EvolutionState(
            timestamp=time.time(),
            node_count=10,
            edge_count=20,
            task_queue_size=5,
            tasks_executed=100,
            error_count=2,
            avg_task_time=0.01,
            memory_usage=50.0,
            knowledge_density=2.0
        )
        assert state.node_count == 10
        assert state.knowledge_density == 2.0

    def test_to_dict(self):
        state = EvolutionState(
            timestamp=123.0, node_count=1, edge_count=1,
            task_queue_size=0, tasks_executed=0, error_count=0,
            avg_task_time=0.0, memory_usage=0.0, knowledge_density=1.0
        )
        d = state.to_dict()
        assert d["node_count"] == 1
        assert d["timestamp"] == 123.0


class TestEvolutionAction:
    def test_creation(self):
        action = EvolutionAction(
            action_type="config_change",
            target="loop_delay",
            old_value=1.0,
            new_value=2.0,
            reason="test",
            expected_outcome="better"
        )
        assert action.action_type == "config_change"

    def test_to_dict(self):
        action = EvolutionAction(
            action_type="test", target="t", old_value=0, new_value=1,
            reason="r", expected_outcome="o"
        )
        d = action.to_dict()
        assert d["target"] == "t"


class TestPerceptionModule:
    @pytest.fixture
    def agent(self):
        kg = KnowledgeGraph(save_path="test_perception.json")
        kg.clear()
        return EternalSelfAgent(kg_save_path="test_perception.json")

    def test_perceive(self, agent):
        module = PerceptionModule()
        state = module.perceive(agent)
        assert state.node_count >= 0
        assert state.memory_usage >= 0

    def test_detect_anomalies_empty(self):
        module = PerceptionModule()
        anomalies = module.detect_anomalies()
        assert anomalies == []

    def test_detect_anomalies_with_data(self):
        module = PerceptionModule()
        for i in range(20):
            module.metric_history['memory'].append(50.0)
        module.metric_history['memory'].append(200.0)  # 异常值
        anomalies = module.detect_anomalies()
        assert len(anomalies) >= 1
        assert anomalies[0]['metric'] == 'memory'

    def test_detect_trends(self):
        module = PerceptionModule()
        for i in range(30):
            module.metric_history['node_count'].append(float(i))
        trends = module.detect_trends()
        assert len(trends) >= 1
        assert trends[0]['direction'] == 'increasing'

    def test_get_state_summary(self, agent):
        module = PerceptionModule()
        module.perceive(agent)
        summary = module.get_state_summary()
        assert 'latest' in summary
        assert 'anomalies' in summary
        assert 'trends' in summary


class TestDecisionEngine:
    def test_creation(self):
        engine = DecisionEngine()
        assert engine.exploration_rate == 0.2

    def test_decide_with_anomaly(self):
        engine = DecisionEngine()
        perception = {
            'anomalies': [{
                'metric': 'memory',
                'direction': 'high',
                'severity': 2.0,
                'z_score': 3.0
            }],
            'trends': []
        }
        actions = engine.decide(perception, {'evolve_step': 100})
        assert len(actions) >= 1
        assert actions[0].action_type == 'config_change'

    def test_decide_with_trend(self):
        engine = DecisionEngine()
        perception = {
            'anomalies': [],
            'trends': [{
                'metric': 'node_count',
                'direction': 'increasing',
                'change_pct': 0.5
            }]
        }
        actions = engine.decide(perception, {'evolve_step': 100})
        assert len(actions) >= 1

    def test_record_result(self):
        engine = DecisionEngine()
        action = EvolutionAction(
            action_type="config_change", target="t",
            old_value=0, new_value=1, reason="r", expected_outcome="o"
        )
        engine.record_result(action, True)
        assert len(engine.success_rates['config_change']) == 1


class TestExecutionModule:
    @pytest.fixture
    def agent(self):
        kg = KnowledgeGraph(save_path="test_execution.json")
        kg.clear()
        return EternalSelfAgent(kg_save_path="test_execution.json")

    def test_execute_config_change(self, agent):
        module = ExecutionModule()
        action = EvolutionAction(
            action_type="config_change",
            target="loop_delay",
            old_value=1.0,
            new_value=1.5,
            reason="test",
            expected_outcome="slower"
        )
        success, message = module.execute(action, agent)
        assert success is True
        assert "loop_delay" in message

    def test_execute_knowledge_prune(self, agent):
        module = ExecutionModule()
        # 添加一些节点和边
        agent.knowledge_graph.add_node("A")
        agent.knowledge_graph.add_node("B")
        agent.knowledge_graph.add_edge("A", "B", "test", 0.9)

        action = EvolutionAction(
            action_type="knowledge_prune",
            target="weight_threshold",
            old_value=0.1,
            new_value=0.5,
            reason="test",
            expected_outcome="prune"
        )
        success, message = module.execute(action, agent)
        assert success is True

    def test_execute_unknown_action(self, agent):
        module = ExecutionModule()
        action = EvolutionAction(
            action_type="unknown", target="t",
            old_value=0, new_value=1, reason="r", expected_outcome="o"
        )
        success, message = module.execute(action, agent)
        assert success is False


class TestLearningModule:
    def test_evaluate(self):
        module = LearningModule()
        before = EvolutionState(
            timestamp=1.0, node_count=10, edge_count=20,
            task_queue_size=5, tasks_executed=100, error_count=10,
            avg_task_time=0.1, memory_usage=100.0, knowledge_density=2.0
        )
        after = EvolutionState(
            timestamp=2.0, node_count=10, edge_count=20,
            task_queue_size=5, tasks_executed=100, error_count=5,
            avg_task_time=0.05, memory_usage=80.0, knowledge_density=2.0
        )
        action = EvolutionAction(
            action_type="config_change", target="loop_delay",
            old_value=1.0, new_value=2.0, reason="test", expected_outcome="better"
        )
        feedback = module.evaluate(action, before, after)
        assert feedback.score > 0  # 错误率降低，得分应该为正
        assert feedback.success is True

    def test_get_best_strategies(self):
        module = LearningModule()
        before = EvolutionState(
            timestamp=1.0, node_count=1, edge_count=1,
            task_queue_size=0, tasks_executed=1, error_count=1,
            avg_task_time=0.1, memory_usage=100.0, knowledge_density=1.0
        )
        after = EvolutionState(
            timestamp=2.0, node_count=1, edge_count=1,
            task_queue_size=0, tasks_executed=1, error_count=0,
            avg_task_time=0.05, memory_usage=90.0, knowledge_density=1.0
        )
        action = EvolutionAction(
            action_type="config_change", target="test",
            old_value=0, new_value=1, reason="r", expected_outcome="o"
        )
        module.evaluate(action, before, after)
        best = module.get_best_strategies()
        assert len(best) >= 1

    def test_get_learning_report_empty(self):
        module = LearningModule()
        report = module.get_learning_report()
        assert report["status"] == "no_data"


class TestMetaLearningModule:
    def test_adapt_warming_up(self):
        meta = MetaLearningModule()
        learning = LearningModule()
        decision = DecisionEngine()

        actions = meta.adapt(learning, decision)
        assert decision.exploration_rate == 0.3  # 预热期探索率

    def test_adapt_high_success(self):
        meta = MetaLearningModule()
        learning = LearningModule()
        decision = DecisionEngine()

        # 模拟多次成功进化
        before = EvolutionState(
            timestamp=1.0, node_count=1, edge_count=1,
            task_queue_size=0, tasks_executed=1, error_count=1,
            avg_task_time=0.1, memory_usage=100.0, knowledge_density=1.0
        )
        after = EvolutionState(
            timestamp=2.0, node_count=1, edge_count=1,
            task_queue_size=0, tasks_executed=1, error_count=0,
            avg_task_time=0.05, memory_usage=90.0, knowledge_density=1.0
        )
        for _ in range(15):
            action = EvolutionAction(
                action_type="config_change", target="loop_delay",
                old_value=1.0, new_value=1.5, reason="r", expected_outcome="o"
            )
            learning.evaluate(action, before, after)

        old_rate = decision.exploration_rate
        actions = meta.adapt(learning, decision)
        assert decision.exploration_rate < old_rate  # 成功率高，应该降低探索率


class TestAutoEvolutionEngine:
    @pytest.fixture
    def agent(self):
        kg = KnowledgeGraph(save_path="test_auto_evolve.json")
        kg.clear()
        return EternalSelfAgent(kg_save_path="test_auto_evolve.json")

    @pytest.fixture
    def engine(self, agent):
        return AutoEvolutionEngine(agent, evolution_interval=10)

    def test_creation(self, agent):
        engine = AutoEvolutionEngine(agent)
        assert engine.enabled is False
        assert engine.evolution_interval == 50  # 默认值

    def test_enable_disable(self, engine):
        engine.enable()
        assert engine.enabled is True
        engine.disable()
        assert engine.enabled is False

    def test_should_evolve_disabled(self, engine):
        engine.disable()
        assert engine.should_evolve() is False

    def test_should_evolve_by_counter(self, engine):
        engine.enable()
        engine.agent.run_counter = 10
        assert engine.should_evolve() is True

    def test_evolve(self, engine):
        engine.enable()
        engine.agent.run_counter = 10
        report = engine.evolve()
        assert report["evolution_id"] == 1
        assert "phases" in report
        assert "perception" in report["phases"]
        assert "decision" in report["phases"]
        assert "execution" in report["phases"]
        assert "learning" in report["phases"]
        assert "meta_learning" in report["phases"]
        assert "summary" in report

    def test_evolve_skipped(self, engine):
        engine.enable()
        engine.agent.run_counter = 1  # 不是 10 的倍数
        engine.last_evolution_time = time.time()  # 刚进化过
        report = engine.evolve()
        assert report["status"] == "skipped"

    def test_get_status(self, engine):
        engine.enable()
        status = engine.get_status()
        assert "enabled" in status
        assert "evolution_count" in status
        assert "learning_report" in status


class TestAutoEvolutionIntegration:
    def test_full_evolution_cycle(self):
        """测试完整进化周期"""
        kg = KnowledgeGraph(save_path="test_full_cycle.json")
        kg.clear()
        agent = EternalSelfAgent(kg_save_path="test_full_cycle.json")

        # 添加一些初始知识
        for i in range(20):
            agent.knowledge_graph.add_node(f"concept_{i}", {"importance": i * 0.05})
        for i in range(19):
            agent.knowledge_graph.add_edge(f"concept_{i}", f"concept_{i+1}", "related", 0.8)

        engine = AutoEvolutionEngine(agent, evolution_interval=5)
        engine.enable()

        # 模拟运行多个周期
        for i in range(15):
            agent.run_counter = i + 1
            if engine.should_evolve():
                report = engine.evolve()
                assert "phases" in report

        # 验证进化确实发生了
        assert engine.evolution_count >= 1

        status = engine.get_status()
        assert status["enabled"] is True

        # 清理
        import os
        for f in ["test_full_cycle.json", "test_full_cycle.json.backup"]:
            if os.path.exists(f):
                os.remove(f)
