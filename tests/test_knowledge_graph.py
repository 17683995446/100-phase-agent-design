import sys
sys.path.insert(0, '/workspace')

import os
import unittest
import tempfile
from core import KnowledgeGraph, Node, Edge


class TestKnowledgeGraph(unittest.TestCase):
    def setUp(self):
        self.test_file = tempfile.mktemp(suffix='.json')
        self.kg = KnowledgeGraph(save_path=self.test_file)

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_initialization(self):
        kg = KnowledgeGraph(save_path=self.test_file)
        self.assertEqual(kg.get_node_count(), 0)
        self.assertEqual(kg.get_edge_count(), 0)

    def test_add_node(self):
        node = self.kg.add_node("concept_a")
        self.assertEqual(node.name, "concept_a")
        self.assertTrue(node.valid_state)
        self.assertEqual(self.kg.get_node_count(), 1)

    def test_add_node_with_attributes(self):
        attrs = {"category": "test", "importance": 5}
        node = self.kg.add_node("concept_b", attributes=attrs)
        self.assertEqual(node.attributes, attrs)

    def test_add_duplicate_node(self):
        self.kg.add_node("concept_c")
        self.kg.add_node("concept_c")
        self.assertEqual(self.kg.get_node_count(), 1)

    def test_get_node(self):
        self.kg.add_node("concept_d")
        node = self.kg.get_node("concept_d")
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "concept_d")

    def test_get_nonexistent_node(self):
        node = self.kg.get_node("nonexistent")
        self.assertIsNone(node)

    def test_has_node(self):
        self.kg.add_node("concept_e")
        self.assertTrue(self.kg.has_node("concept_e"))
        self.assertFalse(self.kg.has_node("nonexistent"))

    def test_delete_node(self):
        self.kg.add_node("concept_f")
        result = self.kg.delete_node("concept_f")
        self.assertTrue(result)
        self.assertEqual(self.kg.get_node_count(), 0)

    def test_delete_node_with_edges(self):
        self.kg.add_edge("a", "b", "relates", 0.5)
        self.kg.delete_node("a")
        self.assertEqual(len(self.kg.get_edges_from_node("a")), 0)

    def test_delete_nonexistent_node(self):
        result = self.kg.delete_node("nonexistent")
        self.assertFalse(result)

    def test_update_node(self):
        self.kg.add_node("concept_g")
        updated = self.kg.update_node("concept_g", valid_state=False)
        self.assertFalse(updated.valid_state)

    def test_update_node_attributes(self):
        self.kg.add_node("concept_h")
        self.kg.update_node("concept_h", attributes={"key": "value"})
        node = self.kg.get_node("concept_h")
        self.assertEqual(node.attributes["key"], "value")

    def test_add_edge(self):
        edge = self.kg.add_edge("node_x", "node_y", "connects", 0.8)
        self.assertEqual(edge.source, "node_x")
        self.assertEqual(edge.target, "node_y")
        self.assertEqual(edge.weight, 0.8)
        self.assertEqual(self.kg.get_edge_count(), 1)

    def test_add_edge_auto_creates_nodes(self):
        self.kg.add_edge("new_src", "new_tgt", "links", 0.6)
        self.assertTrue(self.kg.has_node("new_src"))
        self.assertTrue(self.kg.has_node("new_tgt"))

    def test_get_edges_from_node(self):
        self.kg.add_edge("src", "tgt1", "rel1", 0.5)
        self.kg.add_edge("src", "tgt2", "rel2", 0.7)
        edges = self.kg.get_edges_from_node("src")
        self.assertEqual(len(edges), 2)

    def test_get_edges_to_node(self):
        self.kg.add_edge("src1", "tgt", "rel1", 0.5)
        self.kg.add_edge("src2", "tgt", "rel2", 0.7)
        edges = self.kg.get_edges_to_node("tgt")
        self.assertEqual(len(edges), 2)

    def test_get_all_edges_from_with_min_weight(self):
        self.kg.add_edge("a", "b", "r1", 0.3)
        self.kg.add_edge("a", "c", "r2", 0.8)
        edges = self.kg.get_all_edges_from("a", min_weight=0.5)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].target, "c")

    def test_delete_edge(self):
        self.kg.add_edge("x", "y", "rel", 0.5)
        result = self.kg.delete_edge("x", "y", "rel")
        self.assertTrue(result)
        self.assertEqual(self.kg.get_edge_count(), 0)

    def test_delete_nonexistent_edge(self):
        result = self.kg.delete_edge("none", "none", "none")
        self.assertFalse(result)

    def test_save_and_load(self):
        self.kg.add_node("persistent_node")
        self.kg.add_edge("p_src", "p_tgt", "persists", 0.9)
        self.kg.save()

        new_kg = KnowledgeGraph(save_path=self.test_file)
        self.assertEqual(new_kg.get_node_count(), 3)
        self.assertEqual(new_kg.get_edge_count(), 1)
        self.assertIsNotNone(new_kg.get_node("persistent_node"))

    def test_load_nonexistent_file(self):
        new_path = tempfile.mktemp(suffix='.json')
        if os.path.exists(new_path):
            os.remove(new_path)
        kg = KnowledgeGraph(save_path=new_path)
        self.assertEqual(kg.get_node_count(), 0)
        os.remove(new_path)

    def test_load_corrupted_file(self):
        with open(self.test_file, 'w') as f:
            f.write("invalid json {{{")
        kg = KnowledgeGraph(save_path=self.test_file)
        self.assertEqual(kg.get_node_count(), 0)

    def test_clear(self):
        self.kg.add_node("to_clear")
        self.kg.add_edge("a", "b", "r", 0.5)
        self.kg.clear()
        self.assertEqual(self.kg.get_node_count(), 0)
        self.assertEqual(self.kg.get_edge_count(), 0)

    def test_repr(self):
        self.kg.add_node("test")
        repr_str = repr(self.kg)
        self.assertIn("KnowledgeGraph", repr_str)
        self.assertIn("nodes=1", repr_str)


if __name__ == '__main__':
    unittest.main()
