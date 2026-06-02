"""
contracts 包 —— 多公司协作开发的基础设施

提供模块注册、事件总线、配置中心、契约测试基类等基础设施，
确保各公司开发的模块能够无缝集成。
"""

from .module_registry import ModuleRegistry, ModuleInfo, ModuleStatus
from .event_bus import EventBus, EventPriority, SystemEvents
from .config_center import ConfigCenter
from .contract_test import ContractTest, ContractValidator

__all__ = [
    'ModuleRegistry', 'ModuleInfo', 'ModuleStatus',
    'EventBus', 'EventPriority', 'SystemEvents',
    'ConfigCenter',
    'ContractTest', 'ContractValidator'
]
