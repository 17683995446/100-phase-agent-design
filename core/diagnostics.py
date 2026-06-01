"""
系统诊断工具
"""

import time
import sys
import gc
import os
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from core.knowledge_graph import KnowledgeGraph
from core.task_queue import TaskQueue
from core.agent import EternalSelfAgent


@dataclass
class DiagnosticResult:
    """诊断结果"""
    component: str
    status: str  # "healthy", "warning", "error"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class SystemDiagnostics:
    """系统诊断工具"""
    
    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.results: List[DiagnosticResult] = []
        self.start_time: float = time.time()
        
        # 注册内置检查
        self._register_builtin_checks()
    
    def _register_builtin_checks(self):
        """注册内置的检查项"""
        self.register_check("memory", self._check_memory)
        self.register_check("cpu", self._check_cpu)
        self.register_check("runtime", self._check_runtime)
        self.register_check("gc", self._check_gc)
    
    def register_check(self, name: str, check_func: Callable):
        """注册一个诊断检查"""
        self.checks[name] = check_func
    
    def unregister_check(self, name: str):
        """取消注册一个诊断检查"""
        if name in self.checks:
            del self.checks[name]
    
    def run_all_checks(self, agent: Optional[EternalSelfAgent] = None) -> List[DiagnosticResult]:
        """
        运行所有注册的检查
        
        Args:
            agent: 可选的智能体实例
            
        Returns:
            诊断结果列表
        """
        self.results = []
        
        for name, check_func in self.checks.items():
            try:
                if agent is not None and hasattr(check_func, '__code__'):
                    # 如果函数接受 agent 参数
                    if 'agent' in check_func.__code__.co_varnames:
                        result = check_func(agent)
                    else:
                        result = check_func()
                else:
                    result = check_func()
                self.results.append(result)
            except Exception as e:
                self.results.append(DiagnosticResult(
                    component=name,
                    status="error",
                    message=f"检查执行失败: {str(e)}",
                    details={"exception": str(e)}
                ))
        
        return self.results
    
    def run_check(self, name: str, agent: Optional[EternalSelfAgent] = None) -> Optional[DiagnosticResult]:
        """
        运行单个检查
        
        Args:
            name: 检查名称
            agent: 可选的智能体实例
            
        Returns:
            诊断结果或 None
        """
        if name not in self.checks:
            return None
        
        try:
            check_func = self.checks[name]
            if agent is not None and 'agent' in check_func.__code__.co_varnames:
                result = check_func(agent)
            else:
                result = check_func()
            return result
        except Exception as e:
            return DiagnosticResult(
                component=name,
                status="error",
                message=f"检查执行失败: {str(e)}"
            )
    
    def _check_memory(self) -> DiagnosticResult:
        """检查内存状态"""
        try:
            objects = gc.get_objects()
            obj_count = len(objects)
            
            # 简单的内存健康判断
            status = "healthy"
            message = "内存状态正常"
            
            if obj_count > 100000:
                status = "warning"
                message = "对象数量较多，可能需要关注"
            elif obj_count > 500000:
                status = "error"
                message = "对象数量异常高"
            
            return DiagnosticResult(
                component="memory",
                status=status,
                message=message,
                details={"object_count": obj_count}
            )
        except Exception as e:
            return DiagnosticResult(
                component="memory",
                status="error",
                message=f"内存检查失败: {str(e)}"
            )
    
    def _check_cpu(self) -> DiagnosticResult:
        """检查 CPU 状态"""
        try:
            # 简单的 CPU 检查，实际项目可能需要更复杂的逻辑
            return DiagnosticResult(
                component="cpu",
                status="healthy",
                message="CPU 状态正常",
                details={"cpu_count": os.cpu_count() or 1}
            )
        except Exception as e:
            return DiagnosticResult(
                component="cpu",
                status="error",
                message=f"CPU 检查失败: {str(e)}"
            )
    
    def _check_runtime(self) -> DiagnosticResult:
        """检查运行时状态"""
        try:
            uptime = time.time() - self.start_time
            python_version = sys.version
            
            return DiagnosticResult(
                component="runtime",
                status="healthy",
                message="运行时状态正常",
                details={
                    "uptime_seconds": uptime,
                    "python_version": python_version,
                    "platform": sys.platform
                }
            )
        except Exception as e:
            return DiagnosticResult(
                component="runtime",
                status="error",
                message=f"运行时检查失败: {str(e)}"
            )
    
    def _check_gc(self) -> DiagnosticResult:
        """检查垃圾回收状态"""
        try:
            gc_stats = gc.get_stats()
            gc_threshold = gc.get_threshold()
            gc_enabled = gc.isenabled()
            
            return DiagnosticResult(
                component="gc",
                status="healthy",
                message="垃圾回收状态正常",
                details={
                    "gc_enabled": gc_enabled,
                    "gc_threshold": gc_threshold,
                    "gc_generations": len(gc_stats)
                }
            )
        except Exception as e:
            return DiagnosticResult(
                component="gc",
                status="error",
                message=f"GC 检查失败: {str(e)}"
            )
    
    def get_summary(self) -> Dict[str, Any]:
        """获取诊断摘要"""
        total = len(self.results)
        healthy = sum(1 for r in self.results if r.status == "healthy")
        warning = sum(1 for r in self.results if r.status == "warning")
        error = sum(1 for r in self.results if r.status == "error")
        
        overall_status = "healthy"
        if error > 0:
            overall_status = "error"
        elif warning > 0:
            overall_status = "warning"
        
        return {
            "timestamp": datetime.now().isoformat(),
            "check_count": total,
            "healthy": healthy,
            "warning": warning,
            "error": error,
            "overall_status": overall_status
        }
    
    def generate_report(self) -> str:
        """
        生成诊断报告
        
        Returns:
            格式化的诊断报告
        """
        summary = self.get_summary()
        
        report = [
            "=" * 70,
            "系统诊断报告",
            "=" * 70,
            f"生成时间: {summary['timestamp']}",
            f"检查项总数: {summary['check_count']}",
            f"健康: {summary['healthy']}",
            f"警告: {summary['warning']}",
            f"错误: {summary['error']}",
            f"总体状态: {summary['overall_status'].upper()}",
            "",
            "详细检查结果:",
            "-" * 70
        ]
        
        for result in self.results:
            status_icon = {
                "healthy": "✅",
                "warning": "⚠️",
                "error": "❌"
            }.get(result.status, "?")
            
            report.append(f"\n{status_icon} {result.component.upper()} - {result.status.upper()}")
            report.append(f"  消息: {result.message}")
            if result.details:
                report.append(f"  详情: {result.details}")
        
        report.extend(["", "=" * 70, "报告结束", "=" * 70])
        
        return "\n".join(report)


# 智能体诊断功能
def diagnose_agent(agent: EternalSelfAgent) -> Dict[str, Any]:
    """
    诊断智能体状态
    
    Args:
        agent: 智能体实例
        
    Returns:
        诊断信息字典
    """
    diagnostic = SystemDiagnostics()
    
    # 添加智能体特定的检查
    def check_agent_status(agent):
        return DiagnosticResult(
            component="agent_status",
            status="healthy" if agent.system_alive else "error",
            message="智能体正在运行" if agent.system_alive else "智能体已停止",
            details={"system_alive": agent.system_alive, "run_counter": agent.run_counter}
        )
    
    def check_knowledge_graph(agent):
        try:
            node_count = agent.knowledge_graph.get_node_count()
            edge_count = agent.knowledge_graph.get_edge_count()
            
            status = "healthy"
            message = "知识图谱状态正常"
            
            if node_count > 10000:
                status = "warning"
                message = "知识图谱规模较大"
            
            return DiagnosticResult(
                component="knowledge_graph",
                status=status,
                message=message,
                details={"node_count": node_count, "edge_count": edge_count}
            )
        except Exception as e:
            return DiagnosticResult(
                component="knowledge_graph",
                status="error",
                message=f"知识图谱检查失败: {str(e)}"
            )
    
    def check_task_queue(agent):
        try:
            queue_size = agent.task_queue.size()
            
            status = "healthy"
            message = "任务队列状态正常"
            
            if queue_size > 1000:
                status = "warning"
                message = "任务队列积压较多"
            
            return DiagnosticResult(
                component="task_queue",
                status=status,
                message=message,
                details={"queue_size": queue_size}
            )
        except Exception as e:
            return DiagnosticResult(
                component="task_queue",
                status="error",
                message=f"任务队列检查失败: {str(e)}"
            )
    
    diagnostic.register_check("agent_status", check_agent_status)
    diagnostic.register_check("knowledge_graph", check_knowledge_graph)
    diagnostic.register_check("task_queue", check_task_queue)
    
    # 运行所有检查
    diagnostic.run_all_checks(agent)
    
    return {
        "summary": diagnostic.get_summary(),
        "results": diagnostic.results,
        "report": diagnostic.generate_report()
    }
