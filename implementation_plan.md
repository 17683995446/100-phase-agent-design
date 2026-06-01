# 轻量化永动知识图谱 Agent 系统实施计划

## 文档信息

- **项目名称**：EternalSelfAgent
- **项目目标**：构建零依赖、轻量化、永久自治、自主进化的智能体系统
- **核心原理**：三大公理驱动（存续公理、记忆公理、自驱公理）
- **实施周期**：十阶段递进开发

---

## 第一阶段：核心数据结构定义

### 1.1 阶段目标

建立系统唯一的数据结构基础，定义节点（Node）和边（Edge）的完整数据模型。

### 1.2 实施内容

#### 1.2.1 节点数据结构

```python
class Node:
    name: str                    # 节点唯一标识
    created_at: float           # 创建时间戳（Unix时间）
    valid_state: bool            # 有效状态（记忆公理：标记知识是否有效）
    attributes: dict             # 扩展属性字典
```

#### 1.2.2 边数据结构

```python
class Edge:
    source: str                  # 源节点名称
    target: str                  # 目标节点名称
    relation_name: str           # 关系类型描述
    weight: float               # 权重值（0.0-1.0，记忆公理：智能经验量化标准）
    created_at: float           # 创建时间戳
```

### 1.3 设计约束

- 所有数据结构均可JSON序列化（轻量化要求）
- 节点名称作为唯一主键
- 权重设计为浮点数，支持细粒度权重计算

### 1.4 验收标准

- [ ] 节点结构支持创建时间记录和有效状态标记
- [ ] 边结构支持权重赋值和关系描述
- [ ] 数据结构可完整序列化为JSON格式
- [ ] 基础单元测试验证数据模型正确性

---

## 第二阶段：知识图谱核心类实现

### 2.1 阶段目标

实现 `KnowledgeGraph` 类，完成知识存储、检索、关联的核心功能。

### 2.2 实施内容

#### 2.2.1 类结构设计

```python
class KnowledgeGraph:
    nodes: Dict[str, Node]
    edges: List[Edge]
    save_path: str
    
    def __init__(save_path: str):
    def add_node(name: str, attributes: dict = None) -> None:
    def add_edge(source: str, target: str, relation: str, weight: float) -> None:
    def save() -> None:
    def load() -> None:
    def get_node(name: str) -> Optional[Node]:
    def get_edges_from_node(node_name: str) -> List[Edge]:
```

#### 2.2.2 核心方法实现

**节点管理**

- `add_node`：检查节点是否存在，如不存在则创建新节点并写入 `self.nodes` 字典
- `get_node`：根据名称查找节点，返回节点对象或 None

**边管理**

- `add_edge`：自动确保源节点和目标节点存在，然后添加边记录
- `get_edges_from_node`：返回从指定节点出发的所有边

**持久化**

- `save`：将 `self.nodes` 和 `self.edges` 完整序列化为JSON，写入 `save_path` 文件
- `load`：从 `save_path` 读取JSON文件，反序列化恢复知识图谱状态

### 2.3 公理溯源

- **记忆公理**：所有知识必须结构化存储，`save()` 和 `load()` 保证重启不丢失经验
- **自驱公理**：图谱结构支持关联查询，为任务推演提供数据基础

### 2.4 验收标准

- [ ] 节点增删查操作正常工作
- [ ] 边增删查操作正常工作
- [ ] JSON文件持久化成功保存和加载
- [ ] 基础功能单元测试覆盖率 ≥80%

---

## 第三阶段：任务队列管理系统

### 3.1 阶段目标

实现有限长度的任务队列，支持任务的添加、弹出、去重、容量限制。

### 3.2 实施内容

#### 3.2.1 队列类设计

```python
class TaskQueue:
    queue: Deque[str]
    max_size: int
    processed_history: Set[str]
    
    def __init__(max_size: int = 200):
    def add(task: str) -> bool:
    def batch_add(tasks: List[str]) -> int:
    def pop() -> Optional[str]:
    def is_empty() -> bool:
    def size() -> int:
    def get_all() -> List[str]:
```

#### 3.2.2 核心逻辑

- **容量限制**：队列达到 `max_size` 时，拒绝新任务加入（资源守恒公理）
- **去重机制**：维护 `processed_history` 集合，避免重复任务
- **批量添加**：`batch_add` 方法支持一次性添加多个任务

### 3.3 设计约束

- 使用 `collections.deque` 实现高效的双端操作
- 全局唯一实例，在系统启动时初始化

### 3.4 验收标准

- [ ] 队列容量限制正常工作
- [ ] 任务去重功能正常
- [ ] FIFO 弹出顺序正确
- [ ] 批量添加操作正常

---

## 第四阶段：永续自治智能体主体类

### 4.1 阶段目标

实现 `EternalSelfAgent` 类，整合知识图谱和任务队列，形成智能体核心。

### 4.2 实施内容

#### 4.2.1 类结构设计

```python
class EternalSelfAgent:
    knowledge_graph: KnowledgeGraph
    task_queue: TaskQueue
    run_counter: int
    system_alive: bool
    loop_delay: float
    evolve_step: int
    
    def __init__(
        kg_save_path: str = "knowledge_graph.json",
        loop_delay: float = 0.3,
        evolve_step: int = 50,
        task_queue_max: int = 200
    ):
    def health_check() -> None:
    def self_repair() -> None:
    def get_current_task() -> Optional[str]:
    def idle_self_evolve() -> None:
    def execute_task(task: str) -> None:
    def eternal_loop() -> None:
```

#### 4.2.2 核心方法职责

**初始化**

- 创建 `KnowledgeGraph` 实例
- 创建 `TaskQueue` 实例
- 初始化运行计数器 `run_counter = 0`
- 设置系统存活标志 `system_alive = True`

**健康检查**

- `health_check()`：每执行一次任务，`run_counter += 1`
- 当 `run_counter % evolve_step == 0` 时，触发知识精简

**任务获取**

- `get_current_task()`：从队列弹出一个任务，如队列为空返回 None

**空闲进化**

- `idle_self_evolve()`：队列为空时调用，系统进入低功耗等待状态

**任务执行**

- `execute_task(task)`：
  1. 调用 `knowledge_graph.derive_new_tasks(task)` 获取推演任务
  2. 将当前任务添加为图谱节点
  3. 在任务与迭代任务之间建立权重为 0.8 的边
  4. 将推演任务和新迭代任务加入队列

### 4.3 公理溯源

- **存续公理**：`system_alive` 标志和 `self_repair()` 保证系统永久运行
- **记忆公理**：所有任务执行结果沉淀到 `knowledge_graph`
- **自驱公理**：`derive_new_tasks()` 和 `execute_task()` 实现知识驱动任务生成

### 4.4 验收标准

- [ ] 智能体成功初始化知识图谱和任务队列
- [ ] 健康检查正确更新计数器
- [ ] 任务执行流程完整（沉淀知识 → 生成新任务）
- [ ] 系统启动后可进入 `eternal_loop()` 循环

---

## 第五阶段：永恒循环与主入口

### 5.1 阶段目标

实现系统永恒循环主入口，保证系统永不退出。

### 5.2 实施内容

#### 5.2.1 永恒循环实现

```python
def eternal_loop(self):
    while self.system_alive:
        try:
            self.health_check()
            task = self.get_current_task()
            
            if task is None:
                self.idle_self_evolve()
                continue
            
            self.execute_task(task)
            time.sleep(self.loop_delay)
            
        except Exception as e:
            self.self_repair()
```

#### 5.2.2 主入口函数

```python
def main_entry():
    agent = EternalSelfAgent()
    task_queue = TaskQueue()
    task_queue.add("系统初始认知迭代")
    
    agent.knowledge_graph.add_node("系统初始认知迭代")
    
    agent.eternal_loop()

if __name__ == "__main__":
    main_entry()
```

#### 5.2.3 核心逻辑

- 循环条件：`while self.system_alive == True`（永真条件）
- 异常隔离：`try-except` 捕获所有异常，调用 `self_repair()` 恢复
- 无任务处理：队列为空时调用 `idle_self_evolve()`，维持循环不退出

### 5.3 公理溯源

- **存续公理**：`while True` 循环 + 异常隔离 = 系统永不终止
- 任何局部异常（任务失败、IO错误）被捕获后调用 `self_repair()`，不击穿整体系统

### 5.4 验收标准

- [ ] 系统成功启动并进入永恒循环
- [ ] Ctrl+C 可优雅退出（捕获 KeyboardInterrupt）
- [ ] 异常发生时系统不崩溃
- [ ] 系统可后台持续运行

---

## 第六阶段：自愈与异常处理机制

### 6.1 阶段目标

完善异常处理逻辑，实现系统自愈能力。

### 6.2 实施内容

#### 6.2.1 自愈方法实现

```python
def self_repair(self):
    self.run_counter = 0
    self.system_alive = True
    self.knowledge_graph.save()
    time.sleep(1)
```

#### 6.2.2 异常类型处理

| 异常类型 | 处理策略 |
|---------|----------|
| JSON解析错误 | 备份损坏文件，重新初始化空图谱 |
| 磁盘空间不足 | 记录警告，清理临时文件后重试 |
| 内存溢出 | 强制触发知识精简，减少队列内容 |
| 任务执行超时 | 跳过当前任务，继续下一轮循环 |

#### 6.2.3 日志记录

```python
def log_event(event_type: str, message: str):
    with open("agent_log.txt", "a") as f:
        timestamp = time.time()
        f.write(f"[{timestamp}] {event_type}: {message}\n")
```

### 6.3 公理溯源

- **存续公理**：`self_repair()` 确保任何异常后系统恢复可用状态
- 异常隔离设计保证局部故障不影响整体系统运行

### 6.4 验收标准

- [ ] 模拟异常后系统自动恢复
- [ ] 异常信息记录到日志文件
- [ ] 系统可在无外部干预情况下持续运行
- [ ] 长时间运行无内存泄漏

---

## 第七阶段：知识推演与自进化引擎

### 7.1 阶段目标

实现知识关联自动推演新任务的能力，完成自驱动核心逻辑。

### 7.2 实施内容

#### 7.2.1 知识推演方法

```python
def derive_new_tasks(self, node_name: str) -> List[str]:
    new_tasks = []
    for edge in self.knowledge_graph.edges:
        if edge.source == node_name and edge.weight > 0.2:
            new_tasks.append(f"知识推演任务:{edge.target}")
    return list(set(new_tasks))
```

#### 7.2.2 知识精简方法

```python
def trim_invalid_knowledge(self, weight_threshold: float = 0.1):
    self.knowledge_graph.edges = [
        edge for edge in self.knowledge_graph.edges
        if edge.weight > weight_threshold
    ]
    self.knowledge_graph.save()
```

#### 7.2.3 空闲自进化逻辑

```python
def idle_self_evolve(self):
    if self.run_counter > 0 and self.run_counter % 100 == 0:
        self.perform_deep_reflection()
    time.sleep(self.loop_delay * 2)
    
def perform_deep_reflection(self):
    high_value_nodes = self.get_high_value_nodes()
    for node in high_value_nodes:
        self.knowledge_graph.add_edge(
            node, "自我反思", "关联思考", 0.5
        )
```

### 7.3 公理溯源

- **自驱公理**：`derive_new_tasks()` 基于已有知识自动生成新任务
- **自驱公理**：`trim_invalid_knowledge()` 自动淘汰低价值知识，防止系统臃肿
- 空闲时执行 `deep_reflection`，实现真正的"永不空闲"

### 7.4 验收标准

- [ ] 高权重边成功推演出新任务
- [ ] 低权重边被正确过滤
- [ ] 空闲状态触发自我反思机制
- [ ] 知识精简后图谱体积显著减小

---

## 第八阶段：持久化与配置管理

### 8.1 阶段目标

完善持久化机制，实现配置管理和系统状态恢复。

### 8.2 实施内容

#### 8.2.1 配置文件设计

```json
{
    "version": "1.0.0",
    "loop_delay": 0.3,
    "evolve_step": 50,
    "task_queue_max": 200,
    "weight_threshold": 0.1,
    "kg_save_path": "knowledge_graph.json",
    "log_path": "agent_log.txt",
    "last_run_timestamp": 1234567890.123
}
```

#### 8.2.2 配置加载与保存

```python
class ConfigManager:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self.load()
    
    def load(self) -> dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                return json.load(f)
        return self.get_default_config()
    
    def save(self):
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)
    
    def get_default_config(self) -> dict:
        return {
            "version": "1.0.0",
            "loop_delay": 0.3,
            "evolve_step": 50,
            "task_queue_max": 200,
            "weight_threshold": 0.1,
            "kg_save_path": "knowledge_graph.json",
            "log_path": "agent_log.txt"
        }
```

#### 8.2.3 启动恢复逻辑

```python
def restore_state(self):
    if os.path.exists(self.config["kg_save_path"]):
        self.knowledge_graph.load()
        self.log_event("SYSTEM", "成功从持久化文件恢复状态")
    else:
        self.log_event("SYSTEM", "未找到持久化文件，系统全新启动")
```

### 8.3 公理溯源

- **记忆公理**：配置文件 + 知识图谱文件 = 完整系统状态可恢复
- 任何时刻系统状态改变后立即保存（`save()` 调用），确保断电不丢失

### 8.4 验收标准

- [ ] 配置文件正确加载和保存
- [ ] 系统重启后可恢复完整状态
- [ ] 所有状态变更实时落盘
- [ ] 配置参数可运行时修改

---

## 第九阶段：系统集成与压力测试

### 9.1 阶段目标

完成系统集成，进行长期稳定性和性能测试。

### 9.2 实施内容

#### 9.2.1 集成测试场景

| 测试场景 | 测试方法 | 预期结果 |
|---------|----------|----------|
| 冷启动 | 删除所有持久化文件后启动 | 系统正常启动并初始化 |
| 热恢复 | 正常运行后重启 | 知识图谱和任务队列正确恢复 |
| 异常注入 | 运行中强制抛出异常 | 系统自动恢复，异常被记录 |
| 长时间运行 | 运行 24 小时以上 | CPU/内存占用稳定，无泄漏 |
| 高负载 | 快速添加大量任务 | 队列容量限制生效 |

#### 9.2.2 性能基准测试

```python
def benchmark():
    agent = EternalSelfAgent()
    start_time = time.time()
    
    for i in range(1000):
        agent.execute_task(f"基准测试任务_{i}")
    
    elapsed = time.time() - start_time
    avg_time = elapsed / 1000
    
    print(f"平均任务执行时间: {avg_time:.4f}秒")
    print(f"内存占用: {get_memory_usage()}MB")
```

#### 9.2.3 系统监控接口

```python
def get_system_status() -> dict:
    return {
        "run_counter": agent.run_counter,
        "queue_size": agent.task_queue.size(),
        "node_count": len(agent.knowledge_graph.nodes),
        "edge_count": len(agent.knowledge_graph.edges),
        "system_alive": agent.system_alive,
        "uptime": time.time() - start_time
    }
```

### 9.3 验收标准

- [ ] 所有集成测试通过
- [ ] 长时间运行无内存泄漏
- [ ] 性能指标符合预期（低资源占用）
- [ ] 异常恢复成功率达到 100%

---

## 第十阶段：优化扩展与文档完善

### 10.1 阶段目标

性能优化、功能扩展、完整文档编写。

### 10.2 实施内容

#### 10.2.1 性能优化

- **图谱查询优化**：使用字典索引加速节点查找
- **批量持久化**：积累多次变更后统一写入（可选配置）
- **内存管理**：限制 `processed_history` 集合大小，防止无限增长

```python
def optimize_memory(self):
    if len(self.task_queue.processed_history) > 10000:
        old_tasks = list(self.task_queue.processed_history)[:5000]
        for task in old_tasks:
            self.task_queue.processed_history.discard(task)
```

#### 10.2.2 扩展接口预留

```python
class EternalSelfAgent:
    # 可扩展：自定义任务处理器
    def register_task_handler(self, task_type: str, handler: callable):
        self.task_handlers[task_type] = handler
    
    # 可扩展：外部知识注入
    def inject_external_knowledge(self, node_name: str, edges: List[tuple]):
        for target, relation, weight in edges:
            self.knowledge_graph.add_edge(node_name, target, relation, weight)
    
    # 可扩展：LLM 集成接口（未来版本）
    def integrate_llm(self, llm_client):
        self.llm_client = llm_client
```

#### 10.2.3 完整文档

- 用户使用手册
- API 参考文档
- 架构设计文档
- 部署运维指南

### 10.3 公理溯源

- 所有优化遵循"零冗余"原则，不引入不必要的复杂度
- 扩展设计保持三大公理不变，确保系统本质不变

### 10.4 验收标准

- [ ] 系统内存占用稳定在合理范围
- [ ] 扩展接口可用
- [ ] 完整用户文档完成
- [ ] 交付清单完整

---

## 实施时间估算

| 阶段 | 预估工时 | 关键里程碑 |
|------|----------|------------|
| 第一阶段 | 2 小时 | 核心数据结构完成 |
| 第二阶段 | 4 小时 | 知识图谱类完成 |
| 第三阶段 | 2 小时 | 任务队列完成 |
| 第四阶段 | 4 小时 | 智能体核心完成 |
| 第五阶段 | 2 小时 | 永恒循环可用 |
| 第六阶段 | 3 小时 | 异常处理完善 |
| 第七阶段 | 4 小时 | 自进化引擎完成 |
| 第八阶段 | 3 小时 | 持久化配置完成 |
| 第九阶段 | 6 小时 | 集成测试通过 |
| 第十阶段 | 4 小时 | 优化文档完成 |

**总预估工时**：34 小时

---

## 关键技术指标

| 指标 | 目标值 | 测量方法 |
|------|--------|----------|
| CPU 占用（空闲） | < 1% | `ps` 命令监控 |
| 内存占用（稳态） | < 50MB | `ps` 命令监控 |
| 启动时间 | < 1 秒 | 计时测量 |
| 任务执行延迟 | < 100ms | 日志时间戳 |
| 持久化延迟 | < 50ms | 计时测量 |
| 系统可用性 | 99.99% | 长期运行统计 |

---

## 文件结构

```
EternalSelfAgent/
├── core/
│   ├── __init__.py
│   ├── node.py          # 节点数据结构
│   ├── edge.py          # 边数据结构
│   ├── knowledge_graph.py   # 知识图谱类
│   ├── task_queue.py    # 任务队列类
│   ├── agent.py         # 智能体主体类
│   └── config.py        # 配置管理类
├── main.py              # 系统入口
├── config.json          # 配置文件
├── knowledge_graph.json # 知识持久化文件
├── agent_log.txt        # 日志文件
├── tests/
│   ├── test_node.py
│   ├── test_kg.py
│   ├── test_queue.py
│   └── test_agent.py
└── docs/
    ├── README.md
    ├── ARCHITECTURE.md
    └── API.md
```

---

## 风险评估与应对

| 风险 | 影响程度 | 应对措施 |
|------|----------|----------|
| 磁盘空间耗尽 | 高 | 监控磁盘空间，触发精简 |
| 知识图谱损坏 | 中 | JSON 备份 + 校验机制 |
| 队列无限膨胀 | 中 | 容量限制 + 去重机制 |
| 权重退化失效 | 低 | 多维度权重计算 |
| 版本升级不兼容 | 低 | 配置版本号检查 |

---

## 总结

本实施计划遵循第一性原理，从三大核心公理出发，推导出完整的系统架构。每个阶段都有明确的验收标准，确保开发过程可控。系统最终实现零依赖、轻量化、永久自治的智能体目标，可单机 7×24 小时稳定运行。