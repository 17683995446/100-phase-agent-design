from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import time


class ModuleStatus(Enum):
    """模块状态"""
    REGISTERED = "registered"      # 已注册
    INITIALIZING = "initializing"  # 初始化中
    READY = "ready"                # 就绪
    ERROR = "error"                # 错误
    SHUTDOWN = "shutdown"          # 已关闭


@dataclass
class ModuleInfo:
    """
    模块信息

    每个公司开发的模块必须在初始化时提供此信息
    """
    name: str                      # 模块名（唯一标识）
    version: str                   # 版本号（语义化版本）
    layer: int                     # 架构层（1-5）
    dependencies: List[str]        # 依赖的模块名列表
    interfaces: List[str]          # 实现的接口名列表
    company: str                   # 开发公司名称
    description: str = ""          # 模块描述
    author: str = ""               # 负责人
    contact: str = ""              # 联系方式
    status: ModuleStatus = ModuleStatus.REGISTERED
    registered_at: float = field(default_factory=time.time)
    health_check: Optional[Callable[[], Dict[str, Any]]] = None


class ModuleRegistry:
    """
    模块注册表

    功能：统一管理所有模块的注册、发现和依赖解析
    原理：中心化的模块元数据管理

    使用方式：
        ModuleRegistry.register(my_module_info)
        deps = ModuleRegistry.get_dependencies("nlp")
        all_ready = ModuleRegistry.check_all_ready()
    """

    _modules: Dict[str, ModuleInfo] = {}
    _dependency_graph: Dict[str, Set[str]] = {}

    @classmethod
    def register(cls, info: ModuleInfo) -> bool:
        """
        注册模块

        Args:
            info: 模块信息

        Returns:
            是否成功
        """
        if info.name in cls._modules:
            return False

        cls._modules[info.name] = info
        cls._dependency_graph[info.name] = set(info.dependencies)

        # 验证依赖是否存在
        for dep in info.dependencies:
            if dep not in cls._modules:
                print(f"[WARN] 模块 '{info.name}' 依赖 '{dep}' 尚未注册")

        return True

    @classmethod
    def unregister(cls, name: str) -> bool:
        """注销模块"""
        if name not in cls._modules:
            return False

        del cls._modules[name]
        del cls._dependency_graph[name]

        # 从其他模块的依赖中移除
        for deps in cls._dependency_graph.values():
            deps.discard(name)

        return True

    @classmethod
    def get(cls, name: str) -> Optional[ModuleInfo]:
        """获取模块信息"""
        return cls._modules.get(name)

    @classmethod
    def get_all(cls) -> Dict[str, ModuleInfo]:
        """获取所有模块"""
        return cls._modules.copy()

    @classmethod
    def get_by_layer(cls, layer: int) -> List[ModuleInfo]:
        """按层获取模块"""
        return [m for m in cls._modules.values() if m.layer == layer]

    @classmethod
    def get_by_company(cls, company: str) -> List[ModuleInfo]:
        """按公司获取模块"""
        return [m for m in cls._modules.values() if m.company == company]

    @classmethod
    def get_dependencies(cls, name: str) -> List[str]:
        """获取模块的直接依赖"""
        info = cls._modules.get(name)
        return info.dependencies if info else []

    @classmethod
    def get_all_dependencies(cls, name: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """获取模块的所有依赖（递归）"""
        if visited is None:
            visited = set()

        if name in visited or name not in cls._modules:
            return visited

        visited.add(name)
        for dep in cls._dependency_graph.get(name, set()):
            cls.get_all_dependencies(dep, visited)

        return visited - {name}

    @classmethod
    def get_dependents(cls, name: str) -> List[str]:
        """获取依赖此模块的所有模块"""
        return [
            module_name for module_name, deps in cls._dependency_graph.items()
            if name in deps
        ]

    @classmethod
    def update_status(cls, name: str, status: ModuleStatus) -> bool:
        """更新模块状态"""
        if name not in cls._modules:
            return False
        cls._modules[name].status = status
        return True

    @classmethod
    def check_all_ready(cls) -> bool:
        """检查所有模块是否就绪"""
        return all(
            m.status == ModuleStatus.READY
            for m in cls._modules.values()
        )

    @classmethod
    def check_circular_dependencies(cls) -> List[List[str]]:
        """检测循环依赖"""
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in cls._dependency_graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])

            path.pop()
            rec_stack.remove(node)

        for node in cls._dependency_graph:
            if node not in visited:
                dfs(node, [])

        return cycles

    @classmethod
    def get_init_order(cls) -> List[str]:
        """
        获取模块初始化顺序（拓扑排序）

        确保依赖模块先于被依赖模块初始化
        """
        # 计算每个模块的入度（被多少模块依赖）
        in_degree = {name: 0 for name in cls._modules}
        for name, deps in cls._dependency_graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] += 1  # name 依赖 dep，所以 name 的入度 +1

        # 入度为 0 的模块（不依赖其他模块）先初始化
        queue = [name for name, degree in in_degree.items() if degree == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)

            # 找到所有依赖 node 的模块，减少它们的入度
            for name, deps in cls._dependency_graph.items():
                if node in deps and name in in_degree:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)

        return order

    @classmethod
    def get_dependency_graph(cls) -> Dict[str, Any]:
        """获取依赖关系图（用于可视化）"""
        return {
            "modules": {
                name: {
                    "name": info.name,
                    "version": info.version,
                    "layer": info.layer,
                    "company": info.company,
                    "status": info.status.value,
                    "dependencies": info.dependencies
                }
                for name, info in cls._modules.items()
            },
            "circular_dependencies": [
                " -> ".join(cycle) for cycle in cls.check_circular_dependencies()
            ],
            "init_order": cls.get_init_order()
        }

    @classmethod
    def health_check_all(cls) -> Dict[str, Any]:
        """对所有模块执行健康检查"""
        results = {}
        for name, info in cls._modules.items():
            if info.health_check:
                try:
                    results[name] = info.health_check()
                except Exception as e:
                    results[name] = {"status": "error", "error": str(e)}
            else:
                results[name] = {"status": "no_check", "module_status": info.status.value}
        return results
