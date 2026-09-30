import time
import threading
from typing import Dict, List, Optional, Tuple, Any
from .tree_node import TreeNode
from .audit import AuditLogger

class TreeManager:
    """
    Core Thread-Safe M-Ary Tree Spatial Arbiter for Hospital Resource Locking.
    Enforces O(h) lock validation, TTL leases, and heartbeat renewals.
    """
    def __init__(self, root: TreeNode, audit_logger: Optional[AuditLogger] = None):
        self.root = root
        self.nodes_map: Dict[str, TreeNode] = {}
        self.lock_obj = threading.Lock()
        self.audit = audit_logger or AuditLogger()
        self._index_tree(self.root)

    def _index_tree(self, node: TreeNode) -> None:
        """Recursively indexes all nodes in nodes_map for O(1) direct lookup."""
        self.nodes_map[node.id] = node
        for child in node.children:
            self._index_tree(child)

    def get_node(self, node_id: str) -> Optional[TreeNode]:
        return self.nodes_map.get(node_id)

    def lock(self, node_id: str, agent_id: str, ttl_seconds: float = 30.0) -> Tuple[bool, str]:
        """
        Attempts exclusive lock on node_id for agent_id with a TTL lease.
        Validates in O(h) time:
          1. Node is not already exclusively locked.
          2. Node has zero locked descendants (locked_descendant_count == 0).
          3. No ancestor of node is exclusively locked.
        """
        with self.lock_obj:
            node = self.nodes_map.get(node_id)
            if not node:
                msg = f"Node '{node_id}' does not exist in spatial hierarchy."
                self.audit.log("LOCK_FAILED", node_id, agent_id, False, msg)
                return False, msg

            # Lazy check if current lock has expired
            if node.is_locked and node.expires_at and time.time() > node.expires_at:
                self._force_expire_node_lock(node)

            # Rule 1: Node cannot already be locked
            if node.is_locked:
                msg = f"Node '{node_id}' is already exclusively locked by '{node.locked_by}'."
                self.audit.log("LOCK_FAILED", node_id, agent_id, False, msg)
                return False, msg

            # Rule 2: Node cannot have locked descendants
            if node.locked_descendant_count > 0:
                msg = f"Node '{node_id}' cannot be locked because it has {node.locked_descendant_count} active locked descendant(s)."
                self.audit.log("LOCK_FAILED", node_id, agent_id, False, msg)
                return False, msg

            # Rule 3: Ancestor check (no parent node can be locked)
            curr = node.parent
            while curr is not None:
                if curr.is_locked and curr.expires_at and time.time() > curr.expires_at:
                    self._force_expire_node_lock(curr)

                if curr.is_locked:
                    msg = f"Node '{node_id}' cannot be locked because ancestor '{curr.id}' is locked by '{curr.locked_by}'."
                    self.audit.log("LOCK_FAILED", node_id, agent_id, False, msg)
                    return False, msg
                curr = curr.parent

            # Acquire exclusive lock
            node.is_locked = True
            node.locked_by = agent_id
            node.expires_at = time.time() + ttl_seconds

            # Increment descendant counters up to root
            curr = node.parent
            while curr is not None:
                curr.locked_descendant_count += 1
                curr = curr.parent

            msg = f"Successfully locked '{node_id}' for '{agent_id}' (TTL: {ttl_seconds}s)."
            self.audit.log("LOCK_SUCCESS", node_id, agent_id, True, msg)
            return True, msg

    def unlock(self, node_id: str, agent_id: str) -> Tuple[bool, str]:
        """
        Unlocks node_id if currently locked by agent_id.
        Decrements locked_descendant_count for all ancestors.
        """
        with self.lock_obj:
            node = self.nodes_map.get(node_id)
            if not node:
                msg = f"Node '{node_id}' does not exist."
                self.audit.log("UNLOCK_FAILED", node_id, agent_id, False, msg)
                return False, msg

            if not node.is_locked:
                msg = f"Node '{node_id}' is not currently locked."
                self.audit.log("UNLOCK_FAILED", node_id, agent_id, False, msg)
                return False, msg

            if node.locked_by != agent_id:
                msg = f"Agent '{agent_id}' cannot unlock '{node_id}' owned by '{node.locked_by}'."
                self.audit.log("UNLOCK_FAILED", node_id, agent_id, False, msg)
                return False, msg

            self._force_expire_node_lock(node)

            msg = f"Successfully unlocked '{node_id}' by '{agent_id}'."
            self.audit.log("UNLOCK_SUCCESS", node_id, agent_id, True, msg)
            return True, msg

    def heartbeat(self, node_id: str, agent_id: str, ttl_seconds: float = 30.0) -> Tuple[bool, str]:
        """
        Heartbeat pulse extending lease for node_id if owned by agent_id.
        """
        with self.lock_obj:
            node = self.nodes_map.get(node_id)
            if not node:
                msg = f"Node '{node_id}' not found."
                self.audit.log("HEARTBEAT_FAILED", node_id, agent_id, False, msg)
                return False, msg

            if not node.is_locked:
                msg = f"Node '{node_id}' is not locked; heartbeat rejected."
                self.audit.log("HEARTBEAT_FAILED", node_id, agent_id, False, msg)
                return False, msg

            if node.locked_by != agent_id:
                msg = f"Agent '{agent_id}' does not own lock on '{node_id}'."
                self.audit.log("HEARTBEAT_FAILED", node_id, agent_id, False, msg)
                return False, msg

            node.expires_at = time.time() + ttl_seconds
            msg = f"Heartbeat accepted: Lease for '{node_id}' renewed (+{ttl_seconds}s)."
            self.audit.log("HEARTBEAT_RENEWED", node_id, agent_id, True, msg)
            return True, msg

    def upgrade_lock(self, parent_id: str, agent_id: str, ttl_seconds: float = 30.0) -> Tuple[bool, str]:
        """
        Upgrades locks from children to an exclusive lock on parent_id if agent owns all locked children.
        """
        with self.lock_obj:
            parent = self.nodes_map.get(parent_id)
            if not parent:
                msg = f"Parent node '{parent_id}' does not exist."
                self.audit.log("UPGRADE_FAILED", parent_id, agent_id, False, msg)
                return False, msg

            if parent.is_locked:
                msg = f"Parent '{parent_id}' is already locked."
                self.audit.log("UPGRADE_FAILED", parent_id, agent_id, False, msg)
                return False, msg

            # Check that all currently locked children are owned by agent_id
            locked_children = [c for c in parent.children if c.is_locked]
            if not locked_children:
                msg = f"Parent '{parent_id}' has no locked children to upgrade."
                self.audit.log("UPGRADE_FAILED", parent_id, agent_id, False, msg)
                return False, msg

            for c in locked_children:
                if c.locked_by != agent_id:
                    msg = f"Cannot upgrade: child '{c.id}' is locked by '{c.locked_by}', not '{agent_id}'."
                    self.audit.log("UPGRADE_FAILED", parent_id, agent_id, False, msg)
                    return False, msg

            # Unlock all children
            for c in locked_children:
                self._force_expire_node_lock(c)

            # Lock parent
            parent.is_locked = True
            parent.locked_by = agent_id
            parent.expires_at = time.time() + ttl_seconds

            curr = parent.parent
            while curr is not None:
                curr.locked_descendant_count += 1
                curr = curr.parent

            msg = f"Successfully upgraded locks on children to parent '{parent_id}' for '{agent_id}'."
            self.audit.log("UPGRADE_SUCCESS", parent_id, agent_id, True, msg)
            return True, msg

    def check_and_expire_locks(self) -> List[Dict[str, Any]]:
        """
        Iterates over all nodes and releases any lock whose expires_at timestamp has passed.
        Returns list of expired lock detail dicts.
        """
        expired_events = []
        now = time.time()

        with self.lock_obj:
            for node in self.nodes_map.values():
                if node.is_locked and node.expires_at and now > node.expires_at:
                    owner = node.locked_by
                    node_id = node.id

                    self._force_expire_node_lock(node)

                    msg = f"Lease expired for '{node_id}' (held by '{owner}'). Lock automatically released."
                    entry = self.audit.log("LEASE_EXPIRED", node_id, owner or "unknown", True, msg)
                    expired_events.append(entry)

        return expired_events

    def _force_expire_node_lock(self, node: TreeNode) -> None:
        """Internal helper to clear node lock state and update ancestor counters."""
        node.is_locked = False
        node.locked_by = None
        node.expires_at = None

        curr = node.parent
        while curr is not None:
            curr.locked_descendant_count = max(0, curr.locked_descendant_count - 1)
            curr = curr.parent

    def get_all_nodes_flat(self) -> List[Dict[str, Any]]:
        """Flat list of all nodes in hierarchy."""
        return [
            {
                "id": n.id,
                "name": n.name,
                "type": n.type,
                "is_locked": n.is_locked,
                "locked_by": n.locked_by,
                "ttl_remaining": n.ttl_remaining,
                "locked_descendant_count": n.locked_descendant_count
            }
            for n in self.nodes_map.values()
        ]

def create_default_hospital_tree() -> TreeNode:
    """
    Constructs default hospital spatial resource hierarchy:
    Hospital -> Ward -> Department -> Room -> Bed
    """
    hospital = TreeNode("hospital-1", "St. Thomas' Hospital", "HOSPITAL")

    # Ward Alpha (Acute Care Ward)
    ward_a = TreeNode("ward-Alpha", "Ward Alpha (Acute Care)", "WARD", parent=hospital)
    hospital.add_child(ward_a)

    dept_icu = TreeNode("dept-ICU", "ICU Department", "DEPARTMENT", parent=ward_a)
    ward_a.add_child(dept_icu)

    room_101 = TreeNode("room-101", "Room 101", "ROOM", parent=dept_icu)
    dept_icu.add_child(room_101)

    bed_101a = TreeNode("bed-101A", "Bed 101A", "BED", parent=room_101)
    bed_101b = TreeNode("bed-101B", "Bed 101B", "BED", parent=room_101)
    room_101.add_child(bed_101a)
    room_101.add_child(bed_101b)

    room_102 = TreeNode("room-102", "Room 102", "ROOM", parent=dept_icu)
    dept_icu.add_child(room_102)

    bed_102a = TreeNode("bed-102A", "Bed 102A", "BED", parent=room_102)
    bed_102b = TreeNode("bed-102B", "Bed 102B", "BED", parent=room_102)
    room_102.add_child(bed_102a)
    room_102.add_child(bed_102b)

    dept_card = TreeNode("dept-Cardiology", "Cardiology Dept", "DEPARTMENT", parent=ward_a)
    ward_a.add_child(dept_card)

    room_201 = TreeNode("room-201", "Room 201", "ROOM", parent=dept_card)
    dept_card.add_child(room_201)

    bed_201a = TreeNode("bed-201A", "Bed 201A", "BED", parent=room_201)
    room_201.add_child(bed_201a)

    # Ward Beta (Surgical Ward)
    ward_b = TreeNode("ward-Beta", "Ward Beta (Surgical Ward)", "WARD", parent=hospital)
    hospital.add_child(ward_b)

    dept_surg = TreeNode("dept-Surgery", "Surgical Dept", "DEPARTMENT", parent=ward_b)
    ward_b.add_child(dept_surg)

    room_301 = TreeNode("room-301", "Room 301", "ROOM", parent=dept_surg)
    dept_surg.add_child(room_301)

    bed_301a = TreeNode("bed-301A", "Bed 301A", "BED", parent=room_301)
    room_301.add_child(bed_301a)

    return hospital

