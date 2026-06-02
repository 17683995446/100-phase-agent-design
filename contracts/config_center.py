from typing import Dict, Any, Optional, Callable, List
import threading
import json
import os
import time


class ConfigCenter:
    """
    配置中心

    功能：统一管理所有模块的配置，支持动态更新和监听
    原理：中心化的键值存储 + 观察者模式

    设计原则：
    - 所有配置集中管理，禁止模块私有配置
    - 支持配置版本控制
    - 支持配置变更通知
    - 支持环境隔离（dev/test/prod）

    使用方式：
        # 读取配置
        value = ConfigCenter.get("nlp.tokenizer.max_length", default=100)

        # 设置配置
        ConfigCenter.set("nlp.tokenizer.max_length", 200)

        # 监听变更
        ConfigCenter.watch("nlp.tokenizer.max_length", my_callback)

        # 批量加载
        ConfigCenter.load_from_file("config.json")
    """

    _configs: Dict[str, Any] = {}
    _watchers: Dict[str, List[Callable]] = {}
    _lock = threading.RLock()
    _history: List[Dict[str, Any]] = []
    _max_history = 100
    _environment: str = "dev"

    # 默认配置
    _defaults: Dict[str, Any] = {
        # 系统级配置
        "system.name": "KnowledgeGraphAgent",
        "system.version": "1.0.0",
        "system.debug": False,

        # Agent 配置
        "agent.loop_delay": 1.0,
        "agent.evolve_step": 100,
        "agent.task_queue_max": 1000,
        "agent.idle_evolve_interval": 10,

        # 知识图谱配置
        "kg.save_interval": 50,
        "kg.weight_threshold": 0.1,
        "kg.max_depth": 5,

        # NLP 配置
        "nlp.tokenizer.type": "simple",
        "nlp.tokenizer.max_length": 1000,
        "nlp.entity.min_confidence": 0.5,

        # ML 配置
        "ml.model.default_type": "classifier",
        "ml.training.batch_size": 32,

        # 安全配置
        "security.password.min_length": 8,
        "security.token.expiry_hours": 24,
        "security.max_login_attempts": 5,

        # 存储配置
        "storage.format": "json",
        "storage.compression": False,
        "storage.backup_interval": 100,

        # API 配置
        "api.host": "0.0.0.0",
        "api.port": 8000,
        "api.max_request_size": 1048576,
    }

    @classmethod
    def initialize(cls, env: str = "dev") -> None:
        """初始化配置中心"""
        cls._environment = env
        cls._configs = cls._defaults.copy()

        # 加载环境特定配置
        env_file = f"config.{env}.json"
        if os.path.exists(env_file):
            cls.load_from_file(env_file)

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键（支持点号分隔，如 "nlp.tokenizer.max_length"）
            default: 默认值

        Returns:
            配置值
        """
        with cls._lock:
            return cls._configs.get(key, default)

    @classmethod
    def set(cls, key: str, value: Any, notify: bool = True) -> None:
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
            notify: 是否通知监听器
        """
        with cls._lock:
            old_value = cls._configs.get(key)
            cls._configs[key] = value

            # 记录历史
            cls._history.append({
                'key': key,
                'old_value': old_value,
                'new_value': value,
                'timestamp': time.time()
            })
            if len(cls._history) > cls._max_history:
                cls._history.pop(0)

            # 通知监听器
            if notify:
                watchers = cls._watchers.get(key, []).copy()

        if notify:
            for watcher in watchers:
                try:
                    watcher(key, old_value, value)
                except Exception as e:
                    print(f"[ConfigCenter ERROR] 通知监听器失败: {e}")

    @classmethod
    def get_all(cls, prefix: Optional[str] = None) -> Dict[str, Any]:
        """
        获取所有配置

        Args:
            prefix: 键前缀过滤

        Returns:
            配置字典
        """
        with cls._lock:
            if prefix:
                return {k: v for k, v in cls._configs.items() if k.startswith(prefix)}
            return cls._configs.copy()

    @classmethod
    def watch(cls, key: str, callback: Callable[[str, Any, Any], None]) -> bool:
        """
        监听配置变更

        Args:
            key: 配置键
            callback: 回调函数，签名为 callback(key, old_value, new_value)

        Returns:
            是否成功
        """
        with cls._lock:
            if key not in cls._watchers:
                cls._watchers[key] = []
            if callback not in cls._watchers[key]:
                cls._watchers[key].append(callback)
                return True
            return False

    @classmethod
    def unwatch(cls, key: str, callback: Callable) -> bool:
        """取消监听"""
        with cls._lock:
            if key in cls._watchers and callback in cls._watchers[key]:
                cls._watchers[key].remove(callback)
                return True
            return False

    @classmethod
    def load_from_file(cls, filepath: str) -> bool:
        """从文件加载配置"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for key, value in data.items():
                cls.set(key, value, notify=False)
            return True
        except Exception as e:
            print(f"[ConfigCenter ERROR] 加载配置失败: {e}")
            return False

    @classmethod
    def save_to_file(cls, filepath: str) -> bool:
        """保存配置到文件"""
        try:
            with cls._lock:
                configs = cls._configs.copy()
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ConfigCenter ERROR] 保存配置失败: {e}")
            return False

    @classmethod
    def get_history(cls, key: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取配置变更历史"""
        history = cls._history
        if key:
            history = [h for h in history if h['key'] == key]
        return history[-limit:]

    @classmethod
    def reset(cls) -> None:
        """重置为默认配置"""
        with cls._lock:
            cls._configs = cls._defaults.copy()
            cls._history.clear()

    @classmethod
    def get_environment(cls) -> str:
        """获取当前环境"""
        return cls._environment

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """获取统计信息"""
        with cls._lock:
            return {
                'total_configs': len(cls._configs),
                'total_watchers': sum(len(w) for w in cls._watchers.values()),
                'history_size': len(cls._history),
                'environment': cls._environment
            }
