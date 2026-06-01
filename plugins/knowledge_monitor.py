from core import KnowledgeProcessorPlugin


class KnowledgeMonitorPlugin(KnowledgeProcessorPlugin):
    """
    知识图谱监控插件 - 监控节点和边的变化
    """
    name = "knowledge_monitor"
    version = "1.0.0"
    description = "监控知识图谱的节点和边添加"
    
    def __init__(self):
        super().__init__()
        self.node_count = 0
        self.edge_count = 0
        self.added_nodes = []
        self.added_edges = []
        self.agent = None
    
    def initialize(self, agent):
        super().initialize(agent)
        self.agent = agent
        self.agent.log_event("PLUGIN", "KnowledgeMonitorPlugin 已初始化")
    
    def shutdown(self, agent):
        super().shutdown(agent)
        self.agent.log_event("PLUGIN", f"KnowledgeMonitorPlugin 已关闭。"
                                      f"总共监控到 {self.node_count} 个节点, "
                                      f"{self.edge_count} 条边")
    
    def on_node_added(self, node_name: str, attributes: dict) -> None:
        """
        当节点被添加时调用
        """
        self.node_count += 1
        self.added_nodes.append(node_name)
        if self.agent is not None:
            self.agent.log_event("MONITOR", f"节点添加: {node_name} (总计: {self.node_count})")
    
    def on_edge_added(self, source: str, target: str, relation: str, weight: float) -> None:
        """
        当边被添加时调用
        """
        self.edge_count += 1
        self.added_edges.append((source, target, relation, weight))
        if self.agent is not None:
            self.agent.log_event("MONITOR", f"边添加: {source} --[{relation}]--> {target} (总计: {self.edge_count})")
    
    def get_statistics(self):
        """
        获取监控统计信息
        """
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "last_nodes": self.added_nodes[-10:] if self.added_nodes else [],
            "last_edges": self.added_edges[-10:] if self.added_edges else []
        }
