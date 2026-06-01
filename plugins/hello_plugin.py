from core import TaskHandlerPlugin


class HelloWorldPlugin(TaskHandlerPlugin):
    """
    简单的 Hello World 插件，演示任务处理器功能
    """
    
    name = "hello_world"
    version = "1.0.0"
    description = "一个简单的示例插件，提供 greet 任务处理"
    
    def initialize(self, agent):
        super().initialize(agent)
        self.agent = agent
    
    def get_task_handlers(self):
        return {
            "greet": self.handle_greet
        }
    
    def handle_greet(self, task: str, agent) -> None:
        """
        处理 greet 任务
        """
        if ":" in task:
            name = task.split(":", 1)[1]
        else:
            name = "World"
        agent.log_event("PLUGIN", f"Hello, {name}!")
        agent.knowledge_graph.add_node(f"greeted:{name}")
