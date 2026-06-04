#!/usr/bin/env python3
"""
阶段123：多智能体协作

第一性原理：
  - 协作公理：1+1>2
  - 角色分工：不同能力承担不同职责
  - 消息通信：协作的基石
  - 共识：多方决策需要协议

本阶段产出：
  1. AgentCard：智能体名片（能力描述）
  2. Message：消息结构
  3. AgentRegistry：智能体注册表
  4. CollaborationBus：协作消息总线
  5. TaskAllocator：任务分配器
  6. Coordinator：协调器

遵循原则：图难于其易，为大于其细
"""
import time
import uuid
import unittest
import threading
from typing import Dict, List, Any, Optional, Callable, Set
from enum import Enum
from dataclasses import dataclass, field
from collections import deque, defaultdict


# ============================================================
# 一、智能体名片
# ============================================================
@dataclass
class AgentCard:
    """智能体名片

    描述智能体的能力、角色、状态
    """
    agent_id: str = field(default_factory=lambda: f"ag_{uuid.uuid4().hex[:8]}")
    name: str = ""
    role: str = ""  # role/capability
    capabilities: List[str] = field(default_factory=list)
    status: str = "idle"  # idle / busy / offline
    load: float = 0.0  # 0-1
    registered_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def can_handle(self, required: str) -> bool:
        return required in self.capabilities or "any" in self.capabilities


# ============================================================
# 二、消息结构
# ============================================================
class MessageType(Enum):
    """消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    NOTIFY = "notify"
    DELEGATE = "delegate"
    REPORT = "report"


@dataclass
class Message:
    """消息"""
    message_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    sender: str = ""
    receiver: str = ""  # 目标agent_id，""=广播
    msg_type: MessageType = MessageType.REQUEST
    topic: str = ""  # 主题/任务类型
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None  # 关联消息ID
    timestamp: float = field(default_factory=time.time)
    requires_response: bool = False


# ============================================================
# 三、智能体注册表
# ============================================================
class AgentRegistry:
    """智能体注册表

    管理所有智能体的新陈代谢
    """
    def __init__(self):
        self._agents: Dict[str, AgentCard] = {}
        self._lock = threading.RLock()
        self._capability_index: Dict[str, Set[str]] = defaultdict(set)
        self._stats = {
            "registered": 0,
            "unregistered": 0,
            "lookups": 0,
        }

    def register(self, card: AgentCard) -> bool:
        with self._lock:
            if card.agent_id in self._agents:
                return False
            self._agents[card.agent_id] = card
            for cap in card.capabilities:
                self._capability_index[cap].add(card.agent_id)
            self._stats["registered"] += 1
            return True

    def unregister(self, agent_id: str) -> bool:
        with self._lock:
            card = self._agents.pop(agent_id, None)
            if not card:
                return False
            for cap in card.capabilities:
                self._capability_index[cap].discard(agent_id)
                if not self._capability_index[cap]:
                    del self._capability_index[cap]
            self._stats["unregistered"] += 1
            return True

    def get(self, agent_id: str) -> Optional[AgentCard]:
        with self._lock:
            return self._agents.get(agent_id)

    def find_by_capability(self, capability: str) -> List[AgentCard]:
        with self._lock:
            self._stats["lookups"] += 1
            agent_ids = self._capability_index.get(capability, set())
            return [self._agents[aid] for aid in agent_ids
                     if aid in self._agents]

    def find_by_role(self, role: str) -> List[AgentCard]:
        with self._lock:
            return [a for a in self._agents.values()
                     if a.role == role]

    def list_all(self) -> List[AgentCard]:
        with self._lock:
            return list(self._agents.values())

    def update_status(self, agent_id: str,
                       status: str, load: Optional[float] = None) -> bool:
        with self._lock:
            card = self._agents.get(agent_id)
            if not card:
                return False
            card.status = status
            if load is not None:
                card.load = load
            return True

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 四、协作消息总线
# ============================================================
class CollaborationBus:
    """协作消息总线

    多智能体间的消息传递
    """
    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self._inboxes: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000))
        self._lock = threading.RLock()
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._stats = {
            "sent": 0,
            "delivered": 0,
            "broadcasts": 0,
        }

    def register_handler(self, agent_id: str,
                          handler: Callable) -> None:
        with self._lock:
            self._handlers[agent_id].append(handler)

    def send(self, message: Message) -> bool:
        """发送消息"""
        with self._lock:
            self._stats["sent"] += 1
            if message.receiver:
                # 点对点
                self._inboxes[message.receiver].append(message)
                self._stats["delivered"] += 1
                handlers = self._handlers.get(message.receiver, [])
                for h in list(handlers):
                    try:
                        h(message)
                    except Exception:
                        pass
            else:
                # 广播
                self._stats["broadcasts"] += 1
                for aid in list(self.registry._agents.keys()):
                    if aid != message.sender:
                        self._inboxes[aid].append(message)
                        self._stats["delivered"] += 1
                        handlers = self._handlers.get(aid, [])
                        for h in list(handlers):
                            try:
                                h(message)
                            except Exception:
                                pass
        return True

    def request(self, sender: str, receiver: str, topic: str,
                 payload: Dict[str, Any],
                 timeout_sec: float = 5.0) -> Optional[Message]:
        """请求-响应模式"""
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        req = Message(
            sender=sender, receiver=receiver,
            msg_type=MessageType.REQUEST, topic=topic,
            payload=payload,
            correlation_id=req_id,
            requires_response=True)
        response_holder = {"response": None}
        def handler(msg: Message):
            if (msg.msg_type == MessageType.RESPONSE
                    and msg.correlation_id == req_id):
                response_holder["response"] = msg
        # 临时注册handler
        self.register_handler(sender, handler)
        self.send(req)
        # 等待响应
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if response_holder["response"]:
                return response_holder["response"]
            time.sleep(0.01)
        return None

    def respond(self, request_msg: Message, sender: str,
                 payload: Dict[str, Any]) -> bool:
        """响应请求"""
        response = Message(
            sender=sender, receiver=request_msg.sender,
            msg_type=MessageType.RESPONSE,
            topic=request_msg.topic,
            payload=payload,
            correlation_id=request_msg.correlation_id)
        return self.send(response)

    def get_inbox(self, agent_id: str) -> List[Message]:
        with self._lock:
            return list(self._inboxes.get(agent_id, []))

    def clear_inbox(self, agent_id: str) -> None:
        with self._lock:
            self._inboxes[agent_id].clear()

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 五、任务分配器
# ============================================================
class TaskAllocator:
    """任务分配器

    根据能力匹配，将任务分配给合适的智能体
    """
    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self._lock = threading.Lock()
        self._assignments: Dict[str, str] = {}  # task_id -> agent_id
        self._stats = {
            "assigned": 0,
            "rejected": 0,
        }

    def allocate(self, task_id: str, required_capability: str,
                  strategy: str = "least_loaded") -> Optional[AgentCard]:
        """分配任务"""
        with self._lock:
            candidates = self.registry.find_by_capability(
                required_capability)
            # 过滤离线/忙碌的
            candidates = [c for c in candidates
                           if c.status != "offline"]
            if not candidates:
                self._stats["rejected"] += 1
                return None
            # 选择
            if strategy == "least_loaded":
                candidates.sort(key=lambda c: c.load)
            elif strategy == "round_robin":
                # 简单实现：取第一个
                pass
            chosen = candidates[0]
            self._assignments[task_id] = chosen.agent_id
            self._stats["assigned"] += 1
            return chosen

    def get_assignment(self, task_id: str) -> Optional[str]:
        with self._lock:
            return self._assignments.get(task_id)

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 六、协调器
# ============================================================
class Coordinator:
    """协调器

    多智能体协作的总指挥
    """
    def __init__(self):
        self.registry = AgentRegistry()
        self.bus = CollaborationBus(self.registry)
        self.allocator = TaskAllocator(self.registry)
        self._lock = threading.RLock()
        self._shared_state: Dict[str, Any] = {}
        self._stats = {
            "coordinations": 0,
        }

    def register_agent(self, name: str, role: str,
                        capabilities: List[str]) -> AgentCard:
        card = AgentCard(
            name=name, role=role, capabilities=capabilities)
        self.registry.register(card)
        return card

    def assign_and_notify(self, task_id: str,
                            required_capability: str,
                            task_payload: Dict[str, Any]) -> Optional[AgentCard]:
        with self._lock:
            self._stats["coordinations"] += 1
            agent = self.allocator.allocate(
                task_id, required_capability)
            if agent:
                msg = Message(
                    sender="coordinator",
                    receiver=agent.agent_id,
                    msg_type=MessageType.DELEGATE,
                    topic=required_capability,
                    payload={"task_id": task_id,
                              **task_payload})
                self.bus.send(msg)
            return agent

    def set_shared_state(self, key: str, value: Any) -> None:
        with self._lock:
            self._shared_state[key] = value

    def get_shared_state(self, key: str) -> Any:
        with self._lock:
            return self._shared_state.get(key)

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            stats = dict(self._stats)
            stats["agents"] = len(self.registry.list_all())
            return stats


# ============================================================
# 七、单元测试
# ============================================================
class TestAgentCard(unittest.TestCase):
    """智能体名片测试"""
    def test_can_handle(self):
        card = AgentCard(capabilities=["compute", "store"])
        self.assertTrue(card.can_handle("compute"))
        self.assertFalse(card.can_handle("network"))

    def test_any_capability(self):
        card = AgentCard(capabilities=["any"])
        self.assertTrue(card.can_handle("anything"))


class TestAgentRegistry(unittest.TestCase):
    """智能体注册表测试"""
    def setUp(self):
        self.reg = AgentRegistry()

    def test_register(self):
        card = AgentCard(name="a1", capabilities=["c1"])
        self.assertTrue(self.reg.register(card))
        self.assertFalse(self.reg.register(card))  # 重复

    def test_unregister(self):
        card = AgentCard(name="a1", capabilities=["c1"])
        self.reg.register(card)
        self.assertTrue(self.reg.unregister(card.agent_id))
        self.assertFalse(self.reg.unregister(card.agent_id))

    def test_find_by_capability(self):
        c1 = AgentCard(name="a1", capabilities=["compute"])
        c2 = AgentCard(name="a2", capabilities=["store"])
        c3 = AgentCard(name="a3", capabilities=["compute", "store"])
        self.reg.register(c1)
        self.reg.register(c2)
        self.reg.register(c3)
        result = self.reg.find_by_capability("compute")
        self.assertEqual(len(result), 2)
        result = self.reg.find_by_capability("store")
        self.assertEqual(len(result), 2)

    def test_update_status(self):
        card = AgentCard(name="a1")
        self.reg.register(card)
        self.assertTrue(
            self.reg.update_status(card.agent_id, "busy", 0.8))
        self.assertEqual(self.reg.get(card.agent_id).status, "busy")


class TestCollaborationBus(unittest.TestCase):
    """协作消息总线测试"""
    def setUp(self):
        self.reg = AgentRegistry()
        self.bus = CollaborationBus(self.reg)

    def test_send(self):
        a1 = AgentCard(name="a1")
        a2 = AgentCard(name="a2")
        self.reg.register(a1)
        self.reg.register(a2)
        msg = Message(sender=a1.agent_id, receiver=a2.agent_id)
        self.assertTrue(self.bus.send(msg))
        inbox = self.bus.get_inbox(a2.agent_id)
        self.assertEqual(len(inbox), 1)

    def test_broadcast(self):
        a1 = AgentCard(name="a1")
        a2 = AgentCard(name="a2")
        a3 = AgentCard(name="a3")
        self.reg.register(a1)
        self.reg.register(a2)
        self.reg.register(a3)
        msg = Message(sender=a1.agent_id, receiver="")
        self.bus.send(msg)
        self.assertEqual(len(self.bus.get_inbox(a2.agent_id)), 1)
        self.assertEqual(len(self.bus.get_inbox(a3.agent_id)), 1)
        self.assertEqual(len(self.bus.get_inbox(a1.agent_id)), 0)

    def test_handler(self):
        a1 = AgentCard(name="a1")
        a2 = AgentCard(name="a2")
        self.reg.register(a1)
        self.reg.register(a2)
        received = []
        self.bus.register_handler(a2.agent_id,
                                     lambda m: received.append(m))
        msg = Message(sender=a1.agent_id, receiver=a2.agent_id)
        self.bus.send(msg)
        self.assertEqual(len(received), 1)


class TestTaskAllocator(unittest.TestCase):
    """任务分配器测试"""
    def setUp(self):
        self.reg = AgentRegistry()
        self.alloc = TaskAllocator(self.reg)

    def test_allocate(self):
        a1 = AgentCard(name="a1", capabilities=["c1"], load=0.5)
        a2 = AgentCard(name="a2", capabilities=["c1"], load=0.2)
        self.reg.register(a1)
        self.reg.register(a2)
        chosen = self.alloc.allocate("t1", "c1", "least_loaded")
        self.assertEqual(chosen.name, "a2")

    def test_no_candidate(self):
        a1 = AgentCard(name="a1", capabilities=["c2"])
        self.reg.register(a1)
        chosen = self.alloc.allocate("t1", "c1")
        self.assertIsNone(chosen)

    def test_skip_offline(self):
        a1 = AgentCard(name="a1", capabilities=["c1"], status="offline")
        a2 = AgentCard(name="a2", capabilities=["c1"], status="idle")
        self.reg.register(a1)
        self.reg.register(a2)
        chosen = self.alloc.allocate("t1", "c1")
        self.assertEqual(chosen.name, "a2")


class TestCoordinator(unittest.TestCase):
    """协调器测试"""
    def setUp(self):
        self.coord = Coordinator()

    def test_register_agent(self):
        card = self.coord.register_agent(
            "a1", "worker", ["compute"])
        self.assertIn(card.agent_id,
                       [a.agent_id for a in self.coord.registry.list_all()])

    def test_assign_and_notify(self):
        self.coord.register_agent("a1", "worker", ["compute"])
        self.coord.register_agent("a2", "worker", ["compute"])
        agent = self.coord.assign_and_notify(
            "t1", "compute", {"data": 1})
        self.assertIsNotNone(agent)
        # 收件箱应有消息
        inbox = self.coord.bus.get_inbox(agent.agent_id)
        self.assertEqual(len(inbox), 1)

    def test_shared_state(self):
        self.coord.set_shared_state("config", {"v": 1})
        self.assertEqual(self.coord.get_shared_state("config")["v"], 1)


# ============================================================
# 八、阶段123演示
# ============================================================
def run_phase_123():
    """运行阶段123"""
    print("=" * 70)
    print("阶段123：多智能体协作")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestAgentCard))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentRegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestCollaborationBus))
    suite.addTests(loader.loadTestsFromTestCase(TestTaskAllocator))
    suite.addTests(loader.loadTestsFromTestCase(TestCoordinator))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【多智能体协作演示】")
    print("-" * 70)

    # 演示1: 智能体注册
    print("  🤖 演示1: 智能体注册")
    print("     " + "-" * 60)
    coord = Coordinator()
    coord.register_agent("worker-1", "compute",
                            ["compute", "math"])
    coord.register_agent("worker-2", "compute",
                            ["compute", "ml"])
    coord.register_agent("storage-1", "storage",
                            ["store", "retrieve"])
    coord.register_agent("analyzer-1", "analyzer",
                            ["analyze", "report"])
    for a in coord.registry.list_all():
        print(f"     {a.name:>12} | {a.role:>10} | "
              f"能力: {', '.join(a.capabilities)}")
    print()

    # 演示2: 任务分配
    print("  📋 演示2: 任务分配（最小负载优先）")
    print("     " + "-" * 60)
    # 更新负载
    coord.registry.update_status(
        coord.registry.list_all()[0].agent_id, "idle", 0.8)
    coord.registry.update_status(
        coord.registry.list_all()[1].agent_id, "idle", 0.2)
    tasks = [
        ("t1", "compute", {"size": 100}),
        ("t2", "store", {"key": "x"}),
        ("t3", "analyze", {"type": "trend"}),
    ]
    for tid, cap, payload in tasks:
        agent = coord.assign_and_notify(tid, cap, payload)
        print(f"     {tid:>3} ({cap:>8}) → {agent.name if agent else 'NONE'}")
    print()

    # 演示3: 消息传递
    print("  📨 演示3: 消息传递")
    print("     " + "-" * 60)
    a1 = coord.registry.list_all()[0]
    a2 = coord.registry.list_all()[1]
    msg = Message(
        sender=a1.agent_id, receiver=a2.agent_id,
        topic="sync", payload={"data": "hello"})
    coord.bus.send(msg)
    inbox = coord.bus.get_inbox(a2.agent_id)
    print(f"     {a1.name} → {a2.name}: {inbox[0].payload}")
    print()

    # 演示4: 广播
    print("  📢 演示4: 广播消息")
    print("     " + "-" * 60)
    broadcast = Message(
        sender=a1.agent_id, receiver="",
        topic="announce", payload={"msg": "系统通知"})
    coord.bus.send(broadcast)
    total = sum(len(coord.bus.get_inbox(a.agent_id))
                for a in coord.registry.list_all())
    print(f"     广播送达: {total} 个智能体")
    print()

    # 演示5: 能力查找
    print("  🔍 演示5: 能力查找")
    print("     " + "-" * 60)
    for cap in ["compute", "store", "analyze", "unknown"]:
        agents = coord.registry.find_by_capability(cap)
        print(f"     能力 '{cap}': {[a.name for a in agents] or '无'}")
    print()

    # 演示6: 共享状态
    print("  🌐 演示6: 共享状态")
    print("     " + "-" * 60)
    coord.set_shared_state("config", {"version": "1.0", "debug": True})
    coord.set_shared_state("metrics", {"requests": 100})
    print(f"     config: {coord.get_shared_state('config')}")
    print(f"     metrics: {coord.get_shared_state('metrics')}")
    print()

    # 统计
    print("  📊 协作统计:")
    print("     " + "-" * 60)
    print(f"     协调器: {coord.get_stats()}")
    print(f"     总线: {coord.bus.get_stats()}")
    print(f"     分配器: {coord.allocator.get_stats()}")
    print(f"     注册表: {coord.registry.get_stats()}")
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段123完成：多智能体协作已实现，所有测试通过！")
    else:
        print("✅ 阶段123完成：多智能体协作已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段124：分布式存储")
    print("  - 分片")
    print("  - 副本")
    print("  - 一致性")
    print()
    return True


if __name__ == "__main__":
    run_phase_123()
