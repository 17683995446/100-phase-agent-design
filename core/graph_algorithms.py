import heapq
from typing import Dict, List, Optional, Set, Tuple
from collections import deque, defaultdict


class GraphAlgorithms:
    """
    图算法库

    为知识图谱提供常用图算法实现：
    - 最短路径（Dijkstra）
    - 社区发现（标签传播）
    - PageRank
    - 中心性分析
    """

    def __init__(self, knowledge_graph):
        self.kg = knowledge_graph

    def _get_weighted_adjacency(self, min_weight: float = 0.0) -> Dict[str, List[Tuple[str, float]]]:
        """
        构建带权邻接表

        返回: {node: [(neighbor, weight), ...]}
        """
        adj = defaultdict(list)
        for edge in self.kg.edges:
            if edge.weight >= min_weight:
                adj[edge.source].append((edge.target, edge.weight))
        return dict(adj)

    def dijkstra(self, start: str, end: Optional[str] = None,
                 min_weight: float = 0.0) -> Dict[str, float]:
        """
        Dijkstra 最短路径算法

        功能：计算从起点到所有其他节点（或指定终点）的最短路径
        原理：贪心策略，每次选择距离最小的节点进行扩展

        Args:
            start: 起始节点名
            end: 目标节点名（可选，指定则提前终止）
            min_weight: 最小边权重阈值，低于此值的边忽略

        Returns:
            {节点名: 最短距离, ...}
            距离定义为边权重的倒数之和（权重越大距离越短）
        """
        if start not in self.kg.nodes:
            return {}

        adj = self._get_weighted_adjacency(min_weight)
        distances: Dict[str, float] = {start: 0.0}
        pq = [(0.0, start)]
        visited: Set[str] = set()

        while pq:
            dist, current = heapq.heappop(pq)
            if current in visited:
                continue
            visited.add(current)

            if end is not None and current == end:
                break

            for neighbor, weight in adj.get(current, []):
                if neighbor in visited:
                    continue
                # 权重越大表示距离越短，用 1/weight 作为距离
                edge_dist = 1.0 / max(weight, 0.001)
                new_dist = dist + edge_dist
                if neighbor not in distances or new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    heapq.heappush(pq, (new_dist, neighbor))

        return distances

    def shortest_path(self, start: str, end: str,
                      min_weight: float = 0.0) -> Tuple[List[str], float]:
        """
        获取两点间的最短路径

        功能：返回从 start 到 end 的最短路径及距离

        Returns:
            (路径节点列表, 总距离)
            如果不可达，返回 ([], float('inf'))
        """
        if start not in self.kg.nodes or end not in self.kg.nodes:
            return [], float('inf')

        adj = self._get_weighted_adjacency(min_weight)
        distances: Dict[str, float] = {start: 0.0}
        predecessors: Dict[str, Optional[str]] = {start: None}
        pq = [(0.0, start)]
        visited: Set[str] = set()

        while pq:
            dist, current = heapq.heappop(pq)
            if current in visited:
                continue
            visited.add(current)

            if current == end:
                break

            for neighbor, weight in adj.get(current, []):
                if neighbor in visited:
                    continue
                edge_dist = 1.0 / max(weight, 0.001)
                new_dist = dist + edge_dist
                if neighbor not in distances or new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    predecessors[neighbor] = current
                    heapq.heappush(pq, (new_dist, neighbor))

        if end not in distances:
            return [], float('inf')

        # 重建路径
        path = []
        node: Optional[str] = end
        while node is not None:
            path.append(node)
            node = predecessors.get(node)
        path.reverse()
        return path, distances[end]

    def pagerank(self, damping: float = 0.85, iterations: int = 30,
                 min_weight: float = 0.0) -> Dict[str, float]:
        """
        PageRank 算法

        功能：计算图中每个节点的重要性排名
        原理：模拟随机游走，一个节点的重要性取决于指向它的节点的重要性
        应用：识别知识图谱中的核心概念、权威节点

        Args:
            damping: 阻尼系数（继续随机游走的概率），默认 0.85
            iterations: 迭代次数，默认 30
            min_weight: 最小边权重阈值

        Returns:
            {节点名: PageRank 分数, ...}
        """
        nodes = list(self.kg.nodes.keys())
        n = len(nodes)
        if n == 0:
            return {}

        adj = self._get_weighted_adjacency(min_weight)

        # 计算每个节点的出边权重和
        out_weights: Dict[str, float] = {}
        for node in nodes:
            total = sum(w for _, w in adj.get(node, []))
            out_weights[node] = total if total > 0 else 1.0

        # 初始化 PageRank 值
        pr: Dict[str, float] = {node: 1.0 / n for node in nodes}

        for _ in range(iterations):
            new_pr: Dict[str, float] = {}
            for node in nodes:
                rank = (1.0 - damping) / n
                # 收集所有指向当前节点的贡献
                for source in nodes:
                    for target, weight in adj.get(source, []):
                        if target == node:
                            rank += damping * pr[source] * weight / out_weights[source]
                new_pr[node] = rank
            pr = new_pr

        # 归一化
        total = sum(pr.values())
        if total > 0:
            pr = {k: v / total for k, v in pr.items()}

        return pr

    def label_propagation(self, min_weight: float = 0.0,
                          max_iterations: int = 100) -> Dict[str, int]:
        """
        标签传播社区发现算法

        功能：将图中节点划分为不同的社区（聚类）
        原理：每个节点选择邻居中最多的标签，标签相同的节点属于同一社区
        应用：发现知识图谱中的概念群组、主题聚类

        Args:
            min_weight: 最小边权重阈值
            max_iterations: 最大迭代次数

        Returns:
            {节点名: 社区ID, ...}
        """
        nodes = list(self.kg.nodes.keys())
        n = len(nodes)
        if n == 0:
            return {}

        # 初始化：每个节点有自己的标签
        labels: Dict[str, int] = {node: i for i, node in enumerate(nodes)}
        adj = self._get_weighted_adjacency(min_weight)

        for _ in range(max_iterations):
            changed = False
            # 随机顺序更新（避免振荡）
            import random
            order = nodes.copy()
            random.seed(42)  # 固定种子保证可重复性
            random.shuffle(order)

            for node in order:
                neighbors = adj.get(node, [])
                if not neighbors:
                    continue

                # 统计邻居标签的加权频次
                label_counts: Dict[int, float] = defaultdict(float)
                for neighbor, weight in neighbors:
                    label_counts[labels[neighbor]] += weight

                # 找到权重最大的标签
                if label_counts:
                    best_label = max(label_counts.items(), key=lambda x: (x[1], -x[0]))[0]
                    if labels[node] != best_label:
                        labels[node] = best_label
                        changed = True

            if not changed:
                break

        # 重新编号社区ID为连续整数
        unique_labels = sorted(set(labels.values()))
        label_map = {old: new for new, old in enumerate(unique_labels)}
        return {node: label_map[label] for node, label in labels.items()}

    def betweenness_centrality(self, min_weight: float = 0.0) -> Dict[str, float]:
        """
        介数中心性

        功能：计算每个节点作为"桥梁"的重要性
        原理：统计经过该节点的最短路径数量
        应用：识别知识图谱中的关键连接节点、信息枢纽

        Args:
            min_weight: 最小边权重阈值

        Returns:
            {节点名: 中心性分数, ...}
        """
        nodes = list(self.kg.nodes.keys())
        n = len(nodes)
        if n == 0:
            return {}

        adj = self._get_weighted_adjacency(min_weight)
        centrality: Dict[str, float] = {node: 0.0 for node in nodes}

        for source in nodes:
            # BFS 计算从 source 出发的最短路径
            distances: Dict[str, float] = {source: 0.0}
            predecessors: Dict[str, List[str]] = {source: []}
            queue = deque([source])

            while queue:
                current = queue.popleft()
                for neighbor, weight in adj.get(current, []):
                    edge_dist = 1.0 / max(weight, 0.001)
                    new_dist = distances[current] + edge_dist
                    if neighbor not in distances:
                        distances[neighbor] = new_dist
                        predecessors[neighbor] = [current]
                        queue.append(neighbor)
                    elif abs(new_dist - distances[neighbor]) < 1e-9:
                        predecessors[neighbor].append(current)

            # 计算依赖值
            dependency: Dict[str, float] = {node: 0.0 for node in nodes}
            path_count: Dict[str, float] = {node: 0.0 for node in nodes}
            path_count[source] = 1.0

            # 按距离排序
            sorted_nodes = sorted(distances.keys(), key=lambda x: distances[x], reverse=True)

            for node in sorted_nodes:
                for pred in predecessors.get(node, []):
                    if path_count[node] > 0:
                        ratio = path_count[pred] / path_count[node]
                        dependency[pred] += ratio * (1.0 + dependency[node])

            for node in distances:
                if node != source:
                    centrality[node] += dependency[node]

        # 归一化（无向图）
        if n > 2:
            scale = 2.0 / ((n - 1) * (n - 2))
            centrality = {k: v * scale for k, v in centrality.items()}

        return centrality

    def degree_centrality(self, min_weight: float = 0.0) -> Dict[str, float]:
        """
        度中心性

        功能：计算每个节点的连接数重要性
        原理：连接数越多，中心性越高

        Returns:
            {节点名: 中心性分数, ...}
        """
        nodes = list(self.kg.nodes.keys())
        n = len(nodes)
        if n <= 1:
            return {node: 0.0 for node in nodes}

        adj = self._get_weighted_adjacency(min_weight)
        max_degree = n - 1

        centrality: Dict[str, float] = {}
        for node in nodes:
            degree = len(adj.get(node, []))
            # 考虑入边
            in_degree = sum(
                1 for edges in adj.values()
                for target, _ in edges if target == node
            )
            centrality[node] = (degree + in_degree) / (2.0 * max_degree)

        return centrality

    def clustering_coefficient(self, min_weight: float = 0.0) -> Dict[str, float]:
        """
        聚类系数

        功能：计算每个节点的局部聚类程度
        原理：邻居之间实际连接数 / 可能的最大连接数
        应用：发现知识图谱中的紧密概念群组

        Returns:
            {节点名: 聚类系数, ...}
        """
        nodes = list(self.kg.nodes.keys())
        adj = self._get_weighted_adjacency(min_weight)

        # 构建无向邻居集合
        neighbors: Dict[str, Set[str]] = {node: set() for node in nodes}
        for source, targets in adj.items():
            for target, _ in targets:
                neighbors[source].add(target)
                neighbors[target].add(source)

        coefficients: Dict[str, float] = {}
        for node in nodes:
            node_neighbors = neighbors[node]
            k = len(node_neighbors)
            if k < 2:
                coefficients[node] = 0.0
                continue

            # 计算邻居之间的实际连接数
            actual_edges = 0
            for n1 in node_neighbors:
                for n2 in node_neighbors:
                    if n1 < n2 and n2 in neighbors.get(n1, set()):
                        actual_edges += 1

            possible_edges = k * (k - 1) / 2
            coefficients[node] = actual_edges / possible_edges if possible_edges > 0 else 0.0

        return coefficients

    def find_communities(self, min_weight: float = 0.0) -> List[List[str]]:
        """
        查找所有社区

        功能：基于标签传播算法，返回社区列表

        Returns:
            [[社区1节点列表], [社区2节点列表], ...]
        """
        labels = self.label_propagation(min_weight)
        communities: Dict[int, List[str]] = defaultdict(list)
        for node, label in labels.items():
            communities[label].append(node)
        return list(communities.values())

    def get_top_nodes(self, scores: Dict[str, float], top_k: int = 10) -> List[Tuple[str, float]]:
        """
        获取分数最高的节点

        功能：辅助方法，返回分数排名前 k 的节点

        Returns:
            [(节点名, 分数), ...]
        """
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:top_k]
