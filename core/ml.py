"""
机器学习集成框架模块

提供模型管理、特征提取和推理功能。
遵循"图难于其易，为大于其细"原则，从简单可验证的实现开始。
"""

import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class ModelType(Enum):
    """模型类型"""
    CLASSIFIER = "classifier"
    REGRESSOR = "regressor"
    CLUSTERING = "clustering"
    EMBEDDING = "embedding"
    CUSTOM = "custom"


class ModelStatus(Enum):
    """模型状态"""
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    UNLOADED = "unloaded"


@dataclass
class ModelInfo:
    """模型信息"""
    model_id: str
    name: str
    model_type: ModelType
    version: str = "1.0.0"
    description: str = ""
    created_at: float = field(default_factory=time.time)
    status: ModelStatus = ModelStatus.UNLOADED
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "name": self.name,
            "model_type": self.model_type.value,
            "version": self.version,
            "description": self.description,
            "created_at": self.created_at,
            "status": self.status.value,
            "metadata": self.metadata
        }


class BaseModel:
    """
    基础模型接口
    
    所有自定义模型需要继承此类。
    """
    
    def __init__(self, model_id: str, name: str, model_type: ModelType):
        self.model_id = model_id
        self.name = name
        self.model_type = model_type
        self.status = ModelStatus.UNLOADED
        self._model = None
    
    def load(self, **kwargs) -> bool:
        """加载模型"""
        raise NotImplementedError
    
    def predict(self, features: Any) -> Any:
        """预测"""
        raise NotImplementedError
    
    def unload(self):
        """卸载模型"""
        self._model = None
        self.status = ModelStatus.UNLOADED
    
    def get_info(self) -> ModelInfo:
        """获取模型信息"""
        return ModelInfo(
            model_id=self.model_id,
            name=self.name,
            model_type=self.model_type,
            status=self.status
        )


class SimpleClassifier(BaseModel):
    """
    简单分类器
    
    基于规则的简单分类器，用于演示。
    """
    
    def __init__(self, model_id: str, name: str, rules: Optional[Dict[str, Any]] = None):
        super().__init__(model_id, name, ModelType.CLASSIFIER)
        self.rules = rules or {}
        self._threshold = 0.5
    
    def load(self, rules: Optional[Dict[str, Any]] = None, **kwargs) -> bool:
        """加载分类规则"""
        if rules:
            self.rules = rules
        self.status = ModelStatus.READY
        return True
    
    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于规则的预测
        
        Args:
            features: 特征字典
            
        Returns:
            预测结果
        """
        if self.status != ModelStatus.READY:
            return {"error": "Model not ready"}
        
        results = {}
        for label, conditions in self.rules.items():
            score = 0
            total = len(conditions)
            
            for key, expected_value in conditions.items():
                if key in features:
                    if isinstance(expected_value, (int, float)):
                        # 数值比较
                        actual = features[key]
                        if isinstance(actual, (int, float)):
                            diff = abs(actual - expected_value) / max(abs(expected_value), 1)
                            score += max(0, 1 - diff)
                    elif features[key] == expected_value:
                        score += 1
            
            confidence = score / total if total > 0 else 0
            if confidence >= self._threshold:
                results[label] = confidence
        
        # 返回置信度最高的分类
        if results:
            best_label = max(results, key=results.get)
            return {
                "label": best_label,
                "confidence": results[best_label],
                "all_scores": results
            }
        
        return {"label": "unknown", "confidence": 0.0}


class FeatureExtractor:
    """
    特征提取器
    
    从知识图谱节点中提取特征向量。
    """
    
    @staticmethod
    def extract_node_features(node) -> Dict[str, Any]:
        """
        从节点提取特征
        
        Args:
            node: 知识图谱节点
            
        Returns:
            特征字典
        """
        features = {
            "name": node.name,
            "num_attributes": len(node.attributes),
            "attribute_keys": list(node.attributes.keys()),
        }
        
        # 提取数值属性
        for key, value in node.attributes.items():
            if isinstance(value, (int, float)):
                features[f"attr_{key}"] = value
            elif isinstance(value, bool):
                features[f"attr_{key}"] = 1.0 if value else 0.0
            elif isinstance(value, str):
                features[f"attr_{key}_length"] = len(value)
        
        return features
    
    @staticmethod
    def extract_graph_features(graph) -> Dict[str, Any]:
        """
        从知识图谱提取全局特征
        
        Args:
            graph: 知识图谱
            
        Returns:
            特征字典
        """
        num_nodes = len(graph.nodes)
        num_edges = len(graph.edges)
        
        # 计算平均度数
        degrees = {}
        for edge in graph.edges:
            degrees[edge.source] = degrees.get(edge.source, 0) + 1
            degrees[edge.target] = degrees.get(edge.target, 0) + 1
        
        avg_degree = sum(degrees.values()) / num_nodes if num_nodes > 0 else 0
        max_degree = max(degrees.values()) if degrees else 0
        
        # 计算平均权重
        avg_weight = sum(e.weight for e in graph.edges) / num_edges if num_edges > 0 else 0
        
        return {
            "num_nodes": num_nodes,
            "num_edges": num_edges,
            "density": num_edges / (num_nodes * (num_nodes - 1)) if num_nodes > 1 else 0,
            "avg_degree": avg_degree,
            "max_degree": max_degree,
            "avg_edge_weight": avg_weight,
            "num_isolated_nodes": num_nodes - len(degrees)
        }
    
    @staticmethod
    def normalize_features(features: Dict[str, Any]) -> Dict[str, float]:
        """
        归一化特征
        
        将特征转换为数值向量。
        """
        normalized = {}
        
        for key, value in features.items():
            if isinstance(value, (int, float)):
                normalized[key] = float(value)
            elif isinstance(value, bool):
                normalized[key] = 1.0 if value else 0.0
            elif isinstance(value, str):
                # 字符串哈希化
                normalized[key] = hash(value) % 1000 / 1000.0
            elif isinstance(value, list):
                normalized[f"{key}_count"] = float(len(value))
        
        return normalized


class ModelManager:
    """
    模型管理器
    
    管理多个机器学习模型的生命周期。
    """
    
    def __init__(self):
        self._models: Dict[str, BaseModel] = {}
        self._model_info: Dict[str, ModelInfo] = {}
    
    def register_model(self, model: BaseModel) -> bool:
        """
        注册模型
        
        Args:
            model: 模型实例
            
        Returns:
            是否成功注册
        """
        if model.model_id in self._models:
            return False
        
        self._models[model.model_id] = model
        self._model_info[model.model_id] = model.get_info()
        return True
    
    def load_model(self, model_id: str, **kwargs) -> bool:
        """
        加载模型
        
        Args:
            model_id: 模型标识
            
        Returns:
            是否成功加载
        """
        if model_id not in self._models:
            return False
        
        model = self._models[model_id]
        model.status = ModelStatus.LOADING
        
        try:
            success = model.load(**kwargs)
            if success:
                model.status = ModelStatus.READY
                self._model_info[model_id] = model.get_info()
            else:
                model.status = ModelStatus.ERROR
            return success
        except Exception as e:
            model.status = ModelStatus.ERROR
            return False
    
    def predict(self, model_id: str, features: Any) -> Optional[Any]:
        """
        使用模型进行预测
        
        Args:
            model_id: 模型标识
            features: 输入特征
            
        Returns:
            预测结果
        """
        if model_id not in self._models:
            return None
        
        model = self._models[model_id]
        if model.status != ModelStatus.READY:
            return None
        
        return model.predict(features)
    
    def unload_model(self, model_id: str) -> bool:
        """
        卸载模型
        
        Args:
            model_id: 模型标识
            
        Returns:
            是否成功卸载
        """
        if model_id not in self._models:
            return False
        
        self._models[model_id].unload()
        self._model_info[model_id] = self._models[model_id].get_info()
        return True
    
    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        if model_id in self._model_info:
            return self._model_info[model_id]
        return None
    
    def list_models(self) -> List[ModelInfo]:
        """列出所有模型"""
        return [info for info in self._model_info.values()]
    
    def get_ready_models(self) -> List[str]:
        """获取已就绪的模型列表"""
        return [
            mid for mid, model in self._models.items()
            if model.status == ModelStatus.READY
        ]
    
    def remove_model(self, model_id: str) -> bool:
        """
        移除模型
        
        Args:
            model_id: 模型标识
            
        Returns:
            是否成功移除
        """
        if model_id not in self._models:
            return False
        
        self._models[model_id].unload()
        del self._models[model_id]
        del self._model_info[model_id]
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._models)
        ready = sum(1 for m in self._models.values() if m.status == ModelStatus.READY)
        loading = sum(1 for m in self._models.values() if m.status == ModelStatus.LOADING)
        error = sum(1 for m in self._models.values() if m.status == ModelStatus.ERROR)
        
        return {
            "total_models": total,
            "ready": ready,
            "loading": loading,
            "error": error,
            "unloaded": total - ready - loading - error
        }
    
    def clear(self):
        """清空所有模型"""
        for model in self._models.values():
            model.unload()
        self._models.clear()
        self._model_info.clear()
