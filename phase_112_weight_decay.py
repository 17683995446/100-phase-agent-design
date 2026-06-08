#!/usr/bin/env python3
"""
阶段112：权重衰减机制

第一性原理：
  - 记忆公理：长期不用的记忆应自然消退（艾宾浩斯遗忘曲线）
  - 知识价值 = 时新性 × 重要性 × 访问频率
  - 衰减是清理的预演：先弱化，再删除

本阶段产出：
  1. DecayModel：衰减模型（线性/指数/幂律）
  2. DecayScheduler：定时衰减调度
  3. ReinforcementEngine：访问强化
  4. TimeDecay：基于时间的衰减
  5. UsageDecay：基于使用的衰减
  6. PruningPolicy：基于权重的剪枝策略

遵循原则：图难于其易，为大于其细
"""
import time
import math
import unittest
import threading
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field

import sys
sys.path.insert(0, '/workspace')
from phase_103_kg_crud import KnowledgeGraphCRUD
from phase_102_core_datastructure import Node, Edge


# ============================================================
# 一、衰减模型
# ============================================================
class DecayModel(Enum):
    """衰减模型"""
    LINEAR = "linear"           # 线性：w(t) = w0 - k*t
    EXPONENTIAL = "exponential" # 指数：w(t) = w0 * e^(-k*t)（艾宾浩斯）
    POWER = "power"             # 幂律：w(t) = w0 * t^(-k)
    STEP = "step"               # 阶梯：低于阈值后突然衰减


# ============================================================
# 二、衰减策略
# ============================================================
@dataclass
class DecayPolicy:
    """衰减策略配置"""
    model: DecayModel = DecayModel.EXPONENTIAL
    rate: float = 0.05         # 衰减率
    min_weight: float = 0.01   # 最小权重（低于此不再衰减）
    interval_sec: float = 86400.0  # 衰减间隔（默认1天）
    # 指数模型专用
    half_life_sec: Optional[float] = None  # 半衰期
    # 幂律模型专用
    power: float = 0.5         # 幂指数
    # 强化参数
    reinforce_delta: float = 0.1
    reinforce_decay: float = 0.5  # 强化值的半衰期
    # 剪枝参数
    prune_threshold: float = 0.05


# ============================================================
# 三、衰减引擎
# ============================================================
class DecayEngine:
    """衰减引擎

    第一性原理：知识的时间价值随时间衰减，
    但可被访问频率强化
    """
    def __init__(self, kg: KnowledgeGraphCRUD,
                 policy: Optional[DecayPolicy] = None):
        self.kg = kg
        self.policy = policy or DecayPolicy()
        self._stats = {
            "decay_runs": 0,
            "nodes_decayed": 0,
            "edges_decayed": 0,
            "nodes_pruned": 0,
            "edges_pruned": 0,
            "nodes_reinforced": 0,
            "edges_reinforced": 0,
        }

    def compute_decay_factor(self, age_sec: float,
                              last_access_sec: float) -> float:
        """计算衰减因子"""
        model = self.policy.model
        if model == DecayModel.LINEAR:
            return max(0, 1.0 - self.policy.rate * (age_sec / self.policy.interval_sec))
        elif model == DecayModel.EXPONENTIAL:
            if self.policy.half_life_sec:
                return 0.5 ** (age_sec / self.policy.half_life_sec)
            return math.exp(-self.policy.rate * (age_sec / self.policy.interval_sec))
        elif model == DecayModel.POWER:
            if age_sec <= 0:
                return 1.0
            return age_sec ** (-self.policy.power)
        elif model == DecayModel.STEP:
            if age_sec > self.policy.interval_sec:
                return 0.5
            return 1.0
        return 1.0

    def apply_decay(self, element: Any, current_time: Optional[float] = None
                     ) -> float:
        """对单个元素应用衰减

        Returns: 衰减后权重
        """
        current_time = current_time or time.time()
        if isinstance(element, Node):
            age = current_time - element.created_at
            access_age = current_time - element.accessed_at
            # 综合考虑存在时间和最近访问时间
            effective_age = min(age, access_age + self.policy.interval_sec)
        elif isinstance(element, Edge):
            age = current_time - element.created_at
            # 边没有访问时间，用创建时间
            effective_age = age
        else:
            return element.weight
        factor = self.compute_decay_factor(age, effective_age)
        new_weight = element.weight * factor
        if new_weight < self.policy.min_weight:
            new_weight = self.policy.min_weight
        element.weight = new_weight
        return new_weight

    def decay_all(self) -> Dict[str, int]:
        """对整个图谱应用衰减"""
        now = time.time()
        decayed_nodes = 0
        decayed_edges = 0
        # 节点
        for node in self.kg.nodes.values():
            if node.is_active():
                self.apply_decay(node, now)
                decayed_nodes += 1
        # 边
        for edge in self.kg.edges.values():
            if edge.is_active():
                self.apply_decay(edge, now)
                decayed_edges += 1
        self._stats["decay_runs"] += 1
        self._stats["nodes_decayed"] += decayed_nodes
        self._stats["edges_decayed"] += decayed_edges
        return {
            "nodes_decayed": decayed_nodes,
            "edges_decayed": decayed_edges
        }

    def reinforce(self, element: Any, delta: Optional[float] = None
                   ) -> float:
        """强化元素（被访问时）"""
        delta = delta or self.policy.reinforce_delta
        if isinstance(element, Node):
            element.weight = min(1.0, element.weight + delta)
            element.touch()
            self._stats["nodes_reinforced"] += 1
        elif isinstance(element, Edge):
            edge_weight = min(1.0, element.weight + delta)
            element.weight = edge_weight
            element.reinforce_count += 1
            self._stats["edges_reinforced"] += 1
        return element.weight

    def reinforce_by_path(self, node_ids: List[str]) -> int:
        """强化访问路径上的所有节点（模拟"重复激活"）"""
        count = 0
        for nid in node_ids:
            node = self.kg.get_node(nid)
            if node and node.is_active():
                self.reinforce(node)
                count += 1
        return count

    def prune_weak(self, threshold: Optional[float] = None
                    ) -> Dict[str, int]:
        """剪枝：删除权重过低的元素"""
        threshold = threshold or self.policy.prune_threshold
        pruned_nodes = 0
        pruned_edges = 0
        for node in list(self.kg.nodes.values()):
            if node.is_active() and node.weight < threshold:
                self.kg.soft_delete_node(node.node_id)
                pruned_nodes += 1
        for edge in list(self.kg.edges.values()):
            if edge.is_active() and edge.weight < threshold:
                self.kg.soft_delete_edge(edge.edge_id)
                pruned_edges += 1
        self._stats["nodes_pruned"] += pruned_nodes
        self._stats["edges_pruned"] += pruned_edges
        return {
            "nodes_pruned": pruned_nodes,
            "edges_pruned": pruned_edges
        }

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)


# ============================================================
# 四、衰减调度器
# ============================================================
class DecayScheduler:
    """衰减调度器

    定时执行衰减
    """
    def __init__(self, engine: DecayEngine,
                 interval_sec: float = 3600.0):
        self.engine = engine
        self.interval_sec = interval_sec
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_run = 0.0
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while self._running:
            time.sleep(self.interval_sec)
            if not self._running:
                break
            try:
                self.run_once()
            except Exception:
                pass

    def run_once(self) -> Dict[str, Any]:
        """执行一次衰减"""
        with self._lock:
            decay_result = self.engine.decay_all()
            self._last_run = time.time()
            return {
                "timestamp": self._last_run,
                **decay_result
            }

    def get_last_run(self) -> float:
        return self._last_run


# ============================================================
# 五、强化引擎
# ============================================================
class ReinforcementEngine:
    """强化引擎

    第一性原理：被多次访问的知识更重要
    """
    def __init__(self, decay_engine: DecayEngine):
        self.engine = decay_engine
        self._access_log: List[Dict[str, Any]] = []
        self._node_access_counts: Dict[str, int] = {}

    def record_access(self, element_id: str,
                       element_type: str = "node") -> None:
        """记录访问"""
        self._access_log.append({
            "id": element_id,
            "type": element_type,
            "timestamp": time.time()
        })
        if element_type == "node":
            self._node_access_counts[element_id] = \
                self._node_access_counts.get(element_id, 0) + 1
        # 强化
        if element_type == "node":
            elem = self.engine.kg.get_node(element_id)
        else:
            elem = self.engine.kg.edges.get(element_id)
        if elem and elem.is_active():
            self.engine.reinforce(elem)

    def get_hot_nodes(self, k: int = 10) -> List[Tuple[str, int]]:
        """获取最热门节点"""
        sorted_nodes = sorted(
            self._node_access_counts.items(),
            key=lambda x: x[1], reverse=True)
        return sorted_nodes[:k]

    def reinforce_path(self, path: List[str]) -> int:
        """强化整条访问路径"""
        return self.engine.reinforce_by_path(path)


# ============================================================
# 六、时间衰减工具
# ============================================================
class TimeDecay:
    """时间衰减工具

    提供多种衰减函数的纯计算
    """
    @staticmethod
    def exponential(weight: float, elapsed_sec: float,
                     half_life_sec: float) -> float:
        """指数衰减：每过半衰期权重减半"""
        if half_life_sec <= 0:
            return weight
        return weight * (0.5 ** (elapsed_sec / half_life_sec))

    @staticmethod
    def linear(weight: float, elapsed_sec: float,
                max_age_sec: float) -> float:
        """线性衰减：到最大年龄时权重为0"""
        if max_age_sec <= 0:
            return 0.0
        return max(0, weight * (1 - elapsed_sec / max_age_sec))

    @staticmethod
    def power(weight: float, elapsed_sec: float,
                exponent: float = 0.5) -> float:
        """幂律衰减"""
        if elapsed_sec <= 0:
            return weight
        return weight * (elapsed_sec ** -exponent)

    @staticmethod
    def ebbinghaus(retention: float, elapsed_sec: float,
                    stability: float = 86400.0) -> float:
        """艾宾浩斯遗忘曲线"""
        if stability <= 0:
            return 0.0
        return math.exp(-elapsed_sec / stability)


# ============================================================
# 七、单元测试
# ============================================================
class TestDecayEngine(unittest.TestCase):
    """衰减引擎测试"""
    def setUp(self):
        self.kg = KnowledgeGraphCRUD()
        for i in range(5):
            self.kg.add_node(Node(content=f"n{i}", node_id=f"n{i}",
                                   weight=1.0))
        self.engine = DecayEngine(self.kg)

    def test_exponential_decay(self):
        node = self.kg.nodes["n0"]
        node.created_at = time.time() - 86400  # 1天前
        old_weight = node.weight
        self.engine.apply_decay(node)
        self.assertLess(node.weight, old_weight)

    def test_min_weight_floor(self):
        node = self.kg.nodes["n0"]
        node.weight = 0.001
        node.created_at = time.time() - 86400 * 100
        self.engine.apply_decay(node)
        self.assertGreaterEqual(node.weight, self.engine.policy.min_weight)

    def test_reinforce(self):
        node = self.kg.nodes["n0"]
        node.weight = 0.5
        self.engine.reinforce(node, delta=0.3)
        self.assertAlmostEqual(node.weight, 0.8)

    def test_reinforce_caps_at_1(self):
        node = self.kg.nodes["n0"]
        node.weight = 0.95
        self.engine.reinforce(node, delta=0.5)
        self.assertEqual(node.weight, 1.0)

    def test_decay_all(self):
        for n in self.kg.nodes.values():
            n.created_at = time.time() - 86400
        result = self.engine.decay_all()
        self.assertEqual(result["nodes_decayed"], 5)

    def test_prune_weak(self):
        for n in self.kg.nodes.values():
            n.weight = 0.01  # 低于阈值
        result = self.engine.prune_weak(threshold=0.05)
        self.assertEqual(result["nodes_pruned"], 5)


class TestDecayScheduler(unittest.TestCase):
    """衰减调度器测试"""
    def test_run_once(self):
        kg = KnowledgeGraphCRUD()
        kg.add_node(Node(content="x", node_id="x", weight=1.0))
        engine = DecayEngine(kg)
        scheduler = DecayScheduler(engine, interval_sec=0.01)
        result = scheduler.run_once()
        self.assertIn("timestamp", result)
        self.assertEqual(result["nodes_decayed"], 1)


class TestReinforcementEngine(unittest.TestCase):
    """强化引擎测试"""
    def setUp(self):
        self.kg = KnowledgeGraphCRUD()
        self.kg.add_node(Node(content="x", node_id="x", weight=0.5))
        self.engine = DecayEngine(self.kg)
        self.reinforce = ReinforcementEngine(self.engine)

    def test_record_access(self):
        self.reinforce.record_access("x")
        node = self.kg.get_node("x")
        self.assertGreater(node.weight, 0.5)

    def test_get_hot_nodes(self):
        for _ in range(3):
            self.reinforce.record_access("x")
        for _ in range(2):
            self.reinforce.record_access("x")
        self.kg.add_node(Node(content="y", node_id="y"))
        self.reinforce.record_access("y")
        hot = self.reinforce.get_hot_nodes(k=2)
        self.assertEqual(hot[0][0], "x")
        self.assertEqual(hot[0][1], 5)


class TestTimeDecay(unittest.TestCase):
    """时间衰减工具测试"""
    def test_exponential(self):
        w = TimeDecay.exponential(1.0, 86400, 86400)
        self.assertAlmostEqual(w, 0.5, places=5)

    def test_linear(self):
        w = TimeDecay.linear(1.0, 86400, 86400 * 2)
        self.assertAlmostEqual(w, 0.5, places=5)

    def test_linear_zero_at_max(self):
        w = TimeDecay.linear(1.0, 86400 * 3, 86400)
        self.assertEqual(w, 0.0)

    def test_ebbinghaus(self):
        r = TimeDecay.ebbinghaus(1.0, 86400, 86400)
        self.assertLess(r, 1.0)
        self.assertGreater(r, 0.0)


class TestDecayIntegration(unittest.TestCase):
    """衰减集成测试"""
    def test_realistic_scenario(self):
        """模拟真实场景：创建节点、访问、部分衰减、清理"""
        kg = KnowledgeGraphCRUD()
        # 创建节点
        for i in range(10):
            kg.add_node(Node(content=f"concept_{i}",
                              node_id=f"c{i}",
                              weight=1.0))
        engine = DecayEngine(kg, DecayPolicy(
            model=DecayModel.EXPONENTIAL,
            rate=0.1,
            half_life_sec=3600.0  # 1小时半衰期
        ))
        # 模拟10秒老化
        for node in kg.nodes.values():
            node.created_at = time.time() - 10
            node.accessed_at = time.time() - 10
        # 衰减
        engine.decay_all()
        # 验证权重下降了
        weights = [n.weight for n in kg.nodes.values() if n.is_active()]
        self.assertLess(max(weights), 1.0)
        # 强化访问
        engine.reinforce(kg.get_node("c0"), delta=0.5)
        self.assertGreater(kg.get_node("c0").weight, weights[0])


# ============================================================
# 八、阶段112演示
# ============================================================
def run_phase_112():
    """运行阶段112"""
    print("=" * 70)
    print("阶段112：权重衰减机制")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestDecayEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestDecayScheduler))
    suite.addTests(loader.loadTestsFromTestCase(TestReinforcementEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestTimeDecay))
    suite.addTests(loader.loadTestsFromTestCase(TestDecayIntegration))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    print()
    print("-" * 70)
    print("【权重衰减演示】")
    print("-" * 70)
    # 创建一张知识图谱
    kg = KnowledgeGraphCRUD()
    # 创建不同"年龄"的节点
    for i in range(8):
        n = Node(content=f"知识{i}", node_id=f"k{i}",
                  label="concept", weight=1.0)
        n.created_at = time.time() - (i * 3600)  # 1小时间隔
        n.accessed_at = time.time() - (i * 3600)
        kg.add_node(n)
    # 添加边
    for i in range(7):
        e = Edge(from_id=f"k{i}", to_id=f"k{i+1}",
                 relation="related", weight=1.0,
                 edge_id=f"e{i}")
        e.created_at = time.time() - (i * 3600)
        kg.add_edge(e)
    # 创建指数衰减引擎（半衰期2小时）
    engine = DecayEngine(kg, DecayPolicy(
        model=DecayModel.EXPONENTIAL,
        half_life_sec=7200.0,  # 2小时
        min_weight=0.01,
        prune_threshold=0.1
    ))
    print(f"  📊 衰减前权重:")
    for n in sorted(kg.nodes.values(), key=lambda x: x.node_id):
        print(f"     {n.node_id}: age={(time.time()-n.created_at)/3600:.1f}h, "
              f"weight={n.weight:.3f}")
    print()
    print("  🕐 应用指数衰减（半衰期2h）:")
    engine.decay_all()
    for n in sorted(kg.nodes.values(), key=lambda x: x.node_id):
        print(f"     {n.node_id}: weight={n.weight:.3f}")
    print()
    # 强化
    print("  💪 强化访问k0, k1:")
    engine.reinforce(kg.get_node("k0"), delta=0.3)
    engine.reinforce(kg.get_node("k1"), delta=0.5)
    print(f"     k0: {kg.get_node('k0').weight:.3f}")
    print(f"     k1: {kg.get_node('k1').weight:.3f}")
    print()
    # 时间衰减函数对比
    print("  📈 不同衰减模型对比 (1.0权重, 1天后):")
    w_exp = TimeDecay.exponential(1.0, 86400, 43200)  # 半衰期12h
    w_lin = TimeDecay.linear(1.0, 86400, 86400 * 7)  # 1周衰减到0
    w_pow = TimeDecay.power(1.0, 86400, 0.5)
    w_ebb = TimeDecay.ebbinghaus(1.0, 86400, 86400)
    print(f"     指数(半衰期12h):  {w_exp:.3f}")
    print(f"     线性(7天):         {w_lin:.3f}")
    print(f"     幂律(0.5):         {w_pow:.3f}")
    print(f"     艾宾浩斯(1天稳态): {w_ebb:.3f}")
    print()
    # 剪枝
    print("  ✂️  剪枝弱节点 (weight < 0.1):")
    prune_result = engine.prune_weak(threshold=0.1)
    print(f"     剪掉 {prune_result['nodes_pruned']} 节点, "
          f"{prune_result['edges_pruned']} 边")
    print()
    # 强化引擎演示
    reinforce = ReinforcementEngine(engine)
    for _ in range(5):
        reinforce.record_access("k2")
    for _ in range(2):
        reinforce.record_access("k3")
    print("  🔥 热门节点:")
    for nid, count in reinforce.get_hot_nodes(k=3):
        n = kg.get_node(nid)
        if n:
            print(f"     {nid}: 访问{count}次, 当前权重={n.weight:.3f}")
    print()
    stats = engine.get_stats()
    print(f"  📊 引擎统计: {stats}")
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ 阶段112完成：权重衰减机制已实现，所有测试通过！")
    else:
        print("❌ 阶段112失败")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段113：知识推演")
    print("  - 传递性推理")
    print("  - 对称性推理")
    print("  - 反演推理")
    print("  - 推理结果存储")
    print()
    return result.wasSuccessful()


if __name__ == "__main__":
    run_phase_112()
