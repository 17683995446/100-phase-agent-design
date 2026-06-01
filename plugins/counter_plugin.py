from core import TaskHandlerPlugin


class CounterPlugin(TaskHandlerPlugin):
    """
    计数器插件，跟踪执行的任务数量
    """
    
    name = "counter"
    version = "1.0.0"
    description = "一个简单的计数器插件"
    
    def __init__(self):
        super().__init__()
        self.counter = 0
    
    def initialize(self, agent):
        super().initialize(agent)
        self.agent = agent
    
    def get_task_handlers(self):
        return {
            "count": self.handle_count
        }
    
    def handle_count(self, task: str, agent) -> None:
        """
        处理 count 任务，增加计数
        """
        self.counter += 1
        agent.log_event("PLUGIN", f"Count incremented to: {self.counter}")
        agent.knowledge_graph.add_node(f"count:{self.counter}")
