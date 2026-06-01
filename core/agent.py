import time
import os
import json
import traceback
import gc
import sys
from typing import Optional, List
from .knowledge_graph import KnowledgeGraph
from .task_queue import TaskQueue
from .config import ConfigManager
from .metrics import MetricsCollector
from .plugin import PluginManager, BasePlugin


class EternalSelfAgent:
    def __init__(
        self,
        config_path: str = "config.json",
        kg_save_path: str = None,
        loop_delay: float = None,
        evolve_step: int = None,
        task_queue_max: int = None,
        log_path: str = None,
        task_timeout: float = 30.0
    ):
        self.config_manager = ConfigManager(config_path)
        
        # 如果提供了额外的参数，更新配置
        if kg_save_path is not None:
            self.config_manager.set("kg_save_path", kg_save_path)
        if loop_delay is not None:
            self.config_manager.set("loop_delay", loop_delay)
        if evolve_step is not None:
            self.config_manager.set("evolve_step", evolve_step)
        if task_queue_max is not None:
            self.config_manager.set("task_queue_max", task_queue_max)
        if log_path is not None:
            self.config_manager.set("log_path", log_path)
        
        self.config = self.config_manager.get_all()
        
        self.kg_save_path = self.config["kg_save_path"]
        self.knowledge_graph = KnowledgeGraph(self.kg_save_path)
        
        self.task_queue = TaskQueue(max_size=self.config["task_queue_max"])
        self.run_counter = 0
        self.system_alive = True
        self.loop_delay = self.config["loop_delay"]
        self.evolve_step = self.config["evolve_step"]
        self.task_handlers = {}
        self.log_path = self.config["log_path"]
        self.start_time = time.time()
        self._last_memory_check = 0
        
        # 统计信息
        self.tasks_executed = 0
        self.evolution_count = 0
        self.error_count = 0
        self.last_task_time = 0
        self.total_task_time = 0
        
        # 指标收集器
        self.metrics = MetricsCollector()
        
        # 插件管理器
        self.plugin_manager = PluginManager()
        
        self.log_event("SYSTEM", "智能体初始化完成")
        self.log_event("SYSTEM", f"配置加载成功: {self.config}")

    def _get_memory_usage(self) -> float:
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            try:
                import resource
                return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            except Exception:
                return 0.0

    def _force_memory_cleanup(self) -> None:
        try:
            self.log_event("MEMORY", "执行强制内存清理")
            gc.collect()
            if self.task_queue.get_history_size() > 10000:
                self.task_queue.clear_history()
                self.log_event("MEMORY", "已清理任务历史")
            if len(self.knowledge_graph.edges) > 5000:
                self.knowledge_graph.trim_invalid_knowledge(weight_threshold=0.3)
                self.log_event("MEMORY", "已执行深度知识精简")
        except Exception as e:
            self.log_event("ERROR", f"内存清理失败: {e}")

    def save_config(self) -> None:
        self.config_manager.set("last_run_timestamp", time.time())

    def update_config(self, key: str, value, auto_apply: bool = True) -> bool:
        """
        更新配置，并可选地自动应用到运行时
        """
        success = self.config_manager.set(key, value)
        
        if success and auto_apply:
            self._apply_config_change(key, value)
        
        return success

    def _apply_config_change(self, key: str, value) -> None:
        """
        应用配置变更到运行时
        """
        if key == "loop_delay":
            self.loop_delay = value
        elif key == "evolve_step":
            self.evolve_step = value
        elif key == "task_queue_max":
            self.task_queue.max_size = value
        elif key == "log_path":
            self.log_path = value
        
        self.log_event("CONFIG", f"配置变更: {key} = {value}")

    def restore_state(self) -> bool:
        """
        完整恢复系统状态
        """
        success = False
        
        try:
            if os.path.exists(self.kg_save_path):
                self.knowledge_graph.load()
                node_count = self.knowledge_graph.get_node_count()
                edge_count = self.knowledge_graph.get_edge_count()
                self.log_event("SYSTEM", f"成功从 {self.kg_save_path} 恢复知识图谱")
                self.log_event("SYSTEM", f"恢复了 {node_count} 个节点和 {edge_count} 条边")
                success = True
            else:
                self.log_event("SYSTEM", "未找到持久化文件，系统全新启动")
                success = True
        except Exception as e:
            self.log_event("ERROR", f"状态恢复失败: {e}")
        
        return success

    def save_full_state(self) -> None:
        """
        保存完整系统状态
        """
        try:
            self.knowledge_graph.save()
            self.save_config()
            self.log_event("SYSTEM", "完整系统状态已保存")
        except Exception as e:
            self.log_event("ERROR", f"状态保存失败: {e}")

    def health_check(self) -> None:
        self.run_counter += 1
        
        if self.run_counter % self.evolve_step == 0:
            self.log_event("EVOLVE", "触发知识精简")
            self.knowledge_graph.trim_invalid_knowledge()
            self.evolution_count += 1
        
        if self.run_counter % 200 == 0:
            memory_usage = self._get_memory_usage()
            self.log_event("MEMORY", f"当前内存使用: {memory_usage:.2f}MB")
            if memory_usage > 200:
                self._force_memory_cleanup()
        
        if self.run_counter % 100 == 0:
            self.save_config()

    def self_repair(self, exception_type: Optional[str] = None) -> None:
        error_details = traceback.format_exc()
        self.log_event("ERROR", f"发生异常({exception_type or 'unknown'})，开始自愈: {error_details}")
        self.error_count += 1
        
        try:
            if exception_type == "MemoryError":
                self._force_memory_cleanup()
            elif exception_type == "DiskError":
                self.log_event("ERROR", "磁盘空间不足，尝试紧急清理")
            elif exception_type == "JSONDecodeError":
                self.log_event("ERROR", "JSON解析异常，知识图谱已自动从备份恢复")
            
            self.knowledge_graph.save()
        except Exception as save_err:
            self.log_event("ERROR", f"知识图谱保存失败: {save_err}")
        
        time.sleep(1.0)
        self.log_event("RECOVER", "自愈完成，系统继续运行")

    def get_current_task(self) -> Optional[str]:
        return self.task_queue.pop()

    def idle_self_evolve(self) -> None:
        if self.run_counter > 0:
            if self.run_counter % 100 == 0:
                self.perform_deep_reflection()
            if self.run_counter % 300 == 0:
                self.perform_knowledge_synthesis()
        time.sleep(self.loop_delay)

    def perform_deep_reflection(self) -> None:
        high_value_nodes = self.knowledge_graph.find_highest_value_nodes(
            min_weight=0.6, limit=5
        )
        
        if not high_value_nodes:
            high_value_nodes = list(self.knowledge_graph.nodes.keys())[:5]
        
        processed = 0
        for node in high_value_nodes:
            self.knowledge_graph.add_edge(
                node, "自我反思", "关联思考", 0.5
            )
            processed += 1
        
        self.log_event("DEEP_REFLECTION", f"完成深度反思，处理了{processed}个高价值节点")

    def perform_knowledge_synthesis(self) -> None:
        high_value_nodes = self.knowledge_graph.find_highest_value_nodes(
            min_weight=0.5, limit=10
        )
        
        if len(high_value_nodes) >= 2:
            for i in range(len(high_value_nodes)):
                for j in range(i + 1, len(high_value_nodes)):
                    node1 = high_value_nodes[i]
                    node2 = high_value_nodes[j]
                    self.knowledge_graph.add_edge(
                        node1, node2, "知识关联", 0.4
                    )
        
        self.log_event("KNOWLEDGE_SYNTHESIS", f"完成知识合成，建立了新的知识关联")

    def _has_high_weight_edges(self, node_name: str) -> bool:
        edges = self.knowledge_graph.get_all_edges_from(node_name, min_weight=0.6)
        return len(edges) > 0

    def log_event(self, event_type: str, message: str) -> None:
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                timestamp = time.time()
                f.write(f"[{timestamp}] {event_type}: {message}\n")
        except Exception:
            pass

    def execute_task(self, task: str) -> None:
        task_start_time = time.time()
        
        self.knowledge_graph.add_node(task)
        self.log_event("TASK_EXECUTE", f"执行任务: {task}")
        
        # 检查是否有自定义任务处理器（包括插件提供的）
        task_type = self._extract_task_type(task)
        all_handlers = self.task_handlers.copy()
        all_handlers.update(self.plugin_manager.get_task_handlers())
        
        if task_type in all_handlers:
            try:
                handler = all_handlers[task_type]
                handler(task, self)
            except Exception as e:
                self.log_event("TASK_ERROR", f"任务处理器错误: {e}")
        
        next_iter_task = f"系统迭代任务_{self.run_counter}"
        self.knowledge_graph.add_edge(task, next_iter_task, "自主衍生", 0.8)
        
        derive_tasks = self.knowledge_graph.derive_new_tasks(task, depth=2)
        
        self.task_queue.add(next_iter_task)
        added_count = self.task_queue.batch_add(derive_tasks)
        if added_count > 0:
            self.log_event("NEW_TASKS", f"知识推演新增 {added_count} 个任务")
        
        self.knowledge_graph.update_edge_weight(
            task, next_iter_task, "自主衍生", 0.05
        )
        
        # 更新统计和指标
        task_elapsed = time.time() - task_start_time
        self.tasks_executed += 1
        self.total_task_time += task_elapsed
        self.last_task_time = task_elapsed
        
        # 更新指标
        self.metrics.counter("tasks_executed").inc()
        self.metrics.gauge("graph_nodes").set(self.knowledge_graph.get_node_count())
        self.metrics.gauge("graph_edges").set(self.knowledge_graph.get_edge_count())
    
    def _extract_task_type(self, task: str) -> str:
        """
        提取任务类型（用于任务处理器路由）
        """
        if ":" in task:
            return task.split(":", 1)[0]
        return "default"

    def eternal_loop(self) -> None:
        self.log_event("SYSTEM", "进入永恒循环")
        while self.system_alive:
            try:
                self.health_check()
                task = self.get_current_task()
                if task is None:
                    self.idle_self_evolve()
                    continue
                self.execute_task(task)
                time.sleep(self.loop_delay)
            except KeyboardInterrupt:
                self.log_event("SYSTEM", "收到中断信号，准备退出")
                self.shutdown()
            except MemoryError:
                self.self_repair("MemoryError")
            except json.JSONDecodeError:
                self.self_repair("JSONDecodeError")
            except Exception:
                self.self_repair()

    def shutdown(self) -> None:
        self.log_event("SYSTEM", "开始关闭智能体...")
        self.system_alive = False
        try:
            # 关闭插件
            self.plugin_manager.shutdown_plugins()
            self.knowledge_graph.save()
            self.save_config()
            self.log_event("SYSTEM", "状态保存完成")
        except Exception as e:
            print(f"关闭时保存失败: {e}")
        finally:
            runtime = time.time() - self.start_time
            self.log_event("SYSTEM", f"智能体已安全关闭，运行时长: {runtime:.2f}秒")

    def get_system_status(self) -> dict:
        kg_stats = self.knowledge_graph.get_stats()
        
        avg_task_time = self.total_task_time / self.tasks_executed if self.tasks_executed > 0 else 0
        
        return {
            "run_counter": self.run_counter,
            "queue_size": self.task_queue.size(),
            "node_count": self.knowledge_graph.get_node_count(),
            "edge_count": self.knowledge_graph.get_edge_count(),
            "system_alive": self.system_alive,
            "uptime": time.time() - self.start_time,
            "processed_history_size": self.task_queue.get_history_size(),
            "memory_usage": self._get_memory_usage(),
            "knowledge_graph_stats": kg_stats,
            "config": self.config_manager.get_all(),
            # 新增的统计信息
            "tasks_executed": self.tasks_executed,
            "evolution_count": self.evolution_count,
            "error_count": self.error_count,
            "last_task_time": self.last_task_time,
            "avg_task_time": avg_task_time
        }
    
    def print_status_report(self) -> None:
        """打印美观的状态报告"""
        status = self.get_system_status()
        
        print("\n" + "=" * 60)
        print("系统状态报告")
        print("=" * 60)
        print(f"系统存活: {'✓' if status['system_alive'] else '✗'}")
        print(f"运行时长: {status['uptime']:.2f}秒")
        print(f"运行计数器: {status['run_counter']}")
        print(f"任务队列大小: {status['queue_size']}")
        print(f"\n知识图谱统计:")
        print(f"  - 节点数: {status['node_count']}")
        print(f"  - 边数: {status['edge_count']}")
        print(f"  - 保存次数: {status['knowledge_graph_stats']['save_count']}")
        print(f"\n运行统计:")
        print(f"  - 执行任务数: {status['tasks_executed']}")
        print(f"  - 平均任务时间: {status['avg_task_time']:.6f}秒")
        print(f"  - 最后任务时间: {status['last_task_time']:.6f}秒")
        print(f"  - 知识进化次数: {status['evolution_count']}")
        print(f"  - 错误数: {status['error_count']}")
        print(f"\n内存使用: {status['memory_usage']:.2f}MB")
        print(f"处理历史大小: {status['processed_history_size']}")
        print("=" * 60 + "\n")

    def __repr__(self) -> str:
        return f"EternalSelfAgent(counter={self.run_counter}, nodes={self.knowledge_graph.get_node_count()}, tasks={self.task_queue.size()})"
    
    # ==================== 可观测性扩展 ====================
    def enhanced_health_check(self) -> dict:
        """
        增强的健康检查
        """
        checks = {
            "system_alive": self.system_alive,
            "knowledge_graph": "healthy",
            "task_queue": "healthy",
            "timestamp": time.time()
        }
        
        # 检查知识图谱
        try:
            _ = self.knowledge_graph.get_node_count()
            _ = self.knowledge_graph.get_edge_count()
        except Exception:
            checks["knowledge_graph"] = "unhealthy"
        
        # 检查任务队列
        try:
            _ = self.task_queue.size()
        except Exception:
            checks["task_queue"] = "unhealthy"
        
        checks["overall"] = "healthy" if all(
            v == "healthy" or isinstance(v, bool) and v
            for k, v in checks.items()
            if k not in ["timestamp"]
        ) else "unhealthy"
        
        return checks
    
    def get_metrics(self) -> dict:
        """
        获取所有指标
        """
        return {
            "uptime": self.metrics.get_uptime(),
            "metrics": self.metrics.export()
        }
    
    def export_metrics_json(self) -> str:
        """
        导出指标为 JSON
        """
        return self.metrics.export_json()
    
    # ==================== 插件管理接口 ====================
    def register_plugin(self, plugin: BasePlugin) -> bool:
        """
        注册一个插件
        
        Args:
            plugin: 要注册的插件实例
            
        Returns:
            bool: 注册是否成功
        """
        success = self.plugin_manager.register_plugin(plugin)
        if success:
            self.log_event("PLUGIN", f"注册插件: {plugin.name} v{plugin.version}")
            # 如果 Agent 已经初始化，立即初始化插件
            if success and not plugin.is_initialized:
                plugin.initialize(self)
            # 如果是 KnowledgeProcessorPlugin，注册回调
            from .plugin import KnowledgeProcessorPlugin
            if isinstance(plugin, KnowledgeProcessorPlugin):
                self.knowledge_graph.register_on_node_add(plugin.on_node_added)
                self.knowledge_graph.register_on_edge_add(plugin.on_edge_added)
        return success
    
    def unregister_plugin(self, plugin_name: str) -> bool:
        """
        注销一个插件
        
        Args:
            plugin_name: 要注销的插件名称
            
        Returns:
            bool: 注销是否成功
        """
        plugin = self.plugin_manager.get_plugin(plugin_name)
        if plugin is not None:
            # 如果是 KnowledgeProcessorPlugin，注销回调
            from .plugin import KnowledgeProcessorPlugin
            if isinstance(plugin, KnowledgeProcessorPlugin):
                try:
                    self.knowledge_graph.unregister_on_node_add(plugin.on_node_added)
                    self.knowledge_graph.unregister_on_edge_add(plugin.on_edge_added)
                except Exception:
                    pass
        success = self.plugin_manager.unregister_plugin(plugin_name)
        if success:
            self.log_event("PLUGIN", f"注销插件: {plugin_name}")
        return success
    
    def list_plugins(self) -> list:
        """
        列出所有注册的插件信息
        
        Returns:
            list: 插件信息列表
        """
        return self.plugin_manager.list_plugins()
    
    # ==================== 扩展接口 ====================
    def register_task_handler(self, task_type: str, handler) -> None:
        """
        注册自定义任务处理器
        
        Args:
            task_type: 任务类型（如 "custom"，对应 "custom:task_name" 格式的任务）
            handler: 处理器函数，签名为 handler(task: str, agent: EternalSelfAgent)
        """
        self.task_handlers[task_type] = handler
        self.log_event("REGISTRATION", f"注册任务处理器: {task_type}")
    
    def inject_external_knowledge(self, node_name: str, edges: List[tuple]) -> None:
        """
        注入外部知识到知识图谱
        
        Args:
            node_name: 源节点名称
            edges: 边列表，格式为 [(target_node, relation_name, weight), ...]
        """
        self.knowledge_graph.inject_external_knowledge(node_name, edges)
        self.log_event("INJECTION", f"注入外部知识: {node_name}，{len(edges)}条边")
    
    def add_manual_task(self, task: str) -> bool:
        """
        手动添加任务到队列
        
        Args:
            task: 任务名称
        
        Returns:
            是否添加成功
        """
        success = self.task_queue.add(task)
        if success:
            self.log_event("MANUAL_TASK", f"添加手动任务: {task}")
        return success
    
    def find_related_tasks(self, task: str, depth: int = 2) -> List[str]:
        """
        查找与指定任务相关的任务
        
        Args:
            task: 源任务
            depth: 遍历深度
        
        Returns:
            相关任务列表
        """
        related_nodes = self.knowledge_graph.find_related_nodes(task, depth)
        return [n for n in related_nodes]
