from typing import Optional


class Edge:
    def __init__(
        self,
        source: str,
        target: str,
        relation_name: str,
        weight: float,
        created_at: Optional[float] = None
    ):
        import time
        if not 0.0 <= weight <= 1.0:
            raise ValueError(f"Weight must be between 0.0 and 1.0, got {weight}")
        self.source = source
        self.target = target
        self.relation_name = relation_name
        self.weight = weight
        self.created_at = created_at if created_at is not None else time.time()

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "relation_name": self.relation_name,
            "weight": self.weight,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Edge':
        return cls(
            source=data["source"],
            target=data["target"],
            relation_name=data["relation_name"],
            weight=data["weight"],
            created_at=data["created_at"]
        )

    def __repr__(self) -> str:
        return f"Edge({self.source} --[{self.relation_name}:{self.weight:.2f}]--> {self.target})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Edge):
            return False
        return (
            self.source == other.source and
            self.target == other.target and
            self.relation_name == other.relation_name
        )
