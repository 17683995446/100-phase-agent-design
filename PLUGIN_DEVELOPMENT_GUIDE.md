# 插件开发指南

本文档介绍如何为 EternalSelfAgent 开发插件。

## 目录
1. [插件基础](#插件基础)
2. [任务处理器插件](#任务处理器插件)
3. [知识处理器插件](#知识处理器插件)
4. [插件管理器](#插件管理器)
5. [示例插件](#示例插件)

## 插件基础

### 插件基类

所有插件都继承自 `BasePlugin` 抽象类：

```python
from core import BasePlugin

class MyPlugin(BasePlugin):
    name = "my_plugin"  # 插件唯一名称
    version = "1.0.0"   # 插件版本
    description = "我的第一个插件"  # 插件描述

    def initialize(self, agent):
        """插件初始化时调用"""
        self.agent = agent

    def shutdown(self, agent):
        """插件关闭时调用"""
        pass
```

### 插件生命周期

1. **创建插件实例**
2. **注册到插件管理器**
3. **调用 `initialize(agent)`** - 插件初始化
4. **插件工作**
5. **调用 `shutdown(agent)`** - 插件清理

## 任务处理器插件

`TaskHandlerPlugin` 用于添加自定义任务处理功能：

```python
from core import TaskHandlerPlugin

class GreetPlugin(TaskHandlerPlugin):
    name = "greet_plugin"
    version = "1.0.0"
    description = "问候插件"

    def initialize(self, agent):
        self.agent = agent

    def get_task_handlers(self):
        """返回任务类型到处理函数的映射"""
        return {
            "greet": self.handle_greet,
            "welcome": self.handle_welcome
        }

    def handle_greet(self, task, agent):
        """处理 greet:xxx 格式的任务"""
        # task 格式: "greet:John"
        if ":" in task:
            name = task.split(":", 1)[1]
        else:
            name = "World"
        agent.log_event("PLUGIN", f"Hello, {name}!")
        agent.knowledge_graph.add_node(f"greeted:{name}")

    def handle_welcome(self, task, agent):
        """处理 welcome 任务"""
        agent.log_event("PLUGIN", "Welcome to our system!")
```

## 知识处理器插件

`KnowledgeProcessorPlugin` 用于处理知识图谱事件：

```python
from core import KnowledgeProcessorPlugin

class KnowledgeMonitorPlugin(KnowledgeProcessorPlugin):
    name = "knowledge_monitor"
    version = "1.0.0"
    description = "知识图谱监控插件"

    def initialize(self, agent):
        self.agent = agent
        self.node_count = 0
        self.edge_count = 0

    def on_node_added(self, node_name, attributes):
        """当节点被添加时调用"""
        self.node_count += 1
        self.agent.log_event("MONITOR", f"Node added: {node_name} (total: {self.node_count})")

    def on_edge_added(self, source, target, relation, weight):
        """当边被添加时调用"""
        self.edge_count += 1
        self.agent.log_event("MONITOR", f"Edge added: {source} -> {target} (total: {self.edge_count})")
```

## 插件管理器

### 注册插件

```python
agent.register_plugin(MyPlugin())
```

### 列出插件

```python
plugins = agent.list_plugins()
# 返回格式: [{"name": "...", "version": "...", "description": "...", "initialized": True, "enabled": True}]
```

### 获取插件

```python
plugin = agent.plugin_manager.get_plugin("my_plugin")
```

### 注销插件

```python
agent.unregister_plugin("my_plugin")
```

## 示例插件

### 1. Hello World 插件

见 `plugins/hello_plugin.py` - 一个简单的问候插件。

### 2. 计数器插件

见 `plugins/counter_plugin.py` - 一个简单的计数插件。

## 最佳实践

1. **保持简单** - 遵循第一原理思维，只实现必要功能
2. **向后兼容** - 保持插件的向前和向后兼容性
3. **线程安全** - 插件中的方法应该是线程安全的
4. **文档完善** - 为插件提供清晰的文档
5. **测试覆盖** - 为插件编写完整的测试

## 完整示例

```python
import tempfile
import os
from core import EternalSelfAgent
from plugins.hello_plugin import HelloWorldPlugin

def main():
    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        kg_path = f.name
    
    try:
        agent = EternalSelfAgent(kg_save_path=kg_path, loop_delay=0.001)
        
        # 注册插件
        plugin = HelloWorldPlugin()
        agent.register_plugin(plugin)
        
        # 执行任务
        agent.execute_task("greet:Alice")
        
        # 查看插件状态
        print(f"插件列表: {agent.list_plugins()}")
        
        # 关闭
        agent.shutdown()
        
    finally:
        if os.path.exists(kg_path):
            os.remove(kg_path)
        if os.path.exists("eternal_self_agent.log"):
            try:
                os.remove("eternal_self_agent.log")
            except:
                pass

if __name__ == "__main__":
    main()
```
