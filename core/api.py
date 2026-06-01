"""
用户界面与API模块

提供RESTful风格的API接口和命令行交互界面。
遵循"图难于其易，为大于其细"原则，从简单可验证的实现开始。
"""

import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class ResponseStatus(Enum):
    """响应状态"""
    SUCCESS = "success"
    ERROR = "error"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    VALIDATION_ERROR = "validation_error"


@dataclass
class APIResponse:
    """
    API 响应
    """
    status: ResponseStatus
    data: Any = None
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    request_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value,
            "data": self.data,
            "message": self.message,
            "timestamp": self.timestamp,
            "request_id": self.request_id
        }
    
    @classmethod
    def success(cls, data: Any = None, message: str = "") -> "APIResponse":
        """创建成功响应"""
        return cls(status=ResponseStatus.SUCCESS, data=data, message=message)
    
    @classmethod
    def error(cls, message: str, data: Any = None) -> "APIResponse":
        """创建错误响应"""
        return cls(status=ResponseStatus.ERROR, data=data, message=message)
    
    @classmethod
    def not_found(cls, message: str = "Resource not found") -> "APIResponse":
        """创建未找到响应"""
        return cls(status=ResponseStatus.NOT_FOUND, message=message)
    
    @classmethod
    def unauthorized(cls, message: str = "Unauthorized") -> "APIResponse":
        """创建未授权响应"""
        return cls(status=ResponseStatus.UNAUTHORIZED, message=message)


class APIEndpoint:
    """
    API 端点
    """
    
    def __init__(self, path: str, method: str, handler: Callable,
                 requires_auth: bool = False, required_permissions: Optional[List[str]] = None):
        """
        初始化 API 端点
        
        Args:
            path: 路径
            method: HTTP 方法
            handler: 处理函数
            requires_auth: 是否需要认证
            required_permissions: 需要的权限
        """
        self.path = path
        self.method = method.upper()
        self.handler = handler
        self.requires_auth = requires_auth
        self.required_permissions = required_permissions or []
    
    def match(self, path: str, method: str) -> bool:
        """匹配请求"""
        return self.path == path and self.method == method.upper()
    
    def __repr__(self) -> str:
        return f"APIEndpoint({self.method} {self.path})"


class APIManager:
    """
    API 管理器
    
    管理 API 端点和请求路由。
    """
    
    def __init__(self):
        self._endpoints: List[APIEndpoint] = []
        self._middleware: List[Callable] = []
        self._request_count = 0
    
    def register_endpoint(self, path: str, method: str, handler: Callable,
                         requires_auth: bool = False,
                         required_permissions: Optional[List[str]] = None):
        """
        注册 API 端点
        
        Args:
            path: 路径
            method: HTTP 方法
            handler: 处理函数
            requires_auth: 是否需要认证
            required_permissions: 需要的权限
        """
        endpoint = APIEndpoint(
            path=path,
            method=method,
            handler=handler,
            requires_auth=requires_auth,
            required_permissions=required_permissions
        )
        self._endpoints.append(endpoint)
    
    def register_middleware(self, middleware: Callable):
        """注册中间件"""
        self._middleware.append(middleware)
    
    def handle_request(self, path: str, method: str,
                      params: Optional[Dict[str, Any]] = None,
                      headers: Optional[Dict[str, str]] = None,
                      auth_token: Optional[str] = None) -> APIResponse:
        """
        处理请求
        
        Args:
            path: 请求路径
            method: HTTP 方法
            params: 请求参数
            headers: 请求头
            auth_token: 认证令牌
            
        Returns:
            API 响应
        """
        self._request_count += 1
        request_id = f"req_{self._request_count}"
        
        # 查找端点
        endpoint = None
        for ep in self._endpoints:
            if ep.match(path, method):
                endpoint = ep
                break
        
        if not endpoint:
            response = APIResponse.not_found(f"Endpoint {method} {path} not found")
            response.request_id = request_id
            return response
        
        # 执行中间件
        context = {
            "path": path,
            "method": method,
            "params": params or {},
            "headers": headers or {},
            "auth_token": auth_token,
            "request_id": request_id
        }
        
        for middleware in self._middleware:
            try:
                result = middleware(context)
                if isinstance(result, APIResponse):
                    result.request_id = request_id
                    return result
            except Exception as e:
                response = APIResponse.error(str(e))
                response.request_id = request_id
                return response
        
        # 调用处理函数
        try:
            result = endpoint.handler(context)
            
            if isinstance(result, APIResponse):
                response = result
            elif isinstance(result, dict) and "status" in result:
                response = APIResponse(
                    status=ResponseStatus(result["status"]),
                    data=result.get("data"),
                    message=result.get("message", "")
                )
            else:
                response = APIResponse.success(data=result)
            
            response.request_id = request_id
            return response
        except Exception as e:
            response = APIResponse.error(str(e))
            response.request_id = request_id
            return response
    
    def get_endpoints(self) -> List[Dict[str, Any]]:
        """获取所有端点信息"""
        return [
            {
                "path": ep.path,
                "method": ep.method,
                "requires_auth": ep.requires_auth,
                "required_permissions": ep.required_permissions
            }
            for ep in self._endpoints
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "endpoints": len(self._endpoints),
            "middleware": len(self._middleware),
            "total_requests": self._request_count
        }
    
    def clear(self):
        """清空所有端点"""
        self._endpoints.clear()
        self._middleware.clear()
        self._request_count = 0


class CLICommand:
    """
    CLI 命令
    """
    
    def __init__(self, name: str, description: str, handler: Callable,
                 args: Optional[List[Dict[str, Any]]] = None):
        """
        初始化 CLI 命令
        
        Args:
            name: 命令名称
            description: 命令描述
            handler: 处理函数
            args: 参数定义
        """
        self.name = name
        self.description = description
        self.handler = handler
        self.args = args or []
    
    def execute(self, args: List[str]) -> str:
        """
        执行命令
        
        Args:
            args: 命令参数
            
        Returns:
            命令输出
        """
        try:
            # 解析参数
            parsed_args = self._parse_args(args)
            return self.handler(parsed_args)
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _parse_args(self, args: List[str]) -> Dict[str, Any]:
        """解析参数"""
        parsed = {}
        
        for i, arg_def in enumerate(self.args):
            if i < len(args):
                parsed[arg_def["name"]] = args[i]
            elif "default" in arg_def:
                parsed[arg_def["name"]] = arg_def["default"]
            elif arg_def.get("required", False):
                raise ValueError(f"Missing required argument: {arg_def['name']}")
        
        return parsed
    
    def get_help(self) -> str:
        """获取帮助信息"""
        help_text = f"{self.name} - {self.description}\n"
        if self.args:
            help_text += "Arguments:\n"
            for arg in self.args:
                required = " (required)" if arg.get("required") else ""
                default = f" [default: {arg.get('default')}]" if "default" in arg else ""
                help_text += f"  {arg['name']}: {arg.get('description', '')}{required}{default}\n"
        return help_text


class CLIInterface:
    """
    命令行界面
    """
    
    def __init__(self):
        self._commands: Dict[str, CLICommand] = {}
        self._history: List[str] = []
    
    def register_command(self, name: str, description: str, handler: Callable,
                        args: Optional[List[Dict[str, Any]]] = None):
        """
        注册命令
        
        Args:
            name: 命令名称
            description: 命令描述
            handler: 处理函数
            args: 参数定义
        """
        self._commands[name] = CLICommand(
            name=name,
            description=description,
            handler=handler,
            args=args
        )
    
    def execute(self, command_line: str) -> str:
        """
        执行命令行
        
        Args:
            command_line: 命令行字符串
            
        Returns:
            命令输出
        """
        self._history.append(command_line)
        
        parts = command_line.strip().split()
        if not parts:
            return ""
        
        command_name = parts[0]
        args = parts[1:]
        
        if command_name == "help":
            return self._show_help(args[0] if args else None)
        
        if command_name not in self._commands:
            return f"Unknown command: {command_name}. Type 'help' for available commands."
        
        command = self._commands[command_name]
        return command.execute(args)
    
    def _show_help(self, command_name: Optional[str] = None) -> str:
        """显示帮助"""
        if command_name:
            if command_name in self._commands:
                return self._commands[command_name].get_help()
            return f"Unknown command: {command_name}"
        
        help_text = "Available commands:\n"
        for name, command in sorted(self._commands.items()):
            help_text += f"  {name:20s} - {command.description}\n"
        help_text += "\nType 'help <command>' for detailed help."
        return help_text
    
    def get_history(self) -> List[str]:
        """获取命令历史"""
        return self._history.copy()
    
    def get_commands(self) -> Dict[str, str]:
        """获取所有命令"""
        return {name: cmd.description for name, cmd in self._commands.items()}
    
    def clear_history(self):
        """清空历史"""
        self._history.clear()
    
    def clear(self):
        """清空所有命令"""
        self._commands.clear()
        self._history.clear()


class AgentAPI:
    """
    智能体 API
    
    为 EternalSelfAgent 提供 API 接口。
    """
    
    def __init__(self, agent=None):
        """
        初始化智能体 API
        
        Args:
            agent: EternalSelfAgent 实例
        """
        self.agent = agent
        self.api = APIManager()
        self.cli = CLIInterface()
        
        self._setup_default_endpoints()
        self._setup_default_commands()
    
    def _setup_default_endpoints(self):
        """设置默认 API 端点"""
        # 健康检查
        self.api.register_endpoint("/health", "GET", self._health_check)
        
        # 知识图谱操作
        self.api.register_endpoint("/kg/nodes", "GET", self._list_nodes)
        self.api.register_endpoint("/kg/nodes", "POST", self._add_node)
        self.api.register_endpoint("/kg/nodes/{name}", "GET", self._get_node)
        self.api.register_endpoint("/kg/edges", "GET", self._list_edges)
        self.api.register_endpoint("/kg/edges", "POST", self._add_edge)
        
        # 任务队列操作
        self.api.register_endpoint("/tasks", "GET", self._list_tasks)
        self.api.register_endpoint("/tasks", "POST", self._submit_task)
        self.api.register_endpoint("/tasks/{id}", "GET", self._get_task)
        
        # 统计信息
        self.api.register_endpoint("/stats", "GET", self._get_stats)
    
    def _setup_default_commands(self):
        """设置默认 CLI 命令"""
        self.cli.register_command(
            "status", "Show system status",
            self._cmd_status,
            args=[]
        )
        
        self.cli.register_command(
            "add_node", "Add a node to knowledge graph",
            self._cmd_add_node,
            args=[
                {"name": "name", "description": "Node name", "required": True},
                {"name": "attributes", "description": "Node attributes (JSON)", "default": "{}"}
            ]
        )
        
        self.cli.register_command(
            "add_edge", "Add an edge to knowledge graph",
            self._cmd_add_edge,
            args=[
                {"name": "source", "description": "Source node", "required": True},
                {"name": "target", "description": "Target node", "required": True},
                {"name": "relation", "description": "Relation name", "required": True},
                {"name": "weight", "description": "Edge weight", "default": "0.5"}
            ]
        )
        
        self.cli.register_command(
            "nodes", "List all nodes",
            self._cmd_list_nodes,
            args=[]
        )
        
        self.cli.register_command(
            "tasks", "List pending tasks",
            self._cmd_list_tasks,
            args=[]
        )
        
        self.cli.register_command(
            "submit", "Submit a task",
            self._cmd_submit_task,
            args=[
                {"name": "description", "description": "Task description", "required": True}
            ]
        )
    
    # API 处理函数
    def _health_check(self, context: Dict[str, Any]) -> APIResponse:
        """健康检查"""
        return APIResponse.success(
            data={"status": "healthy", "agent": self.agent is not None}
        )
    
    def _list_nodes(self, context: Dict[str, Any]) -> APIResponse:
        """列出节点"""
        if not self.agent:
            return APIResponse.error("Agent not initialized")
        
        nodes = [
            {"name": name, "attributes": node.attributes}
            for name, node in self.agent.knowledge_graph.nodes.items()
        ]
        return APIResponse.success(data=nodes)
    
    def _add_node(self, context: Dict[str, Any]) -> APIResponse:
        """添加节点"""
        if not self.agent:
            return APIResponse.error("Agent not initialized")
        
        params = context.get("params", {})
        name = params.get("name")
        attributes = params.get("attributes", {})
        
        if not name:
            return APIResponse.error("Node name is required")
        
        node = self.agent.knowledge_graph.add_node(name, attributes)
        return APIResponse.success(
            data={"name": node.name, "attributes": node.attributes},
            message=f"Node '{name}' added successfully"
        )
    
    def _get_node(self, context: Dict[str, Any]) -> APIResponse:
        """获取节点"""
        if not self.agent:
            return APIResponse.error("Agent not initialized")
        
        # 从路径中提取节点名
        path = context.get("path", "")
        name = path.split("/")[-1]
        
        node = self.agent.knowledge_graph.get_node(name)
        if not node:
            return APIResponse.not_found(f"Node '{name}' not found")
        
        return APIResponse.success(
            data={"name": node.name, "attributes": node.attributes}
        )
    
    def _list_edges(self, context: Dict[str, Any]) -> APIResponse:
        """列出边"""
        if not self.agent:
            return APIResponse.error("Agent not initialized")
        
        edges = [
            {
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation_name,
                "weight": edge.weight
            }
            for edge in self.agent.knowledge_graph.edges
        ]
        return APIResponse.success(data=edges)
    
    def _add_edge(self, context: Dict[str, Any]) -> APIResponse:
        """添加边"""
        if not self.agent:
            return APIResponse.error("Agent not initialized")
        
        params = context.get("params", {})
        source = params.get("source")
        target = params.get("target")
        relation = params.get("relation")
        weight = float(params.get("weight", 0.5))
        
        if not all([source, target, relation]):
            return APIResponse.error("Source, target, and relation are required")
        
        edge = self.agent.knowledge_graph.add_edge(source, target, relation, weight)
        return APIResponse.success(
            data={
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation_name,
                "weight": edge.weight
            },
            message=f"Edge from '{source}' to '{target}' added successfully"
        )
    
    def _list_tasks(self, context: Dict[str, Any]) -> APIResponse:
        """列出任务"""
        if not self.agent:
            return APIResponse.error("Agent not initialized")
        
        tasks = self.agent.task_queue.get_all()
        return APIResponse.success(data=tasks)
    
    def _submit_task(self, context: Dict[str, Any]) -> APIResponse:
        """提交任务"""
        if not self.agent:
            return APIResponse.error("Agent not initialized")
        
        params = context.get("params", {})
        description = params.get("description", "")
        
        task = self.agent.task_queue.add_task(description)
        return APIResponse.success(
            data={"task_id": task.task_id, "description": task.description},
            message="Task submitted successfully"
        )
    
    def _get_task(self, context: Dict[str, Any]) -> APIResponse:
        """获取任务"""
        if not self.agent:
            return APIResponse.error("Agent not initialized")
        
        path = context.get("path", "")
        task_id = path.split("/")[-1]
        
        # 简化实现：返回所有任务中匹配的
        for task in self.agent.task_queue.get_all():
            if task.task_id == task_id:
                return APIResponse.success(data={
                    "task_id": task.task_id,
                    "description": task.description,
                    "status": task.status
                })
        
        return APIResponse.not_found(f"Task '{task_id}' not found")
    
    def _get_stats(self, context: Dict[str, Any]) -> APIResponse:
        """获取统计信息"""
        if not self.agent:
            return APIResponse.error("Agent not initialized")
        
        stats = {
            "nodes": len(self.agent.knowledge_graph.nodes),
            "edges": len(self.agent.knowledge_graph.edges),
            "tasks_pending": self.agent.task_queue.size(),
            "tasks_processed": len(self.agent.task_queue.get_history())
        }
        return APIResponse.success(data=stats)
    
    # CLI 处理函数
    def _cmd_status(self, args: Dict[str, Any]) -> str:
        """状态命令"""
        if not self.agent:
            return "Agent not initialized"
        
        lines = [
            "System Status:",
            f"  Nodes: {len(self.agent.knowledge_graph.nodes)}",
            f"  Edges: {len(self.agent.knowledge_graph.edges)}",
            f"  Pending Tasks: {self.agent.task_queue.size()}",
            f"  Processed Tasks: {len(self.agent.task_queue.get_history())}",
            f"  API Endpoints: {self.api.get_stats()['endpoints']}",
            f"  CLI Commands: {len(self.cli.get_commands())}"
        ]
        return "\n".join(lines)
    
    def _cmd_add_node(self, args: Dict[str, Any]) -> str:
        """添加节点命令"""
        if not self.agent:
            return "Agent not initialized"
        
        name = args.get("name")
        attributes_str = args.get("attributes", "{}")
        
        try:
            attributes = json.loads(attributes_str)
        except json.JSONDecodeError:
            return "Error: Invalid JSON for attributes"
        
        self.agent.knowledge_graph.add_node(name, attributes)
        return f"Node '{name}' added successfully"
    
    def _cmd_add_edge(self, args: Dict[str, Any]) -> str:
        """添加边命令"""
        if not self.agent:
            return "Agent not initialized"
        
        source = args.get("source")
        target = args.get("target")
        relation = args.get("relation")
        weight = float(args.get("weight", 0.5))
        
        self.agent.knowledge_graph.add_edge(source, target, relation, weight)
        return f"Edge from '{source}' to '{target}' added successfully"
    
    def _cmd_list_nodes(self, args: Dict[str, Any]) -> str:
        """列出节点命令"""
        if not self.agent:
            return "Agent not initialized"
        
        nodes = list(self.agent.knowledge_graph.nodes.keys())
        if not nodes:
            return "No nodes in knowledge graph"
        
        return "Nodes:\n" + "\n".join(f"  - {name}" for name in nodes)
    
    def _cmd_list_tasks(self, args: Dict[str, Any]) -> str:
        """列出任务命令"""
        if not self.agent:
            return "Agent not initialized"
        
        tasks = self.agent.task_queue.get_all()
        if not tasks:
            return "No pending tasks"
        
        lines = ["Pending Tasks:"]
        for task in tasks:
            lines.append(f"  - {task.task_id}: {task.description}")
        return "\n".join(lines)
    
    def _cmd_submit_task(self, args: Dict[str, Any]) -> str:
        """提交任务命令"""
        if not self.agent:
            return "Agent not initialized"
        
        description = args.get("description", "")
        task = self.agent.task_queue.add_task(description)
        return f"Task submitted: {task.task_id}"
    
    def get_api(self) -> APIManager:
        """获取 API 管理器"""
        return self.api
    
    def get_cli(self) -> CLIInterface:
        """获取 CLI 界面"""
        return self.cli
    
    def handle_api_request(self, path: str, method: str,
                          params: Optional[Dict[str, Any]] = None,
                          headers: Optional[Dict[str, str]] = None,
                          auth_token: Optional[str] = None) -> Dict[str, Any]:
        """
        处理 API 请求
        
        Returns:
            响应字典
        """
        response = self.api.handle_request(path, method, params, headers, auth_token)
        return response.to_dict()
    
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        功能：返回系统健康状态，用于 Docker 健康检查

        Returns:
            健康状态字典
        """
        return {
            "status": "healthy",
            "agent_initialized": self.agent is not None,
            "api_endpoints": self.api.get_stats()["endpoints"],
            "cli_commands": len(self.cli.get_commands()),
            "timestamp": time.time()
        }

    def handle_cli_command(self, command_line: str) -> str:
        """
        处理 CLI 命令

        Returns:
            命令输出
        """
        return self.cli.execute(command_line)
