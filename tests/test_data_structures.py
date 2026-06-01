import sys
sys.path.insert(0, '/workspace')

import unittest
import time
from core import Node, Edge


class TestNode(unittest.TestCase):
    def test_node_creation(self):
        node = Node(name="test_node")
        self.assertEqual(node.name, "test_node")
        self.assertTrue(node.valid_state)
        self.assertIsInstance(node.created_at, float)
        self.assertEqual(node.attributes, {})

    def test_node_with_custom_values(self):
        timestamp = 1234567890.123
        attrs = {"key": "value"}
        node = Node(
            name="custom_node",
            created_at=timestamp,
            valid_state=False,
            attributes=attrs
        )
        self.assertEqual(node.name, "custom_node")
        self.assertEqual(node.created_at, timestamp)
        self.assertFalse(node.valid_state)
        self.assertEqual(node.attributes, attrs)

    def test_node_to_dict(self):
        node = Node(name="test_node")
        data = node.to_dict()
        self.assertIn("name", data)
        self.assertIn("created_at", data)
        self.assertIn("valid_state", data)
        self.assertIn("attributes", data)
        self.assertEqual(data["name"], "test_node")

    def test_node_from_dict(self):
        original = Node(name="test_node", valid_state=False)
        data = original.to_dict()
        restored = Node.from_dict(data)
        self.assertEqual(restored.name, original.name)
        self.assertEqual(restored.created_at, original.created_at)
        self.assertEqual(restored.valid_state, original.valid_state)
        self.assertEqual(restored.attributes, original.attributes)

    def test_node_equality(self):
        node1 = Node(name="same_name")
        node2 = Node(name="same_name")
        node3 = Node(name="different_name")
        self.assertEqual(node1, node2)
        self.assertNotEqual(node1, node3)

    def test_node_repr(self):
        node = Node(name="repr_test")
        self.assertIn("repr_test", repr(node))


class TestEdge(unittest.TestCase):
    def test_edge_creation(self):
        edge = Edge(
            source="node_a",
            target="node_b",
            relation_name="related_to",
            weight=0.8
        )
        self.assertEqual(edge.source, "node_a")
        self.assertEqual(edge.target, "node_b")
        self.assertEqual(edge.relation_name, "related_to")
        self.assertEqual(edge.weight, 0.8)
        self.assertIsInstance(edge.created_at, float)

    def test_edge_with_boundary_weights(self):
        edge_min = Edge("a", "b", "test", 0.0)
        edge_max = Edge("a", "b", "test", 1.0)
        self.assertEqual(edge_min.weight, 0.0)
        self.assertEqual(edge_max.weight, 1.0)

    def test_edge_invalid_weight_raises(self):
        with self.assertRaises(ValueError):
            Edge("a", "b", "test", -0.1)
        with self.assertRaises(ValueError):
            Edge("a", "b", "test", 1.1)

    def test_edge_to_dict(self):
        edge = Edge(
            source="src",
            target="tgt",
            relation_name="connects",
            weight=0.5
        )
        data = edge.to_dict()
        self.assertEqual(data["source"], "src")
        self.assertEqual(data["target"], "tgt")
        self.assertEqual(data["relation_name"], "connects")
        self.assertEqual(data["weight"], 0.5)
        self.assertIn("created_at", data)

    def test_edge_from_dict(self):
        original = Edge("src", "tgt", "connects", 0.7)
        data = original.to_dict()
        restored = Edge.from_dict(data)
        self.assertEqual(restored.source, original.source)
        self.assertEqual(restored.target, original.target)
        self.assertEqual(restored.relation_name, original.relation_name)
        self.assertEqual(restored.weight, original.weight)

    def test_edge_equality(self):
        edge1 = Edge("a", "b", "rel", 0.5)
        edge2 = Edge("a", "b", "rel", 0.9)
        edge3 = Edge("a", "c", "rel", 0.5)
        self.assertEqual(edge1, edge2)
        self.assertNotEqual(edge1, edge3)

    def test_edge_repr(self):
        edge = Edge("A", "B", "links", 0.85)
        repr_str = repr(edge)
        self.assertIn("A", repr_str)
        self.assertIn("B", repr_str)
        self.assertIn("links", repr_str)


if __name__ == '__main__':
    unittest.main()
