import time
import random
import json
import os
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field, asdict
from collections import deque, defaultdict
import statistics


@dataclass
class EvolutionState:
    """
    进化状态快照

    记录系统某一时刻的完整状态，用于对比和评估进化效果
    """
    timestamp: float
    node_count: int
    edge_count: int
    task_queue_size: int
    tasks_executed: int
    error_count: int
    avg_task_time: float
    memory_usage: float
    knowledge_density: float  # 边数/节点数，衡量知识连接度
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EvolutionState':
        return cls(**data)


@dataclass
class EvolutionAction:
    """
    进化动作

    描述系统对自身的一次修改操作
    """
    action_type: str  # 'config_change', 'task_generation', 'knowledge_prune', 'structure_reform'
    target: str       # 修改目标
    old_value: Any
    new_value: Any
    reason: str       # 为什么做这个动作
    expected_outcome: str  # 期望结果
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvolutionFeedback:
    """
    进化反馈

    记录一次进化动作的实际效果
    """
    action: EvolutionAction
    before_state: EvolutionState
    after_state: EvolutionState
    success: bool
    actual_outcome: str
    score: float  # -1.0 到 1.0，评估这次进化的好坏

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "before_state": self.before_state.to_dict(),
            "after_state": self.after_state.to_dict(),
            "success": self.success,
            "actual_outcome": self.actual_outcome,
            "score": self.score
        }


class PerceptionModule:
    """
    感知模块

    功能：持续监测系统状态，提取特征，发现异常和机会
    原理：定期采样 + 事件驱动，构建系统状态的时序表示
    """

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.state_history: deque = deque(maxlen=window_size)
        self.metric_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self._anomaly_threshold = 2.0  # 标准差倍数

    def perceive(self, agent) -> EvolutionState:
        """
        感知当前系统状态

        Args:
            agent: EternalSelfAgent 实例

        Returns:
            EvolutionState 状态快照
        """
        kg = agent.knowledge_graph
        node_count = kg.get_node_count()
        edge_count = kg.get_edge_count()

        # 计算知识密度
        knowledge_density = edge_count / max(node_count, 1)

        # 计算平均任务时间
        avg_task_time = (
            agent.total_task_time / agent.tasks_executed
            if agent.tasks_executed > 0 else 0.0
        )

        state = EvolutionState(
            timestamp=time.time(),
            node_count=node_count,
            edge_count=edge_count,
            task_queue_size=agent.task_queue.size(),
            tasks_executed=agent.tasks_executed,
            error_count=agent.error_count,
            avg_task_time=avg_task_time,
            memory_usage=agent._get_memory_usage(),
            knowledge_density=knowledge_density,
            config=agent.config_manager.get_all().copy()
        )

        self.state_history.append(state)

        # 记录各个指标的历史
        self.metric_history['node_count'].append(node_count)
        self.metric_history['edge_count'].append(edge_count)
        self.metric_history['error_rate'].append(
            agent.error_count / max(agent.run_counter, 1)
        )
        self.metric_history['task_time'].append(avg_task_time)
        self.metric_history['memory'].append(state.memory_usage)

        return state

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        检测异常

        基于统计方法发现系统指标的异常波动

        Returns:
            异常列表，每项包含指标名、当前值、期望值、严重程度
        """
        anomalies = []

        for metric_name, history in self.metric_history.items():
            if len(history) < 10:
                continue

            values = list(history)
            mean = statistics.mean(values)
            stdev = statistics.stdev(values) if len(values) > 1 else 0

            if stdev == 0:
                continue

            current = values[-1]
            z_score = abs(current - mean) / stdev

            if z_score > self._anomaly_threshold:
                severity = min(z_score / self._anomaly_threshold, 3.0)
                anomalies.append({
                    'metric': metric_name,
                    'current': current,
                    'expected': mean,
                    'z_score': z_score,
                    'severity': severity,
                    'direction': 'high' if current > mean else 'low'
                })

        return anomalies

    def detect_trends(self) -> List[Dict[str, Any]]:
        """
        检测趋势

        通过线性拟合发现指标的上升/下降趋势

        Returns:
            趋势列表
        """
        trends = []

        for metric_name, history in self.metric_history.items():
            if len(history) < 20:
                continue

            values = list(history)
            # 简单趋势：比较前半段和后半段的均值
            mid = len(values) // 2
            first_half = statistics.mean(values[:mid])
            second_half = statistics.mean(values[mid:])

            change_pct = (second_half - first_half) / max(abs(first_half), 0.001)

            if abs(change_pct) > 0.1:  # 10% 变化视为趋势
                trends.append({
                    'metric': metric_name,
                    'direction': 'increasing' if change_pct > 0 else 'decreasing',
                    'change_pct': change_pct,
                    'first_half_avg': first_half,
                    'second_half_avg': second_half
                })

        return trends

    def get_state_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        if not self.state_history:
            return {}

        latest = self.state_history[-1]
        return {
            'latest': latest.to_dict(),
            'history_length': len(self.state_history),
            'anomalies': self.detect_anomalies(),
            'trends': self.detect_trends()
        }


class DecisionEngine:
    """
    决策引擎

    功能：基于感知信息，自主决定系统如何进化
    原理：规则 + 统计 + 随机探索的组合策略
    """

    def __init__(self):
        self.action_history: List[EvolutionAction] = []
        self.success_rates: Dict[str, List[bool]] = defaultdict(list)
        self.exploration_rate = 0.2  # 20% 概率随机探索
        self.min_confidence = 0.6    # 最低置信度才执行动作

    def decide(self, perception: Dict[str, Any], current_config: Dict[str, Any]) -> List[EvolutionAction]:
        """
        基于感知结果做出进化决策

        Args:
            perception: 感知模块的输出
            current_config: 当前配置

        Returns:
            进化动作列表
        """
        actions = []
        anomalies = perception.get('anomalies', [])
        trends = perception.get('trends', [])

        # 1. 响应异常（最高优先级）
        for anomaly in anomalies:
            action = self._respond_to_anomaly(anomaly, current_config)
            if action:
                actions.append(action)

        # 2. 响应趋势
        for trend in trends:
            action = self._respond_to_trend(trend, current_config)
            if action:
                actions.append(action)

        # 3. 探索性进化（随机尝试新配置）
        if random.random() < self.exploration_rate:
            explore_action = self._generate_exploratory_action(current_config)
            if explore_action:
                actions.append(explore_action)

        # 4. 基于历史成功率的优化
        optimize_action = self._generate_optimization_action(current_config)
        if optimize_action:
            actions.append(optimize_action)

        return actions

    def _respond_to_anomaly(self, anomaly: Dict[str, Any], config: Dict[str, Any]) -> Optional[EvolutionAction]:
        """针对异常生成响应动作"""
        metric = anomaly['metric']
        direction = anomaly['direction']
        severity = anomaly['severity']

        if metric == 'memory' and direction == 'high':
            # 内存过高：降低 evolve_step 频率，减少知识保留
            return EvolutionAction(
                action_type='config_change',
                target='evolve_step',
                old_value=config.get('evolve_step', 100),
                new_value=int(config.get('evolve_step', 100) * 1.5),
                reason=f"内存异常高 (z={anomaly['z_score']:.2f})，降低进化频率",
                expected_outcome="减少内存占用"
            )

        if metric == 'error_rate' and direction == 'high':
            # 错误率过高：增加 loop_delay，给系统更多恢复时间
            return EvolutionAction(
                action_type='config_change',
                target='loop_delay',
                old_value=config.get('loop_delay', 1.0),
                new_value=config.get('loop_delay', 1.0) * 1.5,
                reason=f"错误率异常高 (z={anomaly['z_score']:.2f})，降低运行速度",
                expected_outcome="减少错误发生"
            )

        if metric == 'task_time' and direction == 'high':
            # 任务执行时间变长：可能知识图谱太大，需要精简
            return EvolutionAction(
                action_type='knowledge_prune',
                target='weight_threshold',
                old_value=0.1,
                new_value=min(0.1 + 0.05 * severity, 0.5),
                reason=f"任务执行时间异常长 (z={anomaly['z_score']:.2f})，提高知识精简阈值",
                expected_outcome="减少知识图谱规模，提升执行速度"
            )

        return None

    def _respond_to_trend(self, trend: Dict[str, Any], config: Dict[str, Any]) -> Optional[EvolutionAction]:
        """针对趋势生成响应动作"""
        metric = trend['metric']
        direction = trend['direction']

        if metric == 'node_count' and direction == 'increasing':
            # 节点快速增长：提前增加进化频率
            return EvolutionAction(
                action_type='config_change',
                target='evolve_step',
                old_value=config.get('evolve_step', 100),
                new_value=max(int(config.get('evolve_step', 100) * 0.8), 50),
                reason="节点数快速增长，增加进化频率防止膨胀",
                expected_outcome="及时精简知识，保持高效"
            )

        if metric == 'error_rate' and direction == 'increasing':
            # 错误率持续上升：系统可能不稳定，需要保守策略
            return EvolutionAction(
                action_type='config_change',
                target='loop_delay',
                old_value=config.get('loop_delay', 1.0),
                new_value=config.get('loop_delay', 1.0) * 1.3,
                reason="错误率持续上升，采取保守策略",
                expected_outcome="降低错误率，提高稳定性"
            )

        return None

    def _generate_exploratory_action(self, config: Dict[str, Any]) -> Optional[EvolutionAction]:
        """生成探索性动作"""
        # 随机选择一个配置参数进行微调
        config_options = [
            ('loop_delay', 0.5, 3.0, 0.1),
            ('evolve_step', 50, 500, 10),
            ('task_queue_max', 100, 2000, 50)
        ]

        target, min_val, max_val, step = random.choice(config_options)
        current = config.get(target, (min_val + max_val) / 2)

        # 随机增减
        new_value = current + random.choice([-1, 1]) * step
        new_value = max(min_val, min(max_val, new_value))

        # 对于整数配置
        if target in ('evolve_step', 'task_queue_max'):
            new_value = int(new_value)

        return EvolutionAction(
            action_type='config_change',
            target=target,
            old_value=current,
            new_value=new_value,
            reason="探索性进化：随机尝试新配置",
            expected_outcome="可能发现更优配置"
        )

    def _generate_optimization_action(self, config: Dict[str, Any]) -> Optional[EvolutionAction]:
        """基于历史成功率生成优化动作"""
        if not self.success_rates:
            return None

        # 找出成功率最高的动作类型，多做这类动作
        best_action_type = None
        best_rate = 0.0

        for action_type, results in self.success_rates.items():
            if len(results) >= 5:
                rate = sum(results) / len(results)
                if rate > best_rate:
                    best_rate = rate
                    best_action_type = action_type

        if best_action_type and best_rate > 0.7:
            # 如果某类动作成功率高，继续微调相关参数
            if best_action_type == 'config_change':
                # 微调 loop_delay
                current = config.get('loop_delay', 1.0)
                return EvolutionAction(
                    action_type='config_change',
                    target='loop_delay',
                    old_value=current,
                    new_value=round(current * random.uniform(0.9, 1.1), 2),
                    reason=f"基于历史高成功率({best_rate:.2f})的微调优化",
                    expected_outcome="持续优化性能"
                )

        return None

    def record_result(self, action: EvolutionAction, success: bool) -> None:
        """记录动作执行结果"""
        self.action_history.append(action)
        self.success_rates[action.action_type].append(success)

        # 保持历史长度
        if len(self.success_rates[action.action_type]) > 100:
            self.success_rates[action.action_type].pop(0)


class ExecutionModule:
    """
    执行模块

    功能：安全地执行进化动作
    原理：事务化执行 + 回滚机制
    """

    def __init__(self):
        self.execution_log: List[Dict[str, Any]] = []
        self._backup_states: List[Dict[str, Any]] = []

    def execute(self, action: EvolutionAction, agent) -> Tuple[bool, str]:
        """
        执行进化动作

        Args:
            action: 进化动作
            agent: EternalSelfAgent 实例

        Returns:
            (是否成功, 结果描述)
        """
        try:
            if action.action_type == 'config_change':
                return self._execute_config_change(action, agent)
            elif action.action_type == 'knowledge_prune':
                return self._execute_knowledge_prune(action, agent)
            elif action.action_type == 'task_generation':
                return self._execute_task_generation(action, agent)
            elif action.action_type == 'structure_reform':
                return self._execute_structure_reform(action, agent)
            else:
                return False, f"未知动作类型: {action.action_type}"
        except Exception as e:
            return False, f"执行异常: {str(e)}"

    def _execute_config_change(self, action: EvolutionAction, agent) -> Tuple[bool, str]:
        """执行配置变更"""
        target = action.target
        new_value = action.new_value

        # 保存旧值
        old_value = agent.config_manager.get(target)

        # 应用新配置
        success = agent.update_config(target, new_value)

        if success:
            self.execution_log.append({
                'action': action.to_dict(),
                'result': 'success',
                'old_value': old_value
            })
            return True, f"配置 {target} 从 {old_value} 变更为 {new_value}"
        else:
            return False, f"配置变更失败: {target}"

    def _execute_knowledge_prune(self, action: EvolutionAction, agent) -> Tuple[bool, str]:
        """执行知识精简"""
        threshold = action.new_value

        before_nodes = agent.knowledge_graph.get_node_count()
        before_edges = agent.knowledge_graph.get_edge_count()

        agent.knowledge_graph.trim_invalid_knowledge(weight_threshold=threshold)

        after_nodes = agent.knowledge_graph.get_node_count()
        after_edges = agent.knowledge_graph.get_edge_count()

        return True, (
            f"知识精简完成: 节点 {before_nodes}->{after_nodes}, "
            f"边 {before_edges}->{after_edges}, 阈值={threshold:.3f}"
        )

    def _execute_task_generation(self, action: EvolutionAction, agent) -> Tuple[bool, str]:
        """执行自生成任务"""
        task_template = action.target
        new_task = f"{task_template}_{int(time.time())}"

        success = agent.task_queue.add(new_task)
        if success:
            return True, f"生成新任务: {new_task}"
        return False, "任务队列已满"

    def _execute_structure_reform(self, action: EvolutionAction, agent) -> Tuple[bool, str]:
        """执行结构重组"""
        # 例如：重建索引、优化存储结构等
        agent.knowledge_graph._rebuild_edge_indexes()
        return True, "结构重组完成"


class LearningModule:
    """
    学习模块

    功能：评估进化效果，学习最优策略
    原理：强化学习思想 —— 好的进化被记住，坏的进化被避免
    """

    def __init__(self, learning_rate: float = 0.1):
        self.learning_rate = learning_rate
        self.feedback_history: List[EvolutionFeedback] = []
        self.strategy_scores: Dict[str, float] = defaultdict(float)
        self.strategy_counts: Dict[str, int] = defaultdict(int)

    def evaluate(self, action: EvolutionAction, before: EvolutionState, after: EvolutionState) -> EvolutionFeedback:
        """
        评估一次进化的效果

        Args:
            action: 执行的动作
            before: 执行前状态
            after: 执行后状态

        Returns:
            EvolutionFeedback 反馈对象
        """
        score = self._calculate_score(before, after, action)

        success = score > 0

        feedback = EvolutionFeedback(
            action=action,
            before_state=before,
            after_state=after,
            success=success,
            actual_outcome=self._describe_outcome(before, after),
            score=score
        )

        self.feedback_history.append(feedback)

        # 更新策略评分
        strategy_key = f"{action.action_type}:{action.target}"
        self.strategy_scores[strategy_key] += score
        self.strategy_counts[strategy_key] += 1

        return feedback

    def _calculate_score(self, before: EvolutionState, after: EvolutionState, action: EvolutionAction) -> float:
        """
        计算进化得分

        综合考虑多个维度：
        - 错误率变化（越低越好）
        - 任务效率变化（越快越好）
        - 知识质量变化（密度适中最好）
        - 内存使用变化（越低越好）
        """
        scores = []

        # 1. 错误率变化（负向指标）
        before_error_rate = before.error_count / max(before.tasks_executed, 1)
        after_error_rate = after.error_count / max(after.tasks_executed, 1)
        error_improvement = before_error_rate - after_error_rate
        scores.append(error_improvement * 5.0)  # 错误率权重高

        # 2. 任务效率变化
        time_improvement = before.avg_task_time - after.avg_task_time
        scores.append(time_improvement * 2.0)

        # 3. 知识密度（适中最好，0.5-2.0 为理想范围）
        density_score = 0.0
        if 0.5 <= after.knowledge_density <= 2.0:
            density_score = 0.2
        elif after.knowledge_density < 0.3:
            density_score = -0.3  # 太稀疏
        elif after.knowledge_density > 3.0:
            density_score = -0.3  # 太稠密
        scores.append(density_score)

        # 4. 内存使用变化（越低越好）
        memory_improvement = before.memory_usage - after.memory_usage
        scores.append(memory_improvement * 0.01)

        # 5. 任务队列健康度（不为空也不爆满）
        queue_score = 0.0
        if 1 <= after.task_queue_size <= 100:
            queue_score = 0.1
        elif after.task_queue_size > 500:
            queue_score = -0.2
        scores.append(queue_score)

        total_score = sum(scores)
        return max(-1.0, min(1.0, total_score))

    def _describe_outcome(self, before: EvolutionState, after: EvolutionState) -> str:
        """描述进化结果"""
        changes = []

        if after.node_count != before.node_count:
            changes.append(f"节点: {before.node_count}->{after.node_count}")
        if after.edge_count != before.edge_count:
            changes.append(f"边: {before.edge_count}->{after.edge_count}")
        if after.avg_task_time != before.avg_task_time:
            changes.append(f"任务时间: {before.avg_task_time:.4f}->{after.avg_task_time:.4f}")
        if after.memory_usage != before.memory_usage:
            changes.append(f"内存: {before.memory_usage:.1f}->{after.memory_usage:.1f}MB")

        return "; ".join(changes) if changes else "无显著变化"

    def get_best_strategies(self, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        获取最佳策略

        Returns:
            [(策略名, 平均得分), ...]
        """
        averages = {}
        for strategy, total_score in self.strategy_scores.items():
            count = self.strategy_counts[strategy]
            if count > 0:
                averages[strategy] = total_score / count

        return sorted(averages.items(), key=lambda x: x[1], reverse=True)[:top_k]

    def get_learning_report(self) -> Dict[str, Any]:
        """获取学习报告"""
        if not self.feedback_history:
            return {"status": "no_data"}

        recent = self.feedback_history[-50:]
        success_count = sum(1 for f in recent if f.success)

        return {
            "total_evolutions": len(self.feedback_history),
            "recent_success_rate": success_count / len(recent) if recent else 0,
            "best_strategies": self.get_best_strategies(),
            "average_score": statistics.mean(f.score for f in recent) if recent else 0,
            "learning_status": "active" if len(self.feedback_history) > 10 else "warming_up"
        }


class MetaLearningModule:
    """
    元学习模块

    功能：学习如何学习 —— 优化进化策略本身
    原理：监控学习模块的效果，调整决策引擎的参数
    """

    def __init__(self):
        self.meta_history: List[Dict[str, Any]] = []
        self.exploration_schedule = [0.3, 0.2, 0.15, 0.1, 0.05]  # 随时间递减的探索率
        self.current_phase = 0

    def adapt(self, learning_module: LearningModule, decision_engine: DecisionEngine) -> List[EvolutionAction]:
        """
        根据学习效果调整决策策略

        Returns:
            元级进化动作（修改决策引擎自身）
        """
        report = learning_module.get_learning_report()
        meta_actions = []

        # 处理无数据情况
        if report.get("status") == "no_data":
            # 无数据时保持默认探索率
            decision_engine.exploration_rate = self.exploration_schedule[0]
            return meta_actions

        if report.get("learning_status") == "warming_up":
            # 预热期：保持高探索率
            decision_engine.exploration_rate = self.exploration_schedule[0]
        else:
            # 根据成功率调整探索率
            success_rate = report.get("recent_success_rate", 0)

            if success_rate > 0.8:
                # 成功率高，减少探索，多利用
                decision_engine.exploration_rate = max(0.05, decision_engine.exploration_rate * 0.9)
                meta_actions.append(EvolutionAction(
                    action_type='structure_reform',
                    target='exploration_rate',
                    old_value=decision_engine.exploration_rate / 0.9,
                    new_value=decision_engine.exploration_rate,
                    reason="进化成功率高，降低探索率",
                    expected_outcome="更稳定地利用已知好策略"
                ))
            elif success_rate < 0.3:
                # 成功率低，增加探索
                decision_engine.exploration_rate = min(0.5, decision_engine.exploration_rate * 1.2)
                meta_actions.append(EvolutionAction(
                    action_type='structure_reform',
                    target='exploration_rate',
                    old_value=decision_engine.exploration_rate / 1.2,
                    new_value=decision_engine.exploration_rate,
                    reason="进化成功率低，增加探索",
                    expected_outcome="发现新的有效策略"
                ))

        # 记录元学习历史
        self.meta_history.append({
            'timestamp': time.time(),
            'exploration_rate': decision_engine.exploration_rate,
            'success_rate': report.get("recent_success_rate", 0)
        })

        return meta_actions


class AutoEvolutionEngine:
    """
    自动进化引擎

    功能：整合感知、决策、执行、学习、元学习五大模块，
          实现几乎无需人类干预的自动进化

    使用方式：
        engine = AutoEvolutionEngine(agent)
        engine.enable()  # 启动自动进化
        # 之后 agent 的 eternal_loop 会自动调用进化
    """

    def __init__(self, agent, evolution_interval: int = 50):
        self.agent = agent
        self.evolution_interval = evolution_interval
        self.enabled = False

        # 五大核心模块
        self.perception = PerceptionModule()
        self.decision = DecisionEngine()
        self.execution = ExecutionModule()
        self.learning = LearningModule()
        self.meta_learning = MetaLearningModule()

        # 统计
        self.evolution_count = 0
        self.last_evolution_time = 0

    def enable(self) -> None:
        """启用自动进化"""
        self.enabled = True
        self.agent.log_event("AUTO_EVOLVE", "自动进化引擎已启用")

    def disable(self) -> None:
        """禁用自动进化"""
        self.enabled = False
        self.agent.log_event("AUTO_EVOLVE", "自动进化引擎已禁用")

    def should_evolve(self) -> bool:
        """判断是否应该执行进化"""
        if not self.enabled:
            return False

        # 基于运行计数器判断
        if self.agent.run_counter % self.evolution_interval == 0:
            return True

        # 基于时间间隔判断（至少间隔 10 秒）
        if time.time() - self.last_evolution_time > 10:
            return True

        return False

    def evolve(self) -> Dict[str, Any]:
        """
        执行一次完整的进化周期

        Returns:
            进化结果报告
        """
        if not self.should_evolve():
            return {"status": "skipped"}

        self.last_evolution_time = time.time()
        self.evolution_count += 1

        report = {
            "evolution_id": self.evolution_count,
            "timestamp": self.last_evolution_time,
            "phases": {}
        }

        # Phase 1: 感知
        before_state = self.perception.perceive(self.agent)
        perception_summary = self.perception.get_state_summary()
        report["phases"]["perception"] = perception_summary

        # Phase 2: 决策
        actions = self.decision.decide(
            perception_summary,
            self.agent.config_manager.get_all()
        )
        report["phases"]["decision"] = {
            "actions_count": len(actions),
            "actions": [a.to_dict() for a in actions]
        }

        # Phase 3: 执行
        execution_results = []
        for action in actions:
            success, message = self.execution.execute(action, self.agent)
            execution_results.append({
                "action": action.to_dict(),
                "success": success,
                "message": message
            })
            self.decision.record_result(action, success)

        report["phases"]["execution"] = execution_results

        # Phase 4: 再次感知（评估效果）
        after_state = self.perception.perceive(self.agent)

        # Phase 5: 学习
        feedbacks = []
        for i, action in enumerate(actions):
            if i < len(execution_results) and execution_results[i]["success"]:
                feedback = self.learning.evaluate(action, before_state, after_state)
                feedbacks.append(feedback.to_dict())

        report["phases"]["learning"] = feedbacks

        # Phase 6: 元学习
        meta_actions = self.meta_learning.adapt(self.learning, self.decision)
        report["phases"]["meta_learning"] = [a.to_dict() for a in meta_actions]

        # 总结
        report["summary"] = {
            "total_actions": len(actions),
            "successful_actions": sum(1 for r in execution_results if r["success"]),
            "learning_report": self.learning.get_learning_report()
        }

        self.agent.log_event(
            "AUTO_EVOLVE",
            f"第{self.evolution_count}次进化完成: {report['summary']['successful_actions']}/{report['summary']['total_actions']} 动作成功"
        )

        return report

    def get_status(self) -> Dict[str, Any]:
        """获取进化引擎状态"""
        return {
            "enabled": self.enabled,
            "evolution_count": self.evolution_count,
            "evolution_interval": self.evolution_interval,
            "last_evolution_time": self.last_evolution_time,
            "perception_history": len(self.perception.state_history),
            "learning_report": self.learning.get_learning_report(),
            "best_strategies": self.learning.get_best_strategies()
        }
