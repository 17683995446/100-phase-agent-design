import os
import json
import time
from typing import Dict, Any, Optional


class ConfigManager:
    """
    配置管理器，负责系统配置的加载、保存和验证
    """

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._last_save_time: float = 0.0
        self._lock: bool = False
        self.load()

    def load(self) -> Dict[str, Any]:
        """
        加载配置文件，如果不存在则创建默认配置
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                self._config = {**self.get_default_config(), **loaded_config}
                self._last_save_time = time.time()
                return self._config
            except Exception as e:
                print(f"配置文件加载失败，使用默认配置: {e}")
                self._config = self.get_default_config()
                self.save()
                return self._config
        else:
            self._config = self.get_default_config()
            self.save()
            return self._config

    def save(self) -> None:
        """
        保存当前配置到文件
        """
        temp_path = f"{self.config_path}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            if os.path.exists(self.config_path):
                os.replace(temp_path, self.config_path)
            else:
                os.rename(temp_path, self.config_path)
            self._last_save_time = time.time()
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            raise RuntimeError(f"配置保存失败: {e}")

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """
        获取默认配置
        """
        return {
            "version": "1.0.0",
            "loop_delay": 0.3,
            "evolve_step": 50,
            "task_queue_max": 200,
            "weight_threshold": 0.1,
            "kg_save_path": "knowledge_graph.json",
            "log_path": "agent_log.txt",
            "last_run_timestamp": None
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True) -> bool:
        """
        设置配置项
        """
        if key not in self._config:
            return False
        self._config[key] = value
        if auto_save:
            self.save()
        return True

    def get_all(self) -> Dict[str, Any]:
        """
        获取所有配置
        """
        return self._config.copy()

    def validate_config(self) -> bool:
        """
        验证配置的有效性
        """
        required_keys = [
            "loop_delay", "evolve_step", "task_queue_max",
            "weight_threshold", "kg_save_path", "log_path"
        ]
        for key in required_keys:
            if key not in self._config:
                return False
        
        if not isinstance(self._config["loop_delay"], (int, float)) or self._config["loop_delay"] < 0:
            return False
        
        if not isinstance(self._config["evolve_step"], int) or self._config["evolve_step"] <= 0:
            return False
        
        if not isinstance(self._config["task_queue_max"], int) or self._config["task_queue_max"] < 1:
            return False
        
        if not isinstance(self._config["weight_threshold"], (int, float)):
            return False
        
        return True

    def reset_to_default(self) -> None:
        """
        重置为默认配置
        """
        self._config = self.get_default_config()
        self.save()

    def get_last_save_time(self) -> float:
        """
        获取最后保存时间
        """
        return self._last_save_time
