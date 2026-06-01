import os
import json
import shutil
import time
import threading
from typing import Dict, List, Optional, Set, Callable
from .node import Node
from .edge import Edge


class KnowledgeGraph:
    def __init__(self, save_path: str = "knowledge_graph.json"):
        self.save_path = save_path
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        # 边索引，加速查询
        self._outgoing_edges: Dict[str, List[Edge]] = {}  # source -> [edges]
        self._incoming_edges: Dict[str, List[Edge]] = {}  # target -> [edges]
        self._last_backup_path: Optional[str] = None
        self._last_save_time: float = 0.0
        self._load_count: int = 0
        self._save_count: int = 0
        
        # 变更追踪相关
        self._changes: List[dict] = []  # 变更历史记录
        self._changes_since_last_save: int = 0  # 自上次保存以来的变更数
        self._version: int = 0  # 当前版本号
        self._track_changes: bool = True  # 是否追踪变更
        self._max_changelog_size: int = 1000  # 变更历史最大记录数
        
        # 插件回调支持
        self._on_node_add_callbacks: List[Callable] = []
        self._on_edge_add_callbacks: List[Callable] = []
        
        self.load()

    def _get_backup_path(self) -> str:
        return f"{self.save_path}.backup"

    def _create_backup(self) -> bool:
        try:
            if os.path.exists(self.save_path):
                backup_path = self._get_backup_path()
                shutil.copy2(self.save_path, backup_path)
                self._last_backup_path = backup_path
                return True
        except Exception:
            pass
        return False

    def _restore_from_backup(self) -> bool:
        backup_path = self._get_backup_path()
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, self.save_path)
                return True
            except Exception:
                pass
        return False

    def _check_disk_space(self) -> bool:
        try:
            statvfs = os.statvfs(os.path.dirname(self.save_path) if os.path.dirname(self.save_path) else '.')
            free_bytes = statvfs.f_frsize * statvfs.f_bavail
            return free_bytes > 1024 * 1024  # 需要至少1MB空闲
        except Exception:
            return True  # 如果无法检测，默认继续

    def _record_change(self, change_type: str, data: dict) -> None:
        """
        记录变更
        
        Args:
            change_type: 变更类型（"node_add", "node_delete", "node_update",
                                    "edge_add", "edge_delete", "edge_update")
            data: 变更数据
        """
        if not self._track_changes:
            return
        
        change = {
            "timestamp": time.time(),
            "type": change_type,
            "data": data,
            "version": self._version
        }
        
        self._changes.append(change)
        self._changes_since_last_save += 1
        self._version += 1
        
        # 限制变更历史大小
        if len(self._changes) > self._max_changelog_size:
            self._changes = self._changes[-self._max_changelog_size:]
    
    def _rebuild_edge_indexes(self) -> None:
        """
        重建边索引（加载或修改边后调用）
        """
        self._outgoing_edges.clear()
        self._incoming_edges.clear()
        for edge in self.edges:
            if edge.source not in self._outgoing_edges:
                self._outgoing_edges[edge.source] = []
            self._outgoing_edges[edge.source].append(edge)
            
            if edge.target not in self._incoming_edges:
                self._incoming_edges[edge.target] = []
            self._incoming_edges[edge.target].append(edge)

    def add_node(self, name: str, attributes: Optional[dict] = None) -> Node:
        is_new_node = name not in self.nodes
        if is_new_node:
            self.nodes[name] = Node(name=name, attributes=attributes)
            self._record_change("node_add", {"node_name": name, "attributes": attributes})
            # 触发节点添加回调
            for callback in self._on_node_add_callbacks:
                try:
                    callback(name, attributes or {})
                except Exception:
                    pass
        else:
            # 记录节点更新
            self._record_change("node_update", {"node_name": name, "attributes": attributes})
        return self.nodes[name]
    
    def register_on_node_add(self, callback: Callable) -> None:
        """
        注册节点添加回调
        
        Args:
            callback: 回调函数，签名为 callback(node_name, attributes)
        """
        self._on_node_add_callbacks.append(callback)
    
    def register_on_edge_add(self, callback: Callable) -> None:
        """
        注册边添加回调
        
        Args:
            callback: 回调函数，签名为 callback(source, target, relation, weight)
        """
        self._on_edge_add_callbacks.append(callback)
    
    def unregister_on_node_add(self, callback: Callable) -> None:
        """
        注销节点添加回调
        """
        if callback in self._on_node_add_callbacks:
            self._on_node_add_callbacks.remove(callback)
    
    def unregister_on_edge_add(self, callback: Callable) -> None:
        """
        注销边添加回调
        """
        if callback in self._on_edge_add_callbacks:
            self._on_edge_add_callbacks.remove(callback)

    def get_node(self, name: str) -> Optional[Node]:
        return self.nodes.get(name)

    def has_node(self, name: str) -> bool:
        return name in self.nodes

    def delete_node(self, name: str) -> bool:
        if name not in self.nodes:
            return False
        # 先记录变更
        node_copy = self.nodes[name].to_dict()
        self._record_change("node_delete", {"node_name": name, "node_data": node_copy})
        del self.nodes[name]
        # 删除关联边并重建索引
        self.edges = [
            e for e in self.edges
            if e.source != name and e.target != name
        ]
        self._rebuild_edge_indexes()
        return True

    def update_node(self, name: str, valid_state: Optional[bool] = None,
                    attributes: Optional[dict] = None) -> Optional[Node]:
        node = self.get_node(name)
        if node is None:
            return None
        # 记录变更
        update_data = {}
        if valid_state is not None:
            update_data["valid_state"] = valid_state
        if attributes is not None:
            update_data["attributes"] = attributes
        self._record_change("node_update", {"node_name": name, "update": update_data})
        
        if valid_state is not None:
            node.valid_state = valid_state
        if attributes is not None:
            node.attributes.update(attributes)
        return node

    def add_edge(self, source: str, target: str,
                relation_name: str, weight: float) -> Edge:
        self.add_node(source)
        self.add_node(target)
        
        existing_edge = self._find_existing_edge(source, target, relation_name)
        if existing_edge is not None:
            old_weight = existing_edge.weight
            existing_edge.weight = max(existing_edge.weight, weight)
            if old_weight != existing_edge.weight:
                self._record_change("edge_update", {
                    "source": source, "target": target,
                    "relation_name": relation_name,
                    "old_weight": old_weight,
                    "new_weight": existing_edge.weight
                })
            return existing_edge
        
        edge = Edge(source, target, relation_name, weight)
        self.edges.append(edge)
        self._record_change("edge_add", {
            "source": source, "target": target,
            "relation_name": relation_name, "weight": weight
        })
        
        # 触发边添加回调
        for callback in self._on_edge_add_callbacks:
            try:
                callback(source, target, relation_name, weight)
            except Exception:
                pass
        
        # 更新索引
        if source not in self._outgoing_edges:
            self._outgoing_edges[source] = []
        self._outgoing_edges[source].append(edge)
        
        if target not in self._incoming_edges:
            self._incoming_edges[target] = []
        self._incoming_edges[target].append(edge)
        
        return edge

    def _find_existing_edge(self, source: str, target: str, relation_name: str) -> Optional[Edge]:
        # 优先使用索引查找
        if source in self._outgoing_edges:
            for edge in self._outgoing_edges[source]:
                if edge.target == target and edge.relation_name == relation_name:
                    return edge
        return None

    def update_edge_weight(self, source: str, target: str, 
                          relation_name: str, delta: float) -> bool:
        edge = self._find_existing_edge(source, target, relation_name)
        if edge is not None:
            edge.weight = max(0.0, min(1.0, edge.weight + delta))
            return True
        return False

    def get_edges_from_node(self, node_name: str) -> List[Edge]:
        return self._outgoing_edges.get(node_name, []).copy()

    def get_edges_to_node(self, node_name: str) -> List[Edge]:
        return self._incoming_edges.get(node_name, []).copy()

    def get_all_edges_from(self, node_name: str, min_weight: float = 0.0) -> List[Edge]:
        return [
            e for e in self._outgoing_edges.get(node_name, [])
            if e.weight >= min_weight
        ]

    def delete_edge(self, source: str, target: str, relation_name: str) -> bool:
        # 查找要删除的边以记录变更
        edge_to_delete = None
        for edge in self.edges:
            if edge.source == source and edge.target == target and edge.relation_name == relation_name:
                edge_to_delete = edge
                break
        
        original_count = len(self.edges)
        
        # 从边列表中删除
        self.edges = [
            e for e in self.edges
            if not (e.source == source and e.target == target
                   and e.relation_name == relation_name)
        ]
        
        # 重建索引（简化处理）
        if len(self.edges) < original_count:
            # 记录变更
            if edge_to_delete is not None:
                self._record_change("edge_delete", {
                    "source": source, "target": target,
                    "relation_name": relation_name,
                    "edge_data": edge_to_delete.to_dict()
                })
            self._rebuild_edge_indexes()
            return True
        
        return False

    def save(self) -> None:
        if not self._check_disk_space():
            raise RuntimeError("Insufficient disk space")
        
        self._create_backup()
        
        data = {
            "version": "1.0.0",
            "graph_version": self._version,
            "timestamp": time.time(),
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "metadata": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges)
            }
        }
        
        temp_path = f"{self.save_path}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # 验证临时文件是否有效，验证失败则抛出异常
            if not self._validate_file_integrity(temp_path):
                raise RuntimeError("Saved file failed integrity validation")
            
            if os.path.exists(self.save_path):
                os.replace(temp_path, self.save_path)
            else:
                os.rename(temp_path, self.save_path)
            
            self._last_save_time = time.time()
            self._save_count += 1
            # 保存成功后，重置未保存的变更计数
            self._changes_since_last_save = 0
            
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            raise

    def _validate_file_integrity(self, file_path: str) -> bool:
        """
        验证文件完整性
        """
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 验证必要的字段
            required_fields = ["version", "timestamp", "nodes", "edges", "metadata"]
            for field in required_fields:
                if field not in data:
                    return False
            
            # 验证节点和边数量匹配
            if len(data["nodes"]) != data["metadata"]["node_count"]:
                return False
            if len(data["edges"]) != data["metadata"]["edge_count"]:
                return False
            
            return True
        except Exception:
            return False

    def load(self) -> None:
        self._load_count += 1
        
        if not os.path.exists(self.save_path):
            self.save()
            return
        
        try:
            if not self._validate_file_integrity(self.save_path):
                raise RuntimeError("Invalid knowledge graph file")
            
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.nodes = {
                n["name"]: Node.from_dict(n)
                for n in data.get("nodes", [])
            }
            self.edges = [
                Edge.from_dict(e)
                for e in data.get("edges", [])
            ]
            # 重建索引
            self._rebuild_edge_indexes()
            # 恢复保存的版本号
            self._version = data.get("graph_version", 0)
            self._changes_since_last_save = 0
        except (json.JSONDecodeError, KeyError, RuntimeError):
            if self._restore_from_backup():
                try:
                    self.load()
                    return
                except Exception:
                    pass
            self.nodes = {}
            self.edges = []
            self._rebuild_edge_indexes()
            self.save()
        except Exception:
            if self._restore_from_backup():
                try:
                    self.load()
                    return
                except Exception:
                    pass
            self.nodes = {}
            self.edges = []
            self._rebuild_edge_indexes()
            self.save()

    def get_node_count(self) -> int:
        return len(self.nodes)

    def get_edge_count(self) -> int:
        return len(self.edges)

    def clear(self) -> None:
        self.nodes = {}
        self.edges = []
        self._rebuild_edge_indexes()

    def trim_invalid_knowledge(self, weight_threshold: float = 0.1, 
                              max_edges: Optional[int] = None) -> int:
        original_count = len(self.edges)
        self.edges = [
            edge for edge in self.edges
            if edge.weight > weight_threshold
        ]
        
        if max_edges is not None and len(self.edges) > max_edges:
            self.edges = sorted(self.edges, key=lambda e: e.weight, reverse=True)[:max_edges]
        
        removed = original_count - len(self.edges)
        self._rebuild_edge_indexes()
        self.save()
        return removed

    def find_highest_value_nodes(self, min_weight: float = 0.6, limit: int = 10) -> List[str]:
        node_values: Dict[str, float] = {}
        
        for edge in self.edges:
            if edge.weight > min_weight:
                if edge.source not in node_values:
                    node_values[edge.source] = 0
                node_values[edge.source] += edge.weight
                
                if edge.target not in node_values:
                    node_values[edge.target] = 0
                node_values[edge.target] += edge.weight
        
        sorted_nodes = sorted(node_values.items(), key=lambda x: x[1], reverse=True)
        return [node for node, value in sorted_nodes[:limit]]

    def _traverse_edges(self, start_node: str, depth: int, 
                      visited: Set[str], min_weight: float) -> List[str]:
        if depth == 0 or start_node in visited:
            return []
        
        visited.add(start_node)
        result = []
        
        for edge in self.edges:
            if edge.source == start_node and edge.weight > min_weight:
                result.append(f"知识推演任务:{edge.target}")
                result.extend(self._traverse_edges(edge.target, depth - 1, visited, min_weight))
        
        return result

    def derive_new_tasks(self, node_name: str, min_weight: float = 0.2, 
                        depth: int = 2) -> List[str]:
        if depth <= 0:
            depth = 1
        
        visited: Set[str] = set()
        new_tasks = self._traverse_edges(node_name, depth, visited, min_weight)
        
        return list(set(new_tasks))

    def get_stats(self) -> Dict[str, int]:
        """
        获取知识图谱统计信息
        """
        return {
            "node_count": self.get_node_count(),
            "edge_count": self.get_edge_count(),
            "save_count": self._save_count,
            "load_count": self._load_count,
            "last_save_time": self._last_save_time
        }
    
    # ==================== 扩展接口 ====================
    def inject_external_knowledge(self, node_name: str, edges: List[tuple]) -> None:
        """
        注入外部知识
        
        Args:
            node_name: 源节点名称
            edges: 边列表，格式为 [(target_node, relation_name, weight), ...]
        """
        self.add_node(node_name)
        for target, relation, weight in edges:
            self.add_edge(node_name, target, relation, weight)
    
    def find_related_nodes(self, node_name: str, depth: int = 2, min_weight: float = 0.1) -> Set[str]:
        """
        查找相关节点（BFS遍历）
        
        Args:
            node_name: 起始节点
            depth: 遍历深度
            min_weight: 最小权重阈值
        """
        visited = set([node_name])
        current_level = [node_name]
        
        for _ in range(depth):
            next_level = []
            for node in current_level:
                for edge in self.get_all_edges_from(node, min_weight):
                    if edge.target not in visited:
                        visited.add(edge.target)
                        next_level.append(edge.target)
            current_level = next_level
        
        return visited - {node_name}

    def compute_similarity(self, node_name1: str, node_name2: str) -> float:
        """
        计算两个节点之间的相似度
        
        使用基于共享邻居节点和边权重的算法
        """
        # 检查节点是否存在
        if node_name1 not in self.nodes or node_name2 not in self.nodes:
            return 0.0
        
        # 如果是同一个节点，相似度为 1
        if node_name1 == node_name2:
            return 1.0
        
        # 获取两个节点的邻居
        neighbors1 = set()
        neighbors2 = set()
        
        # 获取 node1 的所有邻居
        for edge in self._outgoing_edges.get(node_name1, []):
            neighbors1.add(edge.target)
        for edge in self._incoming_edges.get(node_name1, []):
            neighbors1.add(edge.source)
        
        # 获取 node2 的所有邻居
        for edge in self._outgoing_edges.get(node_name2, []):
            neighbors2.add(edge.target)
        for edge in self._incoming_edges.get(node_name2, []):
            neighbors2.add(edge.source)
        
        # 计算共享邻居
        shared_neighbors = neighbors1 & neighbors2
        
        # 如果没有共享邻居，相似度为 0
        if not shared_neighbors:
            return 0.0
        
        # 计算 Jaccard 相似度
        union_neighbors = neighbors1 | neighbors2
        jaccard = len(shared_neighbors) / len(union_neighbors) if union_neighbors else 0.0
        
        # 基于边权重的加权相似度
        weight_score = 0.0
        total_weight = 0.0
        
        # 检查 node1 和 node2 之间是否有直接边
        for edge in self._outgoing_edges.get(node_name1, []):
            if edge.target == node_name2:
                weight_score += edge.weight
                total_weight += 1.0
        
        for edge in self._incoming_edges.get(node_name1, []):
            if edge.source == node_name2:
                weight_score += edge.weight
                total_weight += 1.0
        
        direct_similarity = weight_score / total_weight if total_weight > 0 else 0.0
        
        # 综合相似度：结合 Jaccard 和直接边权重
        return 0.7 * jaccard + 0.3 * direct_similarity

    def find_similar_nodes(self, node_name: str, top_k: int = 5) -> List[tuple]:
        """
        找到与给定节点最相似的节点
        
        返回格式：[(node_name, similarity_score), ...]
        """
        if node_name not in self.nodes:
            return []
        
        # 计算与所有其他节点的相似度
        similarities = []
        for other_node in self.nodes.keys():
            if other_node != node_name:
                sim = self.compute_similarity(node_name, other_node)
                if sim > 0:
                    similarities.append((other_node, sim))
        
        # 按相似度降序排序，取前 top_k 个
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def compute_node_importance(self, node_name: str) -> float:
        """
        计算节点的重要性
        
        基于连接数和边权重的综合评分
        """
        if node_name not in self.nodes:
            return 0.0
        
        importance = 0.0
        
        # 1. 基于出边的权重
        for edge in self._outgoing_edges.get(node_name, []):
            importance += edge.weight
        
        # 2. 基于入边的权重
        for edge in self._incoming_edges.get(node_name, []):
            importance += edge.weight
        
        # 3. 基于连接数的基础重要性
        out_edges_count = len(self._outgoing_edges.get(node_name, []))
        in_edges_count = len(self._incoming_edges.get(node_name, []))
        connection_importance = (out_edges_count + in_edges_count) * 0.1
        
        importance += connection_importance
        
        return importance

    def get_most_important_nodes(self, top_k: int = 5) -> List[tuple]:
        """
        获取最重要的节点
        
        返回格式：[(node_name, importance_score), ...]
        """
        if not self.nodes:
            return []
        
        # 计算所有节点的重要性
        importance_scores = []
        for node_name in self.nodes.keys():
            score = self.compute_node_importance(node_name)
            importance_scores.append((node_name, score))
        
        # 按重要性降序排序，取前 top_k 个
        importance_scores.sort(key=lambda x: x[1], reverse=True)
        return importance_scores[:top_k]

    def find_paths(self, source: str, target: str, max_depth: int = 3) -> List[List[str]]:
        """
        找到从源节点到目标节点的所有路径
        
        使用 BFS 算法，限制最大深度
        """
        if source not in self.nodes or target not in self.nodes:
            return []
        
        # 使用 BFS 查找所有路径
        from collections import deque
        
        all_paths = []
        queue = deque([[source]])
        
        while queue:
            path = queue.popleft()
            current_node = path[-1]
            
            # 如果达到目标节点，添加到结果
            if current_node == target:
                all_paths.append(path)
                continue
            
            # 超过最大深度，停止探索
            if len(path) > max_depth:
                continue
            
            # 探索所有邻居
            for edge in self._outgoing_edges.get(current_node, []):
                next_node = edge.target
                # 避免循环路径
                if next_node not in path:
                    new_path = list(path)
                    new_path.append(next_node)
                    queue.append(new_path)
        
        return all_paths

    def aggregate_path_weight(self, path: List[str]) -> float:
        """
        计算路径的聚合权重
        
        将路径上的边权重相乘作为路径权重
        """
        if len(path) < 2:
            return 0.0
        
        total_weight = 1.0
        for i in range(len(path) - 1):
            source = path[i]
            target = path[i + 1]
            
            # 找到对应的边
            edge_found = False
            for edge in self._outgoing_edges.get(source, []):
                if edge.target == target:
                    total_weight *= edge.weight
                    edge_found = True
                    break
            
            if not edge_found:
                # 如果找不到直接边，权重降为 0
                return 0.0
        
        return total_weight

    def get_changelog(self, limit: int = 100, since_version: int = 0) -> List[dict]:
        """
        获取变更历史记录
        
        Args:
            limit: 最多返回的记录数
            since_version: 只返回该版本号之后的变更
            
        Returns:
            变更历史记录列表
        """
        changes = []
        for change in self._changes:
            if change["version"] >= since_version:
                changes.append(change)
        # 按时间戳倒序，返回最新的变更
        return changes[-limit:]
    
    def get_version(self) -> int:
        """
        获取当前版本号
        """
        return self._version
    
    def get_changes_since_last_save(self) -> int:
        """
        获取自上次保存以来的变更数量
        """
        return self._changes_since_last_save
    
    def reset_changelog(self) -> None:
        """
        重置变更历史
        """
        self._changes = []
        self._changes_since_last_save = 0
    
    def has_changes(self) -> bool:
        """
        检查是否有未保存的变更
        """
        return self._changes_since_last_save > 0

    def __repr__(self) -> str:
        return f"KnowledgeGraph(nodes={len(self.nodes)}, edges={len(self.edges)})"


class ConcurrentKnowledgeGraph:
    """
    线程安全的 KnowledgeGraph 包装类
    
    使用互斥锁保护所有操作，确保线程安全。
    保持与 KnowledgeGraph 完全相同的 API。
    """
    
    def __init__(self, save_path: str = "knowledge_graph.json"):
        self._graph = KnowledgeGraph(save_path)
        self._lock = threading.Lock()
    
    def _get_backup_path(self) -> str:
        with self._lock:
            return self._graph._get_backup_path()
    
    def _create_backup(self) -> bool:
        with self._lock:
            return self._graph._create_backup()
    
    def _restore_from_backup(self) -> bool:
        with self._lock:
            return self._graph._restore_from_backup()
    
    def _check_disk_space(self) -> bool:
        with self._lock:
            return self._graph._check_disk_space()
    
    def _rebuild_edge_indexes(self) -> None:
        with self._lock:
            self._graph._rebuild_edge_indexes()
    
    def add_node(self, name: str, attributes: Optional[dict] = None) -> Node:
        with self._lock:
            return self._graph.add_node(name, attributes)
    
    def get_node(self, name: str) -> Optional[Node]:
        with self._lock:
            return self._graph.get_node(name)
    
    def has_node(self, name: str) -> bool:
        with self._lock:
            return self._graph.has_node(name)
    
    def delete_node(self, name: str) -> bool:
        with self._lock:
            return self._graph.delete_node(name)
    
    def update_node(self, name: str, valid_state: Optional[bool] = None,
                   attributes: Optional[dict] = None) -> Optional[Node]:
        with self._lock:
            return self._graph.update_node(name, valid_state, attributes)
    
    def add_edge(self, source: str, target: str, relation: str, weight: float = 1.0) -> Edge:
        with self._lock:
            return self._graph.add_edge(source, target, relation, weight)
    
    def get_edges_from_node(self, node_name: str) -> List[Edge]:
        with self._lock:
            return self._graph.get_edges_from_node(node_name)
    
    def get_edges_to_node(self, node_name: str) -> List[Edge]:
        with self._lock:
            return self._graph.get_edges_to_node(node_name)
    
    def get_all_edges_from(self, node_name: str, min_weight: float = 0.0) -> List[Edge]:
        with self._lock:
            return self._graph.get_all_edges_from(node_name, min_weight)
    
    def get_node_count(self) -> int:
        with self._lock:
            return self._graph.get_node_count()
    
    def get_edge_count(self) -> int:
        with self._lock:
            return self._graph.get_edge_count()
    
    def clear(self) -> None:
        with self._lock:
            self._graph.clear()
    
    def save(self) -> None:
        with self._lock:
            self._graph.save()
    
    def load(self) -> None:
        with self._lock:
            self._graph.load()
    
    def _validate_file_integrity(self, file_path: str) -> bool:
        with self._lock:
            return self._graph._validate_file_integrity(file_path)
    
    def trim_invalid_knowledge(self) -> int:
        with self._lock:
            return self._graph.trim_invalid_knowledge()
    
    def perform_deep_reflection(self, iterations: int = 1) -> Dict[str, int]:
        with self._lock:
            return self._graph.perform_deep_reflection(iterations)
    
    def find_related_nodes(self, node_name: str, max_depth: int = 2) -> Set[str]:
        with self._lock:
            return self._graph.find_related_nodes(node_name, max_depth)
    
    def inject_external_knowledge(self, node_name: str, attributes: Optional[dict] = None,
                               relations: Optional[List[Dict]] = None) -> None:
        with self._lock:
            self._graph.inject_external_knowledge(node_name, attributes, relations)
    
    def compute_similarity(self, node_name1: str, node_name2: str) -> float:
        with self._lock:
            return self._graph.compute_similarity(node_name1, node_name2)
    
    def find_similar_nodes(self, node_name: str, top_k: int = 5) -> List[tuple]:
        with self._lock:
            return self._graph.find_similar_nodes(node_name, top_k)
    
    def compute_node_importance(self, node_name: str) -> float:
        with self._lock:
            return self._graph.compute_node_importance(node_name)
    
    def get_most_important_nodes(self, top_k: int = 5) -> List[tuple]:
        with self._lock:
            return self._graph.get_most_important_nodes(top_k)
    
    def find_paths(self, source: str, target: str, max_depth: int = 3) -> List[List[str]]:
        with self._lock:
            return self._graph.find_paths(source, target, max_depth)
    
    def aggregate_path_weight(self, path: List[str]) -> float:
        with self._lock:
            return self._graph.aggregate_path_weight(path)
    
    def get_changelog(self, limit: int = 100, since_version: int = 0) -> List[dict]:
        with self._lock:
            return self._graph.get_changelog(limit, since_version)
    
    def get_version(self) -> int:
        with self._lock:
            return self._graph.get_version()
    
    def get_changes_since_last_save(self) -> int:
        with self._lock:
            return self._graph.get_changes_since_last_save()
    
    def reset_changelog(self) -> None:
        with self._lock:
            self._graph.reset_changelog()
    
    def has_changes(self) -> bool:
        with self._lock:
            return self._graph.has_changes()
    
    def __repr__(self) -> str:
        with self._lock:
            return f"ConcurrentKnowledgeGraph(nodes={len(self._graph.nodes)}, edges={len(self._graph.edges)})"
    
    @property
    def nodes(self) -> Dict[str, Node]:
        with self._lock:
            return self._graph.nodes.copy()
    
    @property
    def edges(self) -> List[Edge]:
        with self._lock:
            return self._graph.edges.copy()