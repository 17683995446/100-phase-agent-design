from typing import Optional


class Node:
    def __init__(
        self,
        name: str,
        created_at: Optional[float] = None,
        valid_state: bool = True,
        attributes: Optional[dict] = None
    ):
        import time
        self.name = name
        self.created_at = created_at if created_at is not None else time.time()
        self.valid_state = valid_state
        self.attributes = attributes if attributes is not None else {}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "valid_state": self.valid_state,
            "attributes": self.attributes
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Node':
        return cls(
            name=data["name"],
            created_at=data["created_at"],
            valid_state=data["valid_state"],
            attributes=data["attributes"]
        )

    def __repr__(self) -> str:
        return f"Node(name={self.name}, valid={self.valid_state})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Node):
            return False
        return self.name == other.name
