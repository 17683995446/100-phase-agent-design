"""
模块开发模板

这是各公司开发模块时必须遵循的模板。
复制此文件，修改类名和实现即可。

公司：__________
模块名：__________
负责人：__________
联系方式：__________
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from contracts import ModuleRegistry, ModuleInfo, ModuleStatus
from contracts import EventBus, SystemEvents
from contracts import ConfigCenter


# ==================== 接口定义（由总包方提供）====================

class IMyModule(ABC):
    """
    [模块名] 接口契约

    功能：[一句话描述]
    原理：[一句话描述]

    版本：v1.0.0
    最后更新：2026-06-01
    """

    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化模块

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理输入数据

        Args:
            input_data: 输入数据

        Returns:
            处理结果
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        获取模块状态

        Returns:
            状态信息字典
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """关闭模块"""
        pass


# ==================== 实现类（由外包公司编写）====================

class MyModule(IMyModule):
    """
    [模块名] 实现

    开发公司：__________
    版本：v1.0.0
    """

    def __init__(self):
        self._initialized = False
        self._config = {}
        self._stats = {
            'processed_count': 0,
            'error_count': 0
        }

        # 注册模块
        self._register_module()

    def _register_module(self) -> None:
        """向模块注册表注册"""
        info = ModuleInfo(
            name="my_module",  # 替换为实际模块名
            version="1.0.0",
            layer=3,  # 根据实际层修改
            dependencies=["knowledge_graph"],  # 根据实际依赖修改
            interfaces=["IMyModule"],
            company="Company Name",  # 替换为公司名
            description="Module description",
            author="Developer Name",
            contact="email@company.com",
            health_check=self._health_check
        )
        ModuleRegistry.register(info)

    def _health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            'status': 'healthy' if self._initialized else 'not_initialized',
            'stats': self._stats.copy()
        }

    def initialize(self) -> bool:
        """
        初始化模块

        实现说明：
        1. 从配置中心读取配置
        2. 订阅需要的事件
        3. 初始化内部资源
        4. 更新模块状态为 READY
        """
        try:
            # 1. 读取配置
            self._config = ConfigCenter.get_all(prefix="my_module.")

            # 2. 订阅事件
            EventBus.subscribe(
                SystemEvents.SYSTEM_STARTUP,
                self._on_system_startup,
                priority=2
            )

            # 3. 初始化资源
            # TODO: 添加初始化代码

            self._initialized = True

            # 4. 更新状态
            ModuleRegistry.update_status("my_module", ModuleStatus.READY)

            # 发布就绪事件
            EventBus.publish(
                SystemEvents.MODULE_READY,
                {"module": "my_module", "timestamp": time.time()}
            )

            return True
        except Exception as e:
            ModuleRegistry.update_status("my_module", ModuleStatus.ERROR)
            return False

    def _on_system_startup(self, data: Dict[str, Any]) -> None:
        """系统启动事件处理"""
        if not self._initialized:
            self.initialize()

    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理输入数据

        实现说明：
        1. 验证输入
        2. 处理数据
        3. 记录统计
        4. 返回结果
        """
        if not self._initialized:
            return {"error": "Module not initialized"}

        try:
            # 1. 验证输入
            if not self._validate_input(input_data):
                return {"error": "Invalid input"}

            # 2. 处理数据
            # TODO: 添加核心处理逻辑
            result = {"status": "processed", "data": input_data}

            # 3. 记录统计
            self._stats['processed_count'] += 1

            return result
        except Exception as e:
            self._stats['error_count'] += 1
            return {"error": str(e)}

    def _validate_input(self, data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        return isinstance(data, dict)

    def get_status(self) -> Dict[str, Any]:
        """获取模块状态"""
        return {
            "initialized": self._initialized,
            "config": self._config,
            "stats": self._stats.copy()
        }

    def shutdown(self) -> None:
        """关闭模块"""
        # 取消事件订阅
        EventBus.unsubscribe(SystemEvents.SYSTEM_STARTUP, self._on_system_startup)

        # 清理资源
        # TODO: 添加清理代码

        self._initialized = False
        ModuleRegistry.update_status("my_module", ModuleStatus.SHUTDOWN)

    def get_module_info(self) -> ModuleInfo:
        """获取模块信息（用于注册）"""
        return ModuleRegistry.get("my_module")


# ==================== 便捷函数 ====================

def create_module() -> MyModule:
    """创建模块实例"""
    return MyModule()


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 快速测试
    module = create_module()
    print(f"Module created: {module.get_status()}")

    result = module.process({"test": "data"})
    print(f"Process result: {result}")

    module.shutdown()
    print("Module shutdown")
