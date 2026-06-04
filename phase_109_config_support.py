#!/usr/bin/env python3
"""
阶段109：配置文件支持

第一性原理：
  - 适应性：系统应能通过配置适应不同环境
  - 健壮性：缺失/错误配置时能优雅降级到默认值
  - 可观测：配置变更应可追溯

本阶段产出：
  1. ConfigLoader：配置加载器（JSON/YAML）
  2. ConfigSchema：配置校验
  3. ConfigManager：配置管理（热加载）
  4. ConfigProvider：统一配置访问入口

遵循原则：图难于其易，为大于其细
"""
import os
import json
import time
import unittest
import tempfile
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
from copy import deepcopy


# ============================================================
# 一、配置Schema
# ============================================================
@dataclass
class ConfigSchema:
    """配置Schema定义

    通过类型+默认值定义配置项
    """
    name: str
    type: type
    default: Any
    required: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    choices: Optional[List] = None
    description: str = ""


class ConfigValidator:
    """配置校验器

    根据Schema校验配置有效性
    """
    def __init__(self, schemas: List[ConfigSchema]):
        self.schemas = {s.name: s for s in schemas}

    def validate(self, config: Dict[str, Any]) -> List[str]:
        """校验配置

        Returns: 错误列表（空列表表示通过）
        """
        errors = []
        for name, schema in self.schemas.items():
            value = config.get(name, schema.default)
            if schema.required and name not in config:
                errors.append(f"Missing required: {name}")
                continue
            if not self._check_type(value, schema.type):
                errors.append(
                    f"{name}: expected {schema.type.__name__}, "
                    f"got {type(value).__name__}")
                continue
            if schema.min_value is not None and value < schema.min_value:
                errors.append(
                    f"{name}: {value} < min {schema.min_value}")
            if schema.max_value is not None and value > schema.max_value:
                errors.append(
                    f"{name}: {value} > max {schema.max_value}")
            if schema.choices and value not in schema.choices:
                errors.append(
                    f"{name}: {value} not in {schema.choices}")
        return errors

    def _check_type(self, value: Any, expected: type) -> bool:
        if expected is int and isinstance(value, bool):
            return False  # bool是int的子类但不应混淆
        if expected is float and isinstance(value, int):
            return True  # int可接受为float
        return isinstance(value, expected)


# ============================================================
# 二、配置加载器
# ============================================================
class ConfigLoader:
    """配置加载器

    支持 JSON 和简单的 YAML（避免外部依赖）
    """
    @staticmethod
    def load_from_file(path: str) -> Dict[str, Any]:
        """从文件加载配置"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if path.endswith(".yaml") or path.endswith(".yml"):
            return ConfigLoader._parse_simple_yaml(content)
        elif path.endswith(".json"):
            return json.loads(content)
        else:
            # 尝试自动检测
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return ConfigLoader._parse_simple_yaml(content)

    @staticmethod
    def _parse_simple_yaml(content: str) -> Dict[str, Any]:
        """简单YAML解析（仅支持两级kv结构）

        避免引入pyyaml依赖
        """
        result: Dict[str, Any] = {}
        current_section = None
        for line in content.split("\n"):
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            if not line.startswith(" "):
                # 顶级key
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip()
                    value = value.strip()
                    if value == "":
                        current_section = key
                        result[key] = {}
                    else:
                        result[key] = ConfigLoader._parse_value(value)
                        current_section = None
            else:
                # 二级key
                if current_section and ":" in line:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    k, _, v = stripped.partition(":")
                    k = k.strip()
                    v = v.strip()
                    if v == "":
                        v = ""
                    result[current_section][k] = ConfigLoader._parse_value(v)
        return result

    @staticmethod
    def _parse_value(value: str) -> Any:
        """解析值的类型"""
        if value == "":
            return ""
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        if value.lower() == "null" or value.lower() == "none":
            return None
        # 尝试数字
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        # 字符串
        return value

    @staticmethod
    def load_from_env(prefix: str = "MVP_") -> Dict[str, Any]:
        """从环境变量加载配置

        环境变量格式：MVP_AGENT__NAME=xxx
        """
        result: Dict[str, Any] = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                stripped = key[len(prefix):]
                # 支持嵌套：MVP_AGENT__NAME -> agent.name
                parts = stripped.lower().split("__")
                if len(parts) == 1:
                    result[parts[0]] = ConfigLoader._parse_value(value)
                else:
                    current = result
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    current[parts[-1]] = ConfigLoader._parse_value(value)
        return result


# ============================================================
# 三、配置管理器
# ============================================================
class ConfigManager:
    """配置管理器

    功能：
    - 多源配置合并（默认值 < 文件 < 环境变量）
    - 热加载（定时重读）
    - 配置变更通知
    """
    def __init__(self, schemas: List[ConfigSchema],
                 config_path: Optional[str] = None,
                 hot_reload: bool = False,
                 reload_interval: float = 30.0):
        self.schemas = {s.name: s for s in schemas}
        self.validator = ConfigValidator(schemas)
        self.config_path = config_path
        self.hot_reload = hot_reload
        self.reload_interval = reload_interval
        self._config: Dict[str, Any] = {}
        self._last_load_time = 0.0
        self._last_mtime = 0.0
        self._listeners: List[Callable] = []
        self._lock = threading.RLock()

    def load(self) -> Dict[str, Any]:
        """加载配置

        合并顺序（后者覆盖前者）：
        1. Schema默认值
        2. 配置文件
        3. 环境变量
        """
        with self._lock:
            config = self._load_defaults()
            if self.config_path and os.path.exists(self.config_path):
                try:
                    file_config = ConfigLoader.load_from_file(
                        self.config_path)
                    config = self._deep_merge(config, file_config)
                except Exception:
                    pass  # 文件加载失败，使用默认
            # 环境变量
            env_config = ConfigLoader.load_from_env()
            if env_config:
                config = self._deep_merge(config, env_config)
            # 校验
            errors = self.validator.validate(config)
            if errors:
                # 有错误，记录但仍使用当前值
                for err in errors:
                    print(f"Config validation warning: {err}")
            self._config = config
            self._last_load_time = time.time()
            if self.config_path and os.path.exists(self.config_path):
                self._last_mtime = os.path.getmtime(self.config_path)
            return dict(self._config)

    def _load_defaults(self) -> Dict[str, Any]:
        """从schema加载默认值"""
        result = {}
        for name, schema in self.schemas.items():
            if "." in name:
                # 嵌套
                parts = name.split(".")
                current = result
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = schema.default
            else:
                result[name] = schema.default
        return result

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并字典"""
        result = deepcopy(base)
        for key, value in override.items():
            if (key in result and isinstance(result[key], dict)
                    and isinstance(value, dict)):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项

        支持点号分隔的嵌套key
        """
        with self._lock:
            self._check_reload()
            parts = key.split(".")
            current: Any = self._config
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current

    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        with self._lock:
            parts = key.split(".")
            current = self._config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            old_value = current.get(parts[-1])
            current[parts[-1]] = value
            if old_value != value:
                self._notify(key, old_value, value)

    def _check_reload(self) -> None:
        """检查是否需要重载（热加载）"""
        if not self.hot_reload or not self.config_path:
            return
        if not os.path.exists(self.config_path):
            return
        if time.time() - self._last_load_time < self.reload_interval:
            return
        mtime = os.path.getmtime(self.config_path)
        if mtime > self._last_mtime:
            self.load()
            for listener in self._listeners:
                try:
                    listener(self._config)
                except Exception:
                    pass

    def on_change(self, listener: Callable) -> None:
        """注册配置变更监听器"""
        self._listeners.append(listener)

    def _notify(self, key: str, old: Any, new: Any) -> None:
        """通知变更"""
        for listener in self._listeners:
            try:
                listener({key: {"old": old, "new": new}})
            except Exception:
                pass

    def get_all(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._config)


# ============================================================
# 四、MVP配置Schema定义
# ============================================================
def get_mvp_schemas() -> List[ConfigSchema]:
    """获取MVP系统的标准配置Schema"""
    return [
        ConfigSchema("agent.name", str, "mvp-agent",
                    description="Agent名称"),
        ConfigSchema("agent.version", str, "0.1.0",
                    description="版本号"),
        ConfigSchema("agent.data_dir", str, "./mvp_data",
                    description="数据目录"),
        ConfigSchema("agent.log_level", str, "INFO",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    description="日志级别"),
        ConfigSchema("kg.max_nodes", int, 10000,
                    min_value=100, max_value=1000000,
                    description="最大节点数"),
        ConfigSchema("kg.max_edges", int, 50000,
                    min_value=100, max_value=10000000,
                    description="最大边数"),
        ConfigSchema("kg.weight_decay_daily", float, 0.95,
                    min_value=0.5, max_value=1.0,
                    description="日权重衰减率"),
        ConfigSchema("task.queue_max_size", int, 100,
                    min_value=10, max_value=10000,
                    description="任务队列最大大小"),
        ConfigSchema("task.max_retries", int, 3,
                    min_value=0, max_value=10,
                    description="任务最大重试次数"),
        ConfigSchema("loop.cycle_interval_sec", float, 1.0,
                    min_value=0.01, max_value=60.0,
                    description="循环间隔秒数"),
        ConfigSchema("loop.min_interval_sec", float, 0.1,
                    min_value=0.001, max_value=10.0,
                    description="最小循环间隔"),
        ConfigSchema("loop.max_interval_sec", float, 10.0,
                    min_value=1.0, max_value=300.0,
                    description="最大循环间隔"),
        ConfigSchema("persistence.save_interval_cycles", int, 10,
                    min_value=1, max_value=1000,
                    description="保存间隔循环数"),
        ConfigSchema("monitor.memory_limit_mb", int, 200,
                    min_value=50, max_value=10000,
                    description="内存限制MB"),
        ConfigSchema("monitor.metrics_interval_sec", int, 30,
                    min_value=5, max_value=3600,
                    description="指标采集间隔"),
    ]


# ============================================================
# 五、单元测试
# ============================================================
class TestConfigLoader(unittest.TestCase):
    """配置加载器测试"""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_json(self):
        path = os.path.join(self.tmpdir, "c.json")
        with open(path, "w") as f:
            json.dump({"a": 1, "b": "x"}, f)
        config = ConfigLoader.load_from_file(path)
        self.assertEqual(config["a"], 1)
        self.assertEqual(config["b"], "x")

    def test_load_yaml(self):
        path = os.path.join(self.tmpdir, "c.yaml")
        with open(path, "w") as f:
            f.write("agent:\n  name: test\n  port: 8080\n")
        config = ConfigLoader.load_from_file(path)
        self.assertEqual(config["agent"]["name"], "test")
        self.assertEqual(config["agent"]["port"], 8080)

    def test_load_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            ConfigLoader.load_from_file("/nonexistent/path.json")

    def test_load_env(self):
        os.environ["MVP_TEST_KEY"] = "value"
        os.environ["MVP_TEST_NUM"] = "42"
        try:
            config = ConfigLoader.load_from_env()
            self.assertEqual(config.get("test_key"), "value")
            self.assertEqual(config.get("test_num"), 42)
        finally:
            del os.environ["MVP_TEST_KEY"]
            del os.environ["MVP_TEST_NUM"]


class TestConfigValidator(unittest.TestCase):
    """配置校验器测试"""
    def test_type_check(self):
        schemas = [ConfigSchema("port", int, 8080)]
        v = ConfigValidator(schemas)
        errors = v.validate({"port": "not_int"})
        self.assertGreater(len(errors), 0)

    def test_range_check(self):
        schemas = [ConfigSchema("port", int, 8080,
                                min_value=1, max_value=65535)]
        v = ConfigValidator(schemas)
        errors = v.validate({"port": 99999})
        self.assertGreater(len(errors), 0)

    def test_choices(self):
        schemas = [ConfigSchema("level", str, "INFO",
                                choices=["DEBUG", "INFO"])]
        v = ConfigValidator(schemas)
        errors = v.validate({"level": "INVALID"})
        self.assertGreater(len(errors), 0)

    def test_required(self):
        schemas = [ConfigSchema("api_key", str, "", required=True)]
        v = ConfigValidator(schemas)
        errors = v.validate({})
        self.assertGreater(len(errors), 0)


class TestConfigManager(unittest.TestCase):
    """配置管理器测试"""
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.schemas = [
            ConfigSchema("name", str, "default"),
            ConfigSchema("port", int, 8080, min_value=1, max_value=65535),
            ConfigSchema("debug", bool, False),
        ]

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_defaults(self):
        mgr = ConfigManager(self.schemas)
        config = mgr.load()
        self.assertEqual(mgr.get("name"), "default")
        self.assertEqual(mgr.get("port"), 8080)

    def test_file_override(self):
        path = os.path.join(self.tmpdir, "c.json")
        with open(path, "w") as f:
            json.dump({"name": "from_file", "port": 9090}, f)
        mgr = ConfigManager(self.schemas, config_path=path)
        config = mgr.load()
        self.assertEqual(mgr.get("name"), "from_file")
        self.assertEqual(mgr.get("port"), 9090)

    def test_nested_get(self):
        schemas = [ConfigSchema("a.b.c", int, 42)]
        mgr = ConfigManager(schemas)
        mgr.load()
        self.assertEqual(mgr.get("a.b.c"), 42)

    def test_set_and_notify(self):
        mgr = ConfigManager(self.schemas)
        mgr.load()
        notifications = []
        mgr.on_change(lambda c: notifications.append(c))
        mgr.set("name", "new_value")
        self.assertEqual(mgr.get("name"), "new_value")
        self.assertGreater(len(notifications), 0)

    def test_hot_reload(self):
        path = os.path.join(self.tmpdir, "c.json")
        with open(path, "w") as f:
            json.dump({"name": "v1"}, f)
        mgr = ConfigManager(self.schemas, config_path=path,
                            hot_reload=True, reload_interval=0.1)
        mgr.load()
        self.assertEqual(mgr.get("name"), "v1")
        # 修改文件
        time.sleep(0.2)
        with open(path, "w") as f:
            json.dump({"name": "v2"}, f)
        # 触发reload
        mgr._last_load_time = 0
        val = mgr.get("name")
        self.assertEqual(val, "v2")


# ============================================================
# 六、阶段109演示
# ============================================================
def run_phase_109():
    """运行阶段109"""
    print("=" * 70)
    print("阶段109：配置文件支持")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestConfigLoader))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigValidator))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigManager))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    print()
    print("-" * 70)
    print("【配置管理演示】")
    print("-" * 70)
    import shutil
    tmpdir = tempfile.mkdtemp()
    try:
        # 1. 创建配置文件
        config_path = os.path.join(tmpdir, "mvp_config.json")
        config_data = {
            "agent": {"name": "production-agent", "log_level": "INFO"},
            "kg": {"max_nodes": 50000, "weight_decay_daily": 0.97},
            "loop": {"cycle_interval_sec": 2.0},
            "task": {"queue_max_size": 200, "max_retries": 5}
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)
        print(f"  📄 创建配置文件: {config_path}")
        # 2. 加载配置
        mgr = ConfigManager(get_mvp_schemas(), config_path=config_path)
        config = mgr.load()
        print()
        print("  📋 加载后的配置:")
        for key in ["agent.name", "agent.log_level", "kg.max_nodes",
                    "loop.cycle_interval_sec", "task.queue_max_size"]:
            print(f"    {key:35s} = {mgr.get(key)}")
        # 3. 运行时修改
        print()
        print("  🔧 运行时修改配置:")
        old = mgr.get("loop.cycle_interval_sec")
        mgr.set("loop.cycle_interval_sec", 0.5)
        print(f"    loop.cycle_interval_sec: {old}s -> "
              f"{mgr.get('loop.cycle_interval_sec')}s")
        # 4. 配置变更通知
        print()
        print("  🔔 注册配置变更通知:")
        events = []
        mgr.on_change(lambda c: events.append(c))
        mgr.set("agent.log_level", "DEBUG")
        print(f"    收到 {len(events)} 个通知")
        for e in events:
            print(f"    通知内容: {e}")
        # 5. 校验
        print()
        print("  ✅ 配置校验（有效配置）:")
        schemas = get_mvp_schemas()
        validator = ConfigValidator(schemas)
        errors = validator.validate(mgr.get_all())
        if errors:
            print(f"    发现 {len(errors)} 个错误:")
            for e in errors:
                print(f"    - {e}")
        else:
            print("    所有配置项均有效 ✓")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ 阶段109完成：配置文件支持已实现，所有测试通过！")
    else:
        print("❌ 阶段109失败")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段110：MVP集成与端到端测试")
    print("  - 集成所有MVP模块")
    print("  - 端到端测试")
    print("  - 性能基准")
    print("  - 文档完善")
    print()
    return result.wasSuccessful()


if __name__ == "__main__":
    run_phase_109()
