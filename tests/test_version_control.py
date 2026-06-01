import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.knowledge_graph import KnowledgeGraph
from core.version_control import VersionControl, Snapshot, Branch


class TestSnapshot:
    def test_creation(self):
        snapshot = Snapshot("v1", {"a": {"name": "a"}}, [], None)
        assert snapshot.name == "v1"
        assert snapshot.parent is None
        assert snapshot.timestamp > 0

    def test_to_dict(self):
        snapshot = Snapshot("v1", {"a": {"name": "a"}}, [], None)
        d = snapshot.to_dict()
        assert d["name"] == "v1"
        assert d["node_count"] == 1
        assert d["edge_count"] == 0


class TestBranch:
    def test_creation(self):
        branch = Branch("main")
        assert branch.name == "main"
        assert branch.get_latest_snapshot() is None

    def test_add_snapshot(self):
        branch = Branch("main")
        branch.add_snapshot("v1")
        branch.add_snapshot("v2")
        assert branch.get_latest_snapshot() == "v2"


class TestVersionControl:
    @pytest.fixture
    def sample_graph(self):
        kg = KnowledgeGraph(save_path="test_vc.json")
        kg.clear()
        kg.add_node("Alice", {"role": "engineer"})
        kg.add_node("Bob", {"role": "designer"})
        kg.add_edge("Alice", "Bob", "works_with", 0.8)
        return kg

    @pytest.fixture
    def vc(self, sample_graph):
        return VersionControl(sample_graph)

    def test_creation(self, sample_graph):
        vc = VersionControl(sample_graph)
        assert vc.get_current_branch() == "main"
        assert "main" in vc.get_branch_list()

    def test_create_snapshot(self, vc):
        assert vc.create_snapshot("v1") is True
        assert "v1" in vc._snapshots
        assert vc.get_snapshot_history()[-1]["name"] == "v1"

    def test_create_duplicate_snapshot(self, vc):
        vc.create_snapshot("v1")
        assert vc.create_snapshot("v1") is False

    def test_restore_snapshot(self, vc):
        vc.create_snapshot("v1")
        vc.kg.add_node("Carol")
        vc.kg.add_edge("Bob", "Carol", "knows", 0.5)

        assert vc.restore_snapshot("v1") is True
        assert "Carol" not in vc.kg.nodes
        assert len(vc.kg.edges) == 1  # 只有 Alice->Bob

    def test_restore_nonexistent_snapshot(self, vc):
        assert vc.restore_snapshot("nonexistent") is False

    def test_create_branch(self, vc):
        vc.create_snapshot("v1")
        assert vc.create_branch("feature") is True
        assert "feature" in vc.get_branch_list()

    def test_create_duplicate_branch(self, vc):
        assert vc.create_branch("feature") is True
        assert vc.create_branch("feature") is False

    def test_switch_branch(self, vc):
        vc.create_snapshot("v1")
        vc.create_branch("feature")

        # 切换到 feature 分支并添加节点
        vc.switch_branch("feature")
        vc.kg.add_node("Carol")
        vc.create_snapshot("v2")

        # 切换回 main，应该恢复到 v1 的状态（没有 Carol）
        assert vc.switch_branch("main") is True
        assert vc.get_current_branch() == "main"
        assert "Carol" not in vc.kg.nodes

        # 切换到 feature，应该恢复到 v2 的状态（有 Carol）
        assert vc.switch_branch("feature") is True
        assert "Carol" in vc.kg.nodes

    def test_switch_nonexistent_branch(self, vc):
        assert vc.switch_branch("nonexistent") is False

    def test_merge_branch(self, vc):
        vc.create_snapshot("base")
        vc.create_branch("feature")

        # 在 feature 分支添加节点
        vc.switch_branch("feature")
        vc.kg.add_node("Carol", {"role": "manager"})
        vc.kg.add_edge("Bob", "Carol", "reports_to", 0.9)
        vc.create_snapshot("feature_v1")

        # 合并到 main
        result = vc.merge_branch("feature", "main")
        assert result["success"] is True
        assert result["nodes_added"] >= 1
        assert result["edges_added"] >= 1

    def test_merge_nonexistent_branch(self, vc):
        result = vc.merge_branch("nonexistent")
        assert result["success"] is False

    def test_get_snapshot_history(self, vc):
        vc.create_snapshot("v1")
        vc.create_snapshot("v2")
        history = vc.get_snapshot_history()
        assert len(history) == 2
        assert history[0]["name"] == "v1"
        assert history[1]["name"] == "v2"

    def test_delete_snapshot(self, vc):
        vc.create_snapshot("v1")
        assert vc.delete_snapshot("v1") is True
        assert "v1" not in vc._snapshots

    def test_delete_nonexistent_snapshot(self, vc):
        assert vc.delete_snapshot("nonexistent") is False

    def test_delete_branch(self, vc):
        vc.create_snapshot("v1")
        vc.create_branch("feature")
        assert vc.delete_branch("feature") is True
        assert "feature" not in vc.get_branch_list()

    def test_delete_current_branch_fails(self, vc):
        assert vc.delete_branch("main") is False

    def test_diff_snapshots(self, vc):
        vc.create_snapshot("v1")
        vc.kg.add_node("Carol")
        vc.create_snapshot("v2")

        diff = vc.diff_snapshots("v1", "v2")
        assert "nodes_added" in diff
        assert "Carol" in diff["nodes_added"]

    def test_diff_nonexistent_snapshots(self, vc):
        diff = vc.diff_snapshots("v1", "v2")
        assert "error" in diff

    def test_get_stats(self, vc):
        vc.create_snapshot("v1")
        vc.create_branch("feature")
        stats = vc.get_stats()
        assert stats["total_snapshots"] == 1
        assert stats["total_branches"] == 2
        assert stats["current_branch"] == "main"

    def test_snapshot_parent_chain(self, vc):
        vc.create_snapshot("v1")
        vc.create_snapshot("v2")
        assert vc._snapshots["v2"].parent == "v1"


class TestVersionControlIntegration:
    def test_full_workflow(self):
        """测试完整的版本控制工作流"""
        kg = KnowledgeGraph(save_path="test_vc_workflow.json")
        kg.clear()
        kg.add_node("Alice", {"role": "engineer"})
        kg.add_node("Bob", {"role": "designer"})
        kg.add_edge("Alice", "Bob", "works_with", 0.8)

        vc = VersionControl(kg)

        # 1. 创建初始快照
        vc.create_snapshot("initial")

        # 2. 创建 feature 分支
        vc.create_branch("feature", from_snapshot="initial")
        vc.switch_branch("feature")

        # 3. 在 feature 分支上开发
        kg.add_node("Carol", {"role": "manager"})
        kg.add_edge("Bob", "Carol", "reports_to", 0.9)
        vc.create_snapshot("feature_complete")

        # 4. 切换回 main 分支继续开发
        vc.switch_branch("main")
        kg.add_node("David", {"role": "tester"})
        kg.add_edge("Alice", "David", "works_with", 0.7)
        vc.create_snapshot("main_updated")

        # 5. 合并 feature 到 main
        result = vc.merge_branch("feature", "main")
        assert result["success"] is True

        # 6. 验证 main 分支包含所有节点
        vc.switch_branch("main")
        assert "Alice" in kg.nodes
        assert "Bob" in kg.nodes
        assert "Carol" in kg.nodes  # 来自 feature
        assert "David" in kg.nodes  # 来自 main

        # 清理
        import os
        if os.path.exists("test_vc_workflow.json"):
            os.remove("test_vc_workflow.json")
