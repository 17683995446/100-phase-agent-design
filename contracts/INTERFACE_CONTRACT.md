# 第一原理知识图谱智能体 — 模块接口契约（ICD）

## 1. 协作架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                    总包方（架构设计与集成）                         │
│              负责：接口定义、集成测试、验收交付                      │
├─────────────────────────────────────────────────────────────────┤
│  公司A        公司B        公司C        公司D        公司E         │
│  基础数据层    核心引擎层    智能能力层    基础设施层    应用接口层    │
│  ├─node.py   ├─agent.py   ├─nlp.py    ├─security.py ├─api.py     │
│  ├─edge.py   ├─kg.py      ├─ml.py     ├─storage.py  ├─data_ex    │
│  └─config.py └─infer.py   ├─graph.py  ├─cache.py    └─query.py   │
│                           ├─sim.py    ├─metrics.py               │
│                           └─vc.py     └─benchmark.py             │
├─────────────────────────────────────────────────────────────────┤
│  公司F        公司G        公司H                                   │
│  分布式系统    并发控制      自动进化                               │
│  ├─sharding.py├─concurrency.py├─auto_evolution.py                │
│  ├─sync.py    ├─cc.py       └─system_logger.py                   │
│  ├─cluster.py └─dq.py         error_handler.py                   │
│  └─registry.py                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 2. 接口契约核心原则

### 2.1 契约优先（Contract First）
- 接口定义先于实现
- 接口变更需走 RFC（Request for Change）流程
- 版本化接口：v1, v2, ...

### 2.2 黑盒交付
- 各公司只暴露接口，不暴露实现细节
- 禁止跨模块直接访问内部数据结构
- 所有交互通过接口契约进行

### 2.3 独立测试
- 每个模块必须有独立的单元测试（覆盖率 ≥ 90%）
- 每个模块必须有接口契约测试（Contract Test）
- 集成测试由总包方统一执行

## 3. 模块接口定义

### 3.1 基础数据层（公司A）

#### Node 接口
```python
class INode(ABC):
    """节点接口契约"""
    
    @property
    @abstractmethod
    def name(self) -> str: ...
    
    @property
    @abstractmethod
    def created_at(self) -> float: ...
    
    @property
    @abstractmethod
    def valid_state(self) -> bool: ...
    
    @property
    @abstractmethod
    def attributes(self) -> dict: ...
    
    @abstractmethod
    def to_dict(self) -> dict: ...
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> 'INode': ...
```

#### Edge 接口
```python
class IEdge(ABC):
    """边接口契约"""
    
    @property
    @abstractmethod
    def source(self) -> str: ...
    
    @property
    @abstractmethod
    def target(self) -> str: ...
    
    @property
    @abstractmethod
    def relation_name(self) -> str: ...
    
    @property
    @abstractmethod
    def weight(self) -> float: ...
    
    @abstractmethod
    def to_dict(self) -> dict: ...
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> 'IEdge': ...
```

**交付物**：
- `node.py` + `edge.py` 实现
- `test_node_contract.py` + `test_edge_contract.py`
- 性能报告：创建 10000 个节点/边耗时 < 1秒

---

### 3.2 核心引擎层（公司B）

#### KnowledgeGraph 接口
```python
class IKnowledgeGraph(ABC):
    """知识图谱接口契约"""
    
    # ===== 节点操作 =====
    @abstractmethod
    def add_node(self, name: str, attributes: dict = None) -> 'INode': ...
    
    @abstractmethod
    def get_node(self, name: str) -> Optional['INode']: ...
    
    @abstractmethod
    def remove_node(self, name: str) -> bool: ...
    
    @abstractmethod
    def get_node_count(self) -> int: ...
    
    # ===== 边操作 =====
    @abstractmethod
    def add_edge(self, source: str, target: str, 
                 relation: str, weight: float) -> 'IEdge': ...
    
    @abstractmethod
    def get_edges_from(self, source: str, min_weight: float = 0.0) -> List['IEdge']: ...
    
    @abstractmethod
    def get_edge_count(self) -> int: ...
    
    # ===== 查询操作 =====
    @abstractmethod
    def find_paths(self, start: str, end: str, 
                   max_depth: int = 5) -> List[List[str]]: ...
    
    @abstractmethod
    def find_related_nodes(self, node: str, 
                           depth: int = 1) -> List[str]: ...
    
    # ===== 持久化 =====
    @abstractmethod
    def save(self) -> bool: ...
    
    @abstractmethod
    def load(self) -> bool: ...
    
    # ===== 统计 =====
    @abstractmethod
    def get_stats(self) -> dict: ...
```

#### Agent 接口
```python
class IAgent(ABC):
    """智能体接口契约"""
    
    @abstractmethod
    def add_task(self, task: str) -> bool: ...
    
    @abstractmethod
    def get_status(self) -> dict: ...
    
    @abstractmethod
    def start(self) -> None: ...
    
    @abstractmethod
    def stop(self) -> None: ...
    
    @abstractmethod
    def health_check(self) -> dict: ...
```

**交付物**：
- `knowledge_graph.py` + `agent.py` 实现
- `test_kg_contract.py` + `test_agent_contract.py`
- 性能报告：查询 1000 节点图谱 < 100ms

---

### 3.3 智能能力层（公司C）

#### NLP 接口
```python
class INLPModule(ABC):
    """NLP模块接口契约"""
    
    @abstractmethod
    def tokenize(self, text: str) -> List[str]: ...
    
    @abstractmethod
    def extract_entities(self, text: str, 
                         kg: 'IKnowledgeGraph') -> List[str]: ...
    
    @abstractmethod
    def convert_query(self, nl_query: str) -> dict: ...
```

#### ML 接口
```python
class IMLModule(ABC):
    """ML模块接口契约"""
    
    @abstractmethod
    def train(self, data: List[dict], labels: List[str]) -> str: ...
    
    @abstractmethod
    def predict(self, model_id: str, features: dict) -> str: ...
    
    @abstractmethod
    def get_model_status(self, model_id: str) -> dict: ...
```

#### GraphAlgorithms 接口
```python
class IGraphAlgorithms(ABC):
    """图算法接口契约"""
    
    @abstractmethod
    def shortest_path(self, start: str, end: str) -> Tuple[List[str], float]: ...
    
    @abstractmethod
    def pagerank(self) -> Dict[str, float]: ...
    
    @abstractmethod
    def find_communities(self) -> List[List[str]]: ...
```

**交付物**：
- 各模块实现 + `test_*_contract.py`
- 准确率报告：NLP实体提取 > 80%，ML分类 > 85%

---

### 3.4 基础设施层（公司D）

#### Security 接口
```python
class ISecurityModule(ABC):
    """安全模块接口契约"""
    
    @abstractmethod
    def authenticate(self, username: str, password: str) -> Optional[str]: ...
    
    @abstractmethod
    def authorize(self, token: str, resource: str, 
                  action: str) -> bool: ...
    
    @abstractmethod
    def create_user(self, username: str, password: str, 
                    roles: List[str]) -> bool: ...
```

#### Storage 接口
```python
class IStorageModule(ABC):
    """存储模块接口契约"""
    
    @abstractmethod
    def save(self, key: str, data: bytes) -> bool: ...
    
    @abstractmethod
    def load(self, key: str) -> Optional[bytes]: ...
    
    @abstractmethod
    def delete(self, key: str) -> bool: ...
```

**交付物**：
- 各模块实现 + `test_*_contract.py`
- 安全审计报告 + 存储性能报告

---

### 3.5 应用接口层（公司E）

#### API 接口
```python
class IAPIModule(ABC):
    """API模块接口契约"""
    
    @abstractmethod
    def start_server(self, host: str, port: int) -> None: ...
    
    @abstractmethod
    def stop_server(self) -> None: ...
    
    @abstractmethod
    def add_endpoint(self, path: str, handler: Callable) -> bool: ...
```

**交付物**：
- `api.py` + `data_exchange.py` + `query_language.py`
- API文档（OpenAPI/Swagger格式）
- 压力测试报告：支持 1000 QPS

---

### 3.6 分布式系统（公司F）

```python
class IShardingModule(ABC): ...
class ISyncModule(ABC): ...
class IClusterModule(ABC): ...
```

### 3.7 并发控制（公司G）

```python
class IConcurrencyModule(ABC): ...
class ILockModule(ABC): ...
class IDistributedQueue(ABC): ...
```

### 3.8 自动进化（公司H）

```python
class IAutoEvolution(ABC):
    """自动进化模块接口契约"""
    
    @abstractmethod
    def enable(self) -> None: ...
    
    @abstractmethod
    def disable(self) -> None: ...
    
    @abstractmethod
    def evolve(self) -> dict: ...
    
    @abstractmethod
    def get_status(self) -> dict: ...
```

## 4. 集成契约（Integration Contract）

### 4.1 模块注册机制

每个模块必须在启动时向 `ModuleRegistry` 注册：

```python
from contracts import ModuleRegistry, ModuleInfo

class MyModule:
    def __init__(self):
        self.info = ModuleInfo(
            name="nlp",
            version="1.0.0",
            layer=3,  # 智能能力层
            dependencies=["knowledge_graph"],  # 依赖的模块名
            interfaces=["INLPModule"],
            company="Company C"
        )
        ModuleRegistry.register(self.info)
```

### 4.2 事件总线（Event Bus）

模块间通信通过事件总线，禁止直接调用：

```python
from contracts import EventBus

# 发布事件
EventBus.publish("node.added", {"node": "AI", "timestamp": time.time()})

# 订阅事件
EventBus.subscribe("node.added", my_handler)
```

### 4.3 配置中心

所有配置通过统一的配置中心管理：

```python
from contracts import ConfigCenter

# 读取配置
value = ConfigCenter.get("nlp.tokenizer.max_length", default=100)

# 监听配置变更
ConfigCenter.watch("nlp.tokenizer.max_length", my_callback)
```

## 5. 交付标准

### 5.1 代码标准
| 项目 | 要求 |
|------|------|
| 单元测试覆盖率 | ≥ 90% |
| 接口契约测试 | 100% |
| 类型注解 | 100% |
| 文档字符串 | 所有公共接口 |
| 代码风格 | PEP 8 |

### 5.2 性能标准
| 模块 | 指标 | 要求 |
|------|------|------|
| 基础数据 | 创建 10000 节点 | < 1s |
| 知识图谱 | 查询路径 | < 100ms |
| NLP | 实体提取 | < 50ms/文本 |
| ML | 单次预测 | < 10ms |
| API | 并发请求 | ≥ 1000 QPS |
| 存储 | 读写操作 | < 10ms |

### 5.3 安全标准
- 密码必须 bcrypt 哈希存储
- 所有输入必须验证和消毒
- 敏感操作必须记录审计日志

## 6. 验收流程

```
公司开发 → 单元测试 → 契约测试 → 提交PR → 
总包方代码审查 → 集成测试 → 性能测试 → 
安全审计 → 验收通过 → 合并主干
```

### 6.1 契约测试示例

```python
# test_nlp_contract.py
import pytest
from contracts import ContractTest

class TestNLPContract(ContractTest):
    def test_tokenize_interface(self):
        """验证分词接口契约"""
        nlp = get_nlp_module()
        result = nlp.tokenize("人工智能")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(t, str) for t in result)
    
    def test_entity_extraction_contract(self):
        """验证实体提取接口契约"""
        nlp = get_nlp_module()
        kg = create_mock_kg()
        entities = nlp.extract_entities("AI和机器学习", kg)
        assert isinstance(entities, list)
        assert all(isinstance(e, str) for e in entities)
```

## 7. 变更管理

### 7.1 接口版本控制
```
v1.0.0 - 初始版本
v1.1.0 - 向后兼容的新增
v2.0.0 - 破坏性变更（需所有依赖方确认）
```

### 7.2 RFC 流程
1. 提交 RFC 文档
2. 影响分析（哪些模块受影响）
3. 各方评审（72小时）
4. 投票通过（2/3 多数）
5. 实施变更

## 8. 责任矩阵（RACI）

| 活动 | 总包方 | 公司A | 公司B | 公司C | 公司D | 公司E |
|------|--------|-------|-------|-------|-------|-------|
| 架构设计 | R/A | C | C | C | C | C |
| 接口定义 | R/A | C | C | C | C | C |
| 模块实现 | I | R/A | R/A | R/A | R/A | R/A |
| 单元测试 | I | R/A | R/A | R/A | R/A | R/A |
| 集成测试 | R/A | C | C | C | C | C |
| 验收交付 | R/A | C | C | C | C | C |

R=负责执行, A=最终审批, C=咨询, I=知情
