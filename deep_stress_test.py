#!/usr/bin/env python3
"""
深度压力测试工具
测试极端复杂场景下的系统稳定性
"""
import os
import sys
import time
import random
import json
import tempfile
from typing import List, Dict, Any

sys.path.insert(0, '/workspace')

from core.agent import EternalSelfAgent
from core.logger import get_logger


class ChaosGenerator:
    """
    混沌生成器 - 制造极端复杂场景
    """
    
    def __init__(self):
        self.logger = get_logger("chaos_test.log")
    
    def generate_massive_knowledge(self, agent: EternalSelfAgent, node_count: int = 10000) -> None:
        """
        生成大规模知识网络
        """
        self.logger.info("ChaosGenerator", "开始生成大规模知识网络", target_nodes=node_count)
        
        nodes = []
        for i in range(node_count):
            node_name = f"chaos_node_{i}_{random.randint(1000, 9999)}"
            nodes.append(node_name)
            agent.knowledge_graph.add_node(
                node_name,
                {"created_by": "chaos_test", "random_value": random.random()}
            )
            if i % 1000 == 0:
                self.logger.debug("ChaosGenerator", f"已添加 {i} 个节点")
        
        # 随机建立大量边
        edge_count = 0
        for i in range(min(50000, node_count * 5)):
            source = random.choice(nodes)
            target = random.choice(nodes)
            relation = random.choice([
                "关联", "衍生", "依赖", "相似", "相反", "包含", "属于", "产生", "影响"
            ])
            weight = random.random()
            agent.knowledge_graph.add_edge(source, target, relation, weight)
            edge_count += 1
            if edge_count % 5000 == 0:
                self.logger.debug("ChaosGenerator", f"已添加 {edge_count} 条边")
        
        self.logger.info("ChaosGenerator", "大规模知识网络生成完成", 
                         nodes=len(agent.knowledge_graph.nodes),
                         edges=len(agent.knowledge_graph.edges))
    
    def generate_chaotic_tasks(self, agent: EternalSelfAgent, task_count: int = 5000) -> None:
        """
        生成混乱任务序列
        """
        self.logger.info("ChaosGenerator", "开始生成混乱任务", target_tasks=task_count)
        
        task_templates = [
            "计算_{value}_的平方",
            "分析_{subject}的_{aspect}",
            "探索_{topic}的{depth}层关系",
            "验证_{hypothesis}的正确性",
            "优化_{process}的{metric}",
            "整合_{source1}与{source2}的信息",
            "监控_{system}的{parameter}",
            "预测_{event}的{outcome}",
            "修复_{component}的{issue}",
            "扩展_{domain}的{feature}"
        ]
        
        subjects = ["系统", "网络", "存储", "计算", "传输", "加密", "压缩", "索引", "缓存", "调度"]
        aspects = ["性能", "可靠性", "扩展性", "安全性", "可用性", "一致性", "完整性", "效率"]
        values = [random.randint(1, 10000) for _ in range(100)]
        depths = [1, 2, 3, 4, 5, 10, 20]
        
        added = 0
        for i in range(task_count):
            template = random.choice(task_templates)
            task = template.format(
                value=random.choice(values),
                subject=random.choice(subjects),
                aspect=random.choice(aspects),
                topic=random.choice(subjects),
                depth=random.choice(depths),
                hypothesis=f"假设_{random.randint(100, 999)}",
                process=random.choice(subjects),
                metric=random.choice(aspects),
                source1=random.choice(subjects),
                source2=random.choice(subjects),
                system=random.choice(subjects),
                parameter=random.choice(aspects),
                event=f"事件_{random.randint(1000, 9999)}",
                outcome=random.choice(["结果", "可能性", "时间", "概率", "影响"]),
                component=random.choice(subjects),
                issue=f"问题_{random.randint(100, 999)}",
                domain=random.choice(subjects),
                feature=random.choice(aspects)
            )
            if agent.add_manual_task(task):
                added += 1
            if i % 500 == 0:
                self.logger.debug("ChaosGenerator", f"已尝试添加 {i} 个任务，成功 {added} 个")
        
        self.logger.info("ChaosGenerator", "混乱任务生成完成", added=added, queue_size=agent.task_queue.size())
    
    def inject_edge_cases(self, agent: EternalSelfAgent) -> None:
        """
        注入边界情况
        """
        self.logger.info("ChaosGenerator", "开始注入边界情况")
        
        # 测试空字符串
        try:
            agent.add_manual_task("")
        except Exception as e:
            self.logger.warn("ChaosGenerator", "空任务测试", exception=str(e))
        
        # 测试超长字符串
        try:
            long_task = "x" * 10000
            agent.add_manual_task(long_task)
        except Exception as e:
            self.logger.warn("ChaosGenerator", "超长任务测试", exception=str(e))
        
        # 测试特殊字符
        try:
            special_task = "测试_!@#$%^&*()_+{}[]|;:\"'<>,.?/~`\n\t\r测试"
            agent.add_manual_task(special_task)
        except Exception as e:
            self.logger.warn("ChaosGenerator", "特殊字符测试", exception=str(e))
        
        # 测试极端权重
        try:
            agent.knowledge_graph.add_node("边界测试节点")
            for w in [-1.0, 0.0, 1.0, 2.0, 0.5, 0.0001, 0.9999]:
                try:
                    agent.knowledge_graph.add_edge("边界测试节点", f"边界_{w}", "测试", w)
                except ValueError:
                    pass
        except Exception as e:
            self.logger.warn("ChaosGenerator", "边界权重测试", exception=str(e))
        
        self.logger.info("ChaosGenerator", "边界情况注入完成")
    
    def simulate_failure_scenarios(self, agent: EternalSelfAgent) -> None:
        """
        模拟故障场景
        """
        self.logger.info("ChaosGenerator", "开始模拟故障场景")
        
        # 模拟大量重复操作
        for i in range(1000):
            try:
                agent.knowledge_graph.add_node(f"重复测试_{i % 10}")
                agent.knowledge_graph.add_edge(
                    f"重复测试_{i % 10}",
                    f"重复测试_{(i + 1) % 10}",
                    "重复关联",
                    0.5
                )
            except Exception:
                pass
        
        # 模拟频繁保存
        for i in range(100):
            try:
                agent.knowledge_graph.save()
            except Exception:
                pass
        
        self.logger.info("ChaosGenerator", "故障场景模拟完成")


class DeepStressTester:
    """
    深度压力测试器
    """
    
    def __init__(self):
        self.logger = get_logger("deep_stress_test.log")
        self.chaos = ChaosGenerator()
        self.results = {}
    
    def run_full_test_suite(self) -> Dict[str, Any]:
        """
        运行完整测试套件
        """
        self.logger.info("DeepStressTester", "="*60)
        self.logger.info("DeepStressTester", "开始深度压力测试")
        self.logger.info("DeepStressTester", "="*60)
        
        temp_dir = tempfile.mkdtemp()
        config_path = os.path.join(temp_dir, "config_test.json")
        kg_path = os.path.join(temp_dir, "kg_test.json")
        
        self.logger.info("DeepStressTester", "初始化测试环境", temp_dir=temp_dir)
        
        try:
            agent = EternalSelfAgent(
                config_path=config_path,
                kg_save_path=kg_path,
                loop_delay=0.001,
                task_queue_max=10000
            )
            
            # 阶段1: 基础功能压力测试
            self._test_phase_1_basic_load(agent)
            
            # 阶段2: 大规模知识网络测试
            self._test_phase_2_massive_knowledge(agent)
            
            # 阶段3: 混乱任务处理测试
            self._test_phase_3_chaotic_tasks(agent)
            
            # 阶段4: 边界情况和故障注入测试
            self._test_phase_4_edge_cases(agent)
            
            # 阶段5: 长时间运行测试
            self._test_phase_5_long_running(agent)
            
            # 收集结果
            self.results = agent.get_system_status()
            self.results["test_passed"] = True
            
            agent.shutdown()
            
        except Exception as e:
            self.logger.error("DeepStressTester", "压力测试过程中发生严重错误", exception=e)
            self.results["test_passed"] = False
            self.results["error"] = str(e)
        
        self._print_test_report()
        return self.results
    
    def _test_phase_1_basic_load(self, agent: EternalSelfAgent):
        """
        阶段1: 基础负载测试
        """
        self.logger.info("DeepStressTester", "开始阶段1: 基础负载测试")
        
        # 添加初始任务
        for i in range(1000):
            agent.add_manual_task(f"基础任务_{i}")
        
        # 执行部分任务
        executed = 0
        for i in range(500):
            task = agent.get_current_task()
            if task:
                agent.execute_task(task)
                executed += 1
                agent.health_check()
        
        self.logger.info("DeepStressTester", "阶段1完成", executed=executed)
    
    def _test_phase_2_massive_knowledge(self, agent: EternalSelfAgent):
        """
        阶段2: 大规模知识网络测试
        """
        self.logger.info("DeepStressTester", "开始阶段2: 大规模知识网络测试")
        
        self.chaos.generate_massive_knowledge(agent, node_count=5000)
        
        # 测试查询性能
        start_time = time.time()
        nodes = list(agent.knowledge_graph.nodes.keys())
        for i in range(1000):
            node = random.choice(nodes) if nodes else "none"
            agent.knowledge_graph.get_edges_from_node(node)
        query_time = time.time() - start_time
        
        self.logger.info("DeepStressTester", "阶段2完成", query_time=query_time)
    
    def _test_phase_3_chaotic_tasks(self, agent: EternalSelfAgent):
        """
        阶段3: 混乱任务处理测试
        """
        self.logger.info("DeepStressTester", "开始阶段3: 混乱任务处理测试")
        
        self.chaos.generate_chaotic_tasks(agent, task_count=3000)
        
        # 执行大量任务
        executed = 0
        start_time = time.time()
        for i in range(2000):
            task = agent.get_current_task()
            if task:
                agent.execute_task(task)
                executed += 1
            agent.health_check()
        
        exec_time = time.time() - start_time
        
        self.logger.info("DeepStressTester", "阶段3完成", executed=executed, time=exec_time)
    
    def _test_phase_4_edge_cases(self, agent: EternalSelfAgent):
        """
        阶段4: 边界情况测试
        """
        self.logger.info("DeepStressTester", "开始阶段4: 边界情况测试")
        
        self.chaos.inject_edge_cases(agent)
        self.chaos.simulate_failure_scenarios(agent)
        
        self.logger.info("DeepStressTester", "阶段4完成")
    
    def _test_phase_5_long_running(self, agent: EternalSelfAgent):
        """
        阶段5: 长时间运行模拟
        """
        self.logger.info("DeepStressTester", "开始阶段5: 长时间运行模拟")
        
        # 模拟长时间运行的多次迭代
        start_time = time.time()
        target_duration = 10  # 秒
        
        while time.time() - start_time < target_duration:
            # 执行一些任务
            for _ in range(10):
                task = agent.get_current_task()
                if task:
                    agent.execute_task(task)
                agent.health_check()
            
            # 添加新任务
            for _ in range(5):
                agent.add_manual_task(f"长期任务_{time.time()}_{random.randint(1000, 9999)}")
        
        self.logger.info("DeepStressTester", "阶段5完成")
    
    def _print_test_report(self):
        """
        打印测试报告
        """
        print("\n" + "="*60)
        print("深度压力测试报告")
        print("="*60)
        print(f"测试通过: {'✓' if self.results.get('test_passed', False) else '✗'}")
        if "error" in self.results:
            print(f"错误信息: {self.results['error']}")
        
        if "node_count" in self.results:
            print(f"\n知识图谱统计:")
            print(f"  - 节点数: {self.results['node_count']}")
            print(f"  - 边数: {self.results['edge_count']}")
        
        if "tasks_executed" in self.results:
            print(f"\n执行统计:")
            print(f"  - 执行任务数: {self.results['tasks_executed']}")
            print(f"  - 进化次数: {self.results['evolution_count']}")
            print(f"  - 错误数: {self.results['error_count']}")
        
        if "memory_usage" in self.results:
            print(f"\n资源使用:")
            print(f"  - 内存使用: {self.results['memory_usage']:.2f}MB")
        
        print("="*60 + "\n")


def main():
    tester = DeepStressTester()
    results = tester.run_full_test_suite()
    return 0 if results.get("test_passed", False) else 1


if __name__ == "__main__":
    sys.exit(main())
