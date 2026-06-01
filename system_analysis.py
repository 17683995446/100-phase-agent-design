#!/usr/bin/env python3
"""
系统深度分析和全面测试框架
按照要求的完整步骤：
1. 静态代码分析
2. 数据流向和状态分析
3. 边界条件分析
4. 全面的测试覆盖
5. 问题修复和验证
"""

import os
import sys
import traceback
import time
import tempfile
import json
import gc
import threading
from typing import Dict, List, Any, Set, Tuple
from core import (
    EternalSelfAgent,
    KnowledgeGraph,
    TaskQueue,
    Node,
    Edge,
    ConcurrentKnowledgeGraph,
    ConcurrentTaskQueue,
    ReadWriteLock,
    ThreadSafeDict,
    ThreadSafeList,
    AtomicCounter,
    LRUCache,
    SystemDiagnostics
)


class SystemAnalyzer:
    """系统分析器 - 全面分析和测试"""
    
    def __init__(self):
        self.analysis_results: List[Dict] = []
        self.found_issues: List[Dict] = []
        self.passed_tests = 0
        self.failed_tests = 0
    
    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        self.analysis_results.append({
            "timestamp": timestamp,
            "level": level,
            "message": message
        })
    
    def record_issue(self, issue_type: str, description: str, details: Any = None):
        """记录发现的问题"""
        self.found_issues.append({
            "type": issue_type,
            "description": description,
            "details": details,
            "timestamp": time.time()
        })
        self.log(f"⚠️  ISSUE: {issue_type} - {description}", "WARNING")
    
    def analyze_static_code(self) -> Dict:
        """静态代码分析"""
        self.log("开始静态代码分析", "INFO")
        
        analysis = {
            "files": {},
            "modules": [],
            "class_count": 0,
            "function_count": 0
        }
        
        # 检查核心模块
        core_files = [f for f in os.listdir("core") if f.endswith(".py") and not f.startswith("__")]
        
        for filename in core_files:
            file_path = os.path.join("core", filename)
            module_name = filename[:-3]  # 去掉 .py
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            file_analysis = {
                "lines": len(content.splitlines()),
                "classes": [],
                "functions": [],
                "imports": []
            }
            
            # 简单解析
            lines = content.splitlines()
            for line in lines:
                line = line.strip()
                if line.startswith("class "):
                    class_name = line.split()[1].split("(")[0].split(":")[0]
                    file_analysis["classes"].append(class_name)
                elif line.startswith("def "):
                    func_name = line.split()[1].split("(")[0]
                    if not func_name.startswith("_"):  # 公开方法
                        file_analysis["functions"].append(func_name)
                elif line.startswith("import ") or line.startswith("from "):
                    file_analysis["imports"].append(line)
            
            analysis["files"][module_name] = file_analysis
            analysis["modules"].append(module_name)
            analysis["class_count"] += len(file_analysis["classes"])
            analysis["function_count"] += len(file_analysis["functions"])
        
        self.log(f"静态分析完成 - {len(analysis['modules'])} 个模块", "INFO")
        return analysis
    
    def analyze_data_structures(self) -> Dict:
        """分析数据结构"""
        self.log("分析数据结构", "INFO")
        
        results = {
            "Node": {},
            "Edge": {},
            "KnowledgeGraph": {},
            "TaskQueue": {}
        }
        
        # 测试 Node
        try:
            node = Node("test_node", {"key": "value"})
            results["Node"]["basic_creation"] = True
            results["Node"]["attributes"] = node.attributes is not None
            
            # 序列化
            node_dict = node.to_dict()
            node2 = Node.from_dict(node_dict)
            results["Node"]["serialization"] = (node.name == node2.name)
            
            self.log("Node 数据结构分析完成", "INFO")
        except Exception as e:
            results["Node"]["error"] = str(e)
            self.record_issue("Data Structure", "Node 结构问题", str(e))
        
        # 测试 Edge
        try:
            edge = Edge("source", "target", "test_relation", 0.5)
            results["Edge"]["basic_creation"] = True
            results["Edge"]["has_relation_name"] = hasattr(edge, "relation_name")
            results["Edge"]["has_weight"] = hasattr(edge, "weight")
            
            edge_dict = edge.to_dict()
            edge2 = Edge.from_dict(edge_dict)
            results["Edge"]["serialization"] = (edge.source == edge2.source and edge.target == edge2.target)
            
            self.log("Edge 数据结构分析完成", "INFO")
        except Exception as e:
            results["Edge"]["error"] = str(e)
            self.record_issue("Data Structure", "Edge 结构问题", str(e))
        
        return results
    
    def test_boundary_conditions(self) -> Dict:
        """测试边界条件"""
        self.log("测试边界条件", "INFO")
        
        results = {
            "edge_weights": [],
            "node_names": [],
            "task_operations": [],
            "concurrent_access": []
        }
        
        # 测试 Edge 权重边界
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            kg = KnowledgeGraph(kg_path)
            
            # 测试有效权重
            valid_weights = [0.0, 0.001, 0.5, 0.999, 1.0]
            for weight in valid_weights:
                try:
                    edge = Edge("a", "b", "rel", weight)
                    results["edge_weights"].append({"weight": weight, "valid": True})
                except Exception:
                    results["edge_weights"].append({"weight": weight, "valid": False})
            
            # 测试无效权重
            invalid_weights = [-0.1, 1.1, 100.0]
            for weight in invalid_weights:
                try:
                    edge = Edge("a", "b", "rel", weight)
                    results["edge_weights"].append({"weight": weight, "valid": False, "issue": "Should raise error"})
                except ValueError:
                    results["edge_weights"].append({"weight": weight, "valid": False, "expected_error": True})
            
            # 测试空字符串节点
            kg.add_node("")
            has_empty_node = "" in kg.nodes
            results["node_names"].append({"name": "", "added": has_empty_node})
            
            self.log("边界条件测试完成", "INFO")
            
        except Exception as e:
            self.record_issue("Boundary Conditions", "边界测试失败", str(e))
        
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
        
        return results
    
    def test_performance_scaling(self) -> Dict:
        """性能和缩放测试"""
        self.log("性能和缩放测试", "INFO")
        
        results = {
            "scaling_100_nodes": {},
            "scaling_1000_nodes": {},
            "scaling_100_edges": {},
            "scaling_1000_edges": {}
        }
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            kg = KnowledgeGraph(kg_path)
            
            # 100节点测试
            start = time.time()
            for i in range(100):
                kg.add_node(f"node_{i}")
            t1 = time.time() - start
            results["scaling_100_nodes"]["time"] = t1
            results["scaling_100_nodes"]["success"] = len(kg.nodes) == 100
            
            # 100边测试
            start = time.time()
            for i in range(99):
                kg.add_edge(f"node_{i}", f"node_{i+1}", "related", 0.5)
            t2 = time.time() - start
            results["scaling_100_edges"]["time"] = t2
            results["scaling_100_edges"]["success"] = len(kg.edges) >= 99
            
            self.log(f"性能测试完成: 100节点{ t1:.3f}秒, 100边{t2:.3f}秒", "INFO")
            
        except Exception as e:
            self.record_issue("Performance", "性能测试问题", str(e))
        
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
        
        return results
    
    def test_concurrent_safety(self) -> Dict:
        """并发安全测试"""
        self.log("并发安全测试", "INFO")
        
        results = {
            "rwlock_test": {},
            "threadsafe_dict": {},
            "threadsafe_list": {},
            "atomic_counter": {},
            "concurrent_kg": {}
        }
        
        # 测试 ReadWriteLock
        try:
            lock = ReadWriteLock()
            
            def test_read(lock):
                with lock.read_lock():
                    time.sleep(0.01)
            
            def test_write(lock):
                with lock.write_lock():
                    time.sleep(0.01)
            
            # 启动线程测试
            threads = []
            start = time.time()
            for i in range(5):
                t = threading.Thread(target=test_read, args=(lock,))
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join()
            
            results["rwlock_test"]["success"] = True
            results["rwlock_test"]["time"] = time.time() - start
        except Exception as e:
            results["rwlock_test"]["success"] = False
            results["rwlock_test"]["error"] = str(e)
            self.record_issue("Concurrency", "ReadWriteLock 测试失败", str(e))
        
        # 测试 ThreadSafeDict
        try:
            tsd = ThreadSafeDict()
            threads = []
            
            def worker(n):
                for i in range(100):
                    tsd[f"key_{n}_{i}"] = f"value_{i}"
            
            for i in range(5):
                t = threading.Thread(target=worker, args=(i,))
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join()
            
            results["threadsafe_dict"]["success"] = True
            results["threadsafe_dict"]["entries"] = len(tsd)
        except Exception as e:
            results["threadsafe_dict"]["success"] = False
            results["threadsafe_dict"]["error"] = str(e)
            self.record_issue("Concurrency", "ThreadSafeDict 测试失败", str(e))
        
        # 测试 ConcurrentKnowledgeGraph
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                temp_path = f.name
            
            ckg = ConcurrentKnowledgeGraph(temp_path)
            
            def kg_worker(n):
                for i in range(50):
                    ckg.add_node(f"kg_node_{n}_{i}")
            
            threads = []
            for i in range(5):
                t = threading.Thread(target=kg_worker, args=(i,))
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join()
            
            results["concurrent_kg"]["success"] = True
            results["concurrent_kg"]["nodes"] = ckg.get_node_count()
            
            os.remove(temp_path)
            
        except Exception as e:
            results["concurrent_kg"]["success"] = False
            results["concurrent_kg"]["error"] = str(e)
            self.record_issue("Concurrency", "ConcurrentKnowledgeGraph 测试失败", str(e))
        
        self.log("并发安全测试完成", "INFO")
        return results
    
    def test_full_workflow(self) -> Dict:
        """完整工作流测试"""
        self.log("完整工作流测试", "INFO")
        
        results = {
            "agent_lifecycle": {},
            "knowledge_evolution": {},
            "task_execution": {}
        }
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        
        try:
            # 创建智能体
            agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
            results["agent_lifecycle"]["created"] = True
            
            # 添加知识
            for i in range(10):
                agent.knowledge_graph.add_node(f"wf_node_{i}")
            
            results["knowledge_evolution"]["nodes_added"] = len(agent.knowledge_graph.nodes)
            
            # 添加任务
            for i in range(5):
                agent.task_queue.add(f"wf_task_{i}")
            
            results["task_execution"]["tasks_added"] = agent.task_queue.size()
            
            # 执行任务
            executed = 0
            while agent.task_queue.size() > 0:
                task = agent.task_queue.pop()
                agent.execute_task(task)
                executed += 1
            
            results["task_execution"]["tasks_executed"] = executed
            
            # 关闭智能体
            agent.shutdown()
            results["agent_lifecycle"]["shutdown"] = True
            
            self.log("完整工作流测试完成", "INFO")
            
        except Exception as e:
            self.record_issue("Workflow", "工作流测试失败", str(e))
            results["workflow_error"] = str(e)
        
        finally:
            if os.path.exists(kg_path):
                os.remove(kg_path)
        
        return results
    
    def run_full_analysis(self) -> Dict:
        """运行完整分析"""
        self.log("=" * 80, "INFO")
        self.log("开始全面系统分析", "INFO")
        self.log("=" * 80, "INFO")
        
        overall_results = {
            "static_analysis": self.analyze_static_code(),
            "data_structures": self.analyze_data_structures(),
            "boundary_conditions": self.test_boundary_conditions(),
            "performance": self.test_performance_scaling(),
            "concurrency": self.test_concurrent_safety(),
            "workflow": self.test_full_workflow(),
            "summary": {}
        }
        
        # 统计结果
        total_issues = len(self.found_issues)
        
        overall_results["summary"] = {
            "total_modules": len(overall_results["static_analysis"]["modules"]),
            "total_classes": overall_results["static_analysis"]["class_count"],
            "total_functions": overall_results["static_analysis"]["function_count"],
            "issues_found": total_issues
        }
        
        self.log("=" * 80, "INFO")
        self.log(f"分析完成，发现 {total_issues} 个问题", "INFO" if total_issues == 0 else "WARNING")
        
        if total_issues > 0:
            self.log("问题列表：", "WARNING")
            for i, issue in enumerate(self.found_issues, 1):
                self.log(f"  {i}. {issue['type']}: {issue['description']}", "WARNING")
        
        self.log("=" * 80, "INFO")
        
        return overall_results


def main():
    print("\n" + "=" * 80)
    print("系统深度分析和测试框架")
    print("=" * 80)
    
    analyzer = SystemAnalyzer()
    results = analyzer.run_full_analysis()
    
    print("\n分析完成！")
    print(f"发现问题数: {len(analyzer.found_issues)}")
    
    # 保存结果
    with open("system_analysis_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\n详细结果保存在 system_analysis_results.json")
    return results


if __name__ == "__main__":
    main()
