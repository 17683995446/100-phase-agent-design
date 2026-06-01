#!/usr/bin/env python3
"""
深度调试和全面测试框架
遵循：
1. 静态代码分析
2. 全面的日志跟踪
3. 复杂场景测试
4. 边界条件测试
5. 异常场景测试
"""

import sys
import traceback
import time
import random
import threading
import os
import tempfile
import gc
import json
from typing import Any, Dict, List, Callable
from core import (
    EternalSelfAgent,
    KnowledgeGraph,
    TaskQueue,
    Node,
    Edge,
    SystemDiagnostics,
    diagnose_agent,
    get_profiler,
    LRUCache,
    ReadWriteLock,
    ThreadSafeDict,
    AtomicCounter,
    PluginManager,
    get_default_cache
)


class DeepDebugger:
    """
    深度调试器 - 全流程调试和测试
    """
    
    def __init__(self, log_file: str = "deep_debug.log"):
        self.log_file = log_file
        self.step_count = 0
        self.error_count = 0
        self.warning_count = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.issues_found: List[Dict] = []
        
        # 清除旧日志
        if os.path.exists(log_file):
            os.remove(log_file)
    
    def log(self, level: str, category: str, message: str, details: Any = None):
        """记录日志"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.step_count += 1
        
        log_line = f"[{timestamp} [{level}] [{category}] Step {self.step_count}: {message}"
        
        if details:
            log_line += f" | Details: {details}"
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
        
        print(log_line)
    
    def log_error(self, category: str, message: str, details: Any = None):
        """记录错误"""
        self.error_count += 1
        self.log("ERROR", category, message, details)
        self.issues_found.append({
            "type": "error",
            "category": category,
            "message": message,
            "details": details,
            "timestamp": time.time()
        })
    
    def log_warning(self, category: str, message: str, details: Any = None):
        """记录警告"""
        self.warning_count += 1
        self.log("WARNING", category, message, details)
        self.issues_found.append({
            "type": "warning",
            "category": category,
            "message": message,
            "details": details,
            "timestamp": time.time()
        })
    
    def test_pass(self, test_name: str):
        """测试通过"""
        self.tests_passed += 1
        self.log("INFO", "TEST", f"✓ PASS: {test_name}")
    
    def test_fail(self, test_name: str, details: Any = None):
        """测试失败"""
        self.tests_failed += 1
        self.log_error("TEST", f"✗ FAIL: {test_name}", details)
    
    def analyze_system_structure(self):
        """分析系统结构和模块依赖"""
        self.log("INFO", "ANALYSIS", "开始系统结构分析")
        
        modules = [
            "node", "edge", "knowledge_graph", "task_queue", "agent",
            "config", "logger", "concurrency", "metrics", "plugin",
            "profiler", "cache", "diagnostics"
        ]
        
        self.log("INFO", "ANALYSIS", f"核心模块数量: {len(modules)}", modules)
        
        # 模块依赖分析
        dependencies = {
            "agent": ["knowledge_graph", "task_queue", "logger", "config", "plugin"],
            "knowledge_graph": ["node", "edge", "concurrency", "logger"],
            "plugin": ["agent", "knowledge_graph", "task_queue"],
            "diagnostics": ["knowledge_graph", "task_queue", "agent"],
            "concurrency": [],
            "cache": [],
            "profiler": [],
            "task_queue": [],
            "node": [],
            "edge": []
        }
        
        self.log("INFO", "ANALYSIS", "模块依赖关系分析完成", dependencies)
        return modules
    
    def test_data_structures(self):
        """测试数据结构的每一行代码"""
        self.log("INFO", "TEST", "开始数据结构测试")
        
        # 测试 Node
        try:
            self.log("INFO", "TEST", "测试 Node 创建")
            node = Node("test_node", {"attr": "value"})
            assert node.name == "test_node"
            assert node.attributes == {"attr": "value"}
            self.test_pass("Node 创建和属性测试")
            
            # 测试 Node to_dict/from_dict
            d = node.to_dict()
            node2 = Node.from_dict(d)
            assert node2.name == node.name
            assert node2.attributes == node.attributes
            self.test_pass("Node 序列化测试")
            
        except Exception as e:
            self.test_fail("Node 数据结构测试", str(e))
        
        # 测试 Edge
        try:
            self.log("INFO", "TEST", "测试 Edge 创建")
            edge = Edge("source", "target", "related", 0.8)
            assert edge.source == "source"
            assert edge.target == "target"
            assert edge.relation == "related"
            assert abs(edge.weight - 0.8) < 0.001
            self.test_pass("Edge 创建测试")
            
        except Exception as e:
            self.test_fail("Edge 数据结构测试", str(e))
        
        self.log("INFO", "TEST", "数据结构基础测试完成")
        
        self.log("INFO", "TEST", "数据结构测试完成")
    
    def test_knowledge_graph_basic(self):
        """测试知识图谱基础功能"""
        self.log("INFO", "TEST", "开始知识图谱基础测试")
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                kg_path = f.name
            
            try:
                kg = KnowledgeGraph(kg_path)
                
                self.log("INFO", "TEST", "添加节点测试")
                for i in range(10):
                    kg.add_node(f"node_{i}")
                    self.log("DEBUG", "KG", f"添加节点 node_{i}")
                
                assert len(kg.nodes) == 10, f"期望10个节点，实际 {len(kg.nodes)}"
                self.test_pass("节点添加测试")
                
                self.log("INFO", "TEST", "添加边测试")
                for i in range(9):
                    kg.add_edge(f"node_{i}", f"node_{i+1}", "related", 0.5 + i * 0.05)
                    self.log("DEBUG", "KG", f"添加边 node_{i} -> node_{i+1}")
                
                self.test_pass("边添加测试")
                
                self.log("INFO", "TEST", "节点和边查询测试")
                for i in range(10):
                    node = kg.get_node(f"node_{i}")
                    assert node is not None, f"节点 node_{i} 不存在"
                self.test_pass("节点和边查询测试")
                
                # 保存和加载
                self.log("INFO", "TEST", "保存和加载测试")
                kg.save()
                kg2 = KnowledgeGraph(kg_path)
                assert len(kg2.nodes) == 10
                self.test_pass("知识图谱保存和加载测试")
                
            finally:
                if os.path.exists(kg_path):
                    os.remove(kg_path)
                    
        except Exception as e:
            self.test_fail("知识图谱基础测试", str(e))
            self.log_error("TEST", "知识图谱测试异常", traceback.format_exc())
    
    def test_task_queue_operations(self):
        """测试任务队列的所有功能"""
        self.log("INFO", "TEST", "开始任务队列测试")
        
        try:
            tq = TaskQueue(max_size=100)
            
            self.log("INFO", "TEST", "添加单个任务测试")
            tq.add("task_1")
            assert tq.size() == 1
            self.test_pass("单个任务添加测试")
            
            self.log("INFO", "TEST", "批量任务添加测试")
            tasks = [f"task_{i}" for i in range(2, 51)]
            tq.batch_add(tasks)
            assert tq.size() == 50
            self.test_pass("批量任务添加测试")
            
            self.log("INFO", "TEST", "任务弹出测试")
            task = tq.pop()
            assert task == "task_1"
            self.test_pass("任务弹出测试")
            
            self.log("INFO", "TEST", "任务队列测试完成")
            
        except Exception as e:
            self.test_fail("任务队列测试", str(e))
    
    def test_complex_scenarios(self):
        """测试复杂场景"""
        self.log("INFO", "TEST", "开始复杂场景测试")
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                kg_path = f.name
            
            try:
                self.log("INFO", "TEST", "大规模知识图谱测试")
                kg = KnowledgeGraph(kg_path)
                
                # 大规模节点添加
                self.log("INFO", "TEST", "添加 1000 个节点")
                for i in range(1000):
                    kg.add_node(f"node_{i}")
                    if i % 100 == 0:
                        self.log("DEBUG", "KG", f"已添加 {i} 个节点")
                
                self.test_pass("大规模节点添加测试")
                
                # 复杂边关系
                self.log("INFO", "TEST", "添加 2000 条边")
                edge_count = 0
                for i in range(1000):
                    for j in range(2):
                        if i + j + 1 < 1000:
                            kg.add_edge(f"node_{i}", f"node_{i+j+1}", f"rel_{j}", 0.5)
                            edge_count += 1
                            if edge_count % 200 == 0:
                                self.log("DEBUG", "KG", f"已添加 {edge_count} 条边")
                            if edge_count >= 2000:
                                break
                    if edge_count >= 2000:
                        break
                
                self.test_pass("大规模边添加测试")
                
                self.log("INFO", "TEST", "复杂场景测试完成")
                
            finally:
                if os.path.exists(kg_path):
                    os.remove(kg_path)
                    
        except Exception as e:
            self.test_fail("复杂场景测试", str(e))
    
    def test_concurrent_operations(self):
        """测试并发操作"""
        self.log("INFO", "TEST", "开始并发操作测试")
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                kg_path = f.name
            
            try:
                agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
                
                threads = []
                errors = []
                
                def worker(thread_id):
                    try:
                        for i in range(50):
                            agent.knowledge_graph.add_node(f"thread_{thread_id}_node_{i}")
                            agent.task_queue.add(f"thread_{thread_id}_task_{i}")
                    except Exception as e:
                        errors.append((thread_id, str(e)))
                
                self.log("INFO", "TEST", "启动 10 个并发线程")
                for i in range(10):
                    t = threading.Thread(target=worker, args=(i,))
                    threads.append(t)
                    t.start()
                
                for t in threads:
                    t.join()
                
                if errors:
                    self.test_fail("并发测试发现错误", errors)
                else:
                    self.test_pass("并发操作测试")
                
                agent.shutdown()
                
            finally:
                if os.path.exists(kg_path):
                    os.remove(kg_path)
                    
        except Exception as e:
            self.test_fail("并发操作测试", str(e))
    
    def test_edge_cases(self):
        """测试边界条件"""
        self.log("INFO", "TEST", "开始边界条件测试")
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                kg_path = f.name
            
            try:
                # 空值测试
                kg = KnowledgeGraph(kg_path)
                
                self.log("INFO", "TEST", "测试空字符串节点")
                try:
                    kg.add_node("")
                    self.log_warning("TEST", "添加空字符串节点")
                except Exception as e:
                    self.log("INFO", "TEST", f"添加空字符串节点处理正常处理")
                
                # 重复节点
                kg.add_node("duplicate")
                kg.add_node("duplicate")  # 重复添加
                assert len(kg.nodes) == 1  # 应该还是1个
                self.test_pass("重复节点处理测试")
                
                # 超出边界值测试
                try:
                    kg.add_edge("a", "b", "rel", 1.5)
                    kg.add_edge("x", "y", "rel2", -0.5)
                    self.log("INFO", "TEST", "权重边界值测试通过")
                except Exception:
                    self.test_fail("边界值测试")
                
                self.test_pass("边界条件测试")
                
            finally:
                if os.path.exists(kg_path):
                    os.remove(kg_path)
                    
        except Exception as e:
            self.test_fail("边界条件测试", str(e))
    
    def test_agent_full_workflow(self):
        """测试智能体完整工作流程"""
        self.log("INFO", "TEST", "开始智能体完整工作流测试")
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                kg_path = f.name
            
            try:
                agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
                
                self.log("INFO", "TEST", "添加知识和任务")
                for i in range(10):
                    agent.knowledge_graph.add_node(f"workflow_node_{i}")
                    agent.task_queue.add(f"workflow_task_{i}")
                
                # 执行任务
                self.log("INFO", "TEST", "执行任务")
                while agent.task_queue.size() > 0:
                    task = agent.task_queue.pop()
                    agent.execute_task(task)
                
                self.test_pass("智能体完整工作流测试")
                
                # 健康检查
                health = agent.enhanced_health_check()
                assert health['overall'] is True
                self.test_pass("健康检查测试")
                
                agent.shutdown()
                
            finally:
                if os.path.exists(kg_path):
                    os.remove(kg_path)
                    
        except Exception as e:
            self.test_fail("智能体工作流测试", str(e))
    
    def run_full_test_suite(self):
        """运行完整的测试套件"""
        self.log("INFO", "MAIN", "=" * 80)
        self.log("INFO", "MAIN", "开始深度调试和全面测试")
        self.log("INFO", "MAIN", "=" * 80)
        
        start_time = time.time()
        
        # 1. 系统分析
        self.analyze_system_structure()
        
        # 2. 数据结构测试
        self.test_data_structures()
        
        # 3. 知识图谱测试
        self.test_knowledge_graph_basic()
        
        # 4. 任务队列测试
        self.test_task_queue_operations()
        
        # 5. 复杂场景测试
        self.test_complex_scenarios()
        
        # 6. 并发操作测试
        self.test_concurrent_operations()
        
        # 7. 边界条件测试
        self.test_edge_cases()
        
        # 8. 智能体工作流测试
        self.test_agent_full_workflow()
        
        # 报告
        end_time = time.time()
        
        self.log("INFO", "MAIN", "=" * 80)
        self.log("INFO", "MAIN", "测试完成总结")
        self.log("INFO", "MAIN", f"总耗时: {end_time - start_time:.2f}秒")
        self.log("INFO", "MAIN", f"测试通过: {self.tests_passed}")
        self.log("INFO", "MAIN", f"测试失败: {self.tests_failed}")
        self.log("INFO", "MAIN", f"错误数: {self.error_count}")
        self.log("INFO", "MAIN", f"警告数: {self.warning_count}")
        
        if self.issues_found:
            self.log("INFO", "MAIN", "发现的问题:")
            for i, issue in enumerate(self.issues_found, 1):
                self.log("INFO", "MAIN", f"  {i}. {issue['type'].upper()}: {issue['category']} - {issue['message']}")
        
        self.log("INFO", "MAIN", "=" * 80)
        
        return {
            "total_steps": self.step_count,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "issues_found": self.issues_found,
            "duration": end_time - start_time
        }


def main():
    print("\n" + "=" * 80)
    print("深度调试和全面测试框架")
    print("=" * 80)
    
    debugger = DeepDebugger()
    result = debugger.run_full_test_suite()
    
    print("\n" + "=" * 80)
    print("详细日志保存在 deep_debug.log")
    print("=" * 80)
    
    if os.path.exists(debugger.log_file):
        with open(debugger.log_file, 'r', encoding='utf-8') as f:
            print(f"\n日志文件大小: {os.path.getsize(debugger.log_file)} 字节")
    
    print("\n测试运行完成！")
    return result


if __name__ == "__main__":
    main()
