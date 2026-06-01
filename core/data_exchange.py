import csv
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from io import StringIO


class DataExchange:
    """
    数据导入导出模块

    支持多种数据格式与知识图谱的互转：
    - CSV：表格格式，适合电子表格软件
    - RDF：语义网标准格式
    - GraphML：图数据交换标准格式
    """

    def __init__(self, knowledge_graph):
        self.kg = knowledge_graph

    # ==================== CSV 格式 ====================

    def export_to_csv(self) -> Tuple[str, str]:
        """
        导出为 CSV 格式

        功能：将知识图谱导出为节点和边两个 CSV 字符串
        返回: (nodes_csv, edges_csv)
        """
        # 导出节点
        nodes_buffer = StringIO()
        node_writer = csv.writer(nodes_buffer)
        node_writer.writerow(["name", "valid_state", "attributes"])
        for node in self.kg.nodes.values():
            node_writer.writerow([
                node.name,
                str(node.valid_state),
                json.dumps(node.attributes, ensure_ascii=False)
            ])

        # 导出边
        edges_buffer = StringIO()
        edge_writer = csv.writer(edges_buffer)
        edge_writer.writerow(["source", "target", "relation", "weight"])
        for edge in self.kg.edges:
            edge_writer.writerow([
                edge.source,
                edge.target,
                edge.relation_name,
                str(edge.weight)
            ])

        return nodes_buffer.getvalue(), edges_buffer.getvalue()

    def import_from_csv(self, nodes_csv: str, edges_csv: str) -> Tuple[int, int]:
        """
        从 CSV 导入数据

        功能：将 CSV 格式的节点和边数据导入知识图谱
        返回: (导入节点数, 导入边数)
        """
        node_count = 0
        edge_count = 0

        # 导入节点
        if nodes_csv.strip():
            reader = csv.DictReader(StringIO(nodes_csv))
            for row in reader:
                name = row.get("name", "").strip()
                if not name:
                    continue
                valid_state = row.get("valid_state", "True").lower() == "true"
                try:
                    attributes = json.loads(row.get("attributes", "{}"))
                except json.JSONDecodeError:
                    attributes = {}
                self.kg.add_node(name, attributes)
                self.kg.nodes[name].valid_state = valid_state
                node_count += 1

        # 导入边
        if edges_csv.strip():
            reader = csv.DictReader(StringIO(edges_csv))
            for row in reader:
                source = row.get("source", "").strip()
                target = row.get("target", "").strip()
                relation = row.get("relation", "").strip()
                try:
                    weight = float(row.get("weight", "1.0"))
                except ValueError:
                    weight = 1.0
                if source and target and relation:
                    self.kg.add_edge(source, target, relation, weight)
                    edge_count += 1

        return node_count, edge_count

    # ==================== RDF 格式 ====================

    def export_to_rdf(self, base_uri: str = "http://example.org/kg/") -> str:
        """
        导出为 RDF/Turtle 格式

        功能：将知识图谱导出为 RDF Turtle 格式
        原理：节点映射为 RDF 资源，边映射为 RDF 三元组
        应用：与语义网工具集成

        Args:
            base_uri: 基础 URI 前缀

        Returns:
            RDF Turtle 格式的字符串
        """
        lines = []
        lines.append("@prefix kg: <{}> .".format(base_uri))
        lines.append("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .")
        lines.append("")

        # 导出节点类型声明
        for node in self.kg.nodes.values():
            node_uri = self._to_uri(node.name, base_uri)
            lines.append("{} rdf:type kg:Node .".format(node_uri))
            if node.attributes:
                for key, value in node.attributes.items():
                    safe_key = self._to_safe_identifier(key)
                    safe_value = json.dumps(str(value), ensure_ascii=False)
                    lines.append("{} kg:{} {} .".format(node_uri, safe_key, safe_value))
            lines.append("")

        # 导出边（三元组）
        for edge in self.kg.edges:
            source_uri = self._to_uri(edge.source, base_uri)
            target_uri = self._to_uri(edge.target, base_uri)
            relation_uri = self._to_uri(edge.relation_name, base_uri)
            lines.append("{} {} {} .".format(source_uri, relation_uri, target_uri))
            lines.append("{} kg:weight \"{}\"^^<http://www.w3.org/2001/XMLSchema#float> .".format(
                source_uri, edge.weight))

        return "\n".join(lines)

    def import_from_rdf(self, rdf_text: str, base_uri: str = "http://example.org/kg/") -> Tuple[int, int]:
        """
        从 RDF/Turtle 导入数据

        功能：解析简单的 RDF Turtle 格式导入知识图谱
        注意：仅支持简化格式，完整 RDF 解析需要专用库

        Returns:
            (导入节点数, 导入边数)
        """
        node_count = 0
        edge_count = 0

        # 简单解析三元组
        for line in rdf_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("@prefix") or line.startswith("#"):
                continue
            if not line.endswith(" ."):
                continue

            # 移除末尾的 " ."
            triple = line[:-2].strip()
            parts = triple.split(None, 2)
            if len(parts) != 3:
                continue

            subject, predicate, obj = parts

            # 提取节点名
            subject_name = self._from_uri(subject, base_uri)

            # 如果是类型声明，添加节点
            if predicate == "rdf:type" or predicate.endswith("#type"):
                if obj.endswith("Node>") or obj.endswith("Node"):
                    self.kg.add_node(subject_name)
                    node_count += 1
                continue

            # 统一处理：提取 predicate 名称
            pred_name = self._from_uri(predicate, base_uri)
            is_type = predicate == "rdf:type" or predicate.endswith("#type")
            is_kg_prefix = predicate.startswith("kg:")

            # 如果是类型声明，添加节点
            if is_type:
                if obj.endswith("Node>") or obj.endswith("Node"):
                    self.kg.add_node(subject_name)
                    node_count += 1
                continue

            # 如果是已知属性（weight、attributes等）
            if is_kg_prefix and pred_name in ("weight", "attributes", "valid_state"):
                continue

            # 如果是 kg: 前缀但不是已知属性（如 kg:age, kg:role）
            if is_kg_prefix:
                value = obj.strip('"')
                if subject_name in self.kg.nodes:
                    self.kg.nodes[subject_name].attributes[pred_name] = value
                continue

            # 其余视为关系（边）
            obj_name = self._from_uri(obj, base_uri)
            self.kg.add_edge(subject_name, obj_name, pred_name, 1.0)
            edge_count += 1

        return node_count, edge_count

    # ==================== GraphML 格式 ====================

    def export_to_graphml(self) -> str:
        """
        导出为 GraphML 格式

        功能：将知识图谱导出为 GraphML XML 格式
        应用：与 Gephi、Cytoscape 等图可视化工具集成

        Returns:
            GraphML XML 字符串
        """
        root = ET.Element("graphml")
        root.set("xmlns", "http://graphml.graphdrawing.org/xmlns")

        # 定义属性
        key_valid = ET.SubElement(root, "key")
        key_valid.set("id", "valid_state")
        key_valid.set("for", "node")
        key_valid.set("attr.name", "valid_state")
        key_valid.set("attr.type", "boolean")

        key_attrs = ET.SubElement(root, "key")
        key_attrs.set("id", "attributes")
        key_attrs.set("for", "node")
        key_attrs.set("attr.name", "attributes")
        key_attrs.set("attr.type", "string")

        key_weight = ET.SubElement(root, "key")
        key_weight.set("id", "weight")
        key_weight.set("for", "edge")
        key_weight.set("attr.name", "weight")
        key_weight.set("attr.type", "double")

        key_relation = ET.SubElement(root, "key")
        key_relation.set("id", "relation")
        key_relation.set("for", "edge")
        key_relation.set("attr.name", "relation")
        key_relation.set("attr.type", "string")

        # 图元素
        graph = ET.SubElement(root, "graph")
        graph.set("id", "knowledge_graph")
        graph.set("edgedefault", "directed")

        # 节点
        for node in self.kg.nodes.values():
            node_elem = ET.SubElement(graph, "node")
            node_elem.set("id", node.name)

            data_valid = ET.SubElement(node_elem, "data")
            data_valid.set("key", "valid_state")
            data_valid.text = str(node.valid_state).lower()

            data_attrs = ET.SubElement(node_elem, "data")
            data_attrs.set("key", "attributes")
            data_attrs.text = json.dumps(node.attributes, ensure_ascii=False)

        # 边
        for i, edge in enumerate(self.kg.edges):
            edge_elem = ET.SubElement(graph, "edge")
            edge_elem.set("id", "e{}".format(i))
            edge_elem.set("source", edge.source)
            edge_elem.set("target", edge.target)

            data_weight = ET.SubElement(edge_elem, "data")
            data_weight.set("key", "weight")
            data_weight.text = str(edge.weight)

            data_relation = ET.SubElement(edge_elem, "data")
            data_relation.set("key", "relation")
            data_relation.text = edge.relation_name

        # 格式化输出
        self._indent_xml(root)
        return ET.tostring(root, encoding="unicode")

    def import_from_graphml(self, graphml_text: str) -> Tuple[int, int]:
        """
        从 GraphML 导入数据

        功能：解析 GraphML XML 导入知识图谱

        Returns:
            (导入节点数, 导入边数)
        """
        node_count = 0
        edge_count = 0

        try:
            root = ET.fromstring(graphml_text)
        except ET.ParseError:
            return 0, 0

        # 处理命名空间
        ns = {"g": "http://graphml.graphdrawing.org/xmlns"}

        # 查找图元素
        graph = root.find(".//g:graph", ns)
        if graph is None:
            graph = root.find(".//graph")

        if graph is None:
            return 0, 0

        # 导入节点
        for node_elem in graph.findall("g:node", ns) or graph.findall("node"):
            node_id = node_elem.get("id", "")
            if not node_id:
                continue

            valid_state = True
            attributes = {}

            for data in node_elem.findall("g:data", ns) or node_elem.findall("data"):
                key = data.get("key", "")
                text = data.text or ""
                if key == "valid_state":
                    valid_state = text.lower() == "true"
                elif key == "attributes":
                    try:
                        attributes = json.loads(text)
                    except json.JSONDecodeError:
                        attributes = {}

            self.kg.add_node(node_id, attributes)
            self.kg.nodes[node_id].valid_state = valid_state
            node_count += 1

        # 导入边
        for edge_elem in graph.findall("g:edge", ns) or graph.findall("edge"):
            source = edge_elem.get("source", "")
            target = edge_elem.get("target", "")
            if not source or not target:
                continue

            weight = 1.0
            relation = "relates_to"

            for data in edge_elem.findall("g:data", ns) or edge_elem.findall("data"):
                key = data.get("key", "")
                text = data.text or ""
                if key == "weight":
                    try:
                        weight = float(text)
                    except ValueError:
                        weight = 1.0
                elif key == "relation":
                    relation = text

            self.kg.add_edge(source, target, relation, weight)
            edge_count += 1

        return node_count, edge_count

    # ==================== 辅助方法 ====================

    def _to_uri(self, name: str, base_uri: str) -> str:
        """将名称转换为 URI"""
        safe = self._to_safe_identifier(name)
        return "<{}{}>".format(base_uri, safe)

    def _from_uri(self, uri: str, base_uri: str) -> str:
        """从 URI 提取名称"""
        # 移除尖括号
        uri = uri.strip("<>")
        if uri.startswith(base_uri):
            return uri[len(base_uri):]
        # 处理前缀形式
        if ":" in uri and not uri.startswith("http"):
            return uri.split(":", 1)[1]
        return uri

    def _to_safe_identifier(self, name: str) -> str:
        """将名称转换为安全的标识符"""
        safe = ""
        for c in name:
            if c.isalnum() or c in "_-":
                safe += c
            else:
                safe += "_"
        return safe

    def _indent_xml(self, elem, level: int = 0) -> None:
        """为 XML 元素添加缩进"""
        indent = "\n" + "  " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent
