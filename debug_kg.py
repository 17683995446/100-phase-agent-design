import sys
sys.path.insert(0, '/workspace')

from core import KnowledgeGraph
import tempfile
import os

def test():
    temp_dir = tempfile.mkdtemp()
    kg_path = os.path.join(temp_dir, "test_kg.json")
    try:
        kg = KnowledgeGraph(kg_path)
        
        print("Adding nodes...")
        for i in range(100):
            kg.add_node(f"node_{i}")
        
        print("Adding edges...")
        for i in range(50):
            kg.add_edge(f"node_{i}", f"node_{i + 1}", "rel1", 0.7)
            kg.add_edge(f"node_{i}", f"node_{(i + 2) % 100}", "rel2", 0.5)
        
        print(f"\nTotal edges: {len(kg.edges)}")
        print(f"\nOutgoing edges from node_0: {len(kg.get_edges_from_node('node_0'))}")
        for e in kg.get_edges_from_node('node_0'):
            print(f"  - {e}")
        
        print(f"\nOutgoing edges from node_50: {len(kg.get_edges_from_node('node_50'))}")
        for e in kg.get_edges_from_node('node_50'):
            print(f"  - {e}")
        
        print(f"\nOutgoing indexes: {list(kg._outgoing_edges.keys())}")
        
    finally:
        import shutil
        shutil.rmtree(temp_dir)

test()