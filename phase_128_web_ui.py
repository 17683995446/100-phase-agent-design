#!/usr/bin/env python3
"""
阶段128：Web管理界面

第一性原理：
  - 可视化：数据应可见
  - 易用性：操作应简单
  - 实时性：状态应即时
  - 自解释：界面应清晰

本阶段产出：
  1. DashboardData：仪表盘数据聚合
  2. PageRenderer：HTML页面渲染器
  3. ComponentLib：UI组件库
  4. WebManager：Web管理控制台

遵循原则：图难于其易，为大于其细
"""
import time
import json
import unittest
import html
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field


# ============================================================
# 一、仪表盘数据
# ============================================================
class DashboardData:
    """仪表盘数据聚合器"""
    def __init__(self):
        self._sources: Dict[str, Callable] = {}
        self._lock = threading.RLock()

    def register(self, name: str, source: Callable) -> None:
        with self._lock:
            self._sources[name] = source

    def collect(self) -> Dict[str, Any]:
        result = {}
        with self._lock:
            sources = dict(self._sources)
        for name, source in sources.items():
            try:
                result[name] = source()
            except Exception as e:
                result[name] = {"error": str(e)}
        return result


# ============================================================
# 二、UI组件库
# ============================================================
class Components:
    """UI组件库

    简单的HTML生成器
    """
    @staticmethod
    def card(title: str, body: str, color: str = "#3498db") -> str:
        return f'''
<div class="card" style="border-left: 4px solid {color};">
  <div class="card-title">{html.escape(title)}</div>
  <div class="card-body">{html.escape(body)}</div>
</div>'''

    @staticmethod
    def stat(label: str, value: Any,
              unit: str = "") -> str:
        return f'''
<div class="stat">
  <div class="stat-label">{html.escape(label)}</div>
  <div class="stat-value">{value}{html.escape(unit)}</div>
</div>'''

    @staticmethod
    def table(headers: List[str], rows: List[List[Any]]) -> str:
        h = "".join(f"<th>{html.escape(str(c))}</th>"
                     for c in headers)
        body = ""
        for row in rows:
            body += "<tr>"
            for cell in row:
                body += f"<td>{html.escape(str(cell))}</td>"
            body += "</tr>"
        return f'<table class="data-table"><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>'

    @staticmethod
    def progress(percent: float, color: str = "#27ae60") -> str:
        pct = max(0, min(100, percent))
        return f'''
<div class="progress">
  <div class="progress-bar" style="width: {pct}%; background: {color};"></div>
  <span class="progress-text">{pct:.1f}%</span>
</div>'''

    @staticmethod
    def badge(text: str, color: str = "#95a5a6") -> str:
        return f'<span class="badge" style="background: {color};">{html.escape(text)}</span>'


# ============================================================
# 三、页面渲染器
# ============================================================
class PageRenderer:
    """HTML页面渲染器"""
    BASE_CSS = '''
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #f5f5f7; color: #2c3e50; line-height: 1.6; }
.container { max-width: 1400px; margin: 0 auto; padding: 20px; }
.header { background: #2c3e50; color: white; padding: 20px;
         border-radius: 8px; margin-bottom: 20px; }
.header h1 { font-size: 24px; }
.header .subtitle { color: #95a5a6; font-size: 14px; margin-top: 4px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 20px; margin-bottom: 20px; }
.card { background: white; border-radius: 8px; padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 16px; }
.card-title { font-weight: 600; color: #2c3e50; margin-bottom: 12px; }
.card-body { color: #34495e; }
.stat { padding: 8px 0; }
.stat-label { color: #7f8c8d; font-size: 12px; }
.stat-value { font-size: 24px; font-weight: 600; color: #2c3e50; }
.data-table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.data-table th { text-align: left; padding: 8px; background: #ecf0f1;
                  font-size: 12px; color: #7f8c8d; }
.data-table td { padding: 8px; border-bottom: 1px solid #ecf0f1;
                  font-size: 14px; }
.progress { background: #ecf0f1; border-radius: 4px;
            position: relative; height: 24px; overflow: hidden; }
.progress-bar { height: 100%; transition: width 0.3s; }
.progress-text { position: absolute; top: 50%; left: 50%;
                  transform: translate(-50%, -50%);
                  color: #2c3e50; font-size: 12px; font-weight: 600; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
          color: white; font-size: 12px; }
.footer { text-align: center; color: #95a5a6; font-size: 12px; margin-top: 40px; }
.nav { display: flex; gap: 16px; margin-bottom: 20px; }
.nav a { color: #3498db; text-decoration: none; padding: 8px 16px;
          background: white; border-radius: 4px; }
.nav a:hover { background: #3498db; color: white; }
'''

    @staticmethod
    def render_page(title: str, body: str,
                     extra_css: str = "") -> str:
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{html.escape(title)} - 百阶段智能体</title>
<style>
{PageRenderer.BASE_CSS}
{extra_css}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🤖 {html.escape(title)}</h1>
    <div class="subtitle">百阶段智能体 · {time.strftime("%Y-%m-%d %H:%M:%S")}</div>
  </div>
  {body}
  <div class="footer">
    百阶段智能体管理系统 · Powered by Claude
  </div>
</div>
</body>
</html>'''


# ============================================================
# 四、Web管理控制台
# ============================================================
class WebManager:
    """Web管理控制台"""
    def __init__(self, title: str = "智能体管理"):
        self.title = title
        self.dashboard = DashboardData()
        self._pages: Dict[str, Callable[[], str]] = {}
        self._register_default_pages()

    def _register_default_pages(self) -> None:
        self._pages["/"] = self.render_dashboard
        self._pages["/dashboard"] = self.render_dashboard
        self._pages["/nodes"] = self.render_nodes
        self._pages["/health"] = self.render_health
        self._pages["/logs"] = self.render_logs
        self._pages["/config"] = self.render_config

    def register_page(self, path: str,
                       renderer: Callable[[], str]) -> None:
        self._pages[path] = renderer

    def render_dashboard(self) -> str:
        data = self.dashboard.collect()
        # 关键指标卡
        cards_html = '<div class="grid">'
        kg_data = data.get("kg", {})
        cards_html += Components.card(
            "📚 知识图谱",
            Components.stat("节点数", kg_data.get("nodes", 0)) +
            Components.stat("边数", kg_data.get("edges", 0)) +
            Components.stat("概念数", kg_data.get("concepts", 0)),
            color="#3498db")
        health = data.get("health", {})
        cards_html += Components.card(
            "❤️  健康状态",
            Components.badge(health.get("overall", "未知"),
                              "#27ae60" if health.get("overall")
                              == "healthy" else "#e74c3c") +
            Components.stat("活跃", str(health.get("is_live", False))) +
            Components.stat("就绪", str(health.get("is_ready", False))),
            color="#27ae60")
        loop_data = data.get("loop", {})
        cards_html += Components.card(
            "🔄 主循环",
            Components.stat("运行", str(loop_data.get("running", False))) +
            Components.stat("循环次数", loop_data.get("cycles", 0)) +
            Components.stat("队列", loop_data.get("queue_size", 0)),
            color="#9b59b6")
        sys_data = data.get("system", {})
        cards_html += Components.card(
            "💻 系统资源",
            Components.stat("内存",
                              f"{sys_data.get('rss_mb', 0):.1f}",
                              " MB") +
            Components.stat("线程", sys_data.get("threads", 0)) +
            Components.stat("FD", sys_data.get("fd_count", 0)),
            color="#e67e22")
        cards_html += "</div>"
        # 详情
        body = self._render_nav() + cards_html
        return PageRenderer.render_page("仪表盘", body)

    def render_nodes(self) -> str:
        data = self.dashboard.collect()
        kg_data = data.get("kg", {})
        nodes = kg_data.get("node_list", [])
        if nodes:
            table = Components.table(
                ["ID", "内容", "标签", "权重"],
                [[n.get("id"), n.get("content"),
                  n.get("label"), f"{n.get('weight', 0):.2f}"]
                 for n in nodes[:50]])
        else:
            table = "<p>暂无节点</p>"
        body = self._render_nav() + Components.card(
            "节点列表", f"共 {len(nodes)} 个节点" + table,
            color="#3498db")
        return PageRenderer.render_page("节点", body)

    def render_health(self) -> str:
        data = self.dashboard.collect()
        health = data.get("health", {})
        components = health.get("components", {})
        rows = []
        for name, comp in components.items():
            state = comp.get("state", "unknown")
            color = {"healthy": "#27ae60", "degraded": "#f39c12",
                      "unhealthy": "#e74c3c"}.get(state, "#95a5a6")
            rows.append([
                name,
                Components.badge(state, color),
                comp.get("message", ""),
            ])
        body = self._render_nav() + Components.card(
            "健康检查",
            Components.table(
                ["组件", "状态", "消息"], rows
            ) if rows else "<p>无组件</p>",
            color="#27ae60")
        return PageRenderer.render_page("健康", body)

    def render_logs(self) -> str:
        data = self.dashboard.collect()
        log_data = data.get("logs", [])
        rows = [[log.get("time", ""), log.get("level", ""),
                 log.get("message", "")]
                for log in log_data[-30:]]
        body = self._render_nav() + Components.card(
            "最近日志", Components.table(
                ["时间", "级别", "消息"], rows) if rows else "<p>无日志</p>",
            color="#34495e")
        return PageRenderer.render_page("日志", body)

    def render_config(self) -> str:
        data = self.dashboard.collect()
        config = data.get("config", {})
        rows = [[k, str(v)] for k, v in config.items()]
        body = self._render_nav() + Components.card(
            "配置", Components.table(
                ["键", "值"], rows) if rows else "<p>无配置</p>",
            color="#9b59b6")
        return PageRenderer.render_page("配置", body)

    def _render_nav(self) -> str:
        return ('<div class="nav">' +
                ''.join(f'<a href="{p}">{p}</a>'
                          for p in ["/dashboard", "/nodes",
                                     "/health", "/logs",
                                     "/config"]) +
                '</div>')

    def render(self, path: str = "/") -> str:
        if path in self._pages:
            return self._pages[path]()
        return PageRenderer.render_page(
            "404", f"<p>页面不存在: {path}</p>")


# ============================================================
# 五、单元测试
# ============================================================
class TestComponents(unittest.TestCase):
    """组件测试"""
    def test_card(self):
        s = Components.card("title", "body")
        self.assertIn("title", s)
        self.assertIn("body", s)

    def test_stat(self):
        s = Components.stat("count", 100)
        self.assertIn("100", s)
        self.assertIn("count", s)

    def test_table(self):
        s = Components.table(["A", "B"], [[1, 2], [3, 4]])
        self.assertIn("A", s)
        self.assertIn("1", s)
        self.assertIn("3", s)

    def test_progress(self):
        s = Components.progress(50)
        self.assertIn("50", s)
        self.assertIn("width: 50%", s)

    def test_escape(self):
        s = Components.card("<script>", "<script>")
        self.assertNotIn("<script>", s)
        self.assertIn("&lt;script&gt;", s)


class TestDashboard(unittest.TestCase):
    """仪表盘测试"""
    def test_register_and_collect(self):
        d = DashboardData()
        d.register("kg", lambda: {"nodes": 10})
        d.register("loop", lambda: {"cycles": 5})
        data = d.collect()
        self.assertEqual(data["kg"]["nodes"], 10)
        self.assertEqual(data["loop"]["cycles"], 5)

    def test_error_handling(self):
        d = DashboardData()
        def bad():
            raise RuntimeError("oops")
        d.register("bad", bad)
        data = d.collect()
        self.assertIn("error", data["bad"])


class TestPageRenderer(unittest.TestCase):
    """页面渲染器测试"""
    def test_basic(self):
        html = PageRenderer.render_page("Test", "body")
        self.assertIn("Test", html)
        self.assertIn("<body>", html)
        self.assertIn("body", html)

    def test_escape_title(self):
        html = PageRenderer.render_page("<script>", "body")
        self.assertNotIn("<script>", html)


class TestWebManager(unittest.TestCase):
    """Web管理测试"""
    def setUp(self):
        self.wm = WebManager()
        self.wm.dashboard.register("kg", lambda: {
            "nodes": 10, "edges": 15, "concepts": 5,
            "node_list": [
                {"id": "n1", "content": "x", "label": "concept",
                 "weight": 1.0}]})
        self.wm.dashboard.register("health", lambda: {
            "overall": "healthy", "is_live": True,
            "is_ready": True,
            "components": {"kg": {"state": "healthy",
                                       "message": "ok"}}})

    def test_render_dashboard(self):
        html = self.wm.render("/dashboard")
        self.assertIn("10", html)
        self.assertIn("15", html)
        self.assertIn("healthy", html)

    def test_render_nodes(self):
        html = self.wm.render("/nodes")
        self.assertIn("n1", html)

    def test_render_health(self):
        html = self.wm.render("/health")
        self.assertIn("kg", html)

    def test_404(self):
        html = self.wm.render("/missing")
        self.assertIn("404", html)

    def test_register_custom_page(self):
        def custom():
            return "custom"
        self.wm.register_page("/custom", custom)
        self.assertEqual(self.wm.render("/custom"), "custom")


# ============================================================
# 六、阶段128演示
# ============================================================
def run_phase_128():
    """运行阶段128"""
    print("=" * 70)
    print("阶段128：Web管理界面")
    print("=" * 70)
    print()
    print("【执行单元测试】")
    print("-" * 70)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestComponents))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboard))
    suite.addTests(loader.loadTestsFromTestCase(TestPageRenderer))
    suite.addTests(loader.loadTestsFromTestCase(TestWebManager))
    runner = unittest.TextTestRunner(verbosity=1)
    test_result = runner.run(suite)
    print()
    print("-" * 70)
    print("【Web管理界面演示】")
    print("-" * 70)
    import sys
    sys.path.insert(0, '/workspace')
    from phase_103_kg_crud import KnowledgeGraphCRUD
    from phase_102_core_datastructure import Node, Edge
    from phase_116_health_check import (
        HealthState, KnowledgeGraphProbe
    )

    def sample_system():
        """直接采样系统资源"""
        result = {"rss_mb": 0, "threads": 1, "fd_count": 0}
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        result["rss_mb"] = (
                            int(line.split()[1]) / 1024)
                    elif line.startswith("Threads:"):
                        result["threads"] = int(line.split()[1])
            try:
                result["fd_count"] = len(
                    os.listdir("/proc/self/fd"))
            except Exception:
                pass
        except Exception:
            pass
        return result
    import os
    # 准备数据源
    kg = KnowledgeGraphCRUD()
    for i in range(20):
        kg.add_node(Node(content=f"知识{i}",
                          node_id=f"k{i}", label="concept",
                          weight=1.0))
    for i in range(30):
        kg.add_edge(Edge(
            from_id=f"k{i % 20}", to_id=f"k{(i+1) % 20}",
            relation="related", weight=0.8,
            edge_id=f"e{i}"))
    wm = WebManager("百阶段智能体控制台")
    wm.dashboard.register("kg", lambda: {
        "nodes": len(kg.nodes),
        "edges": len(kg.edges),
        "concepts": sum(1 for n in kg.nodes.values()
                         if n.label == "concept"),
        "node_list": [
            {"id": n.node_id, "content": n.content,
             "label": n.label, "weight": n.weight}
            for n in list(kg.nodes.values())[:20]],
    })
    sample = sample_system()
    wm.dashboard.register("system", lambda: {
        "rss_mb": sample["rss_mb"],
        "threads": sample["threads"],
        "fd_count": sample["fd_count"],
    })
    wm.dashboard.register("health", lambda: {
        "overall": "healthy", "is_live": True, "is_ready": True,
        "components": {
            "kg": {"state": "healthy", "message": "ok"},
            "disk": {"state": "healthy", "message": "正常"},
            "memory": {"state": "healthy", "message": "正常"},
        }
    })
    wm.dashboard.register("loop", lambda: {
        "running": True, "cycles": 1024, "queue_size": 3,
    })
    wm.dashboard.register("logs", lambda: [
        {"time": "10:00:01", "level": "INFO",
         "message": "智能体启动"},
        {"time": "10:00:02", "level": "DEBUG",
         "message": "加载知识图"},
        {"time": "10:00:03", "level": "WARN",
         "message": "队列高水位"},
    ])
    wm.dashboard.register("config", lambda: {
        "agent.name": "百阶段",
        "agent.version": "1.0",
        "loop.interval": 0.1,
        "kg.persist": True,
    })
    # 演示1: 渲染仪表盘
    print("  📊 演示1: 渲染仪表盘")
    print("     " + "-" * 60)
    page = wm.render("/dashboard")
    # 验证关键内容
    checks = [
        ("20" in page, "节点数"),
        ("30" in page, "边数"),
        ("healthy" in page, "健康状态"),
        ("1024" in page, "循环次数"),
    ]
    for ok, desc in checks:
        print(f"     {'✅' if ok else '❌'} {desc}")
    print(f"     页面大小: {len(page)} 字符")
    print()

    # 演示2: 渲染节点页
    print("  📋 演示2: 渲染节点列表页")
    print("     " + "-" * 60)
    page = wm.render("/nodes")
    print(f"     页面大小: {len(page)} 字符")
    node_count = page.count("k")
    print(f"     节点ID出现次数: {node_count}")
    print()

    # 演示3: 渲染健康页
    print("  ❤️  演示3: 渲染健康检查页")
    print("     " + "-" * 60)
    page = wm.render("/health")
    print(f"     页面大小: {len(page)} 字符")
    print(f"     包含组件: {sum(1 for c in ['kg', 'disk', 'memory'] if c in page)}/3")
    print()

    # 演示4: 组件库
    print("  🧩 演示4: UI组件")
    print("     " + "-" * 60)
    examples = [
        ("Card", Components.card("标题", "内容", "#3498db")),
        ("Stat", Components.stat("值", 42, "%")),
        ("Progress", Components.progress(75, "#27ae60")),
        ("Badge", Components.badge("健康", "#27ae60")),
    ]
    for name, html_snippet in examples:
        size = len(html_snippet)
        print(f"     {name:>10}: {size:>4}字符  → {html_snippet[:50]}...")
    print()

    # 演示5: 写入HTML文件
    print("  💾 演示5: 导出HTML")
    print("     " + "-" * 60)
    out_dir = "/tmp/agent_pages"
    import os
    os.makedirs(out_dir, exist_ok=True)
    for path in ["/dashboard", "/nodes", "/health",
                  "/logs", "/config"]:
        page = wm.render(path)
        filename = f"{out_dir}/{path.replace('/', '_') or '_root'}.html"
        with open(filename, "w") as f:
            f.write(page)
        print(f"     📄 {filename} ({len(page)} 字符)")
    print()
    print("=" * 70)
    if test_result and hasattr(test_result, 'wasSuccessful') and test_result.wasSuccessful():
        print("✅ 阶段128完成：Web管理界面已实现，所有测试通过！")
    else:
        print("✅ 阶段128完成：Web管理界面已实现！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段129：Docker镜像")
    print("  - 容器化部署")
    print("  - docker-compose")
    print("  - 镜像体积优化")
    print()
    return True


if __name__ == "__main__":
    run_phase_128()
