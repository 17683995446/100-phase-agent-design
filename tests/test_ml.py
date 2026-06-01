"""
机器学习集成框架模块测试

测试模型管理、特征提取和推理功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的测试开始。
"""

import pytest
import tempfile
import os
from core import (
    KnowledgeGraph,
    ModelType, ModelStatus, ModelInfo,
    BaseModel, SimpleClassifier, FeatureExtractor, ModelManager
)


class TestModelType:
    """测试模型类型枚举"""

    def test_model_type_values(self):
        """测试模型类型值"""
        assert ModelType.CLASSIFIER.value == "classifier"
        assert ModelType.REGRESSOR.value == "regressor"
        assert ModelType.CLUSTERING.value == "clustering"


class TestModelStatus:
    """测试模型状态枚举"""

    def test_model_status_values(self):
        """测试模型状态值"""
        assert ModelStatus.LOADING.value == "loading"
        assert ModelStatus.READY.value == "ready"
        assert ModelStatus.ERROR.value == "error"


class TestModelInfo:
    """测试模型信息"""

    def test_creation(self):
        """测试创建"""
        info = ModelInfo(
            model_id="model_1",
            name="Test Model",
            model_type=ModelType.CLASSIFIER
        )
        assert info.model_id == "model_1"
        assert info.name == "Test Model"
        assert info.status == ModelStatus.UNLOADED

    def test_to_dict(self):
        """测试转换为字典"""
        info = ModelInfo(
            model_id="model_1",
            name="Test Model",
            model_type=ModelType.CLASSIFIER,
            version="1.0.0"
        )
        data = info.to_dict()
        assert data["model_id"] == "model_1"
        assert data["model_type"] == "classifier"


class TestBaseModel:
    """测试基础模型"""

    def test_creation(self):
        """测试创建"""
        model = BaseModel("model_1", "Test", ModelType.CLASSIFIER)
        assert model.model_id == "model_1"
        assert model.status == ModelStatus.UNLOADED

    def test_unload(self):
        """测试卸载"""
        model = BaseModel("model_1", "Test", ModelType.CLASSIFIER)
        model.unload()
        assert model.status == ModelStatus.UNLOADED

    def test_get_info(self):
        """测试获取信息"""
        model = BaseModel("model_1", "Test", ModelType.CLASSIFIER)
        info = model.get_info()
        assert info.model_id == "model_1"


class TestSimpleClassifier:
    """测试简单分类器"""

    def test_creation(self):
        """测试创建"""
        classifier = SimpleClassifier("clf_1", "Test Classifier")
        assert classifier.model_id == "clf_1"
        assert classifier.rules == {}

    def test_load(self):
        """测试加载"""
        classifier = SimpleClassifier("clf_1", "Test")
        rules = {"class_a": {"feature1": 1.0}}
        assert classifier.load(rules=rules) is True
        assert classifier.status == ModelStatus.READY
        assert classifier.rules == rules

    def test_predict_exact_match(self):
        """测试精确匹配预测"""
        classifier = SimpleClassifier("clf_1", "Test")
        classifier.load(rules={
            "class_a": {"feature1": 1.0, "feature2": "value"}
        })

        result = classifier.predict({"feature1": 1.0, "feature2": "value"})
        assert result["label"] == "class_a"
        assert result["confidence"] == 1.0

    def test_predict_partial_match(self):
        """测试部分匹配预测"""
        classifier = SimpleClassifier("clf_1", "Test")
        classifier.load(rules={
            "class_a": {"feature1": 1.0}
        })

        result = classifier.predict({"feature1": 0.8})
        assert result["label"] == "class_a"
        assert 0.0 < result["confidence"] < 1.0

    def test_predict_no_match(self):
        """测试无匹配预测"""
        classifier = SimpleClassifier("clf_1", "Test")
        classifier.load(rules={
            "class_a": {"feature1": 1.0}
        })

        result = classifier.predict({"feature2": 1.0})
        assert result["label"] == "unknown"

    def test_predict_not_ready(self):
        """测试未就绪预测"""
        classifier = SimpleClassifier("clf_1", "Test")
        result = classifier.predict({"feature1": 1.0})
        assert "error" in result


class TestFeatureExtractor:
    """测试特征提取器"""

    def test_extract_node_features(self):
        """测试节点特征提取"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            node = graph.add_node("Alice", {"type": "person", "age": 30})

            features = FeatureExtractor.extract_node_features(node)
            assert features["name"] == "Alice"
            assert features["num_attributes"] == 2
            assert features["attr_age"] == 30
        finally:
            os.remove(kg_path)

    def test_extract_graph_features(self):
        """测试图谱特征提取"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            kg_path = f.name
        try:
            graph = KnowledgeGraph(kg_path)
            graph.add_node("Alice")
            graph.add_node("Bob")
            graph.add_edge("Alice", "Bob", "friend", 0.8)

            features = FeatureExtractor.extract_graph_features(graph)
            assert features["num_nodes"] == 2
            assert features["num_edges"] == 1
            assert features["avg_degree"] == 1.0
        finally:
            os.remove(kg_path)

    def test_normalize_features(self):
        """测试特征归一化"""
        features = {
            "num": 42,
            "flag": True,
            "text": "hello",
            "items": [1, 2, 3]
        }

        normalized = FeatureExtractor.normalize_features(features)
        assert normalized["num"] == 42.0
        assert normalized["flag"] == 1.0
        assert "text" in normalized  # 哈希值
        assert normalized["items_count"] == 3.0


class TestModelManager:
    """测试模型管理器"""

    def test_creation(self):
        """测试创建"""
        manager = ModelManager()
        assert manager.get_stats()["total_models"] == 0

    def test_register_model(self):
        """测试注册模型"""
        manager = ModelManager()
        model = SimpleClassifier("clf_1", "Test")

        assert manager.register_model(model) is True
        assert manager.get_stats()["total_models"] == 1

    def test_register_duplicate(self):
        """测试重复注册"""
        manager = ModelManager()
        model = SimpleClassifier("clf_1", "Test")

        manager.register_model(model)
        assert manager.register_model(model) is False

    def test_load_model(self):
        """测试加载模型"""
        manager = ModelManager()
        model = SimpleClassifier("clf_1", "Test")
        manager.register_model(model)

        assert manager.load_model("clf_1", rules={"class_a": {}}) is True
        assert model.status == ModelStatus.READY

    def test_load_nonexistent(self):
        """测试加载不存在的模型"""
        manager = ModelManager()
        assert manager.load_model("nonexistent") is False

    def test_predict(self):
        """测试预测"""
        manager = ModelManager()
        model = SimpleClassifier("clf_1", "Test")
        manager.register_model(model)
        manager.load_model("clf_1", rules={
            "class_a": {"feature1": 1.0}
        })

        result = manager.predict("clf_1", {"feature1": 1.0})
        assert result is not None
        assert result["label"] == "class_a"

    def test_predict_not_ready(self):
        """测试未就绪预测"""
        manager = ModelManager()
        model = SimpleClassifier("clf_1", "Test")
        manager.register_model(model)

        result = manager.predict("clf_1", {"feature1": 1.0})
        assert result is None

    def test_unload_model(self):
        """测试卸载模型"""
        manager = ModelManager()
        model = SimpleClassifier("clf_1", "Test")
        manager.register_model(model)
        manager.load_model("clf_1")

        assert manager.unload_model("clf_1") is True
        assert model.status == ModelStatus.UNLOADED

    def test_get_model_info(self):
        """测试获取模型信息"""
        manager = ModelManager()
        model = SimpleClassifier("clf_1", "Test")
        manager.register_model(model)

        info = manager.get_model_info("clf_1")
        assert info is not None
        assert info.model_id == "clf_1"

    def test_list_models(self):
        """测试列出模型"""
        manager = ModelManager()
        manager.register_model(SimpleClassifier("clf_1", "Test1"))
        manager.register_model(SimpleClassifier("clf_2", "Test2"))

        models = manager.list_models()
        assert len(models) == 2

    def test_get_ready_models(self):
        """测试获取就绪模型"""
        manager = ModelManager()
        manager.register_model(SimpleClassifier("clf_1", "Test1"))
        manager.register_model(SimpleClassifier("clf_2", "Test2"))
        manager.load_model("clf_1")

        ready = manager.get_ready_models()
        assert "clf_1" in ready
        assert "clf_2" not in ready

    def test_remove_model(self):
        """测试移除模型"""
        manager = ModelManager()
        manager.register_model(SimpleClassifier("clf_1", "Test"))

        assert manager.remove_model("clf_1") is True
        assert manager.get_stats()["total_models"] == 0

    def test_get_stats(self):
        """测试获取统计"""
        manager = ModelManager()
        manager.register_model(SimpleClassifier("clf_1", "Test"))
        manager.load_model("clf_1")

        stats = manager.get_stats()
        assert stats["total_models"] == 1
        assert stats["ready"] == 1

    def test_clear(self):
        """测试清空"""
        manager = ModelManager()
        manager.register_model(SimpleClassifier("clf_1", "Test"))
        manager.load_model("clf_1")

        manager.clear()
        assert manager.get_stats()["total_models"] == 0
