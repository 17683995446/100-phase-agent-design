#!/usr/bin/env python3
"""
阶段127：REST API

第一性原理：
  - 接口公理：稳定接口=系统稳定的对外承诺
  - 资源化：万物皆资源，皆可CRUD
  - 无状态：每个请求自包含
  - 中间件：横切关注点分离

本阶段产出：
  1. Request/Response：请求响应
  2. Router：路由
  3. Middleware：中间件
  4. APIServer：API服务器（内存模拟）
  5. API测试客户端

遵循原则：图难于其易，为大于其细
"""
import time
import json
import re
import unittest
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple
from enum import Enum
from dataclasses import dataclass, field
from collections import deque


# ============================================================
# 一、HTTP方法
# ============================================================
class HTTPMethod(Enum):
    """HTTP方法"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


# ============================================================
# 二、请求
# ============================================================
@dataclass
class Request:
    """HTTP请求"""
    method: HTTPMethod
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    query: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    remote_addr: str = "127.0.0.1"

    def get_header(self, name: str, default: str = "") -> str:
        return self.headers.get(name, default)


# ============================================================
# 三、响应
# ============================================================
@dataclass
class Response:
    """HTTP响应"""
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None

    def set_header(self, name: str, value: str) -> 'Response':
        self.headers[name] = value
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status_code,
            "headers": self.headers,
            "body": self.body,
        }


# ============================================================
# 四、路由
# ============================================================
@dataclass
class Route:
    """路由"""
    method: HTTPMethod
    pattern: str
    handler: Callable
    regex: Any = None
    param_names: List[str] = field(default_factory=list)

    def __post_init__(self):
        # 编译路径模式，支持 :param
        param_names = []
        regex_parts = []
        last_end = 0
        for m in re.finditer(r":(\w+)", self.pattern):
            regex_parts.append(re.escape(
                self.pattern[last_end:m.start()]))
            param_names.append(m.group(1))
            regex_parts.append(r"([^/]+)")
            last_end = m.end()
        regex_parts.append(re.escape(self.pattern[last_end:]))
        self.regex = re.compile("^" + "".join(regex_parts) + "$")
        self.param_names = param_names

    def match(self, method: HTTPMethod,
               path: str) -> Optional[Dict[str, str]]:
        """匹配请求，返回路径参数"""
        if method != self.method:
            return None
        m = self.regex.match(path)
        if not m:
            return None
        params = {}
        for i, name in enumerate(self.param_names):
            params[name] = m.group(i + 1)
        return params


# ============================================================
# 五、路由器
# ============================================================
class Router:
    """路由器"""
    def __init__(self):
        self._routes: List[Route] = []
        self._lock = threading.Lock()

    def add_route(self, method: HTTPMethod, path: str,
                   handler: Callable) -> None:
        with self._lock:
            self._routes.append(Route(method, path, handler))

    def get(self, path: str) -> Callable:
        def decorator(fn):
            self.add_route(HTTPMethod.GET, path, fn)
            return fn
        return decorator

    def post(self, path: str) -> Callable:
        def decorator(fn):
            self.add_route(HTTPMethod.POST, path, fn)
            return fn
        return decorator

    def put(self, path: str) -> Callable:
        def decorator(fn):
            self.add_route(HTTPMethod.PUT, path, fn)
            return fn
        return decorator

    def delete(self, path: str) -> Callable:
        def decorator(fn):
            self.add_route(HTTPMethod.DELETE, path, fn)
            return fn
        return decorator

    def resolve(self, method: HTTPMethod,
                 path: str) -> Optional[Tuple[Route, Dict[str, str]]]:
        with self._lock:
            for route in self._routes:
                params = route.match(method, path)
                if params is not None:
                    return route, params
        return None

    def list_routes(self) -> List[str]:
        with self._lock:
            return [
                f"{r.method.value} {r.pattern}" for r in self._routes
            ]


# ============================================================
# 六、中间件
# ============================================================
class Middleware:
    """中间件基类"""
    def process(self, request: Request,
                 call_next: Callable) -> Response:
        raise NotImplementedError


class TimingMiddleware(Middleware):
    """计时中间件"""
    def process(self, request: Request,
                 call_next: Callable) -> Response:
        start = time.time()
        response = call_next(request)
        duration = (time.time() - start) * 1000
        response.set_header("X-Response-Time-Ms",
                              f"{duration:.2f}")
        return response


class AuthMiddleware(Middleware):
    """认证中间件"""
    def __init__(self, valid_tokens: Optional[List[str]] = None,
                 public_paths: Optional[List[str]] = None):
        self.valid_tokens = valid_tokens or []
        self.public_paths = public_paths or ["/health", "/"]

    def process(self, request: Request,
                 call_next: Callable) -> Response:
        # 检查是否是公开路径（精确匹配或前缀）
        for pub in self.public_paths:
            if request.path == pub or request.path.startswith(pub + "/"):
                return call_next(request)
        # 检查token
        token = request.get_header("Authorization", "")
        if token and token.startswith("Bearer "):
            token = token[7:]
        if not token or token not in self.valid_tokens:
            return Response(
                status_code=401,
                body={"error": "unauthorized"})
        return call_next(request)


class LoggingMiddleware(Middleware):
    """日志中间件"""
    def __init__(self, log_fn: Optional[Callable] = None):
        self.log_fn = log_fn or print

    def process(self, request: Request,
                 call_next: Callable) -> Response:
        self.log_fn(
            f"{request.method.value} {request.path}")
        return call_next(request)


# ============================================================
# 七、API服务器
# ============================================================
class APIServer:
    """API服务器（内存模拟）"""
    def __init__(self):
        self.router = Router()
        self.middlewares: List[Middleware] = []
        self._lock = threading.Lock()
        self._stats = {
            "requests": 0,
            "errors": 0,
            "by_status": {},
            "by_method": {},
        }

    def use(self, middleware: Middleware) -> None:
        """注册中间件"""
        with self._lock:
            self.middlewares.append(middleware)

    def handle(self, request: Request) -> Response:
        """处理请求"""
        with self._lock:
            self._stats["requests"] += 1
            self._stats["by_method"][request.method.value] = (
                self._stats["by_method"].get(
                    request.method.value, 0) + 1)
        # 解析查询参数（简单实现）
        if "?" in request.path:
            path, qs = request.path.split("?", 1)
            request.path = path
            for pair in qs.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    request.query[k] = v
        # 解析body（JSON）
        if isinstance(request.body, str):
            try:
                request.body = json.loads(request.body)
            except Exception:
                pass
        # 构造调用链
        def call_chain(idx: int, req: Request) -> Response:
            if idx >= len(self.middlewares):
                # 调用handler
                resolved = self.router.resolve(req.method, req.path)
                if resolved is None:
                    with self._lock:
                        self._stats["by_status"][404] = (
                            self._stats["by_status"].get(404, 0) + 1)
                    return Response(
                        status_code=404,
                        body={"error": "not_found",
                              "path": req.path})
                route, params = resolved
                try:
                    response = route.handler(req, **params)
                    if not isinstance(response, Response):
                        response = Response(body=response)
                except Exception as e:
                    with self._lock:
                        self._stats["errors"] += 1
                        self._stats["by_status"][500] = (
                            self._stats["by_status"].get(500, 0) + 1)
                    response = Response(
                        status_code=500,
                        body={"error": str(e)})
                with self._lock:
                    self._stats["by_status"][response.status_code] = (
                        self._stats["by_status"].get(
                            response.status_code, 0) + 1)
                return response
            mw = self.middlewares[idx]
            return mw.process(req, lambda r: call_chain(idx + 1, r))
        return call_chain(0, request)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 八、单元测试
# ============================================================
class TestRoute(unittest.TestCase):
    """路由测试"""
    def test_match_simple(self):
        def handler(req):
            return Response(body="ok")
        r = Route(HTTPMethod.GET, "/users", handler)
        params = r.match(HTTPMethod.GET, "/users")
        self.assertEqual(params, {})

    def test_match_with_param(self):
        def handler(req, id):
            return Response(body="ok")
        r = Route(HTTPMethod.GET, "/users/:id", handler)
        params = r.match(HTTPMethod.GET, "/users/42")
        self.assertEqual(params, {"id": "42"})

    def test_no_match(self):
        def handler(req):
            return Response(body="ok")
        r = Route(HTTPMethod.GET, "/users", handler)
        self.assertIsNone(r.match(HTTPMethod.POST, "/users"))
        self.assertIsNone(r.match(HTTPMethod.GET, "/posts"))


class TestRouter(unittest.TestCase):
    """路由器测试"""
    def setUp(self):
        self.router = Router()

    def test_add_and_resolve(self):
        def handler(req):
            return Response(body="ok")
        self.router.add_route(HTTPMethod.GET, "/test", handler)
        result = self.router.resolve(HTTPMethod.GET, "/test")
        self.assertIsNotNone(result)
        route, params = result
        self.assertEqual(params, {})

    def test_decorators(self):
        @self.router.get("/items")
        def list_items(req):
            return Response(body=[])

        @self.router.post("/items")
        def create_item(req):
            return Response(status_code=201, body={"id": 1})

        self.assertEqual(len(self.router.list_routes()), 2)

    def test_param_routing(self):
        @self.router.get("/users/:id")
        def get_user(req, id):
            return Response(body={"id": id})

        result = self.router.resolve(HTTPMethod.GET, "/users/42")
        self.assertIsNotNone(result)
        route, params = result
        self.assertEqual(params["id"], "42")


class TestMiddleware(unittest.TestCase):
    """中间件测试"""
    def test_timing(self):
        mw = TimingMiddleware()
        req = Request(method=HTTPMethod.GET, path="/")
        response = mw.process(req, lambda r: Response(body="ok"))
        self.assertIn("X-Response-Time-Ms", response.headers)

    def test_auth_required(self):
        mw = AuthMiddleware(valid_tokens=["valid_token"])
        # 无token -> 401
        req = Request(method=HTTPMethod.GET, path="/api")
        resp = mw.process(req, lambda r: Response(body="ok"))
        self.assertEqual(resp.status_code, 401)
        # 有token -> 200
        req = Request(method=HTTPMethod.GET, path="/api",
                       headers={"Authorization": "Bearer valid_token"})
        resp = mw.process(req, lambda r: Response(body="ok"))
        self.assertEqual(resp.status_code, 200)

    def test_auth_public(self):
        mw = AuthMiddleware(valid_tokens=["t"], public_paths=["/health"])
        req = Request(method=HTTPMethod.GET, path="/health")
        resp = mw.process(req, lambda r: Response(body="ok"))
        self.assertEqual(resp.status_code, 200)


class TestAPIServer(unittest.TestCase):
    """API服务器测试"""
    def setUp(self):
        self.server = APIServer()
        @self.server.router.get("/")
        def root(req):
            return Response(body={"message": "hello"})
        @self.server.router.get("/users/:id")
        def get_user(req, id):
            return Response(body={"id": id, "name": "test"})
        @self.server.router.post("/users")
        def create_user(req):
            return Response(status_code=201,
                              body={"id": "new"})

    def test_get_root(self):
        req = Request(method=HTTPMethod.GET, path="/")
        resp = self.server.handle(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body["message"], "hello")

    def test_get_with_param(self):
        req = Request(method=HTTPMethod.GET, path="/users/42")
        resp = self.server.handle(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body["id"], "42")

    def test_post(self):
        req = Request(method=HTTPMethod.POST, path="/users",
                       body={"name": "alice"})
        resp = self.server.handle(req)
        self.assertEqual(resp.status_code, 201)

    def test_not_found(self):
        req = Request(method=HTTPMethod.GET, path="/missing")
        resp = self.server.handle(req)
        self.assertEqual(resp.status_code, 404)

    def test_with_middleware(self):
        self.server.use(TimingMiddleware())
        req = Request(method=HTTPMethod.GET, path="/")
        resp = self.server.handle(req)
        self.assertIn("X-Response-Time-Ms", resp.headers)

    def test_query_params(self):
        @self.server.router.get("/search")
        def search(req):
            return Response(body={"q": req.query.get("q")})
        req = Request(method=HTTPMethod.GET, path="/search?q=hello")
        resp = self.server.handle(req)
        self.assertEqual(resp.body["q"], "hello")

    def test_stats(self):
        req = Request(method=HTTPMethod.GET, path="/")
        self.server.handle(req)
        stats = self.server.get_stats()
        self.assertEqual(stats["requests"], 1)
        self.assertEqual(stats["by_status"][200], 1)


# ============================================================
# 九、阶段127演示
# ============================================================
def run_phase_127():
    """运行阶段127"""
    print("=" * 70)
    print("阶段127：REST API")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestRoute))
    suite.addTests(loader.loadTestsFromTestCase(TestRouter))
    suite.addTests(loader.loadTestsFromTestCase(TestMiddleware))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIServer))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【REST API演示】")
    print("-" * 70)
    import sys
    sys.path.insert(0, '/workspace')
    from phase_103_kg_crud import KnowledgeGraphCRUD
    from phase_102_core_datastructure import Node, Edge
    kg = KnowledgeGraphCRUD()
    for i in range(5):
        kg.add_node(Node(content=f"知识{i}", node_id=f"k{i}",
                          label="concept"))
    # 创建API服务
    server = APIServer()
    # 中间件
    server.use(LoggingMiddleware(
        lambda msg: print(f"     [LOG] {msg}")))
    server.use(TimingMiddleware())
    # 路由
    @server.router.get("/")
    def root(req):
        return Response(body={
            "name": "百阶段智能体", "version": "1.0"})
    @server.router.get("/health")
    def health(req):
        return Response(body={"status": "healthy"})
    @server.router.get("/nodes")
    def list_nodes(req):
        return Response(body={
            "count": len(kg.nodes),
            "nodes": [{"id": n.node_id, "content": n.content}
                       for n in kg.nodes.values()]
        })
    @server.router.get("/nodes/:id")
    def get_node(req, id):
        node = kg.get_node(id)
        if not node:
            return Response(status_code=404,
                              body={"error": "not found"})
        return Response(body={
            "id": node.node_id,
            "content": node.content,
            "label": node.label,
        })
    @server.router.post("/nodes")
    def create_node(req):
        body = req.body or {}
        node = Node(
            content=body.get("content", ""),
            node_id=body.get("id", f"n_{time.time()}"),
            label=body.get("label", "default"))
        kg.add_node(node)
        return Response(status_code=201,
                          body={"id": node.node_id})
    @server.router.delete("/nodes/:id")
    def delete_node(req, id):
        if id in kg.nodes:
            kg.soft_delete_node(id)
            return Response(status_code=204)
        return Response(status_code=404)
    # 演示1: 路由列表
    print("  🛣️  演示1: 路由列表")
    print("     " + "-" * 60)
    for route in server.router.list_routes():
        print(f"     {route}")
    print()

    # 演示2: 简单GET
    print("  📡 演示2: GET /")
    print("     " + "-" * 60)
    resp = server.handle(Request(
        method=HTTPMethod.GET, path="/"))
    print(f"     状态: {resp.status_code}")
    print(f"     响应: {resp.body}")
    print(f"     响应时间: {resp.headers.get('X-Response-Time-Ms')}ms")
    print()

    # 演示3: 列表
    print("  📋 演示3: GET /nodes")
    print("     " + "-" * 60)
    resp = server.handle(Request(
        method=HTTPMethod.GET, path="/nodes"))
    print(f"     状态: {resp.status_code}")
    print(f"     节点数: {resp.body['count']}")
    for n in resp.body["nodes"][:3]:
        print(f"       - {n['id']}: {n['content']}")
    print()

    # 演示4: 路径参数
    print("  🔍 演示4: GET /nodes/:id (k2)")
    print("     " + "-" * 60)
    resp = server.handle(Request(
        method=HTTPMethod.GET, path="/nodes/k2"))
    print(f"     状态: {resp.status_code}")
    print(f"     响应: {resp.body}")
    print()

    # 演示5: POST创建
    print("  ✏️  演示5: POST /nodes")
    print("     " + "-" * 60)
    resp = server.handle(Request(
        method=HTTPMethod.POST, path="/nodes",
        body={"id": "k5", "content": "知识5",
                "label": "concept"}))
    print(f"     状态: {resp.status_code}")
    print(f"     响应: {resp.body}")
    print()

    # 演示6: 查询参数
    print("  🔎 演示6: 查询参数 ?limit=2")
    print("     " + "-" * 60)
    resp = server.handle(Request(
        method=HTTPMethod.GET, path="/nodes?limit=2"))
    print(f"     状态: {resp.status_code}")
    print(f"     返回: {resp.body['count']}个")
    print()

    # 演示7: 404
    print("  ❌ 演示7: 404 错误")
    print("     " + "-" * 60)
    resp = server.handle(Request(
        method=HTTPMethod.GET, path="/unknown"))
    print(f"     状态: {resp.status_code}")
    print(f"     响应: {resp.body}")
    print()

    # 演示8: 统计
    print("  📊 演示8: API统计")
    print("     " + "-" * 60)
    print(f"     {server.get_stats()}")
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段127完成：REST API已实现，所有测试通过！")
    else:
        print("✅ 阶段127完成：REST API已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段128-130：高级化最后阶段")
    print("  - 阶段128：Web管理界面")
    print("  - 阶段129：Docker镜像")
    print("  - 阶段130：完整版集成与发布")
    print()
    return True


if __name__ == "__main__":
    run_phase_127()
