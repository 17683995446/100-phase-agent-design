import re
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict


class QueryParseError(Exception):
    """查询解析错误"""
    pass


class QueryResult:
    """查询结果"""
    def __init__(self, data: List[Dict[str, Any]], columns: List[str]):
        self.data = data
        self.columns = columns

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": self.data,
            "count": len(self.data)
        }


class QueryParser:
    """
    查询解析器

    支持简化类 Cypher 语法：
    - MATCH (n) RETURN n          -- 查询所有节点
    - MATCH (n:Person) RETURN n   -- 按标签过滤节点
    - MATCH (a)-[r]->(b) RETURN a, b, r   -- 查询边
    - MATCH (a)-[r:KNOWS]->(b) WHERE a.name = 'Alice' RETURN b   -- 条件查询
    - MATCH path = (a)-[*]->(b) RETURN path   -- 路径查询
    """

    def __init__(self):
        self._node_pattern = re.compile(
            r'\((\w+)(?::(\w+))?\s*(?:\{([^}]*)\})?\)'
        )
        # 支持 [r], [r:TYPE], [*] 等边模式
        self._edge_pattern = re.compile(
            r'-\[(\w+|\*)(?::(\w+))?\s*(?:\{([^}]*)\})?\]->'
        )
        self._bidirectional_edge_pattern = re.compile(
            r'<-\[(\w+)(?::(\w+))?\s*(?:\{([^}]*)\})?\]->'
        )

    def parse(self, query: str) -> Dict[str, Any]:
        """
        解析查询字符串

        Returns:
            {
                "match_type": "nodes" | "edges" | "path",
                "nodes": [{"var": "n", "label": "Person", "properties": {}}, ...],
                "edges": [{"var": "r", "type": "KNOWS", "properties": {}, "direction": "->"}, ...],
                "where": [{"field": "a.name", "op": "=", "value": "Alice"}, ...],
                "return_vars": ["n", "b"],
                "limit": 100
            }
        """
        query = query.strip()
        if not query:
            raise QueryParseError("Empty query")

        result: Dict[str, Any] = {
            "match_type": "nodes",
            "nodes": [],
            "edges": [],
            "where": [],
            "return_vars": [],
            "limit": None
        }

        # 提取 LIMIT
        limit_match = re.search(r'LIMIT\s+(\d+)', query, re.IGNORECASE)
        if limit_match:
            result["limit"] = int(limit_match.group(1))
            query = query[:limit_match.start()] + query[limit_match.end():]

        # 提取 RETURN
        return_match = re.search(r'RETURN\s+(.+)$', query, re.IGNORECASE)
        if return_match:
            return_str = return_match.group(1).strip()
            result["return_vars"] = [v.strip() for v in return_str.split(",")]
            query = query[:return_match.start()]

        # 提取 WHERE
        where_match = re.search(r'WHERE\s+(.+?)(?:RETURN|$)', query, re.IGNORECASE)
        if where_match:
            where_str = where_match.group(1).strip()
            result["where"] = self._parse_where(where_str)
            query = query[:where_match.start()] + query[where_match.end():]

        # 提取 MATCH
        match_match = re.search(r'MATCH\s+(.+)', query, re.IGNORECASE)
        if not match_match:
            raise QueryParseError("Missing MATCH clause")

        match_str = match_match.group(1).strip()
        result["nodes"], result["edges"], result["match_type"] = self._parse_match(match_str)

        return result

    def _parse_match(self, match_str: str) -> Tuple[List[Dict], List[Dict], str]:
        """解析 MATCH 子句"""
        nodes = []
        edges = []

        # 检查是否是路径查询
        is_path_query = 'path' in match_str.lower() and '=' in match_str
        if is_path_query:
            match_str = match_str.split('=', 1)[1].strip()

        # 解析节点和边
        i = 0
        while i < len(match_str):
            # 尝试匹配节点
            node_match = self._node_pattern.match(match_str[i:])
            if node_match:
                node = {
                    "var": node_match.group(1),
                    "label": node_match.group(2),
                    "properties": self._parse_properties(node_match.group(3))
                }
                nodes.append(node)
                i += node_match.end()
                continue

            # 尝试匹配有向边
            edge_match = self._edge_pattern.match(match_str[i:])
            if edge_match:
                edge = {
                    "var": edge_match.group(1),
                    "type": edge_match.group(2),
                    "properties": self._parse_properties(edge_match.group(3)),
                    "direction": "->"
                }
                edges.append(edge)
                i += edge_match.end()
                continue

            # 尝试匹配双向边
            bi_edge_match = self._bidirectional_edge_pattern.match(match_str[i:])
            if bi_edge_match:
                edge = {
                    "var": bi_edge_match.group(1),
                    "type": bi_edge_match.group(2),
                    "properties": self._parse_properties(bi_edge_match.group(3)),
                    "direction": "<>"
                }
                edges.append(edge)
                i += bi_edge_match.end()
                continue

            i += 1

        if is_path_query:
            match_type = "path"
        elif len(edges) > 0:
            match_type = "edges"
        else:
            match_type = "nodes"

        return nodes, edges, match_type

    def _parse_where(self, where_str: str) -> List[Dict[str, Any]]:
        """解析 WHERE 条件"""
        conditions = []
        # 支持 AND 连接
        parts = re.split(r'\s+AND\s+', where_str, flags=re.IGNORECASE)

        for part in parts:
            part = part.strip()
            # 匹配 field op value
            match = re.match(r"(\w+\.?\w*)\s*(=|!=|<>|>=|<=|>|<)\s*(.+)", part)
            if match:
                field = match.group(1)
                op = match.group(2)
                value = match.group(3).strip()
                # 去除引号
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                else:
                    # 尝试转换为数字
                    try:
                        value = float(value)
                        if value == int(value):
                            value = int(value)
                    except ValueError:
                        pass
                conditions.append({"field": field, "op": op, "value": value})

        return conditions

    def _parse_properties(self, props_str: Optional[str]) -> Dict[str, Any]:
        """解析属性字典 {key: value, ...}"""
        if not props_str:
            return {}

        properties = {}
        # 简单的 key: value 解析
        pairs = re.split(r',\s*', props_str)
        for pair in pairs:
            if ':' in pair:
                key, value = pair.split(':', 1)
                key = key.strip()
                value = value.strip()
                # 去除引号
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                else:
                    try:
                        value = float(value)
                        if value == int(value):
                            value = int(value)
                    except ValueError:
                        pass
                properties[key] = value

        return properties


class QueryExecutor:
    """
    查询执行引擎

    功能：执行解析后的查询，在知识图谱上检索数据
    """

    def __init__(self, knowledge_graph):
        self.kg = knowledge_graph

    def execute(self, parsed_query: Dict[str, Any]) -> QueryResult:
        """执行解析后的查询"""
        match_type = parsed_query.get("match_type", "nodes")

        if match_type == "nodes":
            return self._execute_node_query(parsed_query)
        elif match_type == "edges":
            return self._execute_edge_query(parsed_query)
        elif match_type == "path":
            return self._execute_path_query(parsed_query)
        else:
            return QueryResult([], [])

    def _execute_node_query(self, query: Dict[str, Any]) -> QueryResult:
        """执行节点查询"""
        nodes = query.get("nodes", [])
        where = query.get("where", [])
        return_vars = query.get("return_vars", [])
        limit = query.get("limit")

        if not nodes:
            return QueryResult([], return_vars)

        node_spec = nodes[0]
        var_name = node_spec.get("var", "n")

        # 收集所有节点
        results = []
        for name, node in self.kg.nodes.items():
            row: Dict[str, Any] = {var_name: {"name": name, **node.to_dict()}}

            # 应用 WHERE 条件
            if self._match_where(row, where, var_name):
                results.append(row)

        # 应用 LIMIT
        if limit is not None:
            results = results[:limit]

        # 确定返回列
        columns = return_vars if return_vars else [var_name]
        return QueryResult(results, columns)

    def _execute_edge_query(self, query: Dict[str, Any]) -> QueryResult:
        """执行边查询"""
        nodes = query.get("nodes", [])
        edges = query.get("edges", [])
        where = query.get("where", [])
        return_vars = query.get("return_vars", [])
        limit = query.get("limit")

        if len(nodes) < 2 or not edges:
            return QueryResult([], return_vars)

        source_var = nodes[0].get("var", "a")
        target_var = nodes[1].get("var", "b")
        edge_var = edges[0].get("var", "r")

        results = []
        for edge in self.kg.edges:
            row = {
                source_var: {"name": edge.source, **self.kg.nodes.get(edge.source, {}).to_dict()} if edge.source in self.kg.nodes else {"name": edge.source},
                target_var: {"name": edge.target, **self.kg.nodes.get(edge.target, {}).to_dict()} if edge.target in self.kg.nodes else {"name": edge.target},
                edge_var: {"source": edge.source, "target": edge.target,
                          "relation": edge.relation_name, "weight": edge.weight}
            }

            if self._match_where(row, where, source_var, target_var, edge_var):
                results.append(row)

        if limit is not None:
            results = results[:limit]

        columns = return_vars if return_vars else [source_var, edge_var, target_var]
        return QueryResult(results, columns)

    def _execute_path_query(self, query: Dict[str, Any]) -> QueryResult:
        """执行路径查询（简化版：返回两点间路径）"""
        nodes = query.get("nodes", [])
        return_vars = query.get("return_vars", [])
        limit = query.get("limit")

        if len(nodes) < 2:
            return QueryResult([], return_vars)

        source_var = nodes[0].get("var", "a")
        target_var = nodes[-1].get("var", "b")

        results = []
        for source in self.kg.nodes:
            for target in self.kg.nodes:
                if source == target:
                    continue
                paths = self.kg.find_paths(source, target, max_depth=3)
                for path in paths:
                    row = {
                        source_var: {"name": source},
                        target_var: {"name": target},
                        "path": path
                    }
                    results.append(row)

        if limit is not None:
            results = results[:limit]

        columns = return_vars if return_vars else [source_var, target_var, "path"]
        return QueryResult(results, columns)

    def _match_where(self, row: Dict[str, Any], conditions: List[Dict[str, Any]],
                     *var_names) -> bool:
        """检查行是否匹配 WHERE 条件"""
        for cond in conditions:
            field = cond["field"]
            op = cond["op"]
            expected = cond["value"]

            # 解析字段路径，如 "a.name"
            parts = field.split(".")
            if len(parts) == 2:
                var, attr = parts
                value = row.get(var, {}).get(attr)
            else:
                # 尝试在所有变量中查找
                value = None
                for var in var_names:
                    if var in row and parts[0] in row[var]:
                        value = row[var][parts[0]]
                        break
                if value is None:
                    value = row.get(parts[0]) if len(parts) == 1 else None

            if not self._compare(value, op, expected):
                return False

        return True

    def _compare(self, value: Any, op: str, expected: Any) -> bool:
        """比较值"""
        if value is None:
            return False

        # 尝试类型转换
        if isinstance(expected, (int, float)) and isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                return False

        if op == "=" or op == "==":
            return str(value) == str(expected)
        elif op == "!=" or op == "<>":
            return str(value) != str(expected)
        elif op == ">":
            return value > expected
        elif op == ">=":
            return value >= expected
        elif op == "<":
            return value < expected
        elif op == "<=":
            return value <= expected

        return False


class QueryEngine:
    """
    查询引擎（组合解析器和执行器）

    功能：提供统一的查询接口
    """

    def __init__(self, knowledge_graph):
        self.kg = knowledge_graph
        self.parser = QueryParser()
        self.executor = QueryExecutor(knowledge_graph)

    def query(self, query_str: str) -> QueryResult:
        """
        执行查询字符串

        Args:
            query_str: 查询语句

        Returns:
            QueryResult 对象
        """
        parsed = self.parser.parse(query_str)
        return self.executor.execute(parsed)

    def find_nodes(self, label: Optional[str] = None,
                   properties: Optional[Dict[str, Any]] = None,
                   limit: int = 100) -> QueryResult:
        """
        简化接口：查找节点

        Args:
            label: 节点标签（这里映射为属性中的 _label）
            properties: 属性过滤条件
            limit: 最大返回数

        Returns:
            QueryResult 对象
        """
        results = []
        for name, node in self.kg.nodes.items():
            match = True
            if properties:
                for key, value in properties.items():
                    if node.attributes.get(key) != value:
                        match = False
                        break
            if match:
                results.append({"n": {"name": name, **node.to_dict()}})
            if len(results) >= limit:
                break

        return QueryResult(results, ["n"])

    def find_neighbors(self, node_name: str, relation: Optional[str] = None,
                       min_weight: float = 0.0, limit: int = 100) -> QueryResult:
        """
        简化接口：查找邻居节点

        Args:
            node_name: 中心节点名
            relation: 关系类型过滤
            min_weight: 最小权重
            limit: 最大返回数

        Returns:
            QueryResult 对象
        """
        results = []
        for edge in self.kg.get_all_edges_from(node_name, min_weight):
            if relation is not None and edge.relation_name != relation:
                continue
            target = edge.target
            if target in self.kg.nodes:
                results.append({
                    "source": {"name": node_name},
                    "target": {"name": target, **self.kg.nodes[target].to_dict()},
                    "relation": edge.relation_name,
                    "weight": edge.weight
                })
            if len(results) >= limit:
                break

        return QueryResult(results, ["source", "target", "relation", "weight"])
