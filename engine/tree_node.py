import time
from typing import List, Optional

class TreeNode:
    """
    Represents a spatial resource node in the hospital hierarchy.
    Hierarchy: Hospital -> Ward -> Department -> Room -> Bed
    """
    def __init__(self, node_id: str, name: str, node_type: str, parent: Optional['TreeNode'] = None):
        self.id = node_id
        self.name = name
        self.type = node_type.upper()  # HOSPITAL, WARD, DEPARTMENT, ROOM, BED
        self.parent = parent
        self.children: List['TreeNode'] = []

        # Lock state
        self.is_locked = False
        self.locked_by: Optional[str] = None
        self.expires_at: Optional[float] = None
        self.locked_descendant_count = 0

    @property
    def ttl_remaining(self) -> float:
        """Returns remaining TTL seconds if locked, or 0.0."""
        if not self.is_locked or self.expires_at is None:
            return 0.0
        remaining = self.expires_at - time.time()
        return max(0.0, round(remaining, 1))

    def add_child(self, child: 'TreeNode') -> None:
        child.parent = self
        self.children.append(child)

    def to_dict(self) -> dict:
        """Serializes node and subtree for JSON responses."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "is_locked": self.is_locked,
            "locked_by": self.locked_by,
            "ttl_remaining": self.ttl_remaining,
            "locked_descendant_count": self.locked_descendant_count,
            "children": [c.to_dict() for c in self.children]
        }
