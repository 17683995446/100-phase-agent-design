"""
自然语言处理接口模块

提供简单的文本分词、实体提取和文本相似度计算功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的实现开始。
"""

import re
import math
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import Counter


class SimpleTokenizer:
    """
    简单分词器
    
    基于空格和标点符号的分词实现。
    """
    
    # 中文标点符号
    PUNCTUATION = set("，。！？、；：""''（）【】《》")
    # 英文标点符号
    EN_PUNCTUATION = set(".,!?;:'\"()[]{}<>")
    
    @classmethod
    def tokenize(cls, text: str) -> List[str]:
        """
        分词
        
        Args:
            text: 输入文本
            
        Returns:
            分词结果列表
        """
        if not text:
            return []
        
        # 移除标点符号，替换为空格
        for p in cls.PUNCTUATION | cls.EN_PUNCTUATION:
            text = text.replace(p, " ")
        
        # 按空格分割并过滤空字符串
        tokens = [token.strip().lower() for token in text.split()]
        return [t for t in tokens if t]
    
    @classmethod
    def tokenize_with_positions(cls, text: str) -> List[Tuple[str, int]]:
        """
        带位置信息的分词
        
        Returns:
            [(token, position), ...]
        """
        tokens = cls.tokenize(text)
        return [(token, i) for i, token in enumerate(tokens)]


class EntityExtractor:
    """
    实体提取器
    
    从文本中提取可能的实体（基于知识图谱中的节点名）。
    """
    
    def __init__(self, knowledge_graph=None):
        """
        初始化实体提取器
        
        Args:
            knowledge_graph: 知识图谱实例，用于匹配已知实体
        """
        self.knowledge_graph = knowledge_graph
        self._entity_cache: Set[str] = set()
        self._update_cache()
    
    def _update_cache(self):
        """更新实体缓存"""
        if self.knowledge_graph:
            # 创建大小写不敏感的映射：小写名 -> 原始名
            self._entity_cache = {}
            for name in self.knowledge_graph.nodes.keys():
                self._entity_cache[name.lower()] = name
    
    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中提取实体
        
        Args:
            text: 输入文本
            
        Returns:
            实体列表，每个实体包含名称、类型和位置
        """
        self._update_cache()
        
        # 如果没有知识图谱，返回空列表
        if not self._entity_cache:
            return []
        
        entities = []
        tokens = SimpleTokenizer.tokenize(text)
        
        # 简单匹配：检查每个词是否在知识图谱中（大小写不敏感）
        for i, token in enumerate(tokens):
            # 精确匹配（大小写不敏感）
            if token in self._entity_cache:
                original_name = self._entity_cache[token]
                entities.append({
                    "name": original_name,
                    "type": "exact_match",
                    "position": i,
                    "confidence": 1.0
                })
            else:
                # 部分匹配（前缀匹配）
                for lower_name, original_name in self._entity_cache.items():
                    if token in lower_name or lower_name in token:
                        entities.append({
                            "name": original_name,
                            "type": "partial_match",
                            "position": i,
                            "confidence": 0.5
                        })
                        break
        
        # 去重，保留置信度最高的
        seen = {}
        for entity in entities:
            name = entity["name"]
            if name not in seen or entity["confidence"] > seen[name]["confidence"]:
                seen[name] = entity
        
        return list(seen.values())
    
    def extract_entities_by_pattern(self, text: str,
                                    patterns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        使用正则表达式模式提取实体
        
        Args:
            text: 输入文本
            patterns: 正则表达式模式列表，如果为 None 则使用默认模式
            
        Returns:
            提取的实体列表
        """
        if patterns is None:
            # 默认模式：匹配大写开头的单词（可能是专有名词）
            patterns = [r"[A-Z][a-zA-Z0-9_]+"]
        
        entities = []
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                entities.append({
                    "name": match.group(),
                    "type": "pattern_match",
                    "position": match.start(),
                    "confidence": 0.8
                })
        
        return entities


class TextSimilarity:
    """
    文本相似度计算
    """
    
    @staticmethod
    def jaccard_similarity(text1: str, text2: str) -> float:
        """
        基于 Jaccard 系数的文本相似度
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            相似度分数 (0.0 - 1.0)
        """
        tokens1 = set(SimpleTokenizer.tokenize(text1))
        tokens2 = set(SimpleTokenizer.tokenize(text2))
        
        if not tokens1 and not tokens2:
            return 1.0
        
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        
        return len(intersection) / len(union) if union else 0.0
    
    @staticmethod
    def cosine_similarity(text1: str, text2: str) -> float:
        """
        基于余弦相似度的文本相似度
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            相似度分数 (0.0 - 1.0)
        """
        tokens1 = SimpleTokenizer.tokenize(text1)
        tokens2 = SimpleTokenizer.tokenize(text2)
        
        if not tokens1 and not tokens2:
            return 1.0
        
        # 构建词频向量
        counter1 = Counter(tokens1)
        counter2 = Counter(tokens2)
        
        all_tokens = set(counter1.keys()) | set(counter2.keys())
        
        vec1 = [counter1.get(token, 0) for token in all_tokens]
        vec2 = [counter2.get(token, 0) for token in all_tokens]
        
        # 计算余弦相似度
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    @staticmethod
    def levenshtein_distance(text1: str, text2: str) -> int:
        """
        计算 Levenshtein 编辑距离
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            编辑距离
        """
        if len(text1) < len(text2):
            return TextSimilarity.levenshtein_distance(text2, text1)
        
        if len(text2) == 0:
            return len(text1)
        
        previous_row = range(len(text2) + 1)
        for i, c1 in enumerate(text1):
            current_row = [i + 1]
            for j, c2 in enumerate(text2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    @staticmethod
    def normalized_levenshtein(text1: str, text2: str) -> float:
        """
        归一化的 Levenshtein 相似度
        
        Returns:
            相似度分数 (0.0 - 1.0)
        """
        distance = TextSimilarity.levenshtein_distance(text1, text2)
        max_length = max(len(text1), len(text2))
        
        if max_length == 0:
            return 1.0
        
        return 1.0 - (distance / max_length)


class NLQueryConverter:
    """
    自然语言查询转换器
    
    将自然语言转换为知识图谱查询。
    """
    
    # 查询关键词映射
    QUERY_PATTERNS = {
        "find": ["查找", "找到", "搜索", "查询", "find", "search", "look for"],
        "relation": ["关系", "联系", "关联", "relation", "relationship", "connect"],
        "attribute": ["属性", "特征", "信息", "attribute", "property", "info"],
        "similar": ["相似", "类似", "像", "similar", "like", "alike"]
    }
    
    def __init__(self, knowledge_graph=None):
        """
        初始化查询转换器
        
        Args:
            knowledge_graph: 知识图谱实例
        """
        self.knowledge_graph = knowledge_graph
        self.extractor = EntityExtractor(knowledge_graph)
    
    def convert(self, query: str) -> Dict[str, Any]:
        """
        将自然语言查询转换为结构化查询
        
        Args:
            query: 自然语言查询
            
        Returns:
            结构化查询字典
        """
        query_lower = query.lower()
        tokens = SimpleTokenizer.tokenize(query)
        
        # 提取实体
        entities = self.extractor.extract_entities(query)
        
        # 识别查询类型
        query_type = self._identify_query_type(query_lower)
        
        # 构建结构化查询
        structured_query = {
            "type": query_type,
            "original": query,
            "entities": [e["name"] for e in entities],
            "tokens": tokens
        }
        
        # 根据查询类型添加特定参数
        if query_type == "find":
            structured_query["target"] = entities[0]["name"] if entities else None
        elif query_type == "relation":
            if len(entities) >= 2:
                structured_query["source"] = entities[0]["name"]
                structured_query["target"] = entities[1]["name"]
        elif query_type == "similar":
            structured_query["reference"] = entities[0]["name"] if entities else None
        
        return structured_query
    
    def _identify_query_type(self, query: str) -> str:
        """识别查询类型"""
        for query_type, keywords in self.QUERY_PATTERNS.items():
            for keyword in keywords:
                if keyword.lower() in query:
                    return query_type
        return "unknown"
    
    def execute_query(self, query: str) -> Dict[str, Any]:
        """
        执行自然语言查询
        
        Args:
            query: 自然语言查询
            
        Returns:
            查询结果
        """
        if not self.knowledge_graph:
            return {"error": "Knowledge graph not available"}
        
        structured = self.convert(query)
        query_type = structured["type"]
        
        if query_type == "find":
            target = structured.get("target")
            if target and target in self.knowledge_graph.nodes:
                node = self.knowledge_graph.get_node(target)
                return {
                    "query_type": "find",
                    "found": True,
                    "node": {"name": node.name, "attributes": node.attributes}
                }
            return {"query_type": "find", "found": False}
        
        elif query_type == "relation":
            source = structured.get("source")
            target = structured.get("target")
            
            if source and target:
                edges = [
                    edge for edge in self.knowledge_graph.edges
                    if edge.source == source and edge.target == target
                ]
                return {
                    "query_type": "relation",
                    "relations": [
                        {"relation": e.relation_name, "weight": e.weight}
                        for e in edges
                    ]
                }
            return {"query_type": "relation", "relations": []}
        
        elif query_type == "similar":
            reference = structured.get("reference")
            if reference:
                # 简单的相似度查找：基于共同邻居
                similar_nodes = self._find_similar_nodes(reference)
                return {
                    "query_type": "similar",
                    "reference": reference,
                    "similar_nodes": similar_nodes
                }
            return {"query_type": "similar", "similar_nodes": []}
        
        return {"query_type": "unknown", "message": "Query type not recognized"}
    
    def _find_similar_nodes(self, node_name: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """查找相似节点（基于共同邻居）"""
        if node_name not in self.knowledge_graph.nodes:
            return []
        
        # 获取节点的邻居
        node_neighbors = set()
        for edge in self.knowledge_graph.edges:
            if edge.source == node_name:
                node_neighbors.add(edge.target)
            elif edge.target == node_name:
                node_neighbors.add(edge.source)
        
        # 计算与其他节点的共同邻居数
        similarities = []
        for other_name in self.knowledge_graph.nodes:
            if other_name == node_name:
                continue
            
            other_neighbors = set()
            for edge in self.knowledge_graph.edges:
                if edge.source == other_name:
                    other_neighbors.add(edge.target)
                elif edge.target == other_name:
                    other_neighbors.add(edge.source)
            
            common = node_neighbors & other_neighbors
            if common:
                similarity = len(common) / (len(node_neighbors) | len(other_neighbors))
                similarities.append({
                    "node": other_name,
                    "similarity": similarity,
                    "common_neighbors": list(common)
                })
        
        # 排序并返回前 k 个
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        return similarities[:top_k]


def text_to_knowledge_graph(text: str, knowledge_graph) -> Dict[str, Any]:
    """
    将文本转换为知识图谱条目
    
    Args:
        text: 输入文本
        knowledge_graph: 知识图谱实例
        
    Returns:
        转换结果
    """
    extractor = EntityExtractor(knowledge_graph)
    entities = extractor.extract_entities(text)
    
    added_nodes = []
    for entity in entities:
        name = entity["name"]
        if not knowledge_graph.has_node(name):
            knowledge_graph.add_node(name, {"type": "extracted", "source": "nlp"})
            added_nodes.append(name)
    
    return {
        "text": text,
        "extracted_entities": [e["name"] for e in entities],
        "added_nodes": added_nodes
    }
