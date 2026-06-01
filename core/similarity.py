"""
相似度计算工具
提供多种相似度算法：余弦相似度、Jaccard相似度等
以及知识图谱统计和模式发现功能
"""

import math
from collections import defaultdict
from typing import List, Dict, Any, Optional, Set


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    计算两个向量的余弦相似度
    
    Args:
        vec1: 第一个向量
        vec2: 第二个向量
    
    Returns:
        余弦相似度值 (范围: [-1.0, 1.0])
    
    Raises:
        ValueError: 向量长度不一致或向量为空
    """
    if len(vec1) != len(vec2):
        raise ValueError("向量长度必须一致")
    
    if len(vec1) == 0:
        raise ValueError("向量不能为空")
    
    # 计算点积
    dot_product = 0.0
    norm1 = 0.0
    norm2 = 0.0
    
    for a, b in zip(vec1, vec2):
        dot_product += a * b
        norm1 += a * a
        norm2 += b * b
    
    norm1 = math.sqrt(norm1)
    norm2 = math.sqrt(norm2)
    
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


def jaccard_similarity(set1: set, set2: set) -> float:
    """
    计算两个集合的 Jaccard 相似度
    
    Args:
        set1: 第一个集合
        set2: 第二个集合
    
    Returns:
        Jaccard 相似度值 (范围: [0.0, 1.0])
    """
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    if union == 0:
        return 0.0
    
    return intersection / union


def node_to_vector(node, graph) -> List[float]:
    """
    将知识图谱中的节点转换为特征向量（简单实现）
    
    Args:
        node: 节点对象
        graph: 知识图谱对象
    
    Returns:
        节点的特征向量
    """
    # 简单的特征：节点名称的字符编码 + 边数量
    name_chars = [ord(c) / 255.0 for c in node.name[:10]]  # 最多取前10个字符
    
    # 补0到固定长度
    while len(name_chars) < 10:
        name_chars.append(0.0)
    
    # 加上边数量特征
    out_edges = graph.get_edges_from_node(node.name)
    in_edges = graph.get_edges_to_node(node.name)
    edge_feature = (len(out_edges) + len(in_edges)) / 100.0  # 归一化
    
    name_chars.append(edge_feature)
    return name_chars


def node_to_feature_set(node, graph) -> set:
    """
    将知识图谱中的节点转换为特征集合（用于Jaccard相似度）
    
    Args:
        node: 节点对象
        graph: 知识图谱对象
    
    Returns:
        节点的特征集合
    """
    features = set()
    
    # 节点名称的字符作为特征
    for c in node.name:
        features.add(f"char_{c}")
    
    # 节点名称的前缀和后缀作为特征
    if len(node.name) >= 2:
        features.add(f"prefix_{node.name[:2]}")
        features.add(f"suffix_{node.name[-2:]}")
    if len(node.name) >= 3:
        features.add(f"prefix3_{node.name[:3]}")
        features.add(f"suffix3_{node.name[-3:]}")
    
    # 邻居节点作为特征
    out_edges = graph.get_edges_from_node(node.name)
    for edge in out_edges:
        features.add(f"neighbor_{edge.target}")
        features.add(f"rel_{edge.relation_name}")
    
    in_edges = graph.get_edges_to_node(node.name)
    for edge in in_edges:
        features.add(f"inneighbor_{edge.source}")
    
    return features


def find_similar_nodes_by_cosine(graph, node_name: str, top_k: int = 5) -> List[tuple]:
    """
    使用余弦相似度查找相似节点
    
    Args:
        graph: 知识图谱对象
        node_name: 查询节点的名称
        top_k: 返回最相似的K个节点
    
    Returns:
        (节点名, 相似度) 列表，按相似度降序排列
    """
    target_node = graph.get_node(node_name)
    if not target_node:
        return []
    
    target_vec = node_to_vector(target_node, graph)
    
    scores = []
    for name, node in graph.nodes.items():
        if name == node_name:
            continue
        vec = node_to_vector(node, graph)
        try:
            sim = cosine_similarity(target_vec, vec)
            scores.append((name, sim))
        except ValueError:
            continue
    
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def find_similar_nodes_by_jaccard(graph, node_name: str, top_k: int = 5) -> List[tuple]:
    """
    使用Jaccard相似度查找相似节点
    
    Args:
        graph: 知识图谱对象
        node_name: 查询节点的名称
        top_k: 返回最相似的K个节点
    
    Returns:
        (节点名, 相似度) 列表，按相似度降序排列
    """
    target_node = graph.get_node(node_name)
    if not target_node:
        return []
    
    target_features = node_to_feature_set(target_node, graph)
    
    scores = []
    for name, node in graph.nodes.items():
        if name == node_name:
            continue
        features = node_to_feature_set(node, graph)
        sim = jaccard_similarity(target_features, features)
        scores.append((name, sim))
    
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def get_graph_statistics(graph) -> Dict[str, Any]:
    """
    获取知识图谱的基础统计信息
    
    Args:
        graph: 知识图谱对象
    
    Returns:
        包含统计信息的字典
    """
    # 节点统计
    node_count = len(graph.nodes)
    node_names = list(graph.nodes.keys())
    
    # 边统计
    edge_count = len(graph.edges)
    relation_types = set()
    relation_distribution = defaultdict(int)
    
    # 节点度统计
    out_degrees = defaultdict(int)
    in_degrees = defaultdict(int)
    total_degrees = defaultdict(int)
    
    for edge in graph.edges:
        relation_types.add(edge.relation_name)
        relation_distribution[edge.relation_name] += 1
        out_degrees[edge.source] += 1
        in_degrees[edge.target] += 1
        total_degrees[edge.source] += 1
        total_degrees[edge.target] += 1
    
    # 计算平均度
    avg_out_degree = sum(out_degrees.values()) / node_count if node_count > 0 else 0
    avg_in_degree = sum(in_degrees.values()) / node_count if node_count > 0 else 0
    
    # 找到高度节点
    top_out_degree = sorted(total_degrees.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "relation_types": list(relation_types),
        "relation_distribution": dict(relation_distribution),
        "avg_out_degree": avg_out_degree,
        "avg_in_degree": avg_in_degree,
        "top_nodes_by_degree": top_out_degree
    }


def get_node_statistics(graph, node_name: str) -> Optional[Dict[str, Any]]:
    """
    获取单个节点的详细统计信息
    
    Args:
        graph: 知识图谱对象
        node_name: 节点名称
    
    Returns:
        节点的统计信息，若节点不存在返回 None
    """
    node = graph.get_node(node_name)
    if not node:
        return None
    
    out_edges = graph.get_edges_from_node(node_name)
    in_edges = graph.get_edges_to_node(node_name)
    
    return {
        "node_name": node_name,
        "node_attributes": node.attributes,
        "out_edge_count": len(out_edges),
        "in_edge_count": len(in_edges),
        "total_edge_count": len(out_edges) + len(in_edges),
        "outgoing_relations": list(set(e.relation_name for e in out_edges)),
        "incoming_relations": list(set(e.relation_name for e in in_edges)),
        "neighbor_count": len(set(e.target for e in out_edges) | set(e.source for e in in_edges))
    }


def find_nodes_by_attribute(graph, attr_name: str, attr_value: Any = None) -> List[str]:
    """
    查找具有特定属性的节点
    
    Args:
        graph: 知识图谱对象
        attr_name: 属性名称
        attr_value: 属性值（可选，若不提供则查找所有具有该属性的节点）
    
    Returns:
        符合条件的节点名称列表
    """
    matching_nodes = []
    for node_name, node in graph.nodes.items():
        if attr_name in node.attributes:
            if attr_value is None or node.attributes[attr_name] == attr_value:
                matching_nodes.append(node_name)
    return matching_nodes


def find_relation_patterns(graph, min_occurrences: int = 2) -> Dict[str, List[Dict[str, Any]]]:
    """
    查找常见的关系模式
    
    Args:
        graph: 知识图谱对象
        min_occurrences: 模式出现的最小次数
    
    Returns:
        模式字典，键为模式类型，值为模式列表
    """
    # 1. 源节点属性 + 关系 + 目标节点属性 的模式
    attribute_relation_patterns = defaultdict(int)
    
    for edge in graph.edges:
        source_node = graph.get_node(edge.source)
        target_node = graph.get_node(edge.target)
        if source_node and target_node:
            # 记录源节点和目标节点的属性组合
            for source_attr_key, source_attr_val in source_node.attributes.items():
                for target_attr_key, target_attr_val in target_node.attributes.items():
                    pattern = (
                        f"source_attr:{source_attr_key}={source_attr_val}",
                        f"relation:{edge.relation_name}",
                        f"target_attr:{target_attr_key}={target_attr_val}"
                    )
                    attribute_relation_patterns[pattern] += 1
    
    # 2. 常见的关系序列（基于源节点的多个出边）
    relation_sequence_patterns = defaultdict(int)
    for node_name in graph.nodes:
        out_edges = graph.get_edges_from_node(node_name)
        if len(out_edges) >= 2:
            # 记录关系类型的排序序列（不考虑顺序）
            rel_types = sorted([e.relation_name for e in out_edges])
            pattern = tuple(rel_types)
            relation_sequence_patterns[pattern] += 1
    
    # 构建返回结果
    result = {
        "attribute_relation_patterns": [],
        "relation_sequence_patterns": []
    }
    
    # 筛选高频的属性关系模式
    for pattern, count in attribute_relation_patterns.items():
        if count >= min_occurrences:
            result["attribute_relation_patterns"].append({
                "pattern": pattern,
                "count": count
            })
    
    # 筛选高频的关系序列模式
    for pattern, count in relation_sequence_patterns.items():
        if count >= min_occurrences:
            result["relation_sequence_patterns"].append({
                "pattern": pattern,
                "count": count
            })
    
    # 按出现次数降序排序
    result["attribute_relation_patterns"].sort(key=lambda x: x["count"], reverse=True)
    result["relation_sequence_patterns"].sort(key=lambda x: x["count"], reverse=True)
    
    return result


def get_attribute_distribution(graph) -> Dict[str, Dict[str, int]]:
    """
    获取节点属性的分布统计
    
    Args:
        graph: 知识图谱对象
    
    Returns:
        属性分布字典，结构为 {属性名: {属性值: 出现次数}}
    """
    distribution = defaultdict(lambda: defaultdict(int))
    for node in graph.nodes.values():
        for attr_key, attr_value in node.attributes.items():
            # 转换为字符串以支持作为字典键
            value_str = str(attr_value)
            distribution[attr_key][value_str] += 1
    
    # 转换为普通字典
    result = {}
    for attr_key, value_counts in distribution.items():
        result[attr_key] = dict(value_counts)
    
    return result


# ==================== 基于规则的推理引擎 ====================

class Rule:
    """规则定义类"""
    
    def __init__(self, name: str, conditions: List[Dict], actions: List[Dict], confidence: float = 0.9):
        """
        初始化规则
        
        Args:
            name: 规则名称
            conditions: 规则条件列表
            actions: 规则动作列表
            confidence: 规则置信度
        """
        self.name = name
        self.conditions = conditions
        self.actions = actions
        self.confidence = confidence
    
    def __repr__(self):
        return f"Rule(name={self.name}, confidence={self.confidence})"


class InferenceEngine:
    """推理引擎类"""
    
    def __init__(self):
        self.rules: List[Rule] = []
    
    def add_rule(self, rule: Rule):
        """添加规则到引擎"""
        self.rules.append(rule)
    
    def _match_condition(self, graph, node_name: str, condition: Dict) -> bool:
        """
        检查节点是否满足单个条件
        
        Args:
            graph: 知识图谱
            node_name: 节点名称
            condition: 条件字典
            
        Returns:
            是否满足条件
        """
        condition_type = condition.get("type")
        
        if condition_type == "has_attribute":
            # 检查节点是否有特定属性
            attr_name = condition.get("attribute")
            attr_value = condition.get("value")
            node = graph.get_node(node_name)
            if not node:
                return False
            if attr_value is None:
                return attr_name in node.attributes
            return node.attributes.get(attr_name) == attr_value
        
        elif condition_type == "has_relation":
            # 检查节点是否有特定关系
            relation = condition.get("relation")
            target = condition.get("target")
            out_edges = graph.get_edges_from_node(node_name)
            for edge in out_edges:
                if edge.relation_name == relation:
                    if target is None or edge.target == target:
                        return True
            return False
        
        elif condition_type == "has_in_relation":
            # 检查节点是否有特定入边关系
            relation = condition.get("relation")
            source = condition.get("source")
            in_edges = graph.get_edges_to_node(node_name)
            for edge in in_edges:
                if edge.relation_name == relation:
                    if source is None or edge.source == source:
                        return True
            return False
        
        return False
    
    def _execute_action(self, graph, node_name: str, action: Dict) -> Optional[Dict]:
        """
        执行单个动作
        
        Args:
            graph: 知识图谱
            node_name: 节点名称
            action: 动作字典
            
        Returns:
            执行结果信息
        """
        action_type = action.get("type")
        result = {"action": action_type, "node": node_name}
        
        if action_type == "set_attribute":
            # 设置节点属性
            attr_name = action.get("attribute")
            attr_value = action.get("value")
            node = graph.get_node(node_name)
            if node:
                node.attributes[attr_name] = attr_value
                result["status"] = "success"
                result["attribute"] = attr_name
                result["value"] = attr_value
            else:
                result["status"] = "failed"
                result["reason"] = "Node not found"
        
        elif action_type == "add_relation":
            # 添加关系
            target = action.get("target")
            relation = action.get("relation")
            weight = action.get("weight", 0.5)
            if target and relation:
                graph.add_edge(node_name, target, relation, weight)
                result["status"] = "success"
                result["target"] = target
                result["relation"] = relation
            else:
                result["status"] = "failed"
                result["reason"] = "Missing target or relation"
        
        return result
    
    def infer(self, graph, node_name: str) -> List[Dict]:
        """
        对单个节点进行推理
        
        Args:
            graph: 知识图谱
            node_name: 节点名称
            
        Returns:
            推理结果列表
        """
        results = []
        
        for rule in self.rules:
            # 检查所有条件是否都满足
            all_conditions_met = True
            for condition in rule.conditions:
                if not self._match_condition(graph, node_name, condition):
                    all_conditions_met = False
                    break
            
            if all_conditions_met:
                # 执行动作
                rule_result = {
                    "rule": rule.name,
                    "confidence": rule.confidence,
                    "actions": []
                }
                for action in rule.actions:
                    action_result = self._execute_action(graph, node_name, action)
                    if action_result:
                        rule_result["actions"].append(action_result)
                results.append(rule_result)
        
        return results
    
    def infer_all(self, graph) -> Dict[str, List[Dict]]:
        """
        对图中所有节点进行推理
        
        Args:
            graph: 知识图谱
            
        Returns:
            推理结果字典，键为节点名
        """
        all_results = {}
        for node_name in graph.nodes:
            node_results = self.infer(graph, node_name)
            if node_results:
                all_results[node_name] = node_results
        return all_results


# 快捷函数，创建常用规则
def create_attribute_rule(name: str, condition_attr: str, condition_value: Any, 
                        action_attr: str, action_value: Any, confidence: float = 0.9) -> Rule:
    """
    创建一个基于属性的推理规则
    
    Args:
        name: 规则名称
        condition_attr: 条件属性名
        condition_value: 条件属性值
        action_attr: 动作属性名
        action_value: 动作属性值
        confidence: 规则置信度
        
    Returns:
        创建的规则对象
    """
    conditions = [
        {"type": "has_attribute", "attribute": condition_attr, "value": condition_value}
    ]
    actions = [
        {"type": "set_attribute", "attribute": action_attr, "value": action_value}
    ]
    return Rule(name, conditions, actions, confidence)


def create_relation_rule(name: str, source_relation: str, target_attr: str, 
                        new_relation: str, confidence: float = 0.9) -> Rule:
    """
    创建一个基于关系传递的推理规则
    
    Args:
        name: 规则名称
        source_relation: 源关系
        target_attr: 目标属性
        new_relation: 新关系
        confidence: 规则置信度
        
    Returns:
        创建的规则对象
    """
    conditions = [
        {"type": "has_relation", "relation": source_relation}
    ]
    actions = [
        {"type": "set_attribute", "attribute": target_attr, "value": True}
    ]
    return Rule(name, conditions, actions, confidence)


# ==================== 子图匹配功能 ====================

def find_subgraph_by_pattern(graph, pattern: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    在知识图谱中查找匹配特定模式的子图
    
    Args:
        graph: 知识图谱对象
        pattern: 子图模式字典，包含节点匹配规则和关系匹配规则
            {
                "nodes": [
                    {"name": "node1", "attributes": {"type": "person"}},
                    {"name": "node2", "attributes": {"type": "language"}}
                ],
                "edges": [
                    {"source": "node1", "target": "node2", "relation": "uses"}
                ]
            }
    
    Returns:
        匹配的子图列表，每个子图包含节点映射和匹配的边
    """
    # 提取模式中的节点和边
    pattern_nodes = pattern.get("nodes", [])
    pattern_edges = pattern.get("edges", [])
    
    # 快速返回：如果没有模式节点，返回空
    if not pattern_nodes:
        return []
    
    # 找到每个模式节点的候选节点
    node_candidates = {}
    for p_node in pattern_nodes:
        p_name = p_node.get("name")
        p_attrs = p_node.get("attributes", {})
        
        # 查找匹配的节点
        candidates = []
        for node_name, node in graph.nodes.items():
            # 检查属性是否匹配
            match = True
            for key, value in p_attrs.items():
                if key not in node.attributes or node.attributes[key] != value:
                    match = False
                    break
            if match:
                candidates.append(node_name)
        
        if not candidates:
            # 没有候选节点，无法匹配
            return []
        
        node_candidates[p_name] = candidates
    
    # 递归回溯寻找匹配的子图
    results = []
    node_mapping = {}  # 模式节点名 -> 实际节点名
    
    def backtrack(index: int):
        if index == len(pattern_nodes):
            # 检查边是否匹配
            if _check_edges_match(graph, node_mapping, pattern_edges):
                # 复制并保存匹配结果
                result = {
                    "node_mapping": node_mapping.copy(),
                    "matched_edges": _collect_matched_edges(graph, node_mapping, pattern_edges)
                }
                results.append(result)
            return
        
        p_node = pattern_nodes[index]
        p_name = p_node.get("name")
        
        for candidate in node_candidates[p_name]:
            # 确保一个实际节点只被映射一次
            if candidate in node_mapping.values():
                continue
            
            node_mapping[p_name] = candidate
            backtrack(index + 1)
            del node_mapping[p_name]
    
    backtrack(0)
    return results


def _check_edges_match(graph, node_mapping: Dict[str, str], pattern_edges: List[Dict[str, Any]]) -> bool:
    """
    检查边模式是否匹配
    
    Args:
        graph: 知识图谱
        node_mapping: 模式节点名到实际节点名的映射
        pattern_edges: 模式边列表
    
    Returns:
        是否全部匹配
    """
    for p_edge in pattern_edges:
        p_source = p_edge.get("source")
        p_target = p_edge.get("target")
        p_relation = p_edge.get("relation")
        
        if p_source not in node_mapping or p_target not in node_mapping:
            return False
        
        source = node_mapping[p_source]
        target = node_mapping[p_target]
        
        # 查找是否有这样的边
        found = False
        for edge in graph.edges:
            if edge.source == source and edge.target == target and edge.relation_name == p_relation:
                found = True
                break
        if not found:
            return False
    
    return True


def _collect_matched_edges(graph, node_mapping: Dict[str, str], pattern_edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    收集匹配的边
    
    Args:
        graph: 知识图谱
        node_mapping: 节点映射
        pattern_edges: 模式边列表
    
    Returns:
        匹配的边列表
    """
    matched_edges = []
    
    for p_edge in pattern_edges:
        p_source = p_edge.get("source")
        p_target = p_edge.get("target")
        p_relation = p_edge.get("relation")
        
        source = node_mapping[p_source]
        target = node_mapping[p_target]
        
        for edge in graph.edges:
            if edge.source == source and edge.target == target and edge.relation_name == p_relation:
                matched_edges.append({
                    "source": source,
                    "target": target,
                    "relation": edge.relation_name,
                    "weight": edge.weight
                })
                break
    
    return matched_edges


def find_nodes_by_pattern(graph, node_pattern: Dict[str, Any]) -> List[str]:
    """
    简化版：只查找匹配特定属性模式的节点
    
    Args:
        graph: 知识图谱
        node_pattern: 节点属性模式
    
    Returns:
        匹配的节点名列表
    """
    # 支持两种格式：直接是属性字典或包含 attributes 键
    attributes = node_pattern.get("attributes", node_pattern)
    
    pattern = {
        "nodes": [{"name": "target", "attributes": attributes}],
        "edges": []
    }
    
    results = find_subgraph_by_pattern(graph, pattern)
    return [result["node_mapping"]["target"] for result in results]


def find_neighbors_by_relation(graph, node_name: str, relation: str, direction: str = "outgoing", return_weights: bool = False) -> List:
    """
    查找具有特定关系的邻居节点
    
    Args:
        graph: 知识图谱
        node_name: 起始节点
        relation: 关系名称
        direction: "outgoing" 表示出边，"incoming" 表示入边，"both" 表示双向，或者用 True 表示 reverse=True
        return_weights: 是否返回权重，默认为 False
    
    Returns:
        如果 return_weights=False，返回节点名列表
        如果 return_weights=True，返回 (节点名, 权重) 的元组列表
    """
    # 向后兼容，支持 direction=True 表示反向查询
    reverse = False
    if isinstance(direction, bool):
        reverse = direction
        direction = "incoming" if reverse else "outgoing"
    
    neighbors = []
    
    if direction in ["outgoing", "both"]:
        for edge in graph.get_edges_from_node(node_name):
            if edge.relation_name == relation:
                if return_weights:
                    neighbors.append((edge.target, edge.weight))
                else:
                    neighbors.append(edge.target)
    
    if direction in ["incoming", "both"]:
        for edge in graph.get_edges_to_node(node_name):
            if edge.relation_name == relation:
                if return_weights:
                    neighbors.append((edge.source, edge.weight))
                else:
                    neighbors.append(edge.source)
    
    return neighbors
