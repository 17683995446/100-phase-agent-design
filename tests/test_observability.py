import os
import tempfile
import pytest
from core import (
    EternalSelfAgent, Counter, Gauge, MetricsCollector
)


class TestMetrics:
    
    def test_counter(self):
        """测试计数器指标"""
        counter = Counter("test_counter")
        assert counter.get() == 0
        
        counter.inc()
        assert counter.get() == 1
        
        counter.inc(5)
        assert counter.get() == 6
        
        data = counter.to_dict()
        assert data["name"] == "test_counter"
        assert data["type"] == "counter"
        assert data["value"] == 6
    
    def test_counter_with_labels(self):
        """测试带标签的计数器"""
        counter = Counter("test_counter", labels={"service": "api", "env": "test"})
        assert counter.labels == {"service": "api", "env": "test"}
        assert counter.get() == 0
    
    def test_gauge(self):
        """测试仪表盘指标"""
        gauge = Gauge("test_gauge")
        assert gauge.get() == 0.0
        
        gauge.set(100.0)
        assert gauge.get() == 100.0
        
        gauge.inc(10.0)
        assert gauge.get() == 110.0
        
        gauge.dec(5.0)
        assert gauge.get() == 105.0
        
        data = gauge.to_dict()
        assert data["name"] == "test_gauge"
        assert data["type"] == "gauge"
        assert data["value"] == 105.0
    
    def test_metrics_collector(self):
        """测试指标收集器"""
        collector = MetricsCollector()
        
        # 创建计数器
        counter = collector.counter("requests_total", labels={"endpoint": "/api"})
        counter.inc(10)
        
        # 创建仪表盘
        gauge = collector.gauge("active_connections")
        gauge.set(5)
        
        # 导出指标
        metrics = collector.export()
        assert len(metrics) == 2
        
        # 验证导出
        json_output = collector.export_json()
        assert "exported_at" in json_output
        assert "metrics" in json_output
    
    def test_metrics_reset(self):
        """测试指标重置"""
        collector = MetricsCollector()
        collector.counter("test").inc(5)
        assert len(collector.export()) == 1
        
        collector.reset()
        assert len(collector.export()) == 0
    
    def test_uptime(self):
        """测试运行时间"""
        collector = MetricsCollector()
        import time
        time.sleep(0.01)
        assert collector.get_uptime() > 0


class TestAgentObservability:
    
    def test_agent_has_metrics(self):
        """测试 Agent 有指标收集器"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            assert hasattr(agent, "metrics")
            assert isinstance(agent.metrics, MetricsCollector)
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
    
    def test_enhanced_health_check(self):
        """测试增强健康检查"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            
            health = agent.enhanced_health_check()
            assert health["system_alive"] is True
            assert health["knowledge_graph"] == "healthy"
            assert health["task_queue"] == "healthy"
            assert health["overall"] == "healthy"
            assert "timestamp" in health
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
    
    def test_get_metrics(self):
        """测试获取指标"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            
            metrics = agent.get_metrics()
            assert "uptime" in metrics
            assert "metrics" in metrics
            assert isinstance(metrics["metrics"], list)
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
    
    def test_export_metrics_json(self):
        """测试导出指标 JSON"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            
            json_str = agent.export_metrics_json()
            assert "exported_at" in json_str
            assert "uptime" in json_str
            assert "metrics" in json_str
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
    
    def test_task_execution_updates_metrics(self):
        """测试任务执行更新指标"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            
            # 初始指标
            initial_metrics = agent.get_metrics()
            initial_task_count = 0
            for m in initial_metrics["metrics"]:
                if m["name"] == "tasks_executed":
                    initial_task_count = m["value"]
                    break
            
            # 执行一个任务
            agent.execute_task("test_task")
            
            # 检查指标更新
            final_metrics = agent.get_metrics()
            task_count_updated = False
            for m in final_metrics["metrics"]:
                if m["name"] == "tasks_executed" and m["value"] == initial_task_count + 1:
                    task_count_updated = True
                if m["name"] == "graph_nodes" and m["value"] > 0:
                    assert True
            
            assert task_count_updated
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
            if os.path.exists("eternal_self_agent.log"):
                os.remove("eternal_self_agent.log")
