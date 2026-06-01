"""
多节点部署和负载均衡模块

提供节点发现、健康检查和简单的负载均衡机制。
遵循"图难于其易，为大于其细"原则，从简单可验证的实现开始。
"""

import time
import uuid
from typing import Dict, List, Optional, Set, Tuple, Callable, Any
from dataclasses import dataclass, field
from enum import Enum


class NodeStatus(Enum):
    """节点状态"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    DEGRADED = "degraded"


@dataclass
class ClusterNode:
    """
    集群节点
    """
    node_id: str
    host: str = "localhost"
    port: int = 8000
    status: NodeStatus = NodeStatus.HEALTHY
    last_heartbeat: float = field(default_factory=time.time)
    joined_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 负载信息
    current_load: float = 0.0  # 0.0 - 1.0
    capacity: float = 1.0
    active_connections: int = 0
    
    def is_healthy(self, timeout: float = 30.0) -> bool:
        """检查节点是否健康"""
        if self.status == NodeStatus.OFFLINE:
            return False
        return (time.time() - self.last_heartbeat) < timeout
    
    def get_load_ratio(self) -> float:
        """获取负载比率"""
        if self.capacity <= 0:
            return float('inf')
        return self.current_load / self.capacity
    
    def update_heartbeat(self):
        """更新心跳"""
        self.last_heartbeat = time.time()
        if self.status == NodeStatus.OFFLINE:
            self.status = NodeStatus.HEALTHY
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "status": self.status.value,
            "last_heartbeat": self.last_heartbeat,
            "joined_at": self.joined_at,
            "metadata": self.metadata,
            "current_load": self.current_load,
            "capacity": self.capacity,
            "active_connections": self.active_connections
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClusterNode":
        """从字典创建"""
        node = cls(
            node_id=data["node_id"],
            host=data.get("host", "localhost"),
            port=data.get("port", 8000),
            status=NodeStatus(data.get("status", "healthy")),
            last_heartbeat=data.get("last_heartbeat", time.time()),
            joined_at=data.get("joined_at", time.time()),
            metadata=data.get("metadata", {}),
            current_load=data.get("current_load", 0.0),
            capacity=data.get("capacity", 1.0),
            active_connections=data.get("active_connections", 0)
        )
        return node


class LoadBalancer:
    """
    负载均衡器
    
    支持多种负载均衡策略。
    """
    
    def __init__(self, strategy: str = "round_robin"):
        """
        初始化负载均衡器
        
        Args:
            strategy: 负载均衡策略，可选 "round_robin", "least_connections", "least_load"
        """
        self.strategy = strategy
        self._round_robin_index = 0
    
    def select_node(self, nodes: List[ClusterNode]) -> Optional[ClusterNode]:
        """
        选择节点
        
        Args:
            nodes: 可用节点列表
            
        Returns:
            选中的节点
        """
        if not nodes:
            return None
        
        if self.strategy == "round_robin":
            return self._round_robin(nodes)
        elif self.strategy == "least_connections":
            return self._least_connections(nodes)
        elif self.strategy == "least_load":
            return self._least_load(nodes)
        else:
            return self._round_robin(nodes)
    
    def _round_robin(self, nodes: List[ClusterNode]) -> Optional[ClusterNode]:
        """轮询策略"""
        if not nodes:
            return None
        
        node = nodes[self._round_robin_index % len(nodes)]
        self._round_robin_index += 1
        return node
    
    def _least_connections(self, nodes: List[ClusterNode]) -> Optional[ClusterNode]:
        """最少连接策略"""
        if not nodes:
            return None
        
        return min(nodes, key=lambda n: n.active_connections)
    
    def _least_load(self, nodes: List[ClusterNode]) -> Optional[ClusterNode]:
        """最小负载策略"""
        if not nodes:
            return None
        
        return min(nodes, key=lambda n: n.get_load_ratio())


class ClusterManager:
    """
    集群管理器
    
    管理集群节点、健康检查和负载均衡。
    """
    
    def __init__(self, node_id: Optional[str] = None, host: str = "localhost", port: int = 8000):
        """
        初始化集群管理器
        
        Args:
            node_id: 当前节点 ID，如果为 None 则自动生成
            host: 当前节点主机
            port: 当前节点端口
        """
        self.node_id = node_id or str(uuid.uuid4())
        self.host = host
        self.port = port
        
        self.nodes: Dict[str, ClusterNode] = {}
        self.load_balancer = LoadBalancer()
        
        # 配置
        self.heartbeat_timeout = 30.0
        self.health_check_interval = 10.0
        
        # 回调
        self._callbacks: List[Callable] = []
        
        # 注册自己
        self.register_node(self.node_id, host, port)
    
    def register_node(self, node_id: str, host: str = "localhost", port: int = 8000,
                     metadata: Optional[Dict[str, Any]] = None) -> ClusterNode:
        """
        注册节点
        
        Args:
            node_id: 节点 ID
            host: 主机地址
            port: 端口
            metadata: 元数据
            
        Returns:
            注册的节点
        """
        if node_id in self.nodes:
            # 更新现有节点
            node = self.nodes[node_id]
            node.host = host
            node.port = port
            node.status = NodeStatus.HEALTHY
            node.last_heartbeat = time.time()
            if metadata:
                node.metadata.update(metadata)
        else:
            # 创建新节点
            node = ClusterNode(
                node_id=node_id,
                host=host,
                port=port,
                metadata=metadata or {}
            )
            self.nodes[node_id] = node
            self._notify_callbacks("node_joined", node)
        
        return node
    
    def unregister_node(self, node_id: str) -> bool:
        """
        注销节点
        
        Args:
            node_id: 节点 ID
            
        Returns:
            是否成功注销
        """
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.status = NodeStatus.OFFLINE
            self._notify_callbacks("node_left", node)
            del self.nodes[node_id]
            return True
        return False
    
    def heartbeat(self, node_id: str, load: Optional[float] = None,
                  connections: Optional[int] = None) -> bool:
        """
        节点心跳
        
        Args:
            node_id: 节点 ID
            load: 当前负载
            connections: 活跃连接数
            
        Returns:
            是否成功更新
        """
        if node_id not in self.nodes:
            return False
        
        node = self.nodes[node_id]
        node.update_heartbeat()
        
        if load is not None:
            node.current_load = load
        if connections is not None:
            node.active_connections = connections
        
        return True
    
    def get_node(self, node_id: str) -> Optional[ClusterNode]:
        """获取节点"""
        return self.nodes.get(node_id)
    
    def get_healthy_nodes(self) -> List[ClusterNode]:
        """获取健康节点"""
        return [
            node for node in self.nodes.values()
            if node.is_healthy(self.heartbeat_timeout)
        ]
    
    def get_node_for_task(self) -> Optional[ClusterNode]:
        """
        获取用于处理任务的节点
        
        使用负载均衡策略选择节点。
        """
        healthy_nodes = self.get_healthy_nodes()
        return self.load_balancer.select_node(healthy_nodes)
    
    def check_health(self) -> Dict[str, NodeStatus]:
        """
        检查所有节点健康状态
        
        Returns:
            节点状态字典
        """
        results = {}
        
        for node_id, node in list(self.nodes.items()):
            if not node.is_healthy(self.heartbeat_timeout):
                if node.status != NodeStatus.OFFLINE:
                    node.status = NodeStatus.UNHEALTHY
                    self._notify_callbacks("node_unhealthy", node)
            else:
                if node.status == NodeStatus.UNHEALTHY:
                    node.status = NodeStatus.HEALTHY
                    self._notify_callbacks("node_recovered", node)
            
            results[node_id] = node.status
        
        return results
    
    def get_cluster_stats(self) -> Dict[str, Any]:
        """获取集群统计"""
        healthy_nodes = self.get_healthy_nodes()
        total_capacity = sum(n.capacity for n in self.nodes.values())
        total_load = sum(n.current_load for n in self.nodes.values())
        
        return {
            "total_nodes": len(self.nodes),
            "healthy_nodes": len(healthy_nodes),
            "unhealthy_nodes": len(self.nodes) - len(healthy_nodes),
            "total_capacity": total_capacity,
            "total_load": total_load,
            "average_load": total_load / total_capacity if total_capacity > 0 else 0,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()}
        }
    
    def set_load_balancer_strategy(self, strategy: str):
        """设置负载均衡策略"""
        self.load_balancer = LoadBalancer(strategy)
    
    def register_callback(self, callback: Callable):
        """注册回调"""
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable):
        """注销回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self, event: str, data: Any):
        """通知回调"""
        for callback in self._callbacks:
            try:
                callback(event, data)
            except Exception:
                pass
    
    def clear(self):
        """清空集群"""
        self.nodes.clear()
        self._callbacks.clear()
    
    def __repr__(self) -> str:
        healthy = len(self.get_healthy_nodes())
        total = len(self.nodes)
        return f"ClusterManager(node={self.node_id}, nodes={healthy}/{total})"


class ServiceRegistry:
    """
    服务注册表
    
    管理服务实例的发现和路由。
    """
    
    def __init__(self):
        self._services: Dict[str, List[str]] = {}  # service_name -> [node_ids]
        self._node_services: Dict[str, Set[str]] = {}  # node_id -> {service_names}
    
    def register_service(self, service_name: str, node_id: str):
        """注册服务实例"""
        if service_name not in self._services:
            self._services[service_name] = []
        
        if node_id not in self._services[service_name]:
            self._services[service_name].append(node_id)
        
        if node_id not in self._node_services:
            self._node_services[node_id] = set()
        self._node_services[node_id].add(service_name)
    
    def unregister_service(self, service_name: str, node_id: str):
        """注销服务实例"""
        if service_name in self._services:
            if node_id in self._services[service_name]:
                self._services[service_name].remove(node_id)
        
        if node_id in self._node_services:
            self._node_services[node_id].discard(service_name)
    
    def get_service_nodes(self, service_name: str) -> List[str]:
        """获取服务实例列表"""
        return self._services.get(service_name, []).copy()
    
    def get_node_services(self, node_id: str) -> Set[str]:
        """获取节点提供的服务"""
        return self._node_services.get(node_id, set()).copy()
    
    def is_service_available(self, service_name: str) -> bool:
        """检查服务是否可用"""
        return len(self._services.get(service_name, [])) > 0
    
    def get_all_services(self) -> Dict[str, List[str]]:
        """获取所有服务"""
        return {k: v.copy() for k, v in self._services.items()}
    
    def remove_node(self, node_id: str):
        """移除节点及其所有服务"""
        services = self._node_services.get(node_id, set())
        for service_name in services:
            if service_name in self._services:
                if node_id in self._services[service_name]:
                    self._services[service_name].remove(node_id)
        
        if node_id in self._node_services:
            del self._node_services[node_id]
    
    def clear(self):
        """清空注册表"""
        self._services.clear()
        self._node_services.clear()
