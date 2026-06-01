"""
多节点部署和负载均衡模块测试

测试节点发现、健康检查和负载均衡功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的测试开始。
"""

import pytest
import time
from core import (
    NodeStatus, ClusterNode, LoadBalancer, ClusterManager, ServiceRegistry
)


class TestNodeStatus:
    """测试节点状态枚举"""
    
    def test_status_values(self):
        """测试状态值"""
        assert NodeStatus.HEALTHY.value == "healthy"
        assert NodeStatus.UNHEALTHY.value == "unhealthy"
        assert NodeStatus.OFFLINE.value == "offline"


class TestClusterNode:
    """测试集群节点"""
    
    def test_creation(self):
        """测试创建"""
        node = ClusterNode(node_id="node_1", host="localhost", port=8000)
        assert node.node_id == "node_1"
        assert node.host == "localhost"
        assert node.port == 8000
        assert node.status == NodeStatus.HEALTHY
        assert node.current_load == 0.0
    
    def test_is_healthy(self):
        """测试健康检查"""
        node = ClusterNode(node_id="node_1")
        assert node.is_healthy(timeout=30.0) is True
        
        node.last_heartbeat = time.time() - 60
        assert node.is_healthy(timeout=30.0) is False
        
        node.status = NodeStatus.OFFLINE
        node.last_heartbeat = time.time()
        assert node.is_healthy(timeout=30.0) is False
    
    def test_get_load_ratio(self):
        """测试负载比率"""
        node = ClusterNode(node_id="node_1", capacity=10.0)
        node.current_load = 5.0
        assert node.get_load_ratio() == 0.5
        
        node.current_load = 15.0
        assert node.get_load_ratio() == 1.5
    
    def test_update_heartbeat(self):
        """测试更新心跳"""
        node = ClusterNode(node_id="node_1")
        old_heartbeat = node.last_heartbeat
        
        time.sleep(0.01)
        node.update_heartbeat()
        
        assert node.last_heartbeat > old_heartbeat
        assert node.status == NodeStatus.HEALTHY
    
    def test_serialization(self):
        """测试序列化"""
        node = ClusterNode(
            node_id="node_1",
            host="localhost",
            port=8000,
            status=NodeStatus.HEALTHY,
            current_load=0.5,
            capacity=1.0
        )
        
        data = node.to_dict()
        node2 = ClusterNode.from_dict(data)
        
        assert node2.node_id == node.node_id
        assert node2.host == node.host
        assert node2.port == node.port
        assert node2.status == node.status
        assert node2.current_load == node.current_load


class TestLoadBalancer:
    """测试负载均衡器"""
    
    def test_round_robin(self):
        """测试轮询策略"""
        lb = LoadBalancer("round_robin")
        
        nodes = [
            ClusterNode("node_1"),
            ClusterNode("node_2"),
            ClusterNode("node_3")
        ]
        
        # 轮询应该按顺序返回
        assert lb.select_node(nodes).node_id == "node_1"
        assert lb.select_node(nodes).node_id == "node_2"
        assert lb.select_node(nodes).node_id == "node_3"
        assert lb.select_node(nodes).node_id == "node_1"  # 循环
    
    def test_least_connections(self):
        """测试最少连接策略"""
        lb = LoadBalancer("least_connections")
        
        nodes = [
            ClusterNode("node_1"),
            ClusterNode("node_2"),
            ClusterNode("node_3")
        ]
        nodes[0].active_connections = 10
        nodes[1].active_connections = 5
        nodes[2].active_connections = 15
        
        selected = lb.select_node(nodes)
        assert selected.node_id == "node_2"
    
    def test_least_load(self):
        """测试最小负载策略"""
        lb = LoadBalancer("least_load")
        
        nodes = [
            ClusterNode("node_1", capacity=10.0),
            ClusterNode("node_2", capacity=10.0),
            ClusterNode("node_3", capacity=10.0)
        ]
        nodes[0].current_load = 5.0
        nodes[1].current_load = 3.0
        nodes[2].current_load = 8.0
        
        selected = lb.select_node(nodes)
        assert selected.node_id == "node_2"
    
    def test_empty_nodes(self):
        """测试空节点列表"""
        lb = LoadBalancer()
        assert lb.select_node([]) is None


class TestClusterManager:
    """测试集群管理器"""
    
    def test_creation(self):
        """测试创建"""
        manager = ClusterManager(node_id="master", host="localhost", port=8000)
        assert manager.node_id == "master"
        assert manager.host == "localhost"
        assert manager.port == 8000
        assert len(manager.nodes) == 1  # 自动注册自己
    
    def test_register_node(self):
        """测试注册节点"""
        manager = ClusterManager()
        node = manager.register_node("worker_1", "192.168.1.1", 8001)
        
        assert node.node_id == "worker_1"
        assert node.host == "192.168.1.1"
        assert node.port == 8001
        assert len(manager.nodes) == 2
    
    def test_unregister_node(self):
        """测试注销节点"""
        manager = ClusterManager()
        manager.register_node("worker_1")
        
        assert manager.unregister_node("worker_1") is True
        assert len(manager.nodes) == 1  # 只剩自己
        assert manager.unregister_node("nonexistent") is False
    
    def test_heartbeat(self):
        """测试心跳"""
        manager = ClusterManager()
        manager.register_node("worker_1")
        
        # 模拟超时
        manager.nodes["worker_1"].last_heartbeat = time.time() - 60
        assert manager.nodes["worker_1"].is_healthy(timeout=30.0) is False
        
        # 发送心跳
        assert manager.heartbeat("worker_1", load=0.5, connections=10) is True
        assert manager.nodes["worker_1"].is_healthy(timeout=30.0) is True
        assert manager.nodes["worker_1"].current_load == 0.5
        assert manager.nodes["worker_1"].active_connections == 10
    
    def test_heartbeat_unknown_node(self):
        """测试未知节点的心跳"""
        manager = ClusterManager()
        assert manager.heartbeat("unknown") is False
    
    def test_get_healthy_nodes(self):
        """测试获取健康节点"""
        manager = ClusterManager()
        manager.register_node("worker_1")
        manager.register_node("worker_2")
        
        # 模拟一个节点超时
        manager.nodes["worker_1"].last_heartbeat = time.time() - 60
        
        healthy = manager.get_healthy_nodes()
        assert len(healthy) == 2  # 自己 + worker_2
    
    def test_get_node_for_task(self):
        """测试获取任务节点"""
        manager = ClusterManager()
        manager.register_node("worker_1")
        manager.register_node("worker_2")
        
        node = manager.get_node_for_task()
        assert node is not None
        assert node.node_id in [manager.node_id, "worker_1", "worker_2"]
    
    def test_check_health(self):
        """测试健康检查"""
        manager = ClusterManager()
        manager.register_node("worker_1")
        
        # 模拟超时
        manager.nodes["worker_1"].last_heartbeat = time.time() - 60
        manager.heartbeat_timeout = 30.0
        
        results = manager.check_health()
        assert results["worker_1"] == NodeStatus.UNHEALTHY
    
    def test_check_health_recovery(self):
        """测试健康恢复"""
        manager = ClusterManager()
        manager.register_node("worker_1")
        
        # 先设为不健康
        manager.nodes["worker_1"].status = NodeStatus.UNHEALTHY
        manager.nodes["worker_1"].last_heartbeat = time.time()
        
        results = manager.check_health()
        assert results["worker_1"] == NodeStatus.HEALTHY
    
    def test_get_cluster_stats(self):
        """测试获取集群统计"""
        manager = ClusterManager()
        manager.register_node("worker_1")
        manager.register_node("worker_2")
        
        stats = manager.get_cluster_stats()
        assert stats["total_nodes"] == 3
        assert stats["healthy_nodes"] == 3
        assert "average_load" in stats
    
    def test_set_load_balancer_strategy(self):
        """测试设置负载均衡策略"""
        manager = ClusterManager()
        manager.set_load_balancer_strategy("least_load")
        assert manager.load_balancer.strategy == "least_load"
    
    def test_callback(self):
        """测试回调"""
        manager = ClusterManager()
        
        events = []
        def on_event(event, data):
            events.append(event)
        
        manager.register_callback(on_event)
        manager.register_node("worker_1")
        
        assert "node_joined" in events
    
    def test_clear(self):
        """测试清空"""
        manager = ClusterManager()
        manager.register_node("worker_1")
        
        manager.clear()
        assert len(manager.nodes) == 0


class TestServiceRegistry:
    """测试服务注册表"""
    
    def test_creation(self):
        """测试创建"""
        registry = ServiceRegistry()
        assert len(registry.get_all_services()) == 0
    
    def test_register_service(self):
        """测试注册服务"""
        registry = ServiceRegistry()
        registry.register_service("compute", "node_1")
        registry.register_service("compute", "node_2")
        registry.register_service("storage", "node_1")
        
        compute_nodes = registry.get_service_nodes("compute")
        assert len(compute_nodes) == 2
        assert "node_1" in compute_nodes
        assert "node_2" in compute_nodes
        
        storage_nodes = registry.get_service_nodes("storage")
        assert len(storage_nodes) == 1
    
    def test_unregister_service(self):
        """测试注销服务"""
        registry = ServiceRegistry()
        registry.register_service("compute", "node_1")
        registry.register_service("compute", "node_2")
        
        registry.unregister_service("compute", "node_1")
        
        compute_nodes = registry.get_service_nodes("compute")
        assert len(compute_nodes) == 1
        assert "node_2" in compute_nodes
    
    def test_get_node_services(self):
        """测试获取节点服务"""
        registry = ServiceRegistry()
        registry.register_service("compute", "node_1")
        registry.register_service("storage", "node_1")
        
        services = registry.get_node_services("node_1")
        assert "compute" in services
        assert "storage" in services
    
    def test_is_service_available(self):
        """测试服务可用性检查"""
        registry = ServiceRegistry()
        assert registry.is_service_available("compute") is False
        
        registry.register_service("compute", "node_1")
        assert registry.is_service_available("compute") is True
    
    def test_remove_node(self):
        """测试移除节点"""
        registry = ServiceRegistry()
        registry.register_service("compute", "node_1")
        registry.register_service("storage", "node_1")
        
        registry.remove_node("node_1")
        
        assert len(registry.get_service_nodes("compute")) == 0
        assert len(registry.get_service_nodes("storage")) == 0
    
    def test_clear(self):
        """测试清空"""
        registry = ServiceRegistry()
        registry.register_service("compute", "node_1")
        
        registry.clear()
        assert len(registry.get_all_services()) == 0
