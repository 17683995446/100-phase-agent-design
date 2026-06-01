"""
系统诊断工具测试
"""

import os
import tempfile
import time
import pytest
from core import (
    EternalSelfAgent,
    SystemDiagnostics,
    DiagnosticResult,
    diagnose_agent
)


class TestDiagnosticResult:
    """测试诊断结果数据类"""
    
    def test_init(self):
        """测试初始化"""
        result = DiagnosticResult(
            component="test",
            status="healthy",
            message="test message",
            details={"key": "value"}
        )
        
        assert result.component == "test"
        assert result.status == "healthy"
        assert result.message == "test message"
        assert result.details == {"key": "value"}


class TestSystemDiagnostics:
    """测试系统诊断工具"""
    
    def test_basic_initialization(self):
        """测试基本初始化"""
        diagnostic = SystemDiagnostics()
        
        # 应该有默认的检查
        assert len(diagnostic.checks) > 0
        assert "memory" in diagnostic.checks
        assert "cpu" in diagnostic.checks
        assert "runtime" in diagnostic.checks
        assert "gc" in diagnostic.checks
    
    def test_register_unregister_check(self):
        """测试注册和注销检查"""
        diagnostic = SystemDiagnostics()
        initial_count = len(diagnostic.checks)
        
        # 注册一个新检查
        def test_check():
            return DiagnosticResult(
                component="test_check",
                status="healthy",
                message="test"
            )
        
        diagnostic.register_check("test", test_check)
        assert len(diagnostic.checks) == initial_count + 1
        assert "test" in diagnostic.checks
        
        # 注销检查
        diagnostic.unregister_check("test")
        assert len(diagnostic.checks) == initial_count
        assert "test" not in diagnostic.checks
    
    def test_run_all_checks(self):
        """测试运行所有检查"""
        diagnostic = SystemDiagnostics()
        results = diagnostic.run_all_checks()
        
        assert len(results) == len(diagnostic.checks)
    
    def test_run_single_check(self):
        """测试运行单个检查"""
        diagnostic = SystemDiagnostics()
        
        result = diagnostic.run_check("memory")
        assert result is not None
        assert result.component == "memory"
        
        # 测试不存在的检查
        assert diagnostic.run_check("non_existent") is None
    
    def test_get_summary(self):
        """测试获取诊断摘要"""
        diagnostic = SystemDiagnostics()
        diagnostic.run_all_checks()
        
        summary = diagnostic.get_summary()
        
        assert "check_count" in summary
        assert "healthy" in summary
        assert "warning" in summary
        assert "error" in summary
        assert "overall_status" in summary
        assert summary["check_count"] > 0
    
    def test_generate_report(self):
        """测试生成诊断报告"""
        diagnostic = SystemDiagnostics()
        diagnostic.run_all_checks()
        
        report = diagnostic.generate_report()
        
        assert "系统诊断报告" in report
        assert "详细检查结果" in report


class TestAgentDiagnostics:
    """测试智能体诊断功能"""
    
    def test_diagnose_agent(self):
        """测试智能体诊断"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            
            # 添加一些数据
            agent.knowledge_graph.add_node("test_node")
            agent.knowledge_graph.add_edge("test_node", "another_node", "related", 0.5)
            agent.task_queue.add("test_task")
            
            # 运行诊断
            diag_result = diagnose_agent(agent)
            
            assert "summary" in diag_result
            assert "results" in diag_result
            assert "report" in diag_result
            
            summary = diag_result["summary"]
            assert "check_count" in summary
            assert "overall_status" in summary
            assert summary["overall_status"] in ["healthy", "warning", "error"]
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
    
    def test_custom_check_with_agent(self):
        """测试带智能体的自定义检查"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            diagnostic = SystemDiagnostics()
            
            def custom_check(agent):
                return DiagnosticResult(
                    component="custom",
                    status="healthy",
                    message="custom check",
                    details={"has_agent": agent is not None}
                )
            
            diagnostic.register_check("custom", custom_check)
            
            # 运行检查并传 agent
            result = diagnostic.run_check("custom", agent)
            
            assert result is not None
            assert result.details["has_agent"] is True
            
            agent.shutdown()
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
