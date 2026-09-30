import os
import sys
import time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.tree_manager import TreeManager, create_default_hospital_tree

def test_lock_sets_ttl_expires_at():
    root = create_default_hospital_tree()
    tm = TreeManager(root)

    success, msg = tm.lock("bed-101A", "nurse-jones", ttl_seconds=10.0)
    assert success is True
    bed = tm.get_node("bed-101A")
    assert bed.expires_at is not None
    assert bed.ttl_remaining > 5.0

def test_heartbeat_renewal_extends_lease():
    root = create_default_hospital_tree()
    tm = TreeManager(root)

    tm.lock("bed-101A", "nurse-jones", ttl_seconds=5.0)
    bed = tm.get_node("bed-101A")
    initial_expires = bed.expires_at

    time.sleep(0.1)

    success, msg = tm.heartbeat("bed-101A", "nurse-jones", ttl_seconds=30.0)
    assert success is True
    assert bed.expires_at > initial_expires

def test_heartbeat_unauthorized_agent_rejected():
    root = create_default_hospital_tree()
    tm = TreeManager(root)

    tm.lock("bed-101A", "nurse-jones", ttl_seconds=30.0)
    success, msg = tm.heartbeat("bed-101A", "dr-smith", ttl_seconds=30.0)
    assert success is False
    assert "does not own lock" in msg

def test_heartbeat_unlocked_node_rejected():
    root = create_default_hospital_tree()
    tm = TreeManager(root)

    success, msg = tm.heartbeat("bed-101A", "nurse-jones", ttl_seconds=30.0)
    assert success is False
    assert "is not locked" in msg

def test_automatic_lease_expiration():
    root = create_default_hospital_tree()
    tm = TreeManager(root)

    # Lock bed with short 0.2s TTL
    tm.lock("bed-101A", "nurse-jones", ttl_seconds=0.2)
    assert tm.get_node("bed-101A").is_locked is True
    assert tm.get_node("hospital-1").locked_descendant_count == 1

    time.sleep(0.3)

    expired_list = tm.check_and_expire_locks()
    assert len(expired_list) == 1
    assert expired_list[0]["node_id"] == "bed-101A"

    assert tm.get_node("bed-101A").is_locked is False
    assert tm.get_node("hospital-1").locked_descendant_count == 0
