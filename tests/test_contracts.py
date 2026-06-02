import pytest
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from contracts import (
    ModuleRegistry, ModuleInfo, ModuleStatus,
    EventBus, EventPriority, SystemEvents,
    ConfigCenter,
    ContractValidator, ContractTest
)


# ==================== ModuleRegistry Tests ====================

class TestModuleRegistry:
    def setup_method(self):
        """每个测试前清理注册表"""
        # 注意：由于 ModuleRegistry 使用类变量，需要手动清理
        for name in list(ModuleRegistry.get_all().keys()):
            ModuleRegistry.unregister(name)

    def test_register_module(self):
        info = ModuleInfo(
            name="test_module",
            version="1.0.0",
            layer=3,
            dependencies=[],
            interfaces=["ITest"],
            company="TestCorp"
        )
        assert ModuleRegistry.register(info) is True

    def test_register_duplicate_fails(self):
        info = ModuleInfo(
            name="dup_module",
            version="1.0.0",
            layer=3,
            dependencies=[],
            interfaces=["ITest"],
            company="TestCorp"
        )
        ModuleRegistry.register(info)
        assert ModuleRegistry.register(info) is False

    def test_unregister(self):
        info = ModuleInfo(
            name="unreg_module",
            version="1.0.0",
            layer=3,
            dependencies=[],
            interfaces=["ITest"],
            company="TestCorp"
        )
        ModuleRegistry.register(info)
        assert ModuleRegistry.unregister("unreg_module") is True
        assert ModuleRegistry.unregister("unreg_module") is False

    def test_get_module(self):
        info = ModuleInfo(
            name="get_module",
            version="1.0.0",
            layer=3,
            dependencies=[],
            interfaces=["ITest"],
            company="TestCorp"
        )
        ModuleRegistry.register(info)
        retrieved = ModuleRegistry.get("get_module")
        assert retrieved is not None
        assert retrieved.name == "get_module"

    def test_get_by_layer(self):
        ModuleRegistry.register(ModuleInfo(
            name="layer1", version="1.0", layer=1,
            dependencies=[], interfaces=["I"], company="C"
        ))
        ModuleRegistry.register(ModuleInfo(
            name="layer2", version="1.0", layer=2,
            dependencies=[], interfaces=["I"], company="C"
        ))
        layer1 = ModuleRegistry.get_by_layer(1)
        assert len(layer1) == 1
        assert layer1[0].name == "layer1"

    def test_get_dependencies(self):
        ModuleRegistry.register(ModuleInfo(
            name="dep_a", version="1.0", layer=1,
            dependencies=[], interfaces=["I"], company="C"
        ))
        ModuleRegistry.register(ModuleInfo(
            name="dep_b", version="1.0", layer=2,
            dependencies=["dep_a"], interfaces=["I"], company="C"
        ))
        deps = ModuleRegistry.get_dependencies("dep_b")
        assert deps == ["dep_a"]

    def test_get_all_dependencies(self):
        ModuleRegistry.register(ModuleInfo(
            name="a", version="1.0", layer=1,
            dependencies=[], interfaces=["I"], company="C"
        ))
        ModuleRegistry.register(ModuleInfo(
            name="b", version="1.0", layer=2,
            dependencies=["a"], interfaces=["I"], company="C"
        ))
        ModuleRegistry.register(ModuleInfo(
            name="c", version="1.0", layer=3,
            dependencies=["b"], interfaces=["I"], company="C"
        ))
        all_deps = ModuleRegistry.get_all_dependencies("c")
        assert "a" in all_deps
        assert "b" in all_deps

    def test_check_circular_dependencies(self):
        ModuleRegistry.register(ModuleInfo(
            name="circ_a", version="1.0", layer=1,
            dependencies=["circ_b"], interfaces=["I"], company="C"
        ))
        ModuleRegistry.register(ModuleInfo(
            name="circ_b", version="1.0", layer=1,
            dependencies=["circ_a"], interfaces=["I"], company="C"
        ))
        cycles = ModuleRegistry.check_circular_dependencies()
        assert len(cycles) >= 1

    def test_get_init_order(self):
        ModuleRegistry.register(ModuleInfo(
            name="order_a", version="1.0", layer=1,
            dependencies=[], interfaces=["I"], company="C"
        ))
        ModuleRegistry.register(ModuleInfo(
            name="order_b", version="1.0", layer=2,
            dependencies=["order_a"], interfaces=["I"], company="C"
        ))
        order = ModuleRegistry.get_init_order()
        assert order.index("order_a") < order.index("order_b")

    def test_update_status(self):
        ModuleRegistry.register(ModuleInfo(
            name="status_mod", version="1.0", layer=1,
            dependencies=[], interfaces=["I"], company="C"
        ))
        assert ModuleRegistry.update_status("status_mod", ModuleStatus.READY)
        mod = ModuleRegistry.get("status_mod")
        assert mod.status == ModuleStatus.READY

    def test_check_all_ready(self):
        ModuleRegistry.register(ModuleInfo(
            name="ready1", version="1.0", layer=1,
            dependencies=[], interfaces=["I"], company="C"
        ))
        ModuleRegistry.register(ModuleInfo(
            name="ready2", version="1.0", layer=1,
            dependencies=[], interfaces=["I"], company="C"
        ))
        assert not ModuleRegistry.check_all_ready()
        ModuleRegistry.update_status("ready1", ModuleStatus.READY)
        ModuleRegistry.update_status("ready2", ModuleStatus.READY)
        assert ModuleRegistry.check_all_ready()

    def test_get_dependency_graph(self):
        ModuleRegistry.register(ModuleInfo(
            name="graph_a", version="1.0", layer=1,
            dependencies=[], interfaces=["I"], company="C"
        ))
        graph = ModuleRegistry.get_dependency_graph()
        assert "modules" in graph
        assert "init_order" in graph


# ==================== EventBus Tests ====================

class TestEventBus:
    def setup_method(self):
        EventBus.clear_history()

    def test_subscribe_and_publish(self):
        received = []
        def handler(data):
            received.append(data)

        EventBus.subscribe("test.event", handler)
        EventBus.publish("test.event", {"msg": "hello"})
        assert len(received) == 1
        assert received[0]["msg"] == "hello"

    def test_unsubscribe(self):
        received = []
        def handler(data):
            received.append(data)

        EventBus.subscribe("test.unsub", handler)
        EventBus.publish("test.unsub", {"a": 1})
        assert len(received) == 1

        EventBus.unsubscribe("test.unsub", handler)
        EventBus.publish("test.unsub", {"a": 2})
        assert len(received) == 1  # 不再接收

    def test_priority_order(self):
        order = []
        def high_handler(data):
            order.append("high")
        def low_handler(data):
            order.append("low")

        EventBus.subscribe("test.priority", low_handler, EventPriority.LOW)
        EventBus.subscribe("test.priority", high_handler, EventPriority.HIGH)
        EventBus.publish("test.priority", {})
        assert order == ["high", "low"]

    def test_filter(self):
        received = []
        def handler(data):
            received.append(data)

        EventBus.subscribe("test.filter", handler, filter_fn=lambda d: d.get("type") == "A")
        EventBus.publish("test.filter", {"type": "A"})
        EventBus.publish("test.filter", {"type": "B"})
        assert len(received) == 1

    def test_publish_sync(self):
        def handler(data):
            data["response"] = "ok"

        EventBus.subscribe("test.sync", handler)
        result = EventBus.publish_sync("test.sync", {"request": "test"})
        assert result is not None

    def test_event_history(self):
        EventBus.publish("test.history", {"a": 1})
        EventBus.publish("test.history", {"a": 2})
        history = EventBus.get_event_history("test.history")
        assert len(history) == 2

    def test_get_stats(self):
        EventBus.publish("test.stats", {})
        stats = EventBus.get_stats()
        assert stats["total_event_types"] >= 1

    def test_multiple_subscribers(self):
        count = [0]
        def handler1(data):
            count[0] += 1
        def handler2(data):
            count[0] += 1

        EventBus.subscribe("test.multi", handler1)
        EventBus.subscribe("test.multi", handler2)
        EventBus.publish("test.multi", {})
        assert count[0] == 2


# ==================== ConfigCenter Tests ====================

class TestConfigCenter:
    def setup_method(self):
        ConfigCenter.reset()

    def test_get_default(self):
        value = ConfigCenter.get("agent.loop_delay")
        assert value == 1.0

    def test_get_with_default(self):
        value = ConfigCenter.get("nonexistent.key", default="fallback")
        assert value == "fallback"

    def test_set_and_get(self):
        ConfigCenter.set("test.key", "value")
        assert ConfigCenter.get("test.key") == "value"

    def test_watch(self):
        changes = []
        def callback(key, old, new):
            changes.append((key, old, new))

        ConfigCenter.watch("test.watch", callback)
        ConfigCenter.set("test.watch", "new_value")
        assert len(changes) == 1
        assert changes[0][2] == "new_value"

    def test_unwatch(self):
        changes = []
        def callback(key, old, new):
            changes.append((key, old, new))

        ConfigCenter.watch("test.unwatch", callback)
        ConfigCenter.set("test.unwatch", "v1")
        assert len(changes) == 1

        ConfigCenter.unwatch("test.unwatch", callback)
        ConfigCenter.set("test.unwatch", "v2")
        assert len(changes) == 1

    def test_get_all(self):
        all_configs = ConfigCenter.get_all()
        assert len(all_configs) > 0

    def test_get_all_with_prefix(self):
        nlp_configs = ConfigCenter.get_all(prefix="nlp.")
        assert all(k.startswith("nlp.") for k in nlp_configs.keys())

    def test_history(self):
        ConfigCenter.set("test.history", "v1")
        ConfigCenter.set("test.history", "v2")
        history = ConfigCenter.get_history("test.history")
        assert len(history) == 2

    def test_environment(self):
        ConfigCenter.initialize(env="test")
        assert ConfigCenter.get_environment() == "test"

    def test_stats(self):
        stats = ConfigCenter.get_stats()
        assert "total_configs" in stats
        assert "total_watchers" in stats


# ==================== ContractValidator Tests ====================

class TestContractValidator:
    def test_valid_implementation(self):
        from abc import ABC, abstractmethod

        class ITest(ABC):
            @abstractmethod
            def do_something(self, x: int) -> str: ...

        class TestImpl(ITest):
            def do_something(self, x: int) -> str:
                return str(x)

        validator = ContractValidator(ITest)
        result = validator.validate_implementation(TestImpl)
        assert result["valid"] is True
        assert result["error_count"] == 0

    def test_missing_method(self):
        from abc import ABC, abstractmethod

        class ITest2(ABC):
            @abstractmethod
            def required_method(self) -> None: ...

        class BadImpl(ITest2):
            pass

        validator = ContractValidator(ITest2)
        result = validator.validate_implementation(BadImpl)
        assert result["valid"] is False
        assert "required_method" in str(result["errors"])

    def test_not_subclass(self):
        from abc import ABC

        class ITest3(ABC):
            pass

        class NotImpl:
            pass

        validator = ContractValidator(ITest3)
        result = validator.validate_implementation(NotImpl)
        assert result["valid"] is False


# ==================== Integration Tests ====================

class TestContractsIntegration:
    def test_full_module_lifecycle(self):
        """测试完整的模块生命周期"""
        # 1. 注册模块
        info = ModuleInfo(
            name="lifecycle_mod",
            version="1.0.0",
            layer=3,
            dependencies=[],
            interfaces=["ITest"],
            company="TestCorp"
        )
        assert ModuleRegistry.register(info)

        # 2. 更新状态
        ModuleRegistry.update_status("lifecycle_mod", ModuleStatus.READY)

        # 3. 发布事件
        received = []
        EventBus.subscribe(SystemEvents.MODULE_READY, lambda d: received.append(d))
        EventBus.publish(SystemEvents.MODULE_READY, {"module": "lifecycle_mod"})
        assert len(received) == 1

        # 4. 设置配置
        ConfigCenter.set("lifecycle_mod.setting", "value")
        assert ConfigCenter.get("lifecycle_mod.setting") == "value"

        # 5. 注销模块
        assert ModuleRegistry.unregister("lifecycle_mod")

    def test_dependency_resolution(self):
        """测试依赖解析"""
        ModuleRegistry.register(ModuleInfo(
            name="base", version="1.0", layer=1,
            dependencies=[], interfaces=["I"], company="C"
        ))
        ModuleRegistry.register(ModuleInfo(
            name="middle", version="1.0", layer=2,
            dependencies=["base"], interfaces=["I"], company="C"
        ))
        ModuleRegistry.register(ModuleInfo(
            name="top", version="1.0", layer=3,
            dependencies=["middle"], interfaces=["I"], company="C"
        ))

        init_order = ModuleRegistry.get_init_order()
        assert init_order.index("base") < init_order.index("middle")
        assert init_order.index("middle") < init_order.index("top")
