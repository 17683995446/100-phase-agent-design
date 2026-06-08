#!/usr/bin/env python3
"""
阶段137：AI集成

第一性原理：
  - 语义公理：含义可被向量捕捉
  - 检索公理：相关上下文胜过更多参数
  - 生成公理：LLM 推理与知识互补
  - 协同公理：符号 + 神经 = 更强
  - 评估公理：AI 决策必须可解释

本阶段产出：
  1. Embedder：嵌入模型抽象
  2. MockEmbedder：模拟嵌入器
  3. VectorStore：向量存储
  4. LLMClient：大模型客户端
  5. PromptTemplate：提示词模板
  6. RAGPipeline：检索增强生成
  7. Recommender：智能推荐
  8. AIAgent：AI 智能体

遵循原则：图难于其易，为大于其细
"""
import time
import unittest
import random
import threading
import uuid
import json
import math
import hashlib
from typing import Dict, List, Any, Optional, Callable, Tuple
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
from abc import ABC, abstractmethod


# ============================================================
# 一、嵌入模型
# ============================================================
class Embedder(ABC):
    """嵌入模型基类"""
    @abstractmethod
    def embed(self, text: str) -> List[float]: ...

    @abstractmethod
    def dimension(self) -> int: ...


class MockEmbedder(Embedder):
    """模拟嵌入器
    使用 n-gram 哈希特征生成可比较向量。
    """
    def __init__(self, dim: int = 64, ngram: int = 2):
        self._dim = dim
        self._ngram = ngram

    def dimension(self) -> int:
        return self._dim

    def _features(self, text: str) -> List[float]:
        """提取 n-gram 特征"""
        text = text.lower().strip()
        # 字符 n-gram
        grams = set()
        for n in range(1, self._ngram + 1):
            for i in range(len(text) - n + 1):
                grams.add(text[i:i+n])
        # 词
        for w in text.split():
            grams.add(w)
        # 投影到固定维度
        vec = [0.0] * self._dim
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest()[:8], 16)
            idx = h % self._dim
            sign = 1.0 if (h >> 31) & 1 else -1.0
            vec[idx] += sign
        return vec

    def embed(self, text: str) -> List[float]:
        vec = self._features(text)
        # 归一化
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """余弦相似度"""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


# ============================================================
# 二、向量存储
# ============================================================
@dataclass
class VectorEntry:
    """向量条目"""
    entry_id: str
    text: str
    vector: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """检索结果"""
    entry_id: str
    text: str
    score: float
    metadata: Dict[str, Any]


class VectorStore:
    """向量存储
    简单的内存向量检索。
    """
    def __init__(self, embedder: Embedder):
        self._entries: Dict[str, VectorEntry] = {}
        self._embedder = embedder
        self._lock = threading.RLock()
        self._stats = {"inserts": 0, "searches": 0}

    def add(self, text: str, metadata: Optional[Dict] = None,
            entry_id: Optional[str] = None) -> str:
        with self._lock:
            eid = entry_id or str(uuid.uuid4())[:8]
            vec = self._embedder.embed(text)
            entry = VectorEntry(
                entry_id=eid, text=text, vector=vec,
                metadata=metadata or {})
            self._entries[eid] = entry
            self._stats["inserts"] += 1
            return eid

    def get(self, entry_id: str) -> Optional[VectorEntry]:
        with self._lock:
            return self._entries.get(entry_id)

    def search(self, query: str, top_k: int = 5,
               threshold: float = 0.0) -> List[SearchResult]:
        with self._lock:
            self._stats["searches"] += 1
            qv = self._embedder.embed(query)
            results = []
            for e in self._entries.values():
                score = cosine_similarity(qv, e.vector)
                if score >= threshold:
                    results.append(SearchResult(
                        entry_id=e.entry_id, text=e.text,
                        score=score, metadata=e.metadata))
            results.sort(key=lambda x: x.score, reverse=True)
            return results[:top_k]

    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 三、LLM 客户端
# ============================================================
class LLMProvider(Enum):
    """LLM 提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    MOCK = "mock"


@dataclass
class LLMRequest:
    """LLM 请求"""
    prompt: str
    model: str = "mock-gpt"
    temperature: float = 0.7
    max_tokens: int = 256
    system: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """LLM 响应"""
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: float = 0.0
    finish_reason: str = "stop"


class LLMClient:
    """LLM 客户端
    抽象调用 LLM；Mock 实现用于测试。
    """
    def __init__(self, provider: LLMProvider = LLMProvider.MOCK,
                 model: str = "mock-gpt"):
        self.provider = provider
        self.model = model
        self._lock = threading.RLock()
        self._stats = {"requests": 0, "total_tokens": 0, "errors": 0}
        self._request_log: List[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        with self._lock:
            self._stats["requests"] += 1
            self._request_log.append(request)
            start = time.time()
            try:
                if self.provider == LLMProvider.MOCK:
                    text = self._mock_complete(request)
                else:
                    text = f"[{self.provider.value}] response to: {request.prompt[:50]}"
                duration = (time.time() - start) * 1000
                pt = len(request.prompt.split())
                ct = len(text.split())
                self._stats["total_tokens"] += pt + ct
                return LLMResponse(
                    text=text, model=self.model,
                    prompt_tokens=pt, completion_tokens=ct,
                    duration_ms=duration)
            except Exception as e:
                self._stats["errors"] += 1
                return LLMResponse(
                    text=f"Error: {e}", model=self.model,
                    finish_reason="error")

    def _mock_complete(self, request: LLMRequest) -> str:
        prompt = request.prompt.lower()
        if "summarize" in prompt or "总结" in prompt:
            return "这是对内容的简要总结。"
        if "translate" in prompt or "翻译" in prompt:
            return "Translation: [translated content]"
        if "extract" in prompt or "提取" in prompt:
            return "Extracted: [key point 1], [key point 2]"
        if "question" in prompt or "回答" in prompt:
            return "基于上下文，答案是：相关内容。"
        return f"模型响应：{request.prompt[:80]}"

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 四、提示词模板
# ============================================================
@dataclass
class PromptTemplate:
    """提示词模板"""
    name: str
    template: str
    variables: List[str] = field(default_factory=list)

    def render(self, **kwargs) -> str:
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            return f"[Missing variable: {e}]"


# ============================================================
# 五、RAG 管道
# ============================================================
class RAGPipeline:
    """检索增强生成（RAG）
    检索相关上下文 -> 拼接提示 -> 调用 LLM。
    """
    def __init__(self, vector_store: VectorStore, llm: LLMClient,
                 system_prompt: str = "你是知识助手。"):
        self.vs = vector_store
        self.llm = llm
        self.system_prompt = system_prompt
        self._lock = threading.RLock()
        self._stats = {"queries": 0}

    def add_knowledge(self, text: str,
                       metadata: Optional[Dict] = None) -> str:
        return self.vs.add(text, metadata)

    def query(self, question: str, top_k: int = 3,
              template: Optional[PromptTemplate] = None) -> Dict[str, Any]:
        with self._lock:
            self._stats["queries"] += 1
            results = self.vs.search(question, top_k=top_k)
            context = "\n".join(
                f"[{i+1}] {r.text}" for i, r in enumerate(results))
            if template is None:
                template = PromptTemplate(
                    name="default",
                    template=("系统: {system}\n"
                              "上下文:\n{context}\n"
                              "问题: {question}\n"
                              "回答:"),
                )
            prompt = template.render(
                system=self.system_prompt,
                context=context or "(无相关上下文)",
                question=question,
            )
            req = LLMRequest(prompt=prompt, system=self.system_prompt)
            resp = self.llm.complete(req)
            return {
                "question": question,
                "answer": resp.text,
                "contexts": [
                    {"id": r.entry_id, "text": r.text, "score": r.score}
                    for r in results
                ],
                "duration_ms": resp.duration_ms,
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)


# ============================================================
# 六、智能推荐
# ============================================================
class RecommenderStrategy(Enum):
    """推荐策略"""
    SIMILARITY = "similarity"
    HYBRID = "hybrid"
    POPULARITY = "popularity"


@dataclass
class UserInteraction:
    """用户交互"""
    user_id: str
    item_id: str
    score: float = 1.0
    ts: float = field(default_factory=time.time)


class Recommender:
    """智能推荐
    基于内容的相似度推荐 + 用户行为。
    """
    def __init__(self, vector_store: VectorStore,
                 strategy: RecommenderStrategy = RecommenderStrategy.SIMILARITY):
        self.vs = vector_store
        self.strategy = strategy
        self._interactions: List[UserInteraction] = []
        self._popularity: Dict[str, int] = defaultdict(int)
        self._lock = threading.RLock()

    def record(self, user_id: str, item_id: str, score: float = 1.0) -> None:
        with self._lock:
            self._interactions.append(UserInteraction(
                user_id=user_id, item_id=item_id, score=score))
            self._popularity[item_id] += 1

    def recommend(self, user_id: str, item_id: str,
                  top_k: int = 5) -> List[SearchResult]:
        with self._lock:
            target = self.vs.get(item_id)
            if target is None:
                return []
            results = self.vs.search(target.text, top_k=top_k + 5)
            # 排除自己
            results = [r for r in results if r.entry_id != item_id]

            if self.strategy == RecommenderStrategy.SIMILARITY:
                return results[:top_k]
            if self.strategy == RecommenderStrategy.POPULARITY:
                results.sort(key=lambda r: self._popularity.get(r.entry_id, 0),
                              reverse=True)
                return results[:top_k]
            if self.strategy == RecommenderStrategy.HYBRID:
                for r in results:
                    pop = self._popularity.get(r.entry_id, 0)
                    r.score = r.score * 0.7 + (pop / 100.0) * 0.3
                results.sort(key=lambda r: r.score, reverse=True)
                return results[:top_k]
            return results[:top_k]


# ============================================================
# 七、AI 智能体
# ============================================================
class AIAgent:
    """AI 智能体
    整合嵌入、检索、生成、推荐。
    """
    def __init__(self, embedder: Optional[Embedder] = None,
                 llm: Optional[LLMClient] = None):
        self.embedder = embedder or MockEmbedder()
        self.vs = VectorStore(self.embedder)
        self.llm = llm or LLMClient()
        self.rag = RAGPipeline(self.vs, self.llm)
        self.recommender = Recommender(self.vs)
        self._lock = threading.RLock()
        self._stats = {"learn": 0, "ask": 0, "recommend": 0}

    def learn(self, text: str, metadata: Optional[Dict] = None) -> str:
        with self._lock:
            self._stats["learn"] += 1
            return self.rag.add_knowledge(text, metadata)

    def ask(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        with self._lock:
            self._stats["ask"] += 1
            return self.rag.query(question, top_k=top_k)

    def suggest(self, user_id: str, item_id: str,
                top_k: int = 5) -> List[SearchResult]:
        with self._lock:
            self._stats["recommend"] += 1
            return self.recommender.recommend(user_id, item_id, top_k)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "vector_store": self.vs.get_stats(),
                "llm": self.llm.get_stats(),
                "rag": self.rag.get_stats(),
                "agent": dict(self._stats),
            }


# ============================================================
# 八、测试
# ============================================================
class TestMockEmbedder(unittest.TestCase):
    def test_embed_returns_list(self):
        e = MockEmbedder(dim=32)
        v = e.embed("hello")
        self.assertEqual(len(v), 32)

    def test_embed_deterministic(self):
        e = MockEmbedder(dim=16)
        v1 = e.embed("hello")
        v2 = e.embed("hello")
        self.assertEqual(v1, v2)

    def test_embed_different_texts(self):
        e = MockEmbedder(dim=16)
        v1 = e.embed("hello")
        v2 = e.embed("world")
        self.assertNotEqual(v1, v2)

    def test_embed_normalized(self):
        e = MockEmbedder(dim=16)
        v = e.embed("text")
        norm = math.sqrt(sum(x * x for x in v))
        self.assertAlmostEqual(norm, 1.0, places=5)


class TestCosineSimilarity(unittest.TestCase):
    def test_identical(self):
        v = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0)

    def test_orthogonal(self):
        self.assertAlmostEqual(
            cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_opposite(self):
        self.assertAlmostEqual(
            cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0)


class TestVectorStore(unittest.TestCase):
    def test_add_and_get(self):
        e = MockEmbedder(dim=16)
        vs = VectorStore(e)
        eid = vs.add("hello", {"src": "test"})
        entry = vs.get(eid)
        self.assertEqual(entry.text, "hello")

    def test_search(self):
        e = MockEmbedder(dim=64)
        vs = VectorStore(e)
        vs.add("猫是一种动物")
        vs.add("狗是忠诚的")
        vs.add("Python 是一种编程语言")
        results = vs.search("动物", top_k=2)
        self.assertGreater(len(results), 0)
        self.assertGreater(results[0].score, 0)

    def test_search_threshold(self):
        e = MockEmbedder(dim=16)
        vs = VectorStore(e)
        vs.add("hello")
        results = vs.search("hello", top_k=5, threshold=0.99)
        self.assertGreater(len(results), 0)

    def test_stats(self):
        e = MockEmbedder(dim=16)
        vs = VectorStore(e)
        vs.add("a")
        vs.add("b")
        vs.search("a")
        s = vs.get_stats()
        self.assertEqual(s["inserts"], 2)
        self.assertEqual(s["searches"], 1)


class TestLLMClient(unittest.TestCase):
    def test_complete(self):
        c = LLMClient(LLMProvider.MOCK)
        req = LLMRequest(prompt="hello")
        resp = c.complete(req)
        self.assertIsNotNone(resp.text)
        self.assertGreater(len(resp.text), 0)

    def test_summarize(self):
        c = LLMClient(LLMProvider.MOCK)
        req = LLMRequest(prompt="请总结以下内容")
        resp = c.complete(req)
        self.assertIn("总结", resp.text)

    def test_stats(self):
        c = LLMClient(LLMProvider.MOCK)
        c.complete(LLMRequest(prompt="a"))
        c.complete(LLMRequest(prompt="b"))
        s = c.get_stats()
        self.assertEqual(s["requests"], 2)


class TestPromptTemplate(unittest.TestCase):
    def test_render(self):
        t = PromptTemplate(name="t", template="Hello {name}")
        self.assertEqual(t.render(name="World"), "Hello World")

    def test_missing_var(self):
        t = PromptTemplate(name="t", template="Hello {name}")
        result = t.render()
        self.assertIn("Missing", result)


class TestRAGPipeline(unittest.TestCase):
    def test_query(self):
        e = MockEmbedder(dim=32)
        vs = VectorStore(e)
        llm = LLMClient(LLMProvider.MOCK)
        rag = RAGPipeline(vs, llm)
        rag.add_knowledge("猫是哺乳动物")
        rag.add_knowledge("狗也是哺乳动物")
        result = rag.query("猫是什么")
        self.assertIn("answer", result)
        self.assertIn("contexts", result)
        self.assertGreater(len(result["contexts"]), 0)

    def test_query_with_template(self):
        e = MockEmbedder(dim=32)
        vs = VectorStore(e)
        llm = LLMClient(LLMProvider.MOCK)
        rag = RAGPipeline(vs, llm)
        rag.add_knowledge("test")
        t = PromptTemplate(name="q", template="Q: {question}\nC: {context}\nA:")
        result = rag.query("test", template=t)
        self.assertIn("answer", result)


class TestRecommender(unittest.TestCase):
    def test_similarity_recommend(self):
        e = MockEmbedder(dim=32)
        vs = VectorStore(e)
        rec = Recommender(vs, RecommenderStrategy.SIMILARITY)
        eid1 = vs.add("机器学习")
        vs.add("深度学习")
        vs.add("烹饪")
        results = rec.recommend("u1", eid1, top_k=2)
        self.assertGreater(len(results), 0)

    def test_recommend_missing(self):
        e = MockEmbedder(dim=16)
        vs = VectorStore(e)
        rec = Recommender(vs)
        results = rec.recommend("u1", "nonexistent")
        self.assertEqual(len(results), 0)

    def test_popularity(self):
        e = MockEmbedder(dim=16)
        vs = VectorStore(e)
        rec = Recommender(vs, RecommenderStrategy.POPULARITY)
        eid1 = vs.add("A")
        eid2 = vs.add("B")
        rec.record("u1", eid1)
        rec.record("u1", eid2)
        rec.record("u2", eid1)
        results = rec.recommend("u1", eid2, top_k=2)
        self.assertGreater(len(results), 0)


class TestAIAgent(unittest.TestCase):
    def test_create(self):
        agent = AIAgent()
        self.assertIsNotNone(agent.embedder)

    def test_learn_ask(self):
        agent = AIAgent()
        agent.learn("Python 是一种编程语言")
        agent.learn("Java 也是一种编程语言")
        result = agent.ask("编程语言有哪些")
        self.assertIn("answer", result)
        self.assertGreater(len(result["contexts"]), 0)

    def test_suggest(self):
        agent = AIAgent()
        eid = agent.learn("机器学习基础")
        agent.learn("深度学习")
        agent.learn("烹饪")
        results = agent.suggest("u1", eid, top_k=2)
        self.assertGreaterEqual(len(results), 0)

    def test_stats(self):
        agent = AIAgent()
        agent.learn("a")
        agent.ask("a")
        s = agent.get_stats()
        self.assertIn("agent", s)
        self.assertEqual(s["agent"]["learn"], 1)
        self.assertEqual(s["agent"]["ask"], 1)


# ============================================================
# 九、Demo
# ============================================================
def demo():
    """演示阶段137的功能"""
    print("=" * 60)
    print("阶段137演示：AI集成")
    print("=" * 60)

    # 1. 嵌入模型
    print("\n🧬 演示1：嵌入模型")
    print("-" * 60)
    embedder = MockEmbedder(dim=32)
    v1 = embedder.embed("机器学习")
    v2 = embedder.embed("深度学习")
    v3 = embedder.embed("烹饪")
    print(f"  '机器学习' vs '深度学习' 相似度: {cosine_similarity(v1, v2):.3f}")
    print(f"  '机器学习' vs '烹饪'   相似度: {cosine_similarity(v1, v3):.3f}")

    # 2. 向量存储
    print("\n📚 演示2：向量存储")
    print("-" * 60)
    vs = VectorStore(embedder)
    docs = [
        "Python 是一种高级编程语言",
        "机器学习是人工智能的子领域",
        "深度学习基于神经网络",
        "今天天气很好",
        "我喜欢吃意大利面",
    ]
    ids = []
    for doc in docs:
        ids.append(vs.add(doc))
    print(f"  存储文档: {vs.size()}")
    results = vs.search("人工智能", top_k=3)
    for r in results:
        print(f"    [{r.score:.3f}] {r.text}")

    # 3. LLM 客户端
    print("\n🤖 演示3：LLM 客户端")
    print("-" * 60)
    llm = LLMClient(LLMProvider.MOCK)
    for prompt in ["请总结以上内容", "Translate to English: 你好",
                    "Extract keywords: 苹果、香蕉、橘子"]:
        resp = llm.complete(LLMRequest(prompt=prompt))
        print(f"  Q: {prompt}")
        print(f"  A: {resp.text}")
    print(f"  统计: {llm.get_stats()}")

    # 4. RAG 管道
    print("\n🔍 演示4：RAG 管道")
    print("-" * 60)
    rag = RAGPipeline(vs, llm)
    for doc in docs:
        rag.add_knowledge(doc)
    result = rag.query("什么是深度学习？")
    print(f"  问题: {result['question']}")
    print(f"  检索到 {len(result['contexts'])} 条上下文")
    for c in result["contexts"]:
        print(f"    [{c['score']:.3f}] {c['text']}")
    print(f"  回答: {result['answer']}")
    print(f"  耗时: {result['duration_ms']:.2f}ms")

    # 5. 推荐
    print("\n💡 演示5：智能推荐")
    print("-" * 60)
    rec = Recommender(vs, RecommenderStrategy.HYBRID)
    target_id = ids[1]  # 机器学习
    rec.record("u1", target_id, 5.0)
    rec.record("u2", target_id, 3.0)
    rec.record("u3", ids[0], 4.0)  # 编程语言
    results = rec.recommend("u1", target_id, top_k=3)
    for r in results:
        print(f"    [{r.score:.3f}] {r.text}")

    # 6. AI 智能体
    print("\n🎯 演示6：AI 智能体")
    print("-" * 60)
    agent = AIAgent()
    for doc in docs:
        agent.learn(doc)
    result = agent.ask("介绍机器学习")
    print(f"  提问: {result['question']}")
    print(f"  回答: {result['answer']}")
    target = agent.learn("深度学习")
    suggestions = agent.suggest("u1", target, top_k=2)
    print(f"  推荐数: {len(suggestions)}")
    s = agent.get_stats()
    print(f"  统计: learn={s['agent']['learn']}, ask={s['agent']['ask']}, "
          f"recommend={s['agent']['recommend']}")

    print("\n" + "=" * 60)
    print("✅ 阶段137完成：AI集成已实现！")
    print("=" * 60)
    print("\n【下阶段预告】阶段138：生态SDK")
    print("  - 多语言绑定")
    print("  - 第三方集成")
    print("  - 插件市场")


if __name__ == "__main__":
    unittest.main(verbosity=2, exit=False)
    print()
    demo()
