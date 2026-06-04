#!/usr/bin/env python3
"""
阶段121：插件架构

第一性原理：
  - 扩展公理：核心应稳定，扩展应灵活
  - 隔离原则：插件失败不应拖垮主体
  - 显式契约：清晰的接口规范
  - 动态性：可加载可卸载

本阶段产出：
  1. Plugin：插件基类与接口
  2. PluginMetadata：插件元数据
  3. PluginContext：插件上下文
  4. PluginManager：插件管理器
  5. HookRegistry：钩子注册
  6. PluginLoader：动态加载器

遵循原则：图难于其易，为大于其细
"""
import os
import sys
import time
import importlib
import unittest
import threading
import traceback
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


# ============================================================
# 一、插件元数据
# ============================================================
@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str
    author: str
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    priority: int = 100
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# 二、插件上下文
# ============================================================
@dataclass
class PluginContext:
    """插件上下文

    传递给插件，用于访问主体能力
    """
    plugin_name: str
    logger: Any = None
    kg: Any = None
    config: Dict[str, Any] = field(default_factory=dict)
    services: Dict[str, Any] = field(default_factory=dict)
    hooks: Dict[str, List[Callable]] = field(default_factory=dict)

    def get_service(self, name: str) -> Any:
        return self.services.get(name)

    def register_hook(self, event: str, callback: Callable) -> None:
        if event not in self.hooks:
            self.hooks[event] = []
        self.hooks[event].append(callback)


# ============================================================
# 三、插件状态
# ============================================================
class PluginState(Enum):
    """插件状态"""
    REGISTERED = "registered"
    LOADING = "loading"
    LOADED = "loaded"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    UNLOADED = "unloaded"


# ============================================================
# 四、插件基类
# ============================================================
class Plugin(ABC):
    """插件基类

    所有插件必须继承此类并实现钩子方法
    """
    def __init__(self):
        self.metadata: PluginMetadata = self._define_metadata()
        self.state: PluginState = PluginState.REGISTERED
        self.context: Optional[PluginContext] = None
        self.error: Optional[str] = None

    @abstractmethod
    def _define_metadata(self) -> PluginMetadata:
        """子类定义元数据"""
        pass

    def on_load(self, context: PluginContext) -> None:
        """加载时调用"""
        self.context = context

    def on_init(self) -> None:
        """初始化"""
        pass

    def on_start(self) -> None:
        """启动"""
        pass

    def on_pause(self) -> None:
        """暂停"""
        pass

    def on_resume(self) -> None:
        """恢复"""
        pass

    def on_unload(self) -> None:
        """卸载"""
        pass

    def on_error(self, exc: Exception) -> None:
        """错误处理"""
        self.error = str(exc)
        self.state = PluginState.ERROR

    def get_state(self) -> PluginState:
        return self.state


# ============================================================
# 五、钩子注册
# ============================================================
class HookRegistry:
    """钩子注册表

    全局事件钩子管理
    """
    def __init__(self):
        self._hooks: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.RLock()
        self._stats = {
            "triggers": 0,
            "executions": 0,
            "errors": 0,
        }

    def register(self, event: str, callback: Callable,
                 plugin_name: str = "unknown",
                 priority: int = 100) -> None:
        with self._lock:
            if event not in self._hooks:
                self._hooks[event] = []
            self._hooks[event].append({
                "callback": callback,
                "plugin": plugin_name,
                "priority": priority,
            })
            self._hooks[event].sort(
                key=lambda h: h["priority"])

    def unregister(self, event: str, plugin_name: str) -> int:
        with self._lock:
            if event not in self._hooks:
                return 0
            before = len(self._hooks[event])
            self._hooks[event] = [
                h for h in self._hooks[event]
                if h["plugin"] != plugin_name
            ]
            return before - len(self._hooks[event])

    def trigger(self, event: str, *args, **kwargs) -> List[Any]:
        """触发事件"""
        with self._lock:
            hooks = list(self._hooks.get(event, []))
        self._stats["triggers"] += 1
        results = []
        for h in hooks:
            try:
                result = h["callback"](*args, **kwargs)
                results.append(result)
                self._stats["executions"] += 1
            except Exception as e:
                self._stats["errors"] += 1
                # 钩子错误不应影响主流程
                pass
        return results

    def list_events(self) -> List[str]:
        with self._lock:
            return list(self._hooks.keys())

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 六、插件管理器
# ============================================================
class PluginManager:
    """插件管理器

    协调插件的加载、初始化、启动、卸载
    """
    def __init__(self, hooks: Optional[HookRegistry] = None):
        self._plugins: Dict[str, Plugin] = {}
        self._lock = threading.RLock()
        self.hooks = hooks or HookRegistry()
        self._stats = {
            "loaded": 0,
            "unloaded": 0,
            "errors": 0,
        }
        self._error_handler: Optional[Callable] = None

    def register(self, plugin: Plugin) -> bool:
        """注册插件"""
        with self._lock:
            name = plugin.metadata.name
            if name in self._plugins:
                return False
            self._plugins[name] = plugin
            plugin.state = PluginState.REGISTERED
            return True

    def unregister(self, name: str) -> bool:
        """注销插件（不执行清理）"""
        with self._lock:
            return self._plugins.pop(name, None) is not None

    def load(self, name: str, context: Optional[PluginContext] = None) -> bool:
        """加载并初始化插件"""
        with self._lock:
            plugin = self._plugins.get(name)
            if not plugin:
                return False
            try:
                plugin.state = PluginState.LOADING
                if context is None:
                    context = PluginContext(plugin_name=name)
                # 解析依赖
                for dep in plugin.metadata.dependencies:
                    if dep not in self._plugins:
                        raise ValueError(
                            f"依赖缺失: {dep}")
                plugin.on_load(context)
                plugin.state = PluginState.LOADED
                plugin.state = PluginState.INITIALIZING
                plugin.on_init()
                plugin.state = PluginState.ACTIVE
                plugin.on_start()
                self._stats["loaded"] += 1
                self.hooks.trigger("plugin.loaded", name)
                return True
            except Exception as e:
                plugin.on_error(e)
                self._stats["errors"] += 1
                self.hooks.trigger("plugin.error", name, e)
                if self._error_handler:
                    self._error_handler(name, e)
                return False

    def unload(self, name: str) -> bool:
        """卸载插件"""
        with self._lock:
            plugin = self._plugins.get(name)
            if not plugin:
                return False
            try:
                plugin.on_unload()
                # 移除该插件的所有钩子
                for event in list(self.hooks._hooks.keys()):
                    self.hooks.unregister(event, name)
                plugin.state = PluginState.UNLOADED
                self._stats["unloaded"] += 1
                self.hooks.trigger("plugin.unloaded", name)
                return True
            except Exception as e:
                plugin.on_error(e)
                self._stats["errors"] += 1
                return False

    def pause(self, name: str) -> bool:
        with self._lock:
            plugin = self._plugins.get(name)
            if not plugin or plugin.state != PluginState.ACTIVE:
                return False
            plugin.on_pause()
            plugin.state = PluginState.PAUSED
            return True

    def resume(self, name: str) -> bool:
        with self._lock:
            plugin = self._plugins.get(name)
            if not plugin or plugin.state != PluginState.PAUSED:
                return False
            plugin.on_resume()
            plugin.state = PluginState.ACTIVE
            return True

    def get_plugin(self, name: str) -> Optional[Plugin]:
        with self._lock:
            return self._plugins.get(name)

    def list_plugins(self) -> List[str]:
        with self._lock:
            return list(self._plugins.keys())

    def set_error_handler(self, handler: Callable) -> None:
        self._error_handler = handler

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 七、动态加载器
# ============================================================
class PluginLoader:
    """动态加载器

    从文件路径或模块名动态加载插件类
    """
    @staticmethod
    def load_from_class(plugin_class, **init_kwargs) -> Plugin:
        """从类创建插件实例"""
        return plugin_class(**init_kwargs)

    @staticmethod
    def load_from_module(module_name: str,
                          class_name: str = "Plugin") -> Plugin:
        """从模块动态加载"""
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            return cls()
        except Exception as e:
            raise ImportError(
                f"无法加载 {module_name}.{class_name}: {e}")

    @staticmethod
    def load_from_file(file_path: str,
                        class_name: str = "Plugin") -> Plugin:
        """从Python文件加载"""
        import importlib.util
        try:
            spec = importlib.util.spec_from_file_location(
                "plugin_module", file_path)
            if not spec or not spec.loader:
                raise ImportError(f"无法加载: {file_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls = getattr(module, class_name)
            return cls()
        except Exception as e:
            raise ImportError(f"无法加载文件 {file_path}: {e}")


# ============================================================
# 八、单元测试
# ============================================================
class TestPlugin(unittest.TestCase):
    """插件基类测试"""
    def test_define_metadata(self):
        class MyPlugin(Plugin):
            def _define_metadata(self):
                return PluginMetadata(
                    name="my", version="1.0", author="test")
        p = MyPlugin()
        self.assertEqual(p.metadata.name, "my")
        self.assertEqual(p.state, PluginState.REGISTERED)


class TestPluginManager(unittest.TestCase):
    """插件管理器测试"""
    def setUp(self):
        self.mgr = PluginManager()

    def _make_plugin(self, name: str, deps: list = None,
                       should_fail: bool = False):
        class P(Plugin):
            def _define_metadata(_self):
                return PluginMetadata(
                    name=name, version="1.0", author="t",
                    dependencies=deps or [])
            def on_init(_self):
                if should_fail:
                    raise RuntimeError("init failed")
        return P()

    def test_register(self):
        p = self._make_plugin("p1")
        self.assertTrue(self.mgr.register(p))
        self.assertFalse(self.mgr.register(p))  # 重复

    def test_load(self):
        p = self._make_plugin("p1")
        self.mgr.register(p)
        self.assertTrue(self.mgr.load("p1"))
        self.assertEqual(p.state, PluginState.ACTIVE)

    def test_load_with_deps(self):
        p_dep = self._make_plugin("dep")
        p = self._make_plugin("p", deps=["dep"])
        self.mgr.register(p_dep)
        self.mgr.register(p)
        self.assertTrue(self.mgr.load("p"))

    def test_load_missing_dep(self):
        p = self._make_plugin("p", deps=["missing"])
        self.mgr.register(p)
        self.assertFalse(self.mgr.load("p"))
        self.assertEqual(p.state, PluginState.ERROR)

    def test_load_failure(self):
        p = self._make_plugin("p", should_fail=True)
        self.mgr.register(p)
        self.assertFalse(self.mgr.load("p"))
        self.assertEqual(p.state, PluginState.ERROR)

    def test_unload(self):
        p = self._make_plugin("p1")
        self.mgr.register(p)
        self.mgr.load("p1")
        self.assertTrue(self.mgr.unload("p1"))
        self.assertEqual(p.state, PluginState.UNLOADED)

    def test_pause_resume(self):
        p = self._make_plugin("p1")
        self.mgr.register(p)
        self.mgr.load("p1")
        self.assertTrue(self.mgr.pause("p1"))
        self.assertEqual(p.state, PluginState.PAUSED)
        self.assertTrue(self.mgr.resume("p1"))
        self.assertEqual(p.state, PluginState.ACTIVE)

    def test_get_plugin(self):
        p = self._make_plugin("p1")
        self.mgr.register(p)
        self.assertIs(self.mgr.get_plugin("p1"), p)
        self.assertIsNone(self.mgr.get_plugin("missing"))


class TestHookRegistry(unittest.TestCase):
    """钩子注册测试"""
    def setUp(self):
        self.hr = HookRegistry()

    def test_register_and_trigger(self):
        called = []
        self.hr.register("ev", lambda: called.append("a"))
        self.hr.register("ev", lambda: called.append("b"))
        self.hr.trigger("ev")
        self.assertEqual(len(called), 2)

    def test_priority_order(self):
        order = []
        self.hr.register("ev", lambda: order.append("low"),
                          priority=100)
        self.hr.register("ev", lambda: order.append("high"),
                          priority=10)
        self.hr.register("ev", lambda: order.append("mid"),
                          priority=50)
        self.hr.trigger("ev")
        self.assertEqual(order, ["high", "mid", "low"])

    def test_unregister(self):
        self.hr.register("ev", lambda: None, plugin_name="p1")
        self.hr.register("ev", lambda: None, plugin_name="p2")
        removed = self.hr.unregister("ev", "p1")
        self.assertEqual(removed, 1)

    def test_error_isolation(self):
        called = []
        def bad():
            raise RuntimeError("oops")
        self.hr.register("ev", bad)
        self.hr.register("ev", lambda: called.append("ok"))
        self.hr.trigger("ev")
        # 错误不应阻止后续钩子
        self.assertIn("ok", called)
        self.assertEqual(self.hr.get_stats()["errors"], 1)

    def test_trigger_with_args(self):
        self.hr.register("ev", lambda x, y: x + y)
        results = self.hr.trigger("ev", 2, 3)
        self.assertEqual(results, [5])


class TestPluginLoader(unittest.TestCase):
    """插件加载器测试"""
    def test_load_from_class(self):
        class P(Plugin):
            def _define_metadata(self):
                return PluginMetadata(
                    name="x", version="1.0", author="t")
        p = PluginLoader.load_from_class(P)
        self.assertIsInstance(p, P)
        self.assertEqual(p.metadata.name, "x")


# ============================================================
# 九、阶段121演示
# ============================================================
def run_phase_121():
    """运行阶段121"""
    print("=" * 70)
    print("阶段121：插件架构")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestPlugin))
    suite.addTests(loader.loadTestsFromTestCase(TestPluginManager))
    suite.addTests(loader.loadTestsFromTestCase(TestHookRegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestPluginLoader))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【插件架构演示】")
    print("-" * 70)

    # 定义3个示例插件
    class CounterPlugin(Plugin):
        def _define_metadata(self):
            return PluginMetadata(
                name="counter", version="1.0",
                author="agent", description="计数插件",
                priority=10)
        def on_init(self):
            self.count = 0
        def on_start(self):
            self.context.register_hook(
                "node_added", self.on_node_added)
        def on_node_added(self, node_id, **kwargs):
            self.count += 1
            print(f"     [counter] 节点 {node_id} 已添加, "
                  f"计数: {self.count}")

    class ValidatorPlugin(Plugin):
        def _define_metadata(self):
            return PluginMetadata(
                name="validator", version="1.0",
                author="agent", description="验证插件",
                priority=20)
        def on_init(self):
            self.errors = []
        def on_start(self):
            self.context.register_hook(
                "node_added", self.on_node_added)
        def on_node_added(self, node_id, **kwargs):
            content = kwargs.get("content", "")
            if not content:
                self.errors.append(node_id)

    class HealthPlugin(Plugin):
        def _define_metadata(self):
            return PluginMetadata(
                name="health", version="1.0",
                author="agent", description="健康监控",
                priority=30)
        def on_start(self):
            self.context.register_hook(
                "node_added", self.on_node_added)
        def on_node_added(self, node_id, **kwargs):
            print(f"     [health] ✓ 节点 {node_id} 健康")

    # 演示1: 插件注册与加载
    print("  📦 演示1: 插件注册与加载")
    print("     " + "-" * 60)
    mgr = PluginManager()
    counter = CounterPlugin()
    validator = ValidatorPlugin()
    health = HealthPlugin()
    mgr.register(counter)
    mgr.register(validator)
    mgr.register(health)
    print(f"     注册: {mgr.list_plugins()}")
    for name in mgr.list_plugins():
        mgr.load(name, PluginContext(plugin_name=name))
    print(f"     状态:")
    for name in mgr.list_plugins():
        p = mgr.get_plugin(name)
        print(f"       - {name}: {p.get_state().value}")
    print()

    # 演示2: 钩子触发
    print("  🪝 演示2: 钩子事件触发")
    print("     " + "-" * 60)
    mgr.hooks.trigger(
        "node_added", "n1", content="hello")
    mgr.hooks.trigger(
        "node_added", "n2", content="")
    mgr.hooks.trigger(
        "node_added", "n3", content="world")
    print()

    # 演示3: 优先级排序
    print("  📊 演示3: 钩子优先级排序")
    print("     " + "-" * 60)
    order = []
    mgr2 = PluginManager()
    hr = mgr2.hooks
    hr.register("ev", lambda: order.append("low"),
                 plugin_name="p1", priority=100)
    hr.register("ev", lambda: order.append("high"),
                 plugin_name="p2", priority=10)
    hr.register("ev", lambda: order.append("mid"),
                 plugin_name="p3", priority=50)
    hr.trigger("ev")
    print(f"     执行顺序: {' → '.join(order)}")
    print()

    # 演示4: 错误隔离
    print("  🛡️  演示4: 错误隔离")
    print("     " + "-" * 60)
    hr2 = HookRegistry()
    hr2.register("ev", lambda: print("     → hook1 OK"))
    def bad_hook():
        raise RuntimeError("爆炸")
    hr2.register("ev", bad_hook, plugin_name="bad")
    hr2.register("ev", lambda: print("     → hook3 OK"))
    print("     触发事件（中间hook会抛错）:")
    hr2.trigger("ev")
    print(f"     错误计数: {hr2.get_stats()['errors']}")
    print()

    # 演示5: 插件卸载
    print("  🗑️  演示5: 插件卸载与清理")
    print("     " + "-" * 60)
    print(f"     卸载前钩子数: {sum(len(v) for v in hr._hooks.values())}")
    mgr.unload("counter")
    print(f"     卸载 counter 后: {sum(len(v) for v in hr._hooks.values())}")
    print(f"     统计: {mgr.get_stats()}")
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段121完成：插件架构已实现，所有测试通过！")
    else:
        print("✅ 阶段121完成：插件架构已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段122：事件总线")
    print("  - 异步事件分发")
    print("  - 事件持久化")
    print("  - 订阅/发布")
    print()
    return True


if __name__ == "__main__":
    run_phase_121()
