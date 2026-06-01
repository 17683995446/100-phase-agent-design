"""
用户界面与API模块测试

测试API响应、端点管理和CLI界面功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的测试开始。
"""

import pytest
from core import (
    ResponseStatus, APIResponse, APIEndpoint, APIManager,
    CLICommand, CLIInterface, AgentAPI
)


class TestResponseStatus:
    """测试响应状态枚举"""
    
    def test_status_values(self):
        """测试状态值"""
        assert ResponseStatus.SUCCESS.value == "success"
        assert ResponseStatus.ERROR.value == "error"
        assert ResponseStatus.NOT_FOUND.value == "not_found"
        assert ResponseStatus.UNAUTHORIZED.value == "unauthorized"


class TestAPIResponse:
    """测试API响应"""
    
    def test_success_response(self):
        """测试成功响应"""
        response = APIResponse.success(data={"key": "value"}, message="OK")
        
        assert response.status == ResponseStatus.SUCCESS
        assert response.data == {"key": "value"}
        assert response.message == "OK"
    
    def test_error_response(self):
        """测试错误响应"""
        response = APIResponse.error("Something went wrong")
        
        assert response.status == ResponseStatus.ERROR
        assert response.message == "Something went wrong"
    
    def test_not_found_response(self):
        """测试未找到响应"""
        response = APIResponse.not_found("User not found")
        
        assert response.status == ResponseStatus.NOT_FOUND
        assert "User not found" in response.message
    
    def test_unauthorized_response(self):
        """测试未授权响应"""
        response = APIResponse.unauthorized()
        
        assert response.status == ResponseStatus.UNAUTHORIZED
    
    def test_to_dict(self):
        """测试转换为字典"""
        response = APIResponse.success(data={"key": "value"})
        data = response.to_dict()
        
        assert data["status"] == "success"
        assert data["data"] == {"key": "value"}
        assert "timestamp" in data


class TestAPIEndpoint:
    """测试API端点"""
    
    def test_creation(self):
        """测试创建"""
        def handler(ctx):
            return "ok"
        
        endpoint = APIEndpoint("/test", "GET", handler)
        assert endpoint.path == "/test"
        assert endpoint.method == "GET"
    
    def test_match(self):
        """测试匹配"""
        def handler(ctx):
            return "ok"
        
        endpoint = APIEndpoint("/test", "GET", handler)
        
        assert endpoint.match("/test", "GET") is True
        assert endpoint.match("/test", "POST") is False
        assert endpoint.match("/other", "GET") is False
    
    def test_requires_auth(self):
        """测试认证要求"""
        def handler(ctx):
            return "ok"
        
        endpoint = APIEndpoint("/test", "GET", handler, requires_auth=True)
        assert endpoint.requires_auth is True
        assert endpoint.required_permissions == []


class TestAPIManager:
    """测试API管理器"""
    
    def test_creation(self):
        """测试创建"""
        api = APIManager()
        assert api.get_stats()["endpoints"] == 0
        assert api.get_stats()["total_requests"] == 0
    
    def test_register_endpoint(self):
        """测试注册端点"""
        api = APIManager()
        
        def handler(ctx):
            return APIResponse.success()
        
        api.register_endpoint("/test", "GET", handler)
        assert api.get_stats()["endpoints"] == 1
    
    def test_handle_request_success(self):
        """测试处理请求成功"""
        api = APIManager()
        
        def handler(ctx):
            return APIResponse.success(data={"result": "ok"})
        
        api.register_endpoint("/test", "GET", handler)
        response = api.handle_request("/test", "GET")
        
        assert response.status == ResponseStatus.SUCCESS
        assert response.data == {"result": "ok"}
    
    def test_handle_request_not_found(self):
        """测试处理请求未找到"""
        api = APIManager()
        response = api.handle_request("/nonexistent", "GET")
        
        assert response.status == ResponseStatus.NOT_FOUND
    
    def test_handle_request_error(self):
        """测试处理请求错误"""
        api = APIManager()
        
        def handler(ctx):
            raise ValueError("Test error")
        
        api.register_endpoint("/test", "GET", handler)
        response = api.handle_request("/test", "GET")
        
        assert response.status == ResponseStatus.ERROR
        assert "Test error" in response.message
    
    def test_middleware(self):
        """测试中间件"""
        api = APIManager()
        
        def handler(ctx):
            return APIResponse.success()
        
        def middleware(ctx):
            ctx["modified"] = True
        
        api.register_endpoint("/test", "GET", handler)
        api.register_middleware(middleware)
        
        response = api.handle_request("/test", "GET")
        assert response.status == ResponseStatus.SUCCESS
    
    def test_middleware_returns_response(self):
        """测试中间件返回响应"""
        api = APIManager()
        
        def handler(ctx):
            return APIResponse.success()
        
        def middleware(ctx):
            return APIResponse.unauthorized("Blocked by middleware")
        
        api.register_endpoint("/test", "GET", handler)
        api.register_middleware(middleware)
        
        response = api.handle_request("/test", "GET")
        assert response.status == ResponseStatus.UNAUTHORIZED
    
    def test_request_count(self):
        """测试请求计数"""
        api = APIManager()
        
        def handler(ctx):
            return APIResponse.success()
        
        api.register_endpoint("/test", "GET", handler)
        
        api.handle_request("/test", "GET")
        api.handle_request("/test", "GET")
        
        assert api.get_stats()["total_requests"] == 2
    
    def test_get_endpoints(self):
        """测试获取端点列表"""
        api = APIManager()
        
        def handler(ctx):
            return APIResponse.success()
        
        api.register_endpoint("/test", "GET", handler, requires_auth=True)
        
        endpoints = api.get_endpoints()
        assert len(endpoints) == 1
        assert endpoints[0]["path"] == "/test"
        assert endpoints[0]["requires_auth"] is True
    
    def test_clear(self):
        """测试清空"""
        api = APIManager()
        
        def handler(ctx):
            return APIResponse.success()
        
        api.register_endpoint("/test", "GET", handler)
        api.clear()
        
        assert api.get_stats()["endpoints"] == 0


class TestCLICommand:
    """测试CLI命令"""
    
    def test_creation(self):
        """测试创建"""
        def handler(args):
            return "ok"
        
        cmd = CLICommand("test", "Test command", handler)
        assert cmd.name == "test"
        assert cmd.description == "Test command"
    
    def test_execute(self):
        """测试执行"""
        def handler(args):
            return f"Hello {args.get('name', 'World')}"
        
        cmd = CLICommand(
            "greet", "Greeting command", handler,
            args=[{"name": "name", "default": "World"}]
        )
        
        result = cmd.execute(["Alice"])
        assert result == "Hello Alice"
        
        result = cmd.execute([])
        assert result == "Hello World"
    
    def test_execute_error(self):
        """测试执行错误"""
        def handler(args):
            raise ValueError("Test error")
        
        cmd = CLICommand("error", "Error command", handler)
        result = cmd.execute([])
        
        assert "Error: Test error" in result
    
    def test_required_argument(self):
        """测试必需参数"""
        def handler(args):
            return args["name"]
        
        cmd = CLICommand(
            "test", "Test command", handler,
            args=[{"name": "name", "required": True}]
        )
        
        result = cmd.execute([])
        assert "Missing required argument" in result
    
    def test_get_help(self):
        """测试获取帮助"""
        def handler(args):
            return "ok"
        
        cmd = CLICommand(
            "test", "Test command", handler,
            args=[{"name": "name", "description": "A name", "required": True}]
        )
        
        help_text = cmd.get_help()
        assert "test - Test command" in help_text
        assert "name" in help_text
        assert "required" in help_text


class TestCLIInterface:
    """测试CLI界面"""
    
    def test_creation(self):
        """测试创建"""
        cli = CLIInterface()
        assert len(cli.get_commands()) == 0
    
    def test_register_command(self):
        """测试注册命令"""
        cli = CLIInterface()
        
        def handler(args):
            return "ok"
        
        cli.register_command("test", "Test command", handler)
        assert "test" in cli.get_commands()
    
    def test_execute_command(self):
        """测试执行命令"""
        cli = CLIInterface()
        
        def handler(args):
            return "Hello"
        
        cli.register_command("greet", "Greeting", handler)
        result = cli.execute("greet")
        
        assert result == "Hello"
    
    def test_execute_unknown_command(self):
        """测试执行未知命令"""
        cli = CLIInterface()
        result = cli.execute("unknown")
        
        assert "Unknown command" in result
    
    def test_help_command(self):
        """测试帮助命令"""
        cli = CLIInterface()
        
        def handler(args):
            return "ok"
        
        cli.register_command("test", "Test command", handler)
        result = cli.execute("help")
        
        assert "Available commands" in result
        assert "test" in result
    
    def test_help_specific_command(self):
        """测试特定命令帮助"""
        cli = CLIInterface()
        
        def handler(args):
            return "ok"
        
        cli.register_command("test", "Test command", handler)
        result = cli.execute("help test")
        
        assert "Test command" in result
    
    def test_history(self):
        """测试历史记录"""
        cli = CLIInterface()
        
        def handler(args):
            return "ok"
        
        cli.register_command("test", "Test command", handler)
        cli.execute("test")
        cli.execute("test")
        
        history = cli.get_history()
        assert len(history) == 2
        assert history[0] == "test"
    
    def test_clear_history(self):
        """测试清空历史"""
        cli = CLIInterface()
        
        def handler(args):
            return "ok"
        
        cli.register_command("test", "Test command", handler)
        cli.execute("test")
        cli.clear_history()
        
        assert len(cli.get_history()) == 0
    
    def test_clear(self):
        """测试清空"""
        cli = CLIInterface()
        
        def handler(args):
            return "ok"
        
        cli.register_command("test", "Test command", handler)
        cli.execute("test")
        cli.clear()
        
        assert len(cli.get_commands()) == 0
        assert len(cli.get_history()) == 0


class TestAgentAPI:
    """测试智能体API"""
    
    def test_creation_without_agent(self):
        """测试无智能体创建"""
        agent_api = AgentAPI()
        assert agent_api.agent is None
        assert agent_api.api is not None
        assert agent_api.cli is not None
    
    def test_default_endpoints(self):
        """测试默认端点"""
        agent_api = AgentAPI()
        endpoints = agent_api.get_api().get_endpoints()
        
        paths = [ep["path"] for ep in endpoints]
        assert "/health" in paths
        assert "/kg/nodes" in paths
        assert "/kg/edges" in paths
        assert "/tasks" in paths
        assert "/stats" in paths
    
    def test_default_commands(self):
        """测试默认命令"""
        agent_api = AgentAPI()
        commands = agent_api.get_cli().get_commands()
        
        assert "status" in commands
        assert "add_node" in commands
        assert "add_edge" in commands
        assert "nodes" in commands
        assert "tasks" in commands
        assert "submit" in commands
    
    def test_health_check(self):
        """测试健康检查"""
        agent_api = AgentAPI()
        response = agent_api.handle_api_request("/health", "GET")
        
        assert response["status"] == "success"
        assert response["data"]["status"] == "healthy"
    
    def test_api_without_agent(self):
        """测试无智能体的API"""
        agent_api = AgentAPI()
        response = agent_api.handle_api_request("/kg/nodes", "GET")
        
        assert response["status"] == "error"
        assert "Agent not initialized" in response["message"]
    
    def test_cli_without_agent(self):
        """测试无智能体的CLI"""
        agent_api = AgentAPI()
        result = agent_api.handle_cli_command("status")
        
        assert "Agent not initialized" in result
    
    def test_cli_help(self):
        """测试CLI帮助"""
        agent_api = AgentAPI()
        result = agent_api.handle_cli_command("help")
        
        assert "Available commands" in result
    
    def test_cli_unknown_command(self):
        """测试CLI未知命令"""
        agent_api = AgentAPI()
        result = agent_api.handle_cli_command("unknown")
        
        assert "Unknown command" in result
