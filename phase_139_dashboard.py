#!/usr/bin/env python3
"""
阶段139：监控大盘

第一性原理：
  - 可见公理：不可见即不可控
  - 实时公理：延迟等于失明
  - 关联公理：单点指标无意义
  - 行动公理：告警必须可执行
  - 简洁公理：少而精胜过多而杂

本阶段产出：
  1. Dashboard：监控大盘
  2. Panel：面板（图表单元）
  3. Chart：图表（折线/柱状/饼图/数字）
  4. AlertRule：告警规则
  5. AlertManager：告警管理器
  6. DashboardRenderer：渲染器
  7. DataSource：数据源抽象

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import random
import threading
import uuid
import json
import math
from typing import Dict, List, Any, Optional, Callable, Tuple
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque
from abc import ABC, abstractmethod


# ============================================================
# 一、图表类型
# ============================================================
class ChartType(Enum):
    """图表类型"""
    LINE = "line"          # 折线图
    BAR = "bar"            # 柱状图
    PIE = "pie"            # 饼图
    GAUGE = "gauge"        # 仪表
    NUMBER = "number"      # 数字
    TABLE = "table"        # 表格
    HEATMAP = "heatmap"    # 热力图


@dataclass
class DataPoint:
    """数据点"""
    ts: float
    value: float
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"ts": self.ts, "value": self.value, "label": self.label}


class DataSource(ABC):
    """数据源抽象"""
    @abstractmethod
    def query(self, metric: str, range_s: float = 300.0) -> List[DataPoint]: ...


class InMemoryDataSource(DataSource):
    """内存数据源
    用于演示：从时序环形缓冲中提供数据。
    """
    def __init__(self, max_points: int = 1000):
        self._series: Dict[str, deque] = {}
        self._lock = threading.RLock()
        self._max = max_points

    def push(self, metric: str, value: float, label: str = "") -> None:
        with self._lock:
            if metric not in self._series:
                self._series[metric] = deque(maxlen=self._max)
            self._series[metric].append(
                DataPoint(ts=time.time(), value=value, label=label))

    def query(self, metric: str, range_s: float = 300.0) -> List[DataPoint]:
        with self._lock:
            series = self._series.get(metric, deque())
            cutoff = time.time() - range_s
            return [p for p in series if p.ts >= cutoff]


# ============================================================
# 二、图表与面板
# ============================================================
@dataclass
class Chart:
    """图表"""
    name: str
    chart_type: ChartType
    metric: str
    title: str = ""
    unit: str = ""
    color: str = "#3b82f6"
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    threshold_low: Optional[float] = None
    threshold_high: Optional[float] = None
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Panel:
    """面板"""
    panel_id: str
    title: str
    charts: List[Chart] = field(default_factory=list)
    layout: Dict[str, int] = field(default_factory=dict)  # x, y, w, h

    def add_chart(self, chart: Chart) -> None:
        self.charts.append(chart)


# ============================================================
# 三、告警
# ============================================================
class AlertSeverity(Enum):
    """告警严重度"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertState(Enum):
    """告警状态"""
    OK = "ok"
    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"


class AlertCondition(Enum):
    """告警条件"""
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NEQ = "!="


@dataclass
class AlertRule:
    """告警规则"""
    rule_id: str
    name: str
    metric: str
    condition: AlertCondition
    threshold: float
    duration_s: float = 60.0          # 持续时间
    severity: AlertSeverity = AlertSeverity.WARNING
    enabled: bool = True
    description: str = ""


@dataclass
class Alert:
    """告警实例"""
    alert_id: str
    rule_id: str
    metric: str
    value: float
    threshold: float
    severity: AlertSeverity
    state: AlertState
    started_at: float
    last_eval_at: float
    message: str

    def summary(self) -> Dict[str, Any]:
        return {
            "id": self.alert_id,
            "rule": self.rule_id,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "state": self.state.value,
            "started": self.started_at,
            "message": self.message,
        }


class AlertManager:
    """告警管理器
    持续评估规则，触发/恢复告警。
    """
    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: Dict[str, Alert] = {}
        self._pending: Dict[str, float] = {}  # rule_id -> 触发开始时间
        self._lock = threading.RLock()
        self._handlers: List[Callable] = []

    def add_rule(self, rule: AlertRule) -> None:
        with self._lock:
            self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        with self._lock:
            return self._rules.pop(rule_id, None) is not None

    def add_handler(self, handler: Callable) -> None:
        with self._lock:
            self._handlers.append(handler)

    def evaluate(self, metric: str, value: float,
                 source: Optional[DataSource] = None) -> List[Alert]:
        """评估指标，触发告警"""
        with self._lock:
            now = time.time()
            new_alerts: List[Alert] = []
            for rule in self._rules.values():
                if not rule.enabled or rule.metric != metric:
                    continue
                if self._check_condition(rule, value):
                    # 触发或保持
                    if rule.rule_id not in self._pending:
                        self._pending[rule.rule_id] = now
                    triggered = (now - self._pending[rule.rule_id] >= rule.duration_s)
                    if triggered:
                        # 升级为告警
                        alert = self._alerts.get(rule.rule_id)
                        if alert is None or alert.state == AlertState.RESOLVED:
                            alert = Alert(
                                alert_id=str(uuid.uuid4())[:8],
                                rule_id=rule.rule_id,
                                metric=metric,
                                value=value,
                                threshold=rule.threshold,
                                severity=rule.severity,
                                state=AlertState.FIRING,
                                started_at=now,
                                last_eval_at=now,
                                message=f"{rule.name}: {metric}={value} {rule.condition.value} {rule.threshold}",
                            )
                            self._alerts[rule.rule_id] = alert
                            new_alerts.append(alert)
                            for h in self._handlers:
                                try:
                                    h(alert)
                                except Exception:
                                    pass
                        else:
                            alert.value = value
                            alert.last_eval_at = now
                else:
                    # 恢复
                    self._pending.pop(rule.rule_id, None)
                    if rule.rule_id in self._alerts:
                        a = self._alerts[rule.rule_id]
                        a.state = AlertState.RESOLVED
                        a.last_eval_at = now
            return new_alerts

    def _check_condition(self, rule: AlertRule, value: float) -> bool:
        c = rule.condition
        t = rule.threshold
        if c == AlertCondition.GT:
            return value > t
        if c == AlertCondition.LT:
            return value < t
        if c == AlertCondition.GTE:
            return value >= t
        if c == AlertCondition.LTE:
            return value <= t
        if c == AlertCondition.EQ:
            return value == t
        if c == AlertCondition.NEQ:
            return value != t
        return False

    def firing(self) -> List[Alert]:
        with self._lock:
            return [a for a in self._alerts.values()
                    if a.state == AlertState.FIRING]

    def all(self) -> List[Alert]:
        with self._lock:
            return list(self._alerts.values())


# ============================================================
# 四、监控大盘
# ============================================================
@dataclass
class Dashboard:
    """监控大盘"""
    dashboard_id: str
    name: str
    description: str = ""
    panels: List[Panel] = field(default_factory=list)
    refresh_interval_s: float = 5.0
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def add_panel(self, panel: Panel) -> None:
        self.panels.append(panel)

    def panel_count(self) -> int:
        return len(self.panels)

    def chart_count(self) -> int:
        return sum(len(p.charts) for p in self.panels)

    def summary(self) -> Dict[str, Any]:
        return {
            "id": self.dashboard_id,
            "name": self.name,
            "panels": self.panel_count(),
            "charts": self.chart_count(),
            "tags": self.tags,
        }


class DashboardService:
    """大盘服务
    管理大盘、查询数据、评估告警。
    """
    def __init__(self, data_source: DataSource,
                 alert_manager: AlertManager):
        self.data_source = data_source
        self.alert_manager = alert_manager
        self._dashboards: Dict[str, Dashboard] = {}
        self._lock = threading.RLock()

    def create(self, dashboard: Dashboard) -> None:
        with self._lock:
            self._dashboards[dashboard.dashboard_id] = dashboard

    def get(self, dashboard_id: str) -> Optional[Dashboard]:
        with self._lock:
            return self._dashboards.get(dashboard_id)

    def list_dashboards(self) -> List[Dashboard]:
        with self._lock:
            return list(self._dashboards.values())

    def query_chart_data(self, chart: Chart,
                          range_s: float = 300.0) -> List[Dict[str, Any]]:
        """查询图表数据"""
        points = self.data_source.query(chart.metric, range_s)
        return [p.to_dict() for p in points]

    def snapshot(self, dashboard_id: str) -> Dict[str, Any]:
        """生成大盘快照"""
        with self._lock:
            d = self._dashboards.get(dashboard_id)
            if d is None:
                return {}
            panels = []
            for panel in d.panels:
                charts = []
                for chart in panel.charts:
                    data = self.query_chart_data(chart)
                    latest = data[-1]["value"] if data else None
                    charts.append({
                        "name": chart.name,
                        "type": chart.chart_type.value,
                        "metric": chart.metric,
                        "latest": latest,
                        "data": data,
                    })
                panels.append({
                    "id": panel.panel_id,
                    "title": panel.title,
                    "charts": charts,
                })
            return {
                "dashboard": d.summary(),
                "panels": panels,
                "alerts": [a.summary() for a in self.alert_manager.firing()],
                "ts": time.time(),
            }


# ============================================================
# 五、渲染器
# ============================================================
class DashboardRenderer:
    """大盘渲染器
    将快照转为可视化格式（JSON/HTML）。
    """
    def __init__(self, format: str = "json"):
        self._format = format

    def render(self, snapshot: Dict[str, Any]) -> str:
        if self._format == "json":
            return json.dumps(snapshot, ensure_ascii=False, indent=2)
        if self._format == "html":
            return self._render_html(snapshot)
        if self._format == "summary":
            return self._render_summary(snapshot)
        return json.dumps(snapshot)

    def _render_summary(self, snapshot: Dict[str, Any]) -> str:
        if not snapshot:
            return "空大盘"
        lines = [
            f"=== {snapshot['dashboard']['name']} ===",
            f"  面板: {snapshot['dashboard']['panels']}, "
            f"图表: {snapshot['dashboard']['charts']}",
        ]
        for p in snapshot.get("panels", []):
            lines.append(f"  [{p['title']}]")
            for c in p["charts"]:
                v = c.get("latest", "N/A")
                lines.append(f"    - {c['name']} ({c['metric']}): {v}")
        firing = snapshot.get("alerts", [])
        if firing:
            lines.append(f"  ⚠️  触发告警: {len(firing)}")
            for a in firing:
                lines.append(f"    [{a['severity']}] {a['message']}")
        return "\n".join(lines)

    def _render_html(self, snapshot: Dict[str, Any]) -> str:
        if not snapshot:
            return "<html><body>空</body></html>"
        html = ["<html><head><title>",
                snapshot['dashboard']['name'],
                "</title></head><body><h1>",
                snapshot['dashboard']['name'], "</h1>"]
        for p in snapshot.get("panels", []):
            html.append(f"<div><h2>{p['title']}</h2>")
            for c in p["charts"]:
                v = c.get("latest", "N/A")
                html.append(f"<div>{c['name']} ({c['metric']}): <b>{v}</b></div>")
            html.append("</div>")
        firing = snapshot.get("alerts", [])
        if firing:
            html.append("<h2>告警</h2><ul>")
            for a in firing:
                html.append(f"<li>[{a['severity']}] {a['message']}</li>")
            html.append("</ul>")
        html.append("</body></html>")
        return "".join(html)


# ============================================================
# 六、测试
# ============================================================
class TestDataSource(unittest.TestCase):
    def test_push_and_query(self):
        ds = InMemoryDataSource()
        ds.push("cpu", 0.5)
        ds.push("cpu", 0.6)
        ds.push("cpu", 0.7)
        results = ds.query("cpu", range_s=60.0)
        self.assertEqual(len(results), 3)

    def test_query_range(self):
        ds = InMemoryDataSource()
        ds.push("cpu", 0.5)
        # 等一小段时间后查询极短窗口
        time.sleep(0.05)
        results = ds.query("cpu", range_s=0.001)  # 极短时间窗
        self.assertEqual(len(results), 0)

    def test_query_unknown_metric(self):
        ds = InMemoryDataSource()
        results = ds.query("missing")
        self.assertEqual(len(results), 0)


class TestChart(unittest.TestCase):
    def test_create(self):
        c = Chart(name="cpu_usage", chart_type=ChartType.LINE,
                   metric="cpu", title="CPU")
        self.assertEqual(c.chart_type, ChartType.LINE)


class TestAlertManager(unittest.TestCase):
    def test_add_rule(self):
        am = AlertManager()
        rule = AlertRule(
            rule_id="r1", name="High CPU", metric="cpu",
            condition=AlertCondition.GT, threshold=0.8)
        am.add_rule(rule)
        self.assertIn("r1", am._rules)

    def test_evaluate_trigger(self):
        am = AlertManager()
        rule = AlertRule(
            rule_id="r1", name="High CPU", metric="cpu",
            condition=AlertCondition.GT, threshold=0.8,
            duration_s=0.0)
        am.add_rule(rule)
        alerts = am.evaluate("cpu", 0.9)
        # duration_s=0.0, 立即触发
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].state, AlertState.FIRING)

    def test_evaluate_no_trigger(self):
        am = AlertManager()
        rule = AlertRule(
            rule_id="r1", name="High CPU", metric="cpu",
            condition=AlertCondition.GT, threshold=0.8,
            duration_s=60.0)
        am.add_rule(rule)
        alerts = am.evaluate("cpu", 0.5)
        self.assertEqual(len(alerts), 0)

    def test_evaluate_resolve(self):
        am = AlertManager()
        rule = AlertRule(
            rule_id="r1", name="High CPU", metric="cpu",
            condition=AlertCondition.GT, threshold=0.8,
            duration_s=0.0)
        am.add_rule(rule)
        am.evaluate("cpu", 0.9)  # 触发
        am.evaluate("cpu", 0.5)  # 恢复
        # 第一个evaluate后已触发
        # 第二个evaluate后状态变为resolved
        # 但firing列表中不应包含
        firing = am.firing()
        self.assertEqual(len(firing), 0)

    def test_handler(self):
        am = AlertManager()
        received = []
        am.add_handler(lambda a: received.append(a))
        rule = AlertRule(
            rule_id="r1", name="r", metric="x",
            condition=AlertCondition.GT, threshold=10.0,
            duration_s=0.0)
        am.add_rule(rule)
        am.evaluate("x", 20.0)
        self.assertEqual(len(received), 1)

    def test_disabled_rule(self):
        am = AlertManager()
        rule = AlertRule(
            rule_id="r1", name="r", metric="x",
            condition=AlertCondition.GT, threshold=10.0,
            enabled=False, duration_s=0.0)
        am.add_rule(rule)
        alerts = am.evaluate("x", 20.0)
        self.assertEqual(len(alerts), 0)

    def test_remove_rule(self):
        am = AlertManager()
        am.add_rule(AlertRule(
            rule_id="r1", name="r", metric="x",
            condition=AlertCondition.GT, threshold=10.0))
        self.assertTrue(am.remove_rule("r1"))
        self.assertFalse(am.remove_rule("r1"))

    def test_conditions(self):
        am = AlertManager()
        for cond, val, thr, expected in [
            (AlertCondition.GT, 11, 10, True),
            (AlertCondition.LT, 9, 10, True),
            (AlertCondition.GTE, 10, 10, True),
            (AlertCondition.LTE, 10, 10, True),
            (AlertCondition.EQ, 10, 10, True),
            (AlertCondition.NEQ, 9, 10, True),
        ]:
            rule = AlertRule(
                rule_id=f"r_{cond.value}", name=cond.value,
                metric="m", condition=cond, threshold=thr,
                duration_s=0.0)
            am.add_rule(rule)
        alerts = am.evaluate("m", 10)
        # GT 10>10=False, LT 10<10=False, GTE True, LTE True, EQ True, NEQ 10!=10=False
        # 期望触发: GTE, LTE, EQ = 3
        self.assertEqual(len(alerts), 3)


class TestDashboard(unittest.TestCase):
    def test_create(self):
        d = Dashboard(dashboard_id="d1", name="Test")
        self.assertEqual(d.panel_count(), 0)

    def test_add_panel(self):
        d = Dashboard(dashboard_id="d1", name="Test")
        panel = Panel(panel_id="p1", title="P1")
        panel.add_chart(Chart(name="c1", chart_type=ChartType.LINE,
                                metric="m"))
        d.add_panel(panel)
        self.assertEqual(d.panel_count(), 1)
        self.assertEqual(d.chart_count(), 1)

    def test_summary(self):
        d = Dashboard(dashboard_id="d1", name="Test")
        s = d.summary()
        self.assertEqual(s["name"], "Test")


class TestDashboardService(unittest.TestCase):
    def test_create_and_get(self):
        ds = InMemoryDataSource()
        am = AlertManager()
        svc = DashboardService(ds, am)
        d = Dashboard(dashboard_id="d1", name="Test")
        svc.create(d)
        self.assertIsNotNone(svc.get("d1"))

    def test_snapshot(self):
        ds = InMemoryDataSource()
        am = AlertManager()
        svc = DashboardService(ds, am)
        d = Dashboard(dashboard_id="d1", name="Test")
        panel = Panel(panel_id="p1", title="P1")
        panel.add_chart(Chart(name="c1", chart_type=ChartType.LINE,
                                metric="cpu"))
        d.add_panel(panel)
        svc.create(d)
        ds.push("cpu", 0.5)
        snap = svc.snapshot("d1")
        self.assertIn("panels", snap)
        self.assertEqual(len(snap["panels"]), 1)

    def test_snapshot_unknown(self):
        ds = InMemoryDataSource()
        am = AlertManager()
        svc = DashboardService(ds, am)
        snap = svc.snapshot("nonexistent")
        self.assertEqual(snap, {})


class TestDashboardRenderer(unittest.TestCase):
    def test_render_json(self):
        r = DashboardRenderer("json")
        s = r.render({"name": "test"})
        self.assertIn("name", s)

    def test_render_html(self):
        r = DashboardRenderer("html")
        s = r.render({
            "dashboard": {"name": "T", "panels": 1, "charts": 1, "tags": []},
            "panels": [{"id": "p1", "title": "P1",
                          "charts": [{"name": "c1", "type": "line",
                                        "metric": "m", "latest": 0.5,
                                        "data": []}]}],
            "alerts": [],
        })
        self.assertIn("<html>", s)
        self.assertIn("T", s)

    def test_render_summary(self):
        r = DashboardRenderer("summary")
        s = r.render({
            "dashboard": {"name": "T", "panels": 1, "charts": 1, "tags": []},
            "panels": [{"id": "p1", "title": "P1",
                          "charts": [{"name": "c1", "type": "line",
                                        "metric": "m", "latest": 0.5,
                                        "data": []}]}],
            "alerts": [],
        })
        self.assertIn("===", s)

    def test_render_empty(self):
        r = DashboardRenderer("summary")
        s = r.render({})
        self.assertEqual(s, "空大盘")


# ============================================================
# 七、Demo
# ============================================================
def demo():
    """演示阶段139的功能"""
    print("=" * 60)
    print("阶段139演示：监控大盘")
    print("=" * 60)

    # 1. 数据源
    print("\n📊 演示1：数据源")
    print("-" * 60)
    ds = InMemoryDataSource()
    for i in range(20):
        ds.push("cpu_usage", 0.3 + random.random() * 0.4)
        ds.push("memory_mb", 200 + random.random() * 100)
        ds.push("qps", 50 + random.random() * 50)
    print(f"  cpu_usage点数: {len(ds.query('cpu_usage'))}")
    print(f"  memory_mb点数: {len(ds.query('memory_mb'))}")
    print(f"  qps点数: {len(ds.query('qps'))}")

    # 2. 告警
    print("\n🚨 演示2：告警规则")
    print("-" * 60)
    am = AlertManager()
    received = []
    am.add_handler(lambda a: received.append(a))
    am.add_rule(AlertRule(
        rule_id="cpu_high", name="CPU过高",
        metric="cpu_usage", condition=AlertCondition.GT,
        threshold=0.6, duration_s=0.0,
        severity=AlertSeverity.WARNING))
    am.add_rule(AlertRule(
        rule_id="mem_high", name="内存过高",
        metric="memory_mb", condition=AlertCondition.GT,
        threshold=250.0, duration_s=0.0,
        severity=AlertSeverity.CRITICAL))
    # 模拟数据触发
    for _ in range(3):
        am.evaluate("cpu_usage", 0.7)
        am.evaluate("memory_mb", 280.0)
    print(f"  触发告警数: {len(am.firing())}")
    for a in am.firing():
        s = a.summary()
        print(f"    [{s['severity']}] {s['message']}")

    # 3. 大盘
    print("\n📈 演示3：监控大盘")
    print("-" * 60)
    svc = DashboardService(ds, am)
    d = Dashboard(
        dashboard_id="main", name="智能体总览",
        description="核心指标实时监控")
    # 系统概览面板
    p1 = Panel(panel_id="p1", title="系统概览")
    p1.add_chart(Chart(name="cpu", chart_type=ChartType.LINE,
                          metric="cpu_usage", title="CPU使用率", unit="%"))
    p1.add_chart(Chart(name="mem", chart_type=ChartType.GAUGE,
                          metric="memory_mb", title="内存占用", unit="MB"))
    p1.add_chart(Chart(name="qps", chart_type=ChartType.NUMBER,
                          metric="qps", title="每秒查询"))
    d.add_panel(p1)
    # 业务面板
    p2 = Panel(panel_id="p2", title="业务指标")
    p2.add_chart(Chart(name="latency", chart_type=ChartType.LINE,
                          metric="latency_ms", title="延迟"))
    d.add_panel(p2)
    svc.create(d)
    print(f"  大盘 '{d.name}': {d.panel_count()}面板, {d.chart_count()}图表")

    # 4. 快照
    print("\n📸 演示4：实时快照")
    print("-" * 60)
    snap = svc.snapshot("main")
    renderer = DashboardRenderer("summary")
    print(renderer.render(snap))

    # 5. 告警联动
    print("\n🔔 演示5：告警联动")
    print("-" * 60)
    print(f"  告警处理函数收到: {len(received)} 次")
    if received:
        print(f"  最新: {received[-1].message}")

    # 6. HTML渲染
    print("\n🌐 演示6：HTML 渲染")
    print("-" * 60)
    html_renderer = DashboardRenderer("html")
    html = html_renderer.render(snap)
    print(f"  HTML长度: {len(html)} 字符")
    print(f"  包含 <html>: {'<html>' in html}")
    print(f"  包含告警: {'<ul>' in html}")

    print("\n" + "=" * 60)
    print("✅ 阶段139完成：监控大盘已实现！")
    print("=" * 60)
    print("\n【最终阶段】阶段140：正式版发布")
    print("  - 总结所有阶段")
    print("  - 系统集成验证")
    print("  - 颁发最终证书")


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    print()
    demo()
