import sys
sys.path.insert(0, '/workspace')

import tempfile
import os
from core import KnowledgeGraph


def debug_save_bug():
    """调试保存/加载 bug"""
    temp_dir = tempfile.mkdtemp()
    kg_path = os.path.join(temp_dir, "debug_kg.json")
    
    print("=" * 60)
    print("开始调试保存/加载 bug")
    print("=" * 60)
    
    kg = KnowledgeGraph(kg_path)
    
    print(f"\n阶段 1: 创建 100 个节点，每 10 个保存一次")
    for i in range(100):
        kg.add_node(f"quick_node_{i}")
        kg.add_edge(f"quick_node_{i}", f"quick_node_{(i+1)%100}", "link", 0.5)
        
        if i % 10 == 0:
            print(f"  保存 i={i}, 当前节点数: {kg.get_node_count()}")
            kg.save()
            
            # 立即重新加载并验证
            kg_check = KnowledgeGraph(kg_path)
            print(f"  重新加载后节点数: {kg_check.get_node_count()}")
            
            if kg_check.get_node_count() != i + 1:
                print(f"  ⚠️  发现问题！期望 {i+1} 个节点，实际 {kg_check.get_node_count()}")
    
    print(f"\n阶段 2: 最终验证")
    print(f"  源图节点数: {kg.get_node_count()}")
    
    kg2 = KnowledgeGraph(kg_path)
    print(f"  重新加载后节点数: {kg2.get_node_count()}")
    
    # 详细比较节点
    source_nodes = set(kg.nodes.keys())
    loaded_nodes = set(kg2.nodes.keys())
    
    print(f"\n详细比较:")
    print(f"  源节点数: {len(source_nodes)}")
    print(f"  加载节点数: {len(loaded_nodes)}")
    print(f"  缺失节点: {source_nodes - loaded_nodes}")
    print(f"  多余节点: {loaded_nodes - source_nodes}")
    
    # 检查文件内容
    print(f"\n文件内容检查:")
    with open(kg_path, 'r', encoding='utf-8') as f:
        import json
        data = json.load(f)
        print(f"  元数据节点数: {data['metadata']['node_count']}")
        print(f"  实际节点数: {len(data['nodes'])}")
    
    return kg.get_node_count() == kg2.get_node_count()


if __name__ == "__main__":
    success = debug_save_bug()
    print(f"\n{'✓ Bug 复现成功' if not success else '✓ 未发现 bug'}")
    sys.exit(0 if success else 1)
