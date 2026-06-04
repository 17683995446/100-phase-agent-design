#!/usr/bin/env python3
"""
阶段101：MVP最小可行产品架构设计

第一性原理：
  - 存续公理：MVP必须能持续运行不崩溃
  - 记忆公理：数据持久化是第一公民
  - 自驱公理：必须能自主产生任务并执行

MVP目标：
  1. 能跑起来（python mvp.py即用）
  2. 数据不丢（异常退出也能恢复）
  3. 能扩展（架构为后续阶段留好接口）

遵循原则：图难于其易，为大于其细
"""
import os
import json
from typing import Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ============================================================
# 一、MVP文件结构设计
# ============================================================
MVP_FILE_STRUCTURE = {
    "mvp.py": "主入口，串联所有模块",
    "mvp_config.json": "配置文件",
    "mvp_kg.py": "知识图谱核心（阶段103）",
    "mvp_storage.py": "持久化（阶段104）",
    "mvp_task.py": "任务队列（阶段105）",
    "mvp_loop.py": "主循环（阶段106）",
    "mvp_guard.py": "异常隔离（阶段107）",
    "mvp_monitor.py": "资源监控（阶段108）",
    "mvp_data/": "数据目录",
    "    kg_data.json": "知识图谱数据",
    "    kg_data.json.bak": "备份",
    "    mvp.log": "运行日志",
    "    metrics.json": "监控指标",
}


# ============================================================
# 二、MVP模块依赖图
# ============================================================
MVP_MODULE_DEPENDENCIES = {
    "mvp.py": ["mvp_config", "mvp_loop"],
    "mvp_config": [],
    "mvp_kg": ["mvp_storage"],
    "mvp_storage": [],
    "mvp_task": ["mvp_kg"],
    "mvp_loop": ["mvp_task", "mvp_kg", "mvp_guard", "mvp_monitor"],
    "mvp_guard": [],
    "mvp_monitor": [],
}


# ============================================================
# 三、MVP核心类骨架
# ============================================================
class MVPLayer(Enum):
    """MVP架构层级"""
    ENTRY = "入口层"           # mvp.py
    LOOP = "主循环层"          # mvp_loop.py
    TASK = "任务层"            # mvp_task.py
    KNOWLEDGE = "知识层"       # mvp_kg.py
    STORAGE = "存储层"         # mvp_storage.py
    GUARD = "守护层"           # mvp_guard.py
    MONITOR = "监控层"         # mvp_monitor.py
    CONFIG = "配置层"          # mvp_config


@dataclass
class MVPModuleSpec:
    """MVP模块规格"""
    name: str
    layer: MVPLayer
    dependencies: List[str]
    file_path: str
    key_classes: List[str]
    estimated_loc: int
    responsibility: str
    test_approach: str


# ============================================================
# 四、详细模块规格
# ============================================================
MVP_MODULES = [
    MVPModuleSpec(
        name="mvp_config",
        layer=MVPLayer.CONFIG,
        dependencies=[],
        file_path="mvp_config.py",
        key_classes=["MVPConfig", "ConfigLoader"],
        estimated_loc=80,
        responsibility="加载/校验/提供配置参数",
        test_approach="缺配置/错配置/正常配置三类测试"
    ),
    MVPModuleSpec(
        name="mvp_storage",
        layer=MVPLayer.STORAGE,
        dependencies=[],
        file_path="mvp_storage.py",
        key_classes=["JSONStorage", "AtomicWriter"],
        estimated_loc=120,
        responsibility="JSON原子化写入、备份、损坏自愈",
        test_approach="断电模拟、文件损坏、并发写入"
    ),
    MVPModuleSpec(
        name="mvp_kg",
        layer=MVPLayer.KNOWLEDGE,
        dependencies=["mvp_storage"],
        file_path="mvp_kg.py",
        key_classes=["KnowledgeGraph", "Node", "Edge"],
        estimated_loc=200,
        responsibility="有向属性图的增删改查",
        test_approach="CRUD全覆盖、关系完整性、查询正确性"
    ),
    MVPModuleSpec(
        name="mvp_task",
        layer=MVPLayer.TASK,
        dependencies=["mvp_kg"],
        file_path="mvp_task.py",
        key_classes=["Task", "TaskQueue", "TaskScheduler"],
        estimated_loc=150,
        responsibility="任务定义、队列管理、调度策略",
        test_approach="并发安全、背压、优先级、状态转换"
    ),
    MVPModuleSpec(
        name="mvp_guard",
        layer=MVPLayer.GUARD,
        dependencies=[],
        file_path="mvp_guard.py",
        key_classes=["ExceptionGuard", "CircuitBreaker"],
        estimated_loc=100,
        responsibility="全局异常捕获、降级、重试、熔断",
        test_approach="注入各种异常验证恢复"
    ),
    MVPModuleSpec(
        name="mvp_monitor",
        layer=MVPLayer.MONITOR,
        dependencies=[],
        file_path="mvp_monitor.py",
        key_classes=["ResourceMonitor", "MetricsCollector"],
        estimated_loc=100,
        responsibility="CPU/内存/磁盘监控与指标采集",
        test_approach="资源耗尽模拟"
    ),
    MVPModuleSpec(
        name="mvp_loop",
        layer=MVPLayer.LOOP,
        dependencies=["mvp_task", "mvp_kg", "mvp_guard", "mvp_monitor"],
        file_path="mvp_loop.py",
        key_classes=["MainLoop", "ReflectionEngine"],
        estimated_loc=180,
        responsibility="主循环：保活、任务生成、执行、反思",
        test_approach="长时间运行稳定性"
    ),
    MVPModuleSpec(
        name="mvp",
        layer=MVPLayer.ENTRY,
        dependencies=["mvp_config", "mvp_loop"],
        file_path="mvp.py",
        key_classes=["MVPApplication"],
        estimated_loc=80,
        responsibility="应用入口、信号处理、启动停止",
        test_approach="信号响应、E2E"
    ),
]


# ============================================================
# 五、配置Schema
# ============================================================
DEFAULT_CONFIG = {
    "agent": {
        "name": "mvp-agent",
        "version": "0.1.0",
        "data_dir": "./mvp_data",
        "log_level": "INFO"
    },
    "knowledge_graph": {
        "max_nodes": 10000,
        "max_edges": 50000,
        "auto_prune_threshold": 0.1,
        "weight_decay_daily": 0.95
    },
    "task": {
        "queue_max_size": 100,
        "default_priority": 5,
        "max_concurrent": 1
    },
    "loop": {
        "cycle_interval_sec": 1.0,
        "min_interval_sec": 0.1,
        "max_interval_sec": 10.0,
        "auto_adjust": True
    },
    "persistence": {
        "save_interval_cycles": 10,
        "backup_enabled": True,
        "backup_keep": 3
    },
    "monitor": {
        "memory_limit_mb": 200,
        "metrics_export_interval_sec": 30
    }
}


# ============================================================
# 六、MVP验收标准
# ============================================================
MVP_ACCEPTANCE_CRITERIA = {
    "启动": "python mvp.py 即可启动，无需其他命令",
    "运行": "至少能持续运行1000个循环不崩溃",
    "数据": "重启后能加载上次数据并继续运行",
    "扩展": "新模块能通过标准接口接入，不需改主循环",
    "可观测": "能通过文件查看当前状态、指标、日志",
    "资源": "内存占用 < 200MB，CPU < 5%（空闲时）",
    "异常": "注入任意异常后系统能自愈",
    "优雅停止": "Ctrl+C 后能保存数据后退出",
}


# ============================================================
# 七、阶段101演示
# ============================================================
def demonstrate_phase_101():
    """演示阶段101：MVP架构设计"""
    print("=" * 70)
    print("阶段101：MVP最小可行产品架构设计")
    print("=" * 70)
    print()
    print("【一、文件结构】")
    print("-" * 70)
    for path, desc in MVP_FILE_STRUCTURE.items():
        print(f"  {path:30s}  {desc}")
    print()
    print("【二、模块依赖图】")
    print("-" * 70)
    for module, deps in MVP_MODULE_DEPENDENCIES.items():
        dep_str = " → " + ", ".join(deps) if deps else " (无依赖)"
        print(f"  {module:15s}{dep_str}")
    print()
    print("【三、模块详细规格】")
    print("-" * 70)
    print(f"  {'模块':<15} {'层级':<8} {'代码量':<6} {'关键类':<25} {'责任':<20}")
    print("  " + "-" * 65)
    for m in MVP_MODULES:
        print(f"  {m.name:<15} {m.layer.value:<8} {m.estimated_loc:<6} "
              f"{','.join(m.key_classes):<25} {m.responsibility:<20}")
    print()
    total_loc = sum(m.estimated_loc for m in MVP_MODULES)
    print(f"  📊 总计预计代码量: {total_loc} 行（不含注释和空行）")
    print()
    print("【四、配置Schema】")
    print("-" * 70)
    config_json = json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2)
    for line in config_json.split("\n")[:25]:
        print(f"  {line}")
    print("  ... (省略)")
    print()
    print("【五、MVP验收标准】")
    print("-" * 70)
    for criterion, description in MVP_ACCEPTANCE_CRITERIA.items():
        print(f"  ✅ {criterion}: {description}")
    print()
    print("=" * 70)
    print("✅ 阶段101完成：MVP架构设计已定型！")
    print("=" * 70)
    print()
    print("【下阶段预告】阶段102：核心数据结构落地")
    print("  - 实现 Node/Edge 数据类")
    print("  - 实现 KnowledgeGraph 类骨架")
    print("  - 提供 100% 覆盖的单元测试")
    print()


if __name__ == "__main__":
    demonstrate_phase_101()
